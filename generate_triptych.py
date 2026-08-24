import os
import json
import urllib.parse
import urllib.request
from datetime import datetime
from google import genai
from google.genai import types

# MARK: - Configuration & Client API

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("La variable d'environnement GEMINI_API_KEY est manquante.")

client = genai.Client(api_key=GEMINI_API_KEY)

# MARK: - Enrichisseurs d'Artworks & Métadonnées Réelles

def fetch_book_metadata(title: str, author: str):
    """Récupère la couverture officielle et les infos précises sur Google Books."""
    query = urllib.parse.quote(f"intitle:{title} inauthor:{author}")
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=1"
    
    image_url = None
    page_count = None
    published_year = None
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TriviumApp/2.1"})
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode())
            if "items" in data and len(data["items"]) > 0:
                info = data["items"][0].get("volumeInfo", {})
                images = info.get("imageLinks", {})
                image_url = images.get("thumbnail") or images.get("smallThumbnail")
                if image_url:
                    image_url = image_url.replace("http://", "https://")
                page_count = info.get("pageCount")
                pub_date = info.get("publishedDate", "")
                if len(pub_date) >= 4:
                    published_year = pub_date[:4]
    except Exception as e:
        print(f"[GoogleBooks] Info : Couverture non trouvée pour '{title}' ({e})")
        
    return image_url, page_count, published_year


def fetch_album_metadata(album_title: str, artist: str):
    """Récupère la pochette HD (600x600), la liste des titres et extraits 30s sur iTunes/Apple Music."""
    query = urllib.parse.quote(f"{album_title} {artist}")
    url = f"https://itunes.apple.com/search?term={query}&entity=album&limit=1&country=fr"
    
    image_url = None
    collection_id = None
    tracks = []
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TriviumApp/2.1"})
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode())
            if data.get("resultCount", 0) > 0:
                item = data["results"][0]
                raw_art = item.get("artworkUrl100", "")
                if raw_art:
                    image_url = raw_art.replace("100x100bb", "600x600bb")
                collection_id = item.get("collectionId")
    except Exception as e:
        print(f"[AppleMusic] Erreur recherche album '{album_title}' : {e}")
        
    if collection_id:
        lookup_url = f"https://itunes.apple.com/lookup?id={collection_id}&entity=song&country=fr"
        try:
            req = urllib.request.Request(lookup_url, headers={"User-Agent": "TriviumApp/2.1"})
            with urllib.request.urlopen(req, timeout=8) as response:
                song_data = json.loads(response.read().decode())
                results = song_data.get("results", [])
                for r in results:
                    if r.get("wrapperType") == "track":
                        millis = r.get("trackTimeMillis", 0)
                        seconds = (millis // 1000) % 60
                        minutes = (millis // (1000 * 60))
                        dur_str = f"{minutes}:{seconds:02d}"
                        
                        tracks.append({
                            "trackNumber": r.get("trackNumber", len(tracks) + 1),
                            "title": r.get("trackName", "Piste inconnue"),
                            "duration": dur_str,
                            "previewURL": r.get("previewUrl")
                        })
        except Exception as e:
            print(f"[AppleMusic] Erreur récupération pistes pour '{album_title}' : {e}")
            
    return image_url, tracks


def build_safe_platform_links(item_type: str, title: str, creator: str):
    """Construit des URLs universelles fiables sans AlloCiné ni Canal VOD."""
    encoded_query = urllib.parse.quote(f"{title} {creator}".strip())
    encoded_title = urllib.parse.quote(title.strip())
    
    t = item_type.upper()
    if t == "FILM":
        return [
            {
                "name": "JustWatch (Streaming & VOD)",
                "category": "Disponibilité légale",
                "urlString": f"https://www.justwatch.com/fr/recherche?q={encoded_query}",
                "iconName": "play.tv.fill"
            },
            {
                "name": "Letterboxd",
                "category": "Fiche & Critiques",
                "urlString": f"https://letterboxd.com/search/{encoded_query}/",
                "iconName": "film.fill"
            },
            {
                "name": "Apple TV",
                "category": "Location & Achat",
                "urlString": f"https://tv.apple.com/fr/search?term={encoded_title}",
                "iconName": "apple.logo"
            }
        ]
    elif t == "LIVRE":
        return [
            {
                "name": "Les Libraires",
                "category": "Librairies indépendantes",
                "urlString": f"https://www.leslibraires.fr/recherche/?q={encoded_query}",
                "iconName": "book.fill"
            },
            {
                "name": "Babelio",
                "category": "Critiques & Extraits",
                "urlString": f"https://www.babelio.com/recherche.php?Recherche={encoded_title}",
                "iconName": "quote.bubble.fill"
            },
            {
                "name": "Fnac",
                "category": "Achat livre",
                "urlString": f"https://www.fnac.com/SearchResult/ResultList.aspx?SCat=0&Search={encoded_query}",
                "iconName": "bag.fill"
            }
        ]
    else:  # ALBUM
        return [
            {
                "name": "Apple Music",
                "category": "Écoute intégrale",
                "urlString": f"https://music.apple.com/fr/search?term={encoded_query}",
                "iconName": "apple.logo"
            },
            {
                "name": "Spotify",
                "category": "Streaming audio",
                "urlString": f"https://open.spotify.com/search/{encoded_query}",
                "iconName": "waveform"
            },
            {
                "name": "Discogs",
                "category": "Édition vinyle & CD",
                "urlString": f"https://www.discogs.com/fr/search/?q={encoded_query}&type=release",
                "iconName": "opticaldisc.fill"
            }
        ]


# MARK: - Prompt Système & Génération

SYSTEM_PROMPT = """Tu es le curateur en chef de TRIVIUM, une application d'élite de recommandation culturelle quotidienne.

Ta mission est de concevoir l'édition du jour : UNE THÉMATIQUE COMMUNE FORTE et COHÉRENTE reliant 3 profils distincts :
1. "accessible" (Pop Culture) : Grands classiques incontournables, chefs-d'œuvre grand public, pop culture majeure.
2. "intermediate" (Curieux) : Cinéma d'auteur accessible, pépites littéraires, albums cultes.
3. "expert" (Initié) : Avant-garde, art et essai, expérimentations et raretés exigeantes.

Chaque profil doit contenir EXACTEMENT 3 œuvres reliées par la thématique du jour :
- 1 LIVRE
- 1 FILM
- 1 ALBUM

RÈGLES ÉDITORIALES STRICTES :
1. Les œuvres recommandées doivent être RÉELLES et EXISTANTES.
2. Pour chaque œuvre, fournis une citation réelle ("quote"), une anecdote surprenante ("anecdote"), des notes de presse réalistes ("ratings") et une analyse croisée captivante ("thematicAnalysis").
3. Réponds STRICTEMENT sous la forme d'un objet JSON valide au format ci-dessous, sans texte autour.

Format JSON attendu :
{
  "accessible": {
    "themeTitle": "Titre du thème",
    "themeSubtitle": "Sous-titre poétique expliquant le fil invisible reliant les 3 œuvres",
    "items": [
      {
        "type": "LIVRE",
        "title": "Titre exact",
        "creator": "Nom de l'auteur",
        "year": "1997",
        "origin": "France",
        "genre": "Genre",
        "accessibility": "Pop Culture",
        "formatMetric": "320 pages",
        "quote": "Une citation clé marquante de l'œuvre",
        "anecdote": "Une anecdote fascinante sur la création de l'œuvre",
        "tags": ["Philosophie", "Société", "Classique"],
        "ratings": [
          {"source": "Le Monde", "score": "5/5", "iconName": "star.fill", "excerpt": "Un chef-d'œuvre absolu."},
          {"source": "Télérama", "score": "4/5", "iconName": "star.fill", "excerpt": "Une écriture magistrale."}
        ],
        "aiSummary": "Résumé captivant de l'œuvre en 2 phrases.",
        "thematicAnalysis": "Explication de comment cette œuvre illustre parfaitement le thème du triptyque."
      },
      ... (FILM et ALBUM)
    ]
  },
  "intermediate": { ... },
  "expert": { ... }
}
"""

def generate_daily_edition():
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"🚀 Génération de l'édition Trivium pour le {today_str}...")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Génère le triptyque culturel du jour reliant 1 Livre, 1 Film et 1 Album pour les 3 profils.",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.7
        )
    )

    data = json.loads(response.text)

    # Post-traitement et enrichissement automatique
    for tier in ["accessible", "intermediate", "expert"]:
        if tier not in data:
            continue
        
        for item in data[tier].get("items", []):
            item_type = item.get("type", "").upper()
            title = item.get("title", "")
            creator = item.get("creator", "")

            # 1. Liens sécurisés (JustWatch, Letterboxd, Apple TV)
            item["platformLinks"] = build_safe_platform_links(item_type, title, creator)

            # 2. Enrichissements Google Books & Apple Music
            if item_type == "LIVRE":
                img, pages, pub_year = fetch_book_metadata(title, creator)
                if img:
                    item["imageURL"] = img
                if pages and not item.get("formatMetric"):
                    item["formatMetric"] = f"{pages} pages"
                if pub_year:
                    item["year"] = pub_year

            elif item_type == "ALBUM":
                img, tracks = fetch_album_metadata(title, creator)
                if img:
                    item["imageURL"] = img
                if tracks:
                    item["tracks"] = tracks

    # Enregistrement dans today.json
    output_filename = "today.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Édition enregistrée avec succès dans {output_filename} !")

if __name__ == "__main__":
    generate_daily_edition()

import os
import json
import urllib.parse
import urllib.request
from datetime import datetime
import google.generativeai as genai

# MARK: - Configuration API

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY manquante dans les secrets GitHub.")

genai.configure(api_key=GEMINI_API_KEY)

# MARK: - Enrichisseur Livres (Google Books + OpenLibrary Fallback)

def fetch_book_metadata(title: str, author: str):
    """Récupère la couverture via Google Books puis OpenLibrary si nécessaire."""
    image_url = None
    page_count = None
    published_year = None

    # 1. Tentative Google Books
    queries = [
        f"{title} {author}",
        f"intitle:{title} inauthor:{author}",
        title
    ]

    for q in queries:
        encoded_q = urllib.parse.quote(q)
        url = f"https://www.googleapis.com/books/v1/volumes?q={encoded_q}&maxResults=3&printType=books"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            )
            with urllib.request.urlopen(req, timeout=6) as response:
                data = json.loads(response.read().decode())
                for item in data.get("items", []):
                    info = item.get("volumeInfo", {})
                    images = info.get("imageLinks", {})
                    img = images.get("extraLarge") or images.get("large") or images.get("medium") or images.get("thumbnail") or images.get("smallThumbnail")
                    
                    if img:
                        secure_img = img.replace("http://", "https://")
                        if "&edge=curl" in secure_img:
                            secure_img = secure_img.replace("&edge=curl", "")
                        image_url = secure_img

                    if not page_count and info.get("pageCount"):
                        page_count = info.get("pageCount")
                    if not published_year and len(info.get("publishedDate", "")) >= 4:
                        published_year = info.get("publishedDate", "")[:4]

                    if image_url:
                        break
        except Exception:
            pass

        if image_url:
            break

    # 2. Repli OpenLibrary si Google Books n'a pas renvoyé d'image
    if not image_url:
        try:
            q_ol = urllib.parse.quote(f"{title} {author}")
            ol_url = f"https://openlibrary.org/search.json?q={q_ol}&limit=1"
            req = urllib.request.Request(ol_url, headers={"User-Agent": "TriviumApp/2.1"})
            with urllib.request.urlopen(req, timeout=6) as response:
                ol_data = json.loads(response.read().decode())
                docs = ol_data.get("docs", [])
                if docs and "cover_i" in docs[0]:
                    cover_id = docs[0]["cover_i"]
                    image_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
                if docs and not published_year and "first_publish_year" in docs[0]:
                    published_year = str(docs[0]["first_publish_year"])
        except Exception:
            pass

    return image_url, page_count, published_year

# MARK: - Enrichisseur Films (Affiches HD officielles iTunes Movies)

def fetch_film_metadata(title: str, director: str):
    """Récupère l'affiche HD officielle du film sur iTunes Movie Search."""
    image_url = None
    queries = [f"{title} {director}", title]

    for q in queries:
        encoded_q = urllib.parse.quote(q)
        url = f"https://itunes.apple.com/search?term={encoded_q}&entity=movie&limit=1&country=fr"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TriviumApp/2.1"})
            with urllib.request.urlopen(req, timeout=6) as response:
                data = json.loads(response.read().decode())
                if data.get("resultCount", 0) > 0:
                    raw_art = data["results"][0].get("artworkUrl100", "")
                    if raw_art:
                        image_url = raw_art.replace("100x100bb", "1000x1000bb")
                        break
        except Exception:
            pass

    return image_url

# MARK: - Enrichisseur Albums (Pochettes HD 600x600 & Pistes Apple Music)

def fetch_album_metadata(album_title: str, artist: str):
    query = urllib.parse.quote(f"{album_title} {artist}")
    url = f"https://itunes.apple.com/search?term={query}&entity=album&limit=1&country=fr"
    image_url, collection_id, tracks = None, None, []
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
    except Exception:
        pass

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
                        tracks.append({
                            "trackNumber": r.get("trackNumber", len(tracks) + 1),
                            "title": r.get("trackName", "Piste inconnue"),
                            "duration": f"{minutes}:{seconds:02d}",
                            "previewURL": r.get("previewUrl")
                        })
        except Exception:
            pass
    return image_url, tracks

# MARK: - Liens Directs Utiles (Sans Letterboxd ni Babelio)

def build_safe_platform_links(item_type: str, title: str, creator: str):
    encoded_query = urllib.parse.quote(f"{title} {creator}".strip())
    encoded_title = urllib.parse.quote(title.strip())
    
    t = item_type.upper()
    if t == "FILM":
        return [
            {
                "name": "JustWatch",
                "category": "Disponibilité légale & Streaming",
                "urlString": f"https://www.justwatch.com/fr/recherche?q={encoded_query}",
                "iconName": "play.tv.fill"
            },
            {
                "name": "Apple TV",
                "category": "Location & Achat VOD",
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
                "name": "Fnac",
                "category": "Achat livre & Ebook",
                "urlString": f"https://www.fnac.com/SearchResult/ResultList.aspx?SCat=0&Search={encoded_query}",
                "iconName": "bag.fill"
            }
        ]
    else:  # ALBUM
        return [
            {
                "name": "Apple Music",
                "category": "Écoute intégrale & Lossless",
                "urlString": f"https://music.apple.com/fr/search?term={encoded_query}",
                "iconName": "apple.logo"
            },
            {
                "name": "Spotify",
                "category": "Streaming audio",
                "urlString": f"https://open.spotify.com/search/{encoded_query}",
                "iconName": "waveform"
            }
        ]

# MARK: - Prompt Éditorial & IA

SYSTEM_PROMPT = """Tu es le curateur en chef de TRIVIUM, une application d'élite de recommandation culturelle quotidienne.

Ta mission est de concevoir l'édition du jour avec UNE THÉMATIQUE COMMUNE FORTE reliant 3 profils :
1. "accessible" (Pop Culture)
2. "intermediate" (Curieux)
3. "expert" (Initié)

Chaque profil doit contenir EXACTEMENT : 1 LIVRE, 1 FILM, 1 ALBUM réels et existants.

RÈGLE STRICTE POUR LA REVUE DE PRESSE :
Pour CHAQUE œuvre sans exception, fournis EXACTEMENT 3 critiques comparées ("ratings") provenant de 3 MÉDIAS DISTINCTS et reconnus (exemples : Le Monde, Télérama, Les Inrockuptibles, Libération, Cahiers du Cinéma, Pitchfork, Rolling Stone, The Guardian...).

Réponds STRICTEMENT sous la forme d'un objet JSON valide :
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
        "quote": "Citation clé marquante",
        "anecdote": "Anecdote surprenante sur la genèse de l'œuvre",
        "tags": ["Tag1", "Tag2"],
        "ratings": [
          {"source": "Le Monde", "score": "5/5", "iconName": "star.fill", "excerpt": "Une œuvre magistrale."},
          {"source": "Télérama", "score": "4/5", "iconName": "star.fill", "excerpt": "Un regard bouleversant."},
          {"source": "Les Inrockuptibles", "score": "4.5/5", "iconName": "star.fill", "excerpt": "Une écriture d'une grande finesse."}
        ],
        "aiSummary": "Résumé captivant en 2 phrases.",
        "thematicAnalysis": "Analyse du lien profond avec la thématique du triptyque."
      }
    ]
  },
  "intermediate": { ... },
  "expert": { ... }
}
"""

def generate_daily_edition():
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"🚀 Génération de l'édition du {today_str}...")

    model = genai.GenerativeModel(
        model_name="gemini-3.6-flash",
        generation_config={"response_mime_type": "application/json", "temperature": 0.7},
        system_instruction=SYSTEM_PROMPT
    )

    response = model.generate_content("Génère le triptyque culturel du jour pour les 3 profils avec 3 critiques de médias différents par œuvre.")
    data = json.loads(response.text)

    for tier in ["accessible", "intermediate", "expert"]:
        if tier not in data:
            continue
        for item in data[tier].get("items", []):
            item_type = item.get("type", "").upper()
            title = item.get("title", "")
            creator = item.get("creator", "")

            # Liens plateformes nettoyés
            item["platformLinks"] = build_safe_platform_links(item_type, title, creator)

            # Enrichissement médias réels
            if item_type == "LIVRE":
                img, pages, pub_year = fetch_book_metadata(title, creator)
                if img:
                    item["imageURL"] = img
                if pages and not item.get("formatMetric"):
                    item["formatMetric"] = f"{pages} pages"
                if pub_year:
                    item["year"] = pub_year

            elif item_type == "FILM":
                img = fetch_film_metadata(title, creator)
                if img:
                    item["imageURL"] = img

            elif item_type == "ALBUM":
                img, tracks = fetch_album_metadata(title, creator)
                if img:
                    item["imageURL"] = img
                if tracks:
                    item["tracks"] = tracks

    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("✅ today.json généré avec succès (images livres, affiches films et pochettes albums intégrées).")

if __name__ == "__main__":
    generate_daily_edition()

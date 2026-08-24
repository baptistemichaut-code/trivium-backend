import os
import json
import urllib.parse
import urllib.request
from datetime import datetime

# MARK: - Configuration API

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY manquante dans les secrets GitHub.")

# MARK: - Enrichisseurs d'Artworks & Métadonnées Réelles

def fetch_book_metadata(title: str, author: str):
    query = urllib.parse.quote(f"intitle:{title} inauthor:{author}")
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=1"
    image_url, page_count, published_year = None, None, None
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
    except Exception:
        pass
    return image_url, page_count, published_year

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

def build_safe_platform_links(item_type: str, title: str, creator: str):
    """Génère uniquement les liens fiables (sans AlloCiné ni Canal VOD)."""
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

SYSTEM_PROMPT = """Tu es le curateur en chef de TRIVIUM, une application de recommandation culturelle quotidienne.

Ta mission est de concevoir l'édition du jour avec UNE THÉMATIQUE COMMUNE reliant 3 profils :
1. "accessible" (Pop Culture)
2. "intermediate" (Curieux)
3. "expert" (Initié)

Chaque profil doit contenir EXACTEMENT : 1 LIVRE, 1 FILM, 1 ALBUM réels et existants.

Réponds STRICTEMENT sous la forme d'un objet JSON valide :
{
  "accessible": {
    "themeTitle": "Titre du thème",
    "themeSubtitle": "Sous-titre explicatif",
    "items": [
      {
        "type": "LIVRE",
        "title": "Titre",
        "creator": "Auteur",
        "year": "1997",
        "origin": "France",
        "genre": "Genre",
        "accessibility": "Pop Culture",
        "formatMetric": "320 pages",
        "quote": "Citation clé",
        "anecdote": "Anecdote surprenante",
        "tags": ["Tag1", "Tag2"],
        "ratings": [
          {"source": "Le Monde", "score": "5/5", "iconName": "star.fill", "excerpt": "Critique"}
        ],
        "aiSummary": "Résumé en 2 phrases.",
        "thematicAnalysis": "Analyse du lien avec le thème."
      }
    ]
  },
  "intermediate": { ... },
  "expert": { ... }
}
"""

def generate_daily_edition():
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "Génère le triptyque culturel du jour pour les 3 profils."}
                ]
            }
        ],
        "systemInstruction": {
            "parts": [
                {"text": SYSTEM_PROMPT}
            ]
        },
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.7
        }
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        res_json = json.loads(response.read().decode())

    raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
    data = json.loads(raw_text)

    for tier in ["accessible", "intermediate", "expert"]:
        if tier not in data:
            continue
        for item in data[tier].get("items", []):
            item_type = item.get("type", "").upper()
            title = item.get("title", "")
            creator = item.get("creator", "")

            item["platformLinks"] = build_safe_platform_links(item_type, title, creator)

            if item_type == "LIVRE":
                img, pages, pub_year = fetch_book_metadata(title, creator)
                if img: item["imageURL"] = img
                if pages and not item.get("formatMetric"): item["formatMetric"] = f"{pages} pages"
                if pub_year: item["year"] = pub_year

            elif item_type == "ALBUM":
                img, tracks = fetch_album_metadata(title, creator)
                if img: item["imageURL"] = img
                if tracks: item["tracks"] = tracks

    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("✅ today.json mis à jour sans aucune dépendance externe.")

if __name__ == "__main__":
    generate_daily_edition()

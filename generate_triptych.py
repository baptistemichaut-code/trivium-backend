import os
import json
import datetime
import urllib.parse
import requests

def build_book_links(title, author):
    q = urllib.parse.quote(f"{title} {author}")
    return [
        {"name": "Les Libraires", "category": "Librairie indépendante", "urlString": f"https://www.leslibraires.fr/recherche/?q={q}", "iconName": "books.vertical.fill"},
        {"name": "Fnac", "category": "Format papier & ebook", "urlString": f"https://www.fnac.com/SearchResult/ResultList.aspx?SCat=0&Search={q}", "iconName": "book.closed.fill"},
        {"name": "Audible", "category": "Livre audio", "urlString": f"https://www.audible.fr/search?keywords={q}", "iconName": "headphones"}
    ]

def build_movie_links(title, director):
    q = urllib.parse.quote(f"{title}")
    return [
        {"name": "JustWatch", "category": "Où voir en streaming / VOD", "urlString": f"https://www.justwatch.com/fr/recherche?q={q}", "iconName": "tv.fill"},
        {"name": "Allociné", "category": "Fiche & séances", "urlString": f"https://www.allocine.fr/recherche/?q={q}", "iconName": "film.fill"},
        {"name": "Canal+ VOD", "category": "Location / Achat", "urlString": f"https://www.canalplus.com/recherche?q={q}", "iconName": "play.tv.fill"}
    ]

def build_album_links(title, artist, direct_apple_url=None):
    q = urllib.parse.quote(f"{title} {artist}")
    apple_url = direct_apple_url if direct_apple_url else f"https://music.apple.com/fr/search?term={q}"
    return [
        {"name": "Spotify", "category": "Écouter sur Spotify", "urlString": f"https://open.spotify.com/search/{q}", "iconName": "waveform"},
        {"name": "Apple Music", "category": "Écouter sur Apple Music", "urlString": apple_url, "iconName": "music.note"},
        {"name": "Deezer", "category": "Écouter sur Deezer", "urlString": f"https://www.deezer.com/search/{q}", "iconName": "play.circle.fill"}
    ]

def fetch_album_metadata(title, artist):
    try:
        query = urllib.parse.quote(f"{title} {artist}")
        search_url = f"https://itunes.apple.com/search?term={query}&entity=album&limit=1"
        res = requests.get(search_url, timeout=10).json()
        if res.get("resultCount", 0) > 0:
            album = res["results"][0]
            collection_id = album["collectionId"]
            direct_url = album.get("collectionViewUrl")
            artwork = album.get("artworkUrl100", "").replace("100x100bb.jpg", "600x600bb.jpg")

            lookup_url = f"https://itunes.apple.com/lookup?id={collection_id}&entity=song&limit=15"
            lookup_res = requests.get(lookup_url, timeout=10).json()
            tracks = []
            for item in lookup_res.get("results", []):
                if item.get("wrapperType") == "track":
                    millis = item.get("trackTimeMillis", 0)
                    mins = millis // 60000
                    secs = (millis % 60000) // 1000
                    tracks.append({
                        "trackNumber": item.get("trackNumber", len(tracks) + 1),
                        "title": item.get("trackName", "Piste"),
                        "duration": f"{mins}:{secs:02d}",
                        "previewURL": item.get("previewUrl")
                    })
            return artwork, tracks, direct_url
    except Exception:
        pass
    return None, None, None

def fetch_movie_artwork(title, director):
    try:
        query = urllib.parse.quote(f"{title} {director}")
        search_url = f"https://itunes.apple.com/search?term={query}&entity=movie&limit=1"
        res = requests.get(search_url, timeout=10).json()
        if res.get("resultCount", 0) > 0:
            movie = res["results"][0]
            return movie.get("artworkUrl100", "").replace("100x100bb.jpg", "600x600bb.jpg")
    except Exception:
        pass
    return None

def fetch_book_artwork(title, author):
    try:
        query = urllib.parse.quote(f"intitle:{title}+inauthor:{author}")
        search_url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=1"
        res = requests.get(search_url, timeout=10).json()
        if "items" in res and len(res["items"]) > 0:
            image_links = res["items"][0].get("volumeInfo", {}).get("imageLinks", {})
            thumb = image_links.get("thumbnail") or image_links.get("smallThumbnail")
            if thumb:
                return thumb.replace("http://", "https://")
    except Exception:
        pass
    return None

def enrich_triptych(triptych_dict):
    for item in triptych_dict.get("items", []):
        media_type = item.get("type", "").upper()
        title = item.get("title", "")
        creator = item.get("creator", "")

        if media_type == "LIVRE":
            artwork = fetch_book_artwork(title, creator)
            if artwork:
                item["imageURL"] = artwork
            item["platformLinks"] = build_book_links(title, creator)

        elif media_type == "FILM":
            artwork = fetch_movie_artwork(title, creator)
            if artwork:
                item["imageURL"] = artwork
            item["platformLinks"] = build_movie_links(title, creator)

        elif media_type == "ALBUM":
            artwork, tracks, direct_apple = fetch_album_metadata(title, creator)
            if artwork:
                item["imageURL"] = artwork
            if tracks:
                item["tracks"] = tracks
            item["platformLinks"] = build_album_links(title, creator, direct_apple)

def generate_daily_edition():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY manquant.")

    prompt = """
Tu es le directeur éditorial de l'application culturelle "Trivium".
Chaque jour, tu crées 3 éditions thématiques distinctes selon 3 niveaux d'accessibilité culturelle :

1. "accessible" (POP CULTURE & GRANDS CLASSIQUES) : Des œuvres cultes, grand public de grande qualité, immédiates d'accès (ex: Stephen King, Tarantino, Daft Punk, Pink Floyd, Blade Runner, Orwell, etc.).
2. "intermediate" (CURIEUX & ÉQUILIBRE) : Des œuvres de grande renommée critique, ciné d'auteur accessible, romans modernes marquants, musique indépendante reconnue (ex: Murakami, Bong Joon-ho, Radiohead, Coen, etc.).
3. "expert" (MAXI NERD & NICHE) : Des œuvres pointues, expérimentales, cinéma underground / art et essai, littérature exigeante, musique d'avant-garde / ambient / jazz modal (ex: Perec, Tarkovski, Burial, Béla Tarr, etc.).

Pour chaque niveau, trouve un fil thématique propre et 3 œuvres (1 Livre, 1 Film, 1 Album) avec :
- Une revue de presse de 3 médias reconnus (note + courte phrase d'analyse).
- Une anecdote passionnante ("anecdote").
- Une citation marquante.

Renvoie UNIQUEMENT un objet JSON valide brut (sans markdown ```json) avec la structure exacte suivante :
{
  "accessible": {
    "themeTitle": "Titre du thème accessible",
    "themeSubtitle": "Phrase d'accroche",
    "items": [
      {
        "type": "LIVRE", "title": "Titre", "creator": "Auteur", "year": "Année", "genre": "Genre",
        "origin": "Pays", "formatMetric": "350 pages", "accessibility": "Populaire & Immédiat",
        "quote": "Citation", "aiSummary": "Résumé", "thematicAnalysis": "Analyse", "anecdote": "Anecdote",
        "tags": ["Tag1", "Tag2"],
        "ratings": [{"source": "Le Figaro Littéraire", "score": "5/5", "excerpt": "Critique.", "iconName": "star.fill"}]
      },
      { "type": "FILM", "title": "Titre", "creator": "Réalisateur", "year": "Année", "genre": "Genre", "origin": "Pays", "formatMetric": "2h 00m", "accessibility": "Culte & Grand Public", "quote": "Réplique", "aiSummary": "Synopsis", "thematicAnalysis": "Analyse", "anecdote": "Anecdote", "tags": ["Tag1", "Tag2"], "ratings": [{"source": "Première", "score": "4/5", "excerpt": "Critique.", "iconName": "film.fill"}] },
      { "type": "ALBUM", "title": "Titre", "creator": "Artiste", "year": "Année", "genre": "Genre", "origin": "Pays", "formatMetric": "10 titres", "accessibility": "Écoute Immédiate", "quote": "Paroles", "aiSummary": "Présentation", "thematicAnalysis": "Analyse", "anecdote": "Anecdote", "tags": ["Tag1", "Tag2"], "ratings": [{"source": "Rolling Stone", "score": "5/5", "excerpt": "Critique.", "iconName": "music.note"}] }
    ]
  },
  "intermediate": {
    "themeTitle": "Titre du thème intermédiaire",
    "themeSubtitle": "Phrase d'accroche",
    "items": [ ... 1 LIVRE, 1 FILM, 1 ALBUM ... ]
  },
  "expert": {
    "themeTitle": "Titre du thème expert",
    "themeSubtitle": "Phrase d'accroche",
    "items": [ ... 1 LIVRE, 1 FILM, 1 ALBUM ... ]
  }
}
"""

    host = "https://" + "generativelanguage.googleapis.com"
    endpoint = "/v1beta/models/gemini-3.6-flash:generateContent"
    url = f"{host}{endpoint}?key={api_key}"

    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    print("Génération des 3 triptyques (Accessible, Intermédiaire, Expert)...")
    response = requests.post(url, headers=headers, json=payload, timeout=90)
    response.raise_for_status()

    raw_text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    raw_text = raw_text.strip()

    data = json.loads(raw_text)

    # Enrichissement des 3 niveaux
    for tier in ["accessible", "intermediate", "expert"]:
        if tier in data:
            enrich_triptych(data[tier])

    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("today.json multi-niveaux enregistré.")

    os.makedirs("archive", exist_ok=True)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    archive_path = os.path.join("archive", f"{today_str}.json")
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    generate_daily_edition()

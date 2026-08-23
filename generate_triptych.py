import os
import json
import datetime
import urllib.parse
import requests

def build_book_links(title, author):
    q = urllib.parse.quote(f"{title} {author}")
    return [
        {
            "name": "Les Libraires",
            "category": "Acheter en librairie indépendante",
            "urlString": f"https://www.leslibraires.fr/recherche/?q={q}",
            "iconName": "books.vertical.fill"
        },
        {
            "name": "Fnac",
            "category": "Acheter en format papier ou ebook",
            "urlString": f"https://www.fnac.com/SearchResult/ResultList.aspx?SCat=0&Search={q}",
            "iconName": "book.closed.fill"
        },
        {
            "name": "Audible",
            "category": "Écouter le livre audio",
            "urlString": f"https://www.audible.fr/search?keywords={q}",
            "iconName": "headphones"
        }
    ]

def build_movie_links(title, director):
    q = urllib.parse.quote(f"{title}")
    return [
        {
            "name": "JustWatch",
            "category": "Où voir en streaming / VOD légale",
            "urlString": f"https://www.justwatch.com/fr/recherche?q={q}",
            "iconName": "tv.fill"
        },
        {
            "name": "Allociné",
            "category": "Fiche film & séances cinéma",
            "urlString": f"https://www.allocine.fr/recherche/?q={q}",
            "iconName": "film.fill"
        },
        {
            "name": "Canal+ VOD",
            "category": "Location & achat numérique",
            "urlString": f"https://www.canalplus.com/recherche?q={q}",
            "iconName": "play.tv.fill"
        }
    ]

def build_album_links(title, artist, direct_apple_url=None):
    q = urllib.parse.quote(f"{title} {artist}")
    apple_url = direct_apple_url if direct_apple_url else f"https://music.apple.com/fr/search?term={q}"
    return [
        {
            "name": "Spotify",
            "category": "Écouter sur Spotify",
            "urlString": f"https://open.spotify.com/search/{q}",
            "iconName": "waveform"
        },
        {
            "name": "Apple Music",
            "category": "Écouter sur Apple Music",
            "urlString": apple_url,
            "iconName": "music.note"
        },
        {
            "name": "Deezer",
            "category": "Écouter sur Deezer",
            "urlString": f"https://www.deezer.com/search/{q}",
            "iconName": "play.circle.fill"
        }
    ]

def fetch_album_metadata(title, artist):
    """Récupère la pochette HD, le lien Apple Music et les extraits audio de 30s."""
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
    except Exception as e:
        print(f"Info: Métadonnées album indisponibles ({e})")
    return None, None, None

def fetch_movie_artwork(title, director):
    """Récupère l'affiche HD du film via iTunes."""
    try:
        query = urllib.parse.quote(f"{title} {director}")
        search_url = f"https://itunes.apple.com/search?term={query}&entity=movie&limit=1"
        res = requests.get(search_url, timeout=10).json()
        if res.get("resultCount", 0) > 0:
            movie = res["results"][0]
            return movie.get("artworkUrl100", "").replace("100x100bb.jpg", "600x600bb.jpg")
    except Exception as e:
        print(f"Info: Affiche film indisponible ({e})")
    return None

def fetch_book_artwork(title, author):
    """Récupère la couverture du livre via Google Books."""
    try:
        query = urllib.parse.quote(f"intitle:{title}+inauthor:{author}")
        search_url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=1"
        res = requests.get(search_url, timeout=10).json()
        if "items" in res and len(res["items"]) > 0:
            image_links = res["items"][0].get("volumeInfo", {}).get("imageLinks", {})
            thumb = image_links.get("thumbnail") or image_links.get("smallThumbnail")
            if thumb:
                return thumb.replace("http://", "https://")
    except Exception as e:
        print(f"Info: Couverture livre indisponible ({e})")
    return None

def generate_daily_edition():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY introuvable.")

    prompt = """
Tu es le curateur en chef de l'application culturelle "Trivium".
Génère une édition quotidienne originale composée de 3 œuvres majeures reliées par un fil conducteur thématique puissant :
1. Un Livre (roman, essai ou chef-d'œuvre littéraire)
2. Un Film (long-métrage culte ou d'auteur)
3. Un Album (album musical marquant)

REVUE DE PRESSE PLURIELLE OBLIGATOIRE :
Pour chaque œuvre, fournis obligatoirement 3 ou 4 critiques issues de médias reconnus (ex: Le Monde, Télérama, Libération, Les Inrockuptibles, Cahiers du Cinéma, Pitchfork, Rolling Stone, The Guardian, etc.).
Chaque critique doit comporter le nom du média, la note et une analyse concise (2 phrases) mettant en avant un angle différent (style littéraire, mise en scène, audace sonore, portée politique...).

Renvoie UNIQUEMENT un objet JSON valide (sans balises markdown ```json, juste le texte JSON brut) avec cette structure :
{
  "themeTitle": "Titre poétique du thème",
  "themeSubtitle": "Phrase d'accroche expliquant le lien subtil entre ces 3 œuvres",
  "items": [
    {
      "type": "LIVRE",
      "title": "Titre exact",
      "creator": "Nom de l'auteur",
      "year": "Année",
      "genre": "Genre littéraire",
      "origin": "Pays d'origine",
      "formatMetric": "Ex: 280 pages",
      "accessibility": "Accessible / Exigeant",
      "quote": "Une citation marquante",
      "aiSummary": "Résumé captivant en 2-3 phrases",
      "thematicAnalysis": "Analyse de résonance avec le thème du jour",
      "anecdote": "Une anecdote méconnue sur la genèse de l'ouvrage",
      "tags": ["Littérature", "Style", "Thème"],
      "ratings": [
        {"source": "Le Monde des Livres", "score": "5/5", "excerpt": "Une critique élogieuse sur la densité de l'intrigue.", "iconName": "newspaper.fill"},
        {"source": "Télérama", "score": "TTT", "excerpt": "Un regard sur la sensibilité de la prose.", "iconName": "star.fill"},
        {"source": "Libération", "score": "Coup de cœur", "excerpt": "Une analyse de la portée contemporaine du texte.", "iconName": "quote.bubble.fill"}
      ]
    },
    {
      "type": "FILM",
      "title": "Titre exact",
      "creator": "Nom du réalisateur",
      "year": "Année",
      "genre": "Genre cinématographique",
      "origin": "Pays d'origine",
      "formatMetric": "Ex: 2h 05m",
      "accessibility": "Grand public / Auteur",
      "quote": "Une réplique culte",
      "aiSummary": "Synopsis percutant",
      "thematicAnalysis": "Analyse de résonance avec le thème du jour",
      "anecdote": "Une anecdote marquante sur le tournage ou la réception du film",
      "tags": ["Cinéma", "Mise en scène", "Atmosphère"],
      "ratings": [
        {"source": "Cahiers du Cinéma", "score": "5/5", "excerpt": "Un éloge du montage et du travail de mise en scène.", "iconName": "film.fill"},
        {"source": "Télérama", "score": "TTTT", "excerpt": "Une analyse du jeu d'acteur et de la justesse du récit.", "iconName": "star.fill"},
        {"source": "Les Inrockuptibles", "score": "4.5/5", "excerpt": "Une mise en valeur de la signature esthétique.", "iconName": "newspaper.fill"}
      ]
    },
    {
      "type": "ALBUM",
      "title": "Titre exact de l'album",
      "creator": "Nom de l'artiste ou groupe",
      "year": "Année",
      "genre": "Genre musical",
      "origin": "Pays d'origine",
      "formatMetric": "Ex: 11 titres",
      "accessibility": "Écoute immédiate / Expérimental",
      "quote": "Une phrase ou vers emblématique",
      "aiSummary": "Présentation de l'album",
      "thematicAnalysis": "Analyse de résonance avec le thème du jour",
      "anecdote": "Une anecdote insolite sur la production en studio",
      "tags": ["Musique", "Production", "Ambiance"],
      "ratings": [
        {"source": "Pitchfork", "score": "9.0/10", "excerpt": "Une autopsie méticuleuse de la production sonore.", "iconName": "music.note"},
        {"source": "Rolling Stone", "score": "4.5/5", "excerpt": "Un hommage à la cohérence et à la puissance des morceaux.", "iconName": "star.fill"},
        {"source": "Les Inrockuptibles", "score": "Indispensable", "excerpt": "Une célébration de l'inventivité musicale du disque.", "iconName": "quote.bubble.fill"}
      ]
    }
  ]
}
"""

    host = "https://" + "generativelanguage.googleapis.com"
    endpoint = "/v1beta/models/gemini-3.6-flash:generateContent"
    url = f"{host}{endpoint}?key={api_key}"

    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    print("Génération du triptyque complet avec Gemini 3.6 Flash...")
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()

    result = response.json()
    raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()

    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    raw_text = raw_text.strip()

    data = json.loads(raw_text)

    # Enrichissement dynamique : plateformes, jaquettes et extraits
    for item in data.get("items", []):
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
            artwork, tracks, direct_apple_url = fetch_album_metadata(title, creator)
            if artwork:
                item["imageURL"] = artwork
            if tracks:
                item["tracks"] = tracks
            item["platformLinks"] = build_album_links(title, creator, direct_apple_url)

    # Enregistrement
    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("today.json mis à jour avec les liens de streaming/achat.")

    # Archivage
    os.makedirs("archive", exist_ok=True)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    archive_path = os.path.join("archive", f"{today_str}.json")
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Archive enregistrée : {archive_path}")

if __name__ == "__main__":
    generate_daily_edition()

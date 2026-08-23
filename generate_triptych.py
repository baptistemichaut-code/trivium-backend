import os
import json
import datetime
import urllib.parse
import requests

def fetch_album_metadata(title, artist):
    """Récupère la pochette HD et les extraits audio de 30s via l'API iTunes."""
    try:
        query = urllib.parse.quote(f"{title} {artist}")
        search_url = f"https://itunes.apple.com/search?term={query}&entity=album&limit=1"
        res = requests.get(search_url, timeout=10).json()
        if res.get("resultCount", 0) > 0:
            album = res["results"][0]
            collection_id = album["collectionId"]
            artwork = album.get("artworkUrl100", "").replace("100x100bb.jpg", "600x600bb.jpg")

            # Récupération des pistes avec extraits audio
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

            return artwork, tracks
    except Exception as e:
        print(f"Info: Erreur enrichissement album ({e})")
    return None, None

def fetch_movie_artwork(title, director):
    """Récupère l'affiche du film en haute définition."""
    try:
        query = urllib.parse.quote(f"{title} {director}")
        search_url = f"https://itunes.apple.com/search?term={query}&entity=movie&limit=1"
        res = requests.get(search_url, timeout=10).json()
        if res.get("resultCount", 0) > 0:
            movie = res["results"][0]
            return movie.get("artworkUrl100", "").replace("100x100bb.jpg", "600x600bb.jpg")
    except Exception as e:
        print(f"Info: Erreur enrichissement film ({e})")
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
        print(f"Info: Erreur enrichissement livre ({e})")
    return None

def generate_daily_edition():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY introuvable.")

    prompt = """
Tu es le curateur en chef de l'application culturelle de prestige "Trivium".
Génère une édition quotidienne originale composée de 3 œuvres majeures reliées par un fil conducteur thématique, philosophique ou esthétique puissant :
1. Un Livre (roman marquant, essai ou chef-d'œuvre littéraire)
2. Un Film (long-métrage culte, primé ou d'auteur)
3. Un Album (album musical emblématique, tous genres confondus)

Renvoie UNIQUEMENT un objet JSON valide (sans balises markdown ```json, juste le texte JSON brut) respectant cette structure exacte :
{
  "themeTitle": "Titre poétique ou percutant du thème",
  "themeSubtitle": "Une phrase d'accroche expliquant le fil invisible reliant ces 3 œuvres",
  "items": [
    {
      "type": "LIVRE",
      "title": "Titre exact",
      "creator": "Auteur",
      "year": "Année",
      "genre": "Genre",
      "origin": "Pays d'origine",
      "formatMetric": "Ex: 280 pages",
      "accessibility": "Accessible / Exigeant",
      "quote": "Une citation marquante et authentique",
      "aiSummary": "Résumé captivant en 2-3 phrases",
      "thematicAnalysis": "Analyse approfondie de résonance avec le thème du jour",
      "anecdote": "Une anecdote méconnue et passionnante sur l'écriture ou la publication",
      "tags": ["Tag1", "Tag2", "Tag3"],
      "ratings": [
        {"source": "Le Monde", "score": "5/5", "excerpt": "Une phrase courte d'éloge critique."}
      ],
      "platformLinks": [
        {"name": "Les Libraires", "category": "Acheter en librairie indépendante", "urlString": "[https://www.leslibraires.fr](https://www.leslibraires.fr)", "iconName": "books.vertical.fill"}
      ]
    },
    {
      "type": "FILM",
      "title": "Titre exact",
      "creator": "Réalisateur",
      "year": "Année",
      "genre": "Genre",
      "origin": "Pays d'origine",
      "formatMetric": "Ex: 1h 45m",
      "accessibility": "Grand public / Auteur",
      "quote": "Une réplique culte",
      "aiSummary": "Synopsis percutant",
      "thematicAnalysis": "Analyse de résonance avec le thème du jour",
      "anecdote": "Une anecdote insolite sur le tournage ou la réception du film",
      "tags": ["Tag1", "Tag2", "Tag3"],
      "ratings": [
        {"source": "Télérama", "score": "TTT", "excerpt": "Une critique marquante."}
      ],
      "platformLinks": [
        {"name": "Allociné", "category": "Séances & Streaming", "urlString": "[https://www.allocine.fr](https://www.allocine.fr)", "iconName": "film.fill"}
      ]
    },
    {
      "type": "ALBUM",
      "title": "Titre exact de l'album",
      "creator": "Nom exact de l'artiste",
      "year": "Année",
      "genre": "Genre",
      "origin": "Pays d'origine",
      "formatMetric": "Ex: 10 titres",
      "accessibility": "Écoute immédiate / Expérimental",
      "quote": "Une phrase ou vers marquant",
      "aiSummary": "Présentation de l'album",
      "thematicAnalysis": "Analyse de résonance avec le thème du jour",
      "anecdote": "Une anecdote sur l'enregistrement ou la création sonore",
      "tags": ["Tag1", "Tag2", "Tag3"],
      "ratings": [
        {"source": "Pitchfork", "score": "8.8/10", "excerpt": "Une critique marquante."}
      ],
      "platformLinks": [
        {"name": "Apple Music", "category": "Écouter l'album", "urlString": "[https://music.apple.com](https://music.apple.com)", "iconName": "music.note"}
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

    print("Génération du triptyque avec Gemini 3.6 Flash...")
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

    # Enrichissement multimédia automatique
    for item in data.get("items", []):
        media_type = item.get("type", "").upper()
        title = item.get("title", "")
        creator = item.get("creator", "")

        if media_type == "ALBUM":
            artwork, tracks = fetch_album_metadata(title, creator)
            if artwork:
                item["imageURL"] = artwork
            if tracks:
                item["tracks"] = tracks
        elif media_type == "FILM":
            artwork = fetch_movie_artwork(title, creator)
            if artwork:
                item["imageURL"] = artwork
        elif media_type == "LIVRE":
            artwork = fetch_book_artwork(title, creator)
            if artwork:
                item["imageURL"] = artwork

    # Sauvegarde de l'édition du jour
    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("today.json enrichi et mis à jour.")

    # Archivage
    os.makedirs("archive", exist_ok=True)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    archive_path = os.path.join("archive", f"{today_str}.json")
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Archive enregistrée : {archive_path}")

if __name__ == "__main__":
    generate_daily_edition()

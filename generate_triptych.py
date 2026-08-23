import os
import json
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime
import zoneinfo

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

paris_tz = zoneinfo.ZoneInfo("Europe/Paris")
now_paris = datetime.now(paris_tz)
date_seed = now_paris.strftime("%Y-%m-%d")

def http_get_json(url, headers=None):
    custom_headers = {"User-Agent": "TriviumBot/1.0 (contact@trivium.app)"}
    if headers:
        custom_headers.update(headers)
    req = urllib.request.Request(url, headers=custom_headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

def fetch_gemini_triptych():
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""
    Tu es le grand conservateur culturel de Trivium.
    Date de référence : {date_seed}.
    
    Génère l'édition officielle pour aujourd'hui : 1 Livre, 1 Film et 1 Album unis par un thème subtil et original.
    
    RÈGLES D'OR :
    1. Évite les clichés évidents d'IA (Burial, Perec, Camus, Radiohead, Blade Runner).
    2. Varie les époques et les origines géographiques.
    3. Pour chaque œuvre :
       - 'aiSummary' : Court synopsis (2-3 phrases).
       - 'thematicAnalysis' : Grande analyse unifiée (style/mise en scène + résonance dans le triptyque).
       - 'ratings' : 2 revues de presse réputées avec note et extrait marquant.

    Format JSON strict :
    {{
      "themeTitle": "Titre du thème",
      "themeSubtitle": "Accroche expliquant la résonance entre ces 3 œuvres",
      "heroImageURL": null,
      "items": [
        {{
          "type": "LIVRE",
          "title": "Titre exact",
          "creator": "Nom auteur",
          "year": "Année",
          "genre": "Genre",
          "formatMetric": "280 pages",
          "accessibility": "Accessible ou Équilibrée ou Exigeante",
          "tags": ["Tag1", "Tag2"],
          "quote": "Extrait emblématique",
          "origin": "Pays d'origine",
          "imageURL": null,
          "previewURL": null,
          "tracks": null,
          "aiSummary": "Court résumé",
          "thematicAnalysis": "Analyse critique et lien thématique unifié",
          "ratings": [
            {{
              "source": "Revue littéraire",
              "score": "Incontournable",
              "excerpt": "Citation critique",
              "badgeColorName": "orange",
              "iconName": "quote.bubble.fill"
            }}
          ],
          "platformLinks": []
        }},
        {{
          "type": "FILM",
          "title": "Titre exact",
          "creator": "Nom réalisateur",
          "year": "Année",
          "genre": "Genre",
          "formatMetric": "1 h 52",
          "accessibility": "Accessible ou Équilibrée ou Exigeante",
          "tags": ["Tag1", "Tag2"],
          "quote": "Réplique culte",
          "origin": "Pays d'origine",
          "imageURL": null,
          "previewURL": null,
          "tracks": null,
          "aiSummary": "Court synopsis",
          "thematicAnalysis": "Analyse de la mise en scène et lien thématique",
          "ratings": [
            {{
              "source": "Cahiers du Cinéma",
              "score": "Chef-d'œuvre",
              "excerpt": "Citation critique",
              "badgeColorName": "blue",
              "iconName": "quote.bubble.fill"
            }}
          ],
          "platformLinks": []
        }},
        {{
          "type": "ALBUM",
          "title": "Titre exact",
          "creator": "Nom artiste",
          "year": "Année",
          "genre": "Genre",
          "formatMetric": "10 titres • 44 min",
          "accessibility": "Accessible ou Équilibrée ou Exigeante",
          "tags": ["Tag1", "Tag2"],
          "quote": "Ambiance sonore",
          "origin": "Pays d'origine",
          "imageURL": null,
          "previewURL": null,
          "tracks": null,
          "aiSummary": "Présentation album",
          "thematicAnalysis": "Analyse sonore et lien thématique",
          "ratings": [
            {{
              "source": "Pitchfork",
              "score": "8.8/10",
              "excerpt": "Citation critique",
              "badgeColorName": "red",
              "iconName": "music.note"
            }}
          ],
          "platformLinks": []
        }}
      ]
    }}
    """
    
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json", "temperature": 0.85, "topP": 0.95}
    }
    
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        raw_json = res["candidates"][0]["content"]["parts"][0]["text"].strip()
        if raw_json.startswith("```"):
            raw_json = raw_json.split("\n", 1)[1].rsplit("\n", 1)[0].strip()
        return json.loads(raw_json)

def enrich_movie(title):
    query = urllib.parse.quote(title)
    url_apple = f"[https://itunes.apple.com/search?term=](https://itunes.apple.com/search?term=){query}&media=movie&entity=movie&limit=1&country=FR"
    data = http_get_json(url_apple)
    if data:
        results = data.get("results", [])
        if results and results[0].get("artworkUrl100"):
            return results[0]["artworkUrl100"].replace("100x100bb", "600x900bb")

    url_wiki = f"[https://fr.wikipedia.org/api/rest_v1/page/summary/](https://fr.wikipedia.org/api/rest_v1/page/summary/){query}"
    data_wiki = http_get_json(url_wiki)
    if data_wiki:
        if data_wiki.get("thumbnail") and data_wiki["thumbnail"].get("source"):
            return data_wiki["thumbnail"]["source"]
        if data_wiki.get("originalimage") and data_wiki["originalimage"].get("source"):
            return data_wiki["originalimage"]["source"]

    return None

def enrich_book(title, author):
    clean_query = urllib.parse.quote(f"{title} {author}")
    
    url_google = f"[https://www.googleapis.com/books/v1/volumes?q=](https://www.googleapis.com/books/v1/volumes?q=){clean_query}&maxResults=1"
    data_google = http_get_json(url_google)
    if data_google:
        items = data_google.get("items", [])
        if items:
            image_links = items[0].get("volumeInfo", {}).get("imageLinks", {})
            img = image_links.get("thumbnail") or image_links.get("smallThumbnail")
            if img:
                return img.replace("http://", "https://").replace("&edge=curl", "")

    url_openlib = f"[https://openlibrary.org/search.json?q=](https://openlibrary.org/search.json?q=){clean_query}&limit=1"
    data_open = http_get_json(url_openlib)
    if data_open:
        docs = data_open.get("docs", [])
        if docs and docs[0].get("cover_i"):
            return f"[https://covers.openlibrary.org/b/id/](https://covers.openlibrary.org/b/id/){docs[0]['cover_i']}-L.jpg?default=false"

    url_wiki = f"[https://fr.wikipedia.org/api/rest_v1/page/summary/](https://fr.wikipedia.org/api/rest_v1/page/summary/){urllib.parse.quote(title)}"
    data_wiki = http_get_json(url_wiki)
    if data_wiki and data_wiki.get("thumbnail") and data_wiki["thumbnail"].get("source"):
        return data_wiki["thumbnail"]["source"]

    return None

def enrich_album(title, artist):
    query = urllib.parse.quote(f"{title} {artist}")
    url = f"[https://itunes.apple.com/search?term=](https://itunes.apple.com/search?term=){query}&media=music&entity=album&limit=1&country=FR"
    cover, preview, tracks, apple_url = None, None, [], None
    data = http_get_json(url)
    if data:
        results = data.get("results", [])
        if results:
            album = results[0]
            collection_id = album.get("collectionId")
            apple_url = album.get("collectionViewUrl")
            cover = album.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
            
            if collection_id:
                lookup_url = f"[https://itunes.apple.com/lookup?id=](https://itunes.apple.com/lookup?id=){collection_id}&entity=song&country=FR"
                lookup_data = http_get_json(lookup_url)
                if lookup_data:
                    for item in lookup_data.get("results", []):
                        if item.get("wrapperType") == "track":
                            if not preview:
                                preview = item.get("previewUrl")
                            ms = item.get("trackTimeMillis", 0)
                            sec = (ms // 1000) % 60
                            dur = f"{ms // 60000}:{sec:02d}"
                            tracks.append({
                                "trackNumber": item.get("trackNumber", len(tracks) + 1),
                                "title": item.get("trackName", "Piste"),
                                "duration": dur,
                                "previewURL": item.get("previewUrl")
                            })
    return cover, preview, tracks, apple_url

def build_links(item, apple_music_url=None):
    title = item["title"]
    creator = item["creator"]
    t = item["type"].upper()
    enc_tc = urllib.parse.quote(f"{title} {creator}")
    enc_t = urllib.parse.quote(title)
    
    if t == "ALBUM":
        return [
            {"name": "Spotify", "category": "Écouter l'album", "urlString": f"[https://open.spotify.com/search/](https://open.spotify.com/search/){enc_tc}/albums", "iconName": "music.note"},
            {"name": "Apple Music", "category": "Streaming Lossless", "urlString": apple_music_url or f"[https://music.apple.com/fr/search?term=](https://music.apple.com/fr/search?term=){enc_tc}", "iconName": "apple.logo"},
            {"name": "Deezer", "category": "Streaming Hi-Fi", "urlString": f"[https://www.deezer.com/search/](https://www.deezer.com/search/){enc_tc}/album", "iconName": "play.circle.fill"}
        ]
    elif t == "FILM":
        return [
            {"name": "Où regarder en streaming", "category": "Netflix, Prime, Disney+...", "urlString": f"[https://www.justwatch.com/fr/recherche?q=](https://www.justwatch.com/fr/recherche?q=){enc_t}", "iconName": "play.tv.fill"},
            {"name": "Apple TV", "category": "Location & Achat 4K", "urlString": f"[https://tv.apple.com/fr/search?term=](https://tv.apple.com/fr/search?term=){enc_t}", "iconName": "apple.logo"},
            {"name": "Canal+ VOD", "category": "Location & myCANAL", "urlString": f"[https://vod.canalplus.com/recherche/](https://vod.canalplus.com/recherche/){enc_t}", "iconName": "film.fill"}
        ]
    else:
        return [
            {"name": "Fnac", "category": "Livre papier (Broché / Poche)", "urlString": f"[https://www.fnac.com/SearchResult/ResultList.aspx?Search=](https://www.fnac.com/SearchResult/ResultList.aspx?Search=){enc_tc}", "iconName": "book.closed.fill"},
            {"name": "Kindle", "category": "Édition numérique E-book", "urlString": f"[https://www.amazon.fr/s?k=](https://www.amazon.fr/s?k=){enc_tc}&i=digital-text", "iconName": "ipad.and.arrow.forward"},
            {"name": "Audible", "category": "Livre audio narré", "urlString": f"[https://www.audible.fr/search?keywords=](https://www.audible.fr/search?keywords=){enc_tc}", "iconName": "headphones"}
        ]

def main():
    print(f"Génération pour le {date_seed}...")
    triptych = fetch_gemini_triptych()
    
    for item in triptych.get("items", []):
        t = item["type"].upper()
        if t == "FILM":
            item["imageURL"] = enrich_movie(item["title"])
            item["platformLinks"] = build_links(item)
        elif t == "ALBUM":
            cover, preview, tracks, apple_url = enrich_album(item["title"], item["creator"])
            item["imageURL"] = cover
            item["previewURL"] = preview
            item["tracks"] = tracks
            item["platformLinks"] = build_links(item, apple_url)
        elif t == "LIVRE":
            item["imageURL"] = enrich_book(item["title"], item["creator"])
            item["platformLinks"] = build_links(item)

    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(triptych, f, ensure_ascii=False, indent=2)

    os.makedirs("archive", exist_ok=True)
    with open(f"archive/{date_seed}.json", "w", encoding="utf-8") as f:
        json.dump(triptych, f, ensure_ascii=False, indent=2)

    print("today.json généré avec succès !")

if __name__ == "__main__":
    main()

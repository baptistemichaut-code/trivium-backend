import os
import json
import datetime
import urllib.parse
import requests

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = "gemini-3.6-flash"

# MARK: - 1. Génération IA avec Comparaison de Critiques

def generate_with_gemini(today_str):
    if not GEMINI_API_KEY:
        raise ValueError("La variable GEMINI_API_KEY est introuvable ou vide.")

    prompt = f"""
    Tu es le conservateur culturel en chef de Trivium.
    Date du jour : {today_str}.
    
    Génère un triptyque culturel inédit pour aujourd'hui (1 Livre, 1 Film, 1 Album) uni par un thème subtil et original.
    Évite impérativement les clichés évidents (Burial, Perec, Camus, Radiohead, Blade Runner, etc.).
    
    IMPORTANT : Pour chaque œuvre, fournis 2 à 3 revues de presse distinctes issues de médias de référence pour permettre une comparaison critique (ex : Le Monde, Télérama, Les Inrocks, Cahiers du Cinéma, Pitchfork, Babelio, SensCritique, The Guardian).
    
    Format JSON strict obligatoire (sans texte d'introduction ni balises markdown) :
    {{
      "themeTitle": "Titre éditorial du thème",
      "themeSubtitle": "Accroche synthétique expliquant la résonance entre ces 3 œuvres",
      "heroImageURL": null,
      "items": [
        {{
          "type": "LIVRE",
          "title": "Titre exact de l'œuvre",
          "creator": "Nom de l'auteur",
          "year": "Année",
          "genre": "Genre littéraire",
          "formatMetric": "Ex: 240 pages",
          "accessibility": "Accessible ou Équilibrée ou Exigeante",
          "tags": ["Thème1", "Thème2"],
          "quote": "Extrait marquant",
          "origin": "Pays d'origine",
          "imageURL": null,
          "previewURL": null,
          "tracks": null,
          "aiSummary": "Court synopsis percutant (2-3 phrases).",
          "thematicAnalysis": "Analyse critique et justification argumentée de sa place dans le triptyque.",
          "ratings": [
            {{
              "source": "Le Monde des Livres",
              "score": "Incontournable",
              "excerpt": "Extrait critique",
              "badgeColorName": "orange",
              "iconName": "quote.bubble.fill"
            }},
            {{
              "source": "Télérama",
              "score": "TTT",
              "excerpt": "Extrait critique",
              "badgeColorName": "orange",
              "iconName": "star.fill"
            }},
            {{
              "source": "Babelio",
              "score": "4.3/5",
              "excerpt": "Avis des lecteurs",
              "badgeColorName": "orange",
              "iconName": "star.fill"
            }}
          ],
          "platformLinks": []
        }},
        {{
          "type": "FILM",
          "title": "Titre exact du film",
          "creator": "Nom du réalisateur",
          "year": "Année",
          "genre": "Genre cinématographique",
          "formatMetric": "Ex: 1 h 54",
          "accessibility": "Accessible ou Équilibrée ou Exigeante",
          "tags": ["Thème1", "Thème2"],
          "quote": "Réplique culte",
          "origin": "Pays d'origine",
          "imageURL": null,
          "previewURL": null,
          "tracks": null,
          "aiSummary": "Court synopsis cinématographique (2-3 phrases).",
          "thematicAnalysis": "Analyse de la mise en scène et justification argumentée de sa place dans le triptyque.",
          "ratings": [
            {{
              "source": "Cahiers du Cinéma",
              "score": "Chef-d'œuvre",
              "excerpt": "Extrait critique",
              "badgeColorName": "blue",
              "iconName": "quote.bubble.fill"
            }},
            {{
              "source": "Positif",
              "score": "Remarquable",
              "excerpt": "Extrait critique",
              "badgeColorName": "blue",
              "iconName": "star.fill"
            }},
            {{
              "source": "SensCritique",
              "score": "7.9/10",
              "excerpt": "Synthèse critique",
              "badgeColorName": "blue",
              "iconName": "star.fill"
            }}
          ],
          "platformLinks": []
        }},
        {{
          "type": "ALBUM",
          "title": "Titre exact de l'album",
          "creator": "Nom de l'artiste",
          "year": "Année",
          "genre": "Genre musical",
          "formatMetric": "Ex: 10 titres • 44 min",
          "accessibility": "Accessible ou Équilibrée ou Exigeante",
          "tags": ["Thème1", "Thème2"],
          "quote": "Phrase d'ambiance sonore",
          "origin": "Pays d'origine",
          "imageURL": null,
          "previewURL": null,
          "tracks": null,
          "aiSummary": "Présentation de l'album (2-3 phrases).",
          "thematicAnalysis": "Analyse sonore et justification argumentée de sa place dans le triptyque.",
          "ratings": [
            {{
              "source": "Pitchfork",
              "score": "8.7/10",
              "excerpt": "Extrait critique",
              "badgeColorName": "red",
              "iconName": "music.note"
            }},
            {{
              "source": "Les Inrockuptibles",
              "score": "5/5",
              "excerpt": "Extrait critique",
              "badgeColorName": "red",
              "iconName": "quote.bubble.fill"
            }}
          ],
          "platformLinks": []
        }}
      ]
    }}
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.85
        }
    }

    res = requests.post(url, json=payload, timeout=60)
    if res.status_code != 200:
        raise RuntimeError(f"Erreur API Gemini ({res.status_code}) : {res.text}")

    data = res.json()
    raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()

    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]

    return json.loads(raw_text.strip())

# MARK: - 2. Visuels Films (Apple -> Repli Wikipédia)

def fetch_movie_poster(title):
    try:
        encoded = urllib.parse.quote(title)
        url = f"[https://itunes.apple.com/search?term=](https://itunes.apple.com/search?term=){encoded}&media=movie&entity=movie&limit=1&country=FR"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results and results[0].get("artworkUrl100"):
                return results[0]["artworkUrl100"].replace("100x100bb", "600x900bb")
    except Exception:
        pass

    try:
        encoded = urllib.parse.quote(title)
        wiki_url = f"[https://fr.wikipedia.org/api/rest_v1/page/summary/](https://fr.wikipedia.org/api/rest_v1/page/summary/){encoded}"
        res = requests.get(wiki_url, headers={"User-Agent": "TriviumApp/1.0"}, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if data.get("thumbnail") and data["thumbnail"].get("source"):
                return data["thumbnail"]["source"]
            if data.get("originalimage") and data["originalimage"].get("source"):
                return data["originalimage"]["source"]
    except Exception:
        pass

    return None

# MARK: - 3. Visuels Livres (Google Books -> Repli Open Library)

def fetch_book_cover(title, author):
    try:
        query = urllib.parse.quote(f"intitle:{title} inauthor:{author}")
        url = f"[https://www.googleapis.com/books/v1/volumes?q=](https://www.googleapis.com/books/v1/volumes?q=){query}&maxResults=1"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            items = res.json().get("items", [])
            if items:
                image_links = items[0].get("volumeInfo", {}).get("imageLinks", {})
                img = image_links.get("thumbnail") or image_links.get("smallThumbnail")
                if img:
                    img = img.replace("http://", "https://")
                    if "&edge=curl" in img:
                        img = img.replace("&edge=curl", "")
                    return img
    except Exception:
        pass

    try:
        query = urllib.parse.quote(f"{title} {author}")
        url = f"[https://openlibrary.org/search.json?q=](https://openlibrary.org/search.json?q=){query}&limit=1"
        res = requests.get(url, headers={"User-Agent": "TriviumApp/1.0"}, timeout=10)
        if res.status_code == 200:
            docs = res.json().get("docs", [])
            if docs and docs[0].get("cover_i"):
                return f"[https://covers.openlibrary.org/b/id/](https://covers.openlibrary.org/b/id/){docs[0]['cover_i']}-L.jpg?default=false"
    except Exception:
        pass

    return None

# MARK: - 4. Visuels & Pistes Albums (Apple Music)

def fetch_itunes_album(title, artist):
    try:
        query = urllib.parse.quote(f"{title} {artist}")
        url = f"[https://itunes.apple.com/search?term=](https://itunes.apple.com/search?term=){query}&media=music&entity=album&limit=1&country=FR"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                album = results[0]
                collection_id = album.get("collectionId")
                cover = album.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
                apple_url = album.get("collectionViewUrl")

                lookup_url = f"[https://itunes.apple.com/lookup?id=](https://itunes.apple.com/lookup?id=){collection_id}&entity=song&country=FR"
                lookup_res = requests.get(lookup_url, timeout=10)
                tracks = []
                first_preview = None
                if lookup_res.status_code == 200:
                    for item in lookup_res.json().get("results", []):
                        if item.get("wrapperType") == "track":
                            millis = item.get("trackTimeMillis", 0)
                            secs = millis // 1000
                            duration = f"{secs // 60}:{secs % 60:02d}"
                            if not first_preview:
                                first_preview = item.get("previewUrl")
                            tracks.append({
                                "trackNumber": item.get("trackNumber", len(tracks) + 1),
                                "title": item.get("trackName", "Piste"),
                                "duration": duration,
                                "previewURL": item.get("previewUrl")
                            })
                tracks.sort(key=lambda x: x["trackNumber"])
                return cover, first_preview, tracks, apple_url
    except Exception:
        pass
    return None, None, [], None

# MARK: - Exécution Principale

def main():
    today_date = datetime.date.today()
    today_str = today_date.strftime("%Y-%m-%d")
    print(f"Génération de l'édition : {today_str} via {GEMINI_MODEL}")

    triptych = generate_with_gemini(today_str)

    for item in triptych.get("items", []):
        media_type = item.get("type", "").upper()
        title = item.get("title", "")
        creator = item.get("creator", "")
        encoded_query = urllib.parse.quote(f"{title} {creator}")

        if media_type == "ALBUM":
            cover, preview, tracks, apple_url = fetch_itunes_album(title, creator)
            item["imageURL"] = cover
            item["previewURL"] = preview
            item["tracks"] = tracks
            item["platformLinks"] = [
                {"name": "Spotify", "category": "Écouter l'album", "urlString": f"[https://open.spotify.com/search/](https://open.spotify.com/search/){encoded_query}/albums", "iconName": "music.note"},
                {"name": "Apple Music", "category": "Streaming Lossless", "urlString": apple_url or f"[https://music.apple.com/fr/search?term=](https://music.apple.com/fr/search?term=){encoded_query}", "iconName": "apple.logo"},
                {"name": "Deezer", "category": "Streaming Hi-Fi", "urlString": f"[https://www.deezer.com/search/](https://www.deezer.com/search/){encoded_query}/album", "iconName": "play.circle.fill"}
            ]
        elif media_type == "FILM":
            item["imageURL"] = fetch_movie_poster(title)
            movie_enc = urllib.parse.quote(title)
            item["platformLinks"] = [
                {"name": "Où regarder en streaming", "category": "Netflix, Prime, Disney+...", "urlString": f"[https://www.justwatch.com/fr/recherche?q=](https://www.justwatch.com/fr/recherche?q=){movie_enc}", "iconName": "play.tv.fill"},
                {"name": "Apple TV", "category": "Location & Achat 4K", "urlString": f"[https://tv.apple.com/fr/search?term=](https://tv.apple.com/fr/search?term=){movie_enc}", "iconName": "apple.logo"},
                {"name": "Canal+ VOD", "category": "Location & myCANAL", "urlString": f"[https://vod.canalplus.com/recherche/](https://vod.canalplus.com/recherche/){movie_enc}", "iconName": "film.fill"}
            ]
        elif media_type == "LIVRE":
            item["imageURL"] = fetch_book_cover(title, creator)
            item["platformLinks"] = [
                {"name": "Fnac", "category": "Livre papier (Broché / Poche)", "urlString": f"[https://www.fnac.com/SearchResult/ResultList.aspx?Search=](https://www.fnac.com/SearchResult/ResultList.aspx?Search=){encoded_query}", "iconName": "book.closed.fill"},
                {"name": "Kindle", "category": "Édition numérique E-book", "urlString": f"[https://www.amazon.fr/s?k=](https://www.amazon.fr/s?k=){encoded_query}&i=digital-text", "iconName": "ipad.and.arrow.forward"},
                {"name": "Audible", "category": "Livre audio narré", "urlString": f"[https://www.audible.fr/search?keywords=](https://www.audible.fr/search?keywords=){encoded_query}", "iconName": "headphones"}
            ]

    os.makedirs("archive", exist_ok=True)
    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(triptych, f, ensure_ascii=False, indent=2)

    archive_path = f"archive/{today_str}.json"
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(triptych, f, ensure_ascii=False, indent=2)

    print("Génération réussie et sauvegardée.")

if __name__ == "__main__":
    main()

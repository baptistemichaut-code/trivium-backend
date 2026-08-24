import os
import glob
import json
import time
import datetime
import urllib.parse
import re
import requests

def clean_str(s):
    if not s:
        return ""
    return re.sub(r'[^a-zA-Z0-9\s]', '', s).lower().strip()

def get_previously_used_titles():
    """Scanne et extrait 100 % des œuvres et artistes déjà parus dans les archives."""
    used = set()
    files = glob.glob("archive/*.json")
    if os.path.exists("today.json"):
        files.append("today.json")

    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                for tier in ["accessible", "intermediate", "expert"]:
                    if tier in data and "items" in data[tier]:
                        for item in data[tier]["items"]:
                            t = item.get("title", "").strip()
                            c = item.get("creator", "").strip()
                            if t:
                                used.add(f"« {t} » par {c}" if c else f"« {t} »")
                if "items" in data:
                    for item in data["items"]:
                        t = item.get("title", "").strip()
                        c = item.get("creator", "").strip()
                        if t:
                            used.add(f"« {t} » par {c}" if c else f"« {t} »")
        except Exception:
            continue
    return sorted(list(used))

def build_book_links(title, author):
    clean_t = title.split(":")[0].strip()
    q = urllib.parse.quote(f"{clean_t} {author}")
    return [
        {"name": "Les Libraires", "category": "Librairie indépendante", "urlString": f"https://www.leslibraires.fr/recherche/?q={q}", "iconName": "books.vertical.fill"},
        {"name": "Fnac", "category": "Format papier & ebook", "urlString": f"https://www.fnac.com/SearchResult/ResultList.aspx?SCat=0&Search={q}", "iconName": "book.closed.fill"},
        {"name": "Audible", "category": "Livre audio", "urlString": f"https://www.audible.fr/search?keywords={q}", "iconName": "headphones"}
    ]

def build_movie_links(title, director):
    clean_t = title.split("(")[0].strip()
    q = urllib.parse.quote(clean_t)
    return [
        {"name": "JustWatch", "category": "Où voir en streaming / VOD", "urlString": f"https://www.justwatch.com/fr/recherche?q={q}", "iconName": "tv.fill"},
        {"name": "Allociné", "category": "Fiche & séances", "urlString": f"https://www.allocine.fr/recherche/?q={q}", "iconName": "film.fill"},
        {"name": "Canal+ VOD", "category": "Location / Achat", "urlString": f"https://www.canalplus.com/recherche?q={q}", "iconName": "play.tv.fill"}
    ]

def build_album_links(title, artist, direct_apple_url=None):
    clean_t = title.split("(")[0].strip()
    q = urllib.parse.quote(f"{clean_t} {artist}")
    apple_url = direct_apple_url if direct_apple_url else f"https://music.apple.com/fr/search?term={q}"
    return [
        {"name": "Spotify", "category": "Écouter sur Spotify", "urlString": f"https://open.spotify.com/search/{q}", "iconName": "waveform"},
        {"name": "Apple Music", "category": "Écouter sur Apple Music", "urlString": apple_url, "iconName": "music.note"},
        {"name": "Deezer", "category": "Écouter sur Deezer", "urlString": f"https://www.deezer.com/search/{q}", "iconName": "play.circle.fill"}
    ]

def fetch_album_metadata(title, artist):
    """Recherche ultra-précise avec système de score pour éviter les faux albums."""
    try:
        raw_clean_title = re.sub(r'[\(\[].*?[\)\]]', '', title).strip()
        norm_title = clean_str(raw_clean_title)
        norm_artist = clean_str(artist)

        query = urllib.parse.quote(f"{raw_clean_title} {artist}")

        for country in ["FR", "US", "GB"]:
            search_url = f"https://itunes.apple.com/search?term={query}&entity=album&limit=15&country={country}"
            res = requests.get(search_url, timeout=10).json()
            results = res.get("results", [])
            if not results:
                continue

            best_album = None
            best_score = -1

            for alb in results:
                alb_name = clean_str(alb.get("collectionName", ""))
                art_name = clean_str(alb.get("artistName", ""))

                score = 0
                # Correspondance artiste
                if norm_artist in art_name or art_name in norm_artist:
                    score += 50

                # Correspondance titre
                if norm_title == alb_name:
                    score += 100
                elif norm_title in alb_name:
                    score += 65
                elif alb_name in norm_title:
                    score += 45
                else:
                    title_words = set(norm_title.split())
                    alb_words = set(alb_name.split())
                    common = title_words.intersection(alb_words)
                    if len(title_words) > 0:
                        score += int((len(common) / len(title_words)) * 50)

                # Pénalité stricte sur les reprises ou karaoké
                if "tribute" in alb_name or "karaoke" in alb_name:
                    score -= 80

                if score > best_score and score >= 65:
                    best_score = score
                    best_album = alb

            if best_album:
                collection_id = best_album.get("collectionId")
                direct_url = best_album.get("collectionViewUrl")
                artwork = best_album.get("artworkUrl100", "").replace("100x100bb.jpg", "600x600bb.jpg")

                # Récupération de la tracklist avec gestion multi-disques
                lookup_url = f"https://itunes.apple.com/lookup?id={collection_id}&entity=song&limit=50&country={country}"
                lookup_res = requests.get(lookup_url, timeout=10).json()

                raw_tracks = []
                for item in lookup_res.get("results", []):
                    if item.get("wrapperType") == "track":
                        disc_num = item.get("discNumber", 1)
                        track_num = item.get("trackNumber", 1)
                        millis = item.get("trackTimeMillis", 0)
                        mins = millis // 60000
                        secs = (millis % 60000) // 1000
                        raw_tracks.append({
                            "disc": disc_num,
                            "trackNumber": track_num,
                            "title": item.get("trackName", "Piste"),
                            "duration": f"{mins}:{secs:02d}",
                            "previewURL": item.get("previewUrl")
                        })

                # Tri dans l'ordre réel de l'œuvre (disque puis piste)
                raw_tracks.sort(key=lambda x: (x["disc"], x["trackNumber"]))

                tracks = []
                for idx, t in enumerate(raw_tracks, start=1):
                    tracks.append({
                        "trackNumber": idx,
                        "title": t["title"],
                        "duration": t["duration"],
                        "previewURL": t["previewURL"]
                    })

                return artwork, tracks, direct_url
    except Exception as e:
        print(f"Erreur iTunes ({title}): {e}")
    return None, None, None

def fetch_movie_artwork(title, director):
    """Recherche d'affiche de film sur iTunes Store."""
    try:
        clean_title = title.split("(")[0].strip()
        query = urllib.parse.quote(clean_title)
        for country in ["FR", "US"]:
            search_url = f"https://itunes.apple.com/search?term={query}&entity=movie&limit=5&country={country}"
            res = requests.get(search_url, timeout=10).json()
            results = res.get("results", [])
            if results:
                for movie in results:
                    name = movie.get("trackName", "").lower()
                    if clean_title.lower() in name or name in clean_title.lower():
                        return movie.get("artworkUrl100", "").replace("100x100bb.jpg", "600x600bb.jpg")
                return results[0].get("artworkUrl100", "").replace("100x100bb.jpg", "600x600bb.jpg")
    except Exception as e:
        print(f"Erreur Film ({title}): {e}")
    return None

def fetch_book_artwork(title, author):
    """Recherche de couverture : Google Books puis fallback OpenLibrary."""
    try:
        clean_title = title.split(":")[0].split("(")[0].strip()
        query = urllib.parse.quote(f"{clean_title} {author}")

        search_url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults=5&printType=books"
        res = requests.get(search_url, timeout=10).json()
        if "items" in res and len(res["items"]) > 0:
            for it in res["items"]:
                vol = it.get("volumeInfo", {})
                imgs = vol.get("imageLinks", {})
                thumb = imgs.get("extraLarge") or imgs.get("large") or imgs.get("medium") or imgs.get("thumbnail") or imgs.get("smallThumbnail")
                if thumb:
                    thumb = thumb.replace("http://", "https://").replace("&edge=curl", "")
                    return thumb

        ol_query = urllib.parse.quote(f"{clean_title} {author}")
        ol_url = f"https://openlibrary.org/search.json?q={ol_query}&limit=1"
        ol_res = requests.get(ol_url, timeout=10).json()
        docs = ol_res.get("docs", [])
        if docs and "cover_i" in docs[0]:
            cover_id = docs[0]["cover_i"]
            return f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
    except Exception as e:
        print(f"Erreur Livre ({title}): {e}")
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

    used_titles = get_previously_used_titles()
    exclusion_block = ""
    if used_titles:
        exclusion_list = "\n".join([f"- {t}" for t in used_titles])
        exclusion_block = f"""
LISTE D'EXCLUSION STRICTE (TOUTES CES ŒUVRES ONT DÉJÀ ÉTÉ PROPOSÉES, INTERDICTION FORMELLE DE LES RÉPÉTER) :
{exclusion_list}
"""

    prompt = f"""
Tu es le directeur éditorial de l'application culturelle de prestige "Trivium".
Crée aujourd'hui 3 éditions thématiques TOTALEMENT INÉDITES selon 3 niveaux de curiosité culturelle :
1. "accessible" (Pop culture, grands classiques, œuvres cultes et accessibles).
2. "intermediate" (Cinéma d'auteur accessible, pépites littéraires, albums cultes reconnus).
3. "expert" (Maxi nerd, underground, avant-garde, cinéma d'art et essai, littérature exigeante).

{exclusion_block}

EXIGENCE CRITIQUE STRICTE & FACTUELLE (REVUES DE PRESSE VÉRIFIÉES) :
Pour chaque œuvre sélectionnée, fournis impérativement 3 critiques AUTHENTIQUES issues de médias reconnus :
- LIVRES : citer de vraies revues parmi *Le Monde des Livres*, *Télérama*, *Libération*, *Babelio*, *Le Figaro Littéraire*, *Lire Magazine*.
- FILMS : citer les vraies notes avec leur système de notation réel parmi *Télérama* (notations réelles : T, TT, TTT, TTTT), *Cahiers du Cinéma*, *Allociné Presse* (/5), *SensCritique* (/10), *Rotten Tomatoes* (%).
- ALBUMS : citer la note exacte parmi *Pitchfork* (note réelle à un chiffre après la virgule, ex: 8.4/10), *Rolling Stone* (/5), *Les Inrockuptibles*, *The Guardian*, *AllMusic*.
- AUCUNE INVENTION : chaque extrait ("excerpt") doit fidèlement synthétiser la position critique réelle du média lors de sa parution.

Renvoie UNIQUEMENT un objet JSON valide (texte brut, aucun balisage markdown ```json) respectant scrupuleusement ce schéma :
{{
  "accessible": {{
    "themeTitle": "Titre du thème accessible",
    "themeSubtitle": "Phrase d'accroche",
    "items": [
      {{
        "type": "LIVRE", "title": "Titre exact", "creator": "Auteur", "year": "Année", "genre": "Genre",
        "origin": "Pays", "formatMetric": "340 pages", "accessibility": "Populaire & Immédiat",
        "quote": "Citation authentique", "aiSummary": "Résumé captivant", "thematicAnalysis": "Analyse de résonance", "anecdote": "Anecdote véridique",
        "tags": ["Tag1", "Tag2"],
        "ratings": [
          {{"source": "Le Figaro Littéraire", "score": "5/5", "excerpt": "Synthèse critique.", "iconName": "newspaper.fill"}},
          {{"source": "Babelio", "score": "4.4/5", "excerpt": "Consensus des lecteurs.", "iconName": "star.fill"}},
          {{"source": "Télérama", "score": "TTT", "excerpt": "Regard sur le style.", "iconName": "quote.bubble.fill"}}
        ]
      }},
      {{ "type": "FILM", "title": "Titre exact", "creator": "Réalisateur", "year": "Année", "genre": "Genre", "origin": "Pays", "formatMetric": "2h 05m", "accessibility": "Culte & Grand Public", "quote": "Réplique culte", "aiSummary": "Synopsis", "thematicAnalysis": "Analyse de résonance", "anecdote": "Anecdote véridique", "tags": ["Tag1", "Tag2"], "ratings": [{{"source": "Télérama", "score": "TTTT", "excerpt": "Synthèse critique.", "iconName": "film.fill"}}, {{"source": "Cahiers du Cinéma", "score": "5/5", "excerpt": "Mise en scène.", "iconName": "star.fill"}}, {{"source": "Première", "score": "4/5", "excerpt": "Jeu d'acteur.", "iconName": "newspaper.fill"}}] }},
      {{ "type": "ALBUM", "title": "Titre exact", "creator": "Artiste", "year": "Année", "genre": "Genre", "origin": "Pays", "formatMetric": "10 titres", "accessibility": "Écoute Immédiate", "quote": "Citation", "aiSummary": "Présentation", "thematicAnalysis": "Analyse de résonance", "anecdote": "Anecdote véridique", "tags": ["Tag1", "Tag2"], "ratings": [{{"source": "Pitchfork", "score": "8.8/10", "excerpt": "Synthèse du test.", "iconName": "music.note"}}, {{"source": "Rolling Stone", "score": "5/5", "excerpt": "Puissance des morceaux.", "iconName": "star.fill"}}, {{"source": "Les Inrockuptibles", "score": "Indispensable", "excerpt": "Inventivité.", "iconName": "quote.bubble.fill"}}] }}
    ]
  }},
  "intermediate": {{
    "themeTitle": "Titre du thème intermédiaire",
    "themeSubtitle": "Phrase d'accroche",
    "items": [ ... 1 LIVRE, 1 FILM, 1 ALBUM ... ]
  }},
  "expert": {{
    "themeTitle": "Titre du thème expert",
    "themeSubtitle": "Phrase d'accroche",
    "items": [ ... 1 LIVRE, 1 FILM, 1 ALBUM ... ]
  }}
}}
"""

    host = "https://" + "generativelanguage.googleapis.com"
    endpoint = "/v1beta/models/gemini-3.6-flash:generateContent"
    url = f"{host}{endpoint}?key={api_key}"

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.95
        }
    }

    max_retries = 3
    response = None
    for attempt in range(1, max_retries + 1):
        print(f"Tentative de génération {attempt}/{max_retries}...")
        response = requests.post(url, headers=headers, json=payload, timeout=90)
        if response.status_code == 200:
            break
        elif response.status_code == 429:
            wait_time = 15 * attempt
            print(f"Quota temporaire atteint (429). Pause de {wait_time}s...")
            time.sleep(wait_time)
        else:
            print(f"Erreur API: {response.text}")
            response.raise_for_status()

    response.raise_for_status()

    result = response.json()
    candidate = result.get("candidates", [{}])[0]
    parts = candidate.get("content", {}).get("parts", [])
    raw_text = "".join([part.get("text", "") for part in parts if "text" in part]).strip()

    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    raw_text = raw_text.strip()

    data = json.loads(raw_text)

    for tier in ["accessible", "intermediate", "expert"]:
        if tier in data:
            enrich_triptych(data[tier])

    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("today.json généré et enrichi avec succès.")

    os.makedirs("archive", exist_ok=True)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    archive_path = os.path.join("archive", f"{today_str}.json")
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Archive enregistrée : {archive_path}")

if __name__ == "__main__":
    generate_daily_edition()

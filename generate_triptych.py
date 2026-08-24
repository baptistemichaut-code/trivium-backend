import os
import glob
import json
import time
import datetime
import urllib.parse
import re
import random
import difflib
import requests

# Thèmes d'inspiration aléatoires pour forcer l'IA à varier ses angles
THEME_SEEDS = [
    "La paranoïa et le doute du réel",
    "La solitude dans les mégalopoles modernes",
    "Les métamorphoses du corps et de l'esprit",
    "L'odyssée spatiale et le silence cosmique",
    "Les désillusions du rêve américain",
    "L'héritage, les secrets de famille et le temps",
    "Les contre-cultures et la révolte brute",
    "La mélancolie poétique et le spleen urbain",
    "Les machines conscientes et le techno-fantastique",
    "Les voyages initiatiques au bout du monde",
    "Le jazz nocturne, le polar et la fumée",
    "L'art de la fugue et les labyrinthes mentaux"
]

def clean_str(s):
    if not s:
        return ""
    return re.sub(r'[^a-zA-Z0-9\s]', '', s).lower().strip()

def get_previously_used_titles():
    """Scanne 100 % des œuvres et artistes parus dans toutes les archives."""
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
                            t = clean_str(item.get("title", ""))
                            if t:
                                used.add(t)
        except Exception:
            continue
    return used

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
    """Recherche d'album avec score de similarité textuelle."""
    try:
        # Retrait des mentions d'édition (Remaster, Deluxe, Anniversary...)
        clean_target = re.sub(r'[\(\[].*?[\)\]]', '', title).strip()
        norm_target = clean_str(clean_target)
        norm_artist = clean_str(artist)

        query = urllib.parse.quote(f"{clean_target} {artist}")

        for country in ["FR", "US", "GB"]:
            search_url = f"https://itunes.apple.com/search?term={query}&entity=album&limit=25&country={country}"
            res = requests.get(search_url, timeout=10).json()
            results = res.get("results", [])
            if not results:
                continue

            best_album = None
            best_score = 0.0

            for alb in results:
                alb_raw = alb.get("collectionName", "")
                alb_clean = re.sub(r'[\(\[].*?[\)\]]', '', alb_raw).strip()
                norm_alb = clean_str(alb_clean)
                norm_art = clean_str(alb.get("artistName", ""))

                # Vérification de l'artiste
                artist_match = (norm_artist in norm_art or norm_art in norm_artist)
                if not artist_match:
                    continue

                # Calcul du ratio de ressemblance
                ratio = difflib.SequenceMatcher(None, norm_target, norm_alb).ratio()

                # Pénalisation des albums de reprises
                if "tribute" in norm_alb or "karaoke" in norm_alb:
                    ratio -= 0.5

                if ratio > best_score:
                    best_score = ratio
                    best_album = alb

            if best_album and best_score >= 0.40:
                collection_id = best_album.get("collectionId")
                direct_url = best_album.get("collectionViewUrl")
                artwork = best_album.get("artworkUrl100", "").replace("100x100bb.jpg", "600x600bb.jpg")

                # Récupération de la tracklist ordonnée
                lookup_url = f"https://itunes.apple.com/lookup?id={collection_id}&entity=song&limit=60&country={country}"
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

                # Tri séquentiel (disque, puis piste)
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
                    return thumb.replace("http://", "https://").replace("&edge=curl", "")

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

    used_titles_set = get_previously_used_titles()
    random_seed_theme = random.choice(THEME_SEEDS)

    exclusion_list_text = "\n".join([f"- {t.title()}" for t in sorted(list(used_titles_set))])
    exclusion_block = f"""
LISTE D'EXCLUSION STRICTE (ŒUVRES DÉJÀ PARUES — INTERDICTION ABSOLUE DE LES PROPOSER À NOUVEAU) :
{exclusion_list_text}
"""

    prompt = f"""
Tu es le directeur éditorial de la prestigieuse application culturelle "Trivium".
Aujourd'hui, explore un triptyque original guidé par cette inspiration : « {random_seed_theme} ».

Crée 3 éditions thématiques INÉDITES selon 3 niveaux de sensibilité culturelle :
1. "accessible" (Pop culture, chefs-d'œuvre cultes et universels).
2. "intermediate" (Cinéma d'auteur accessible, pépites littéraires, albums cultes reconnus).
3. "expert" (Underground, avant-garde, cinéma d'art et essai, littérature exigeante).

{exclusion_block}

RÈGLES CRITIQUES STRICTES :
Pour chaque œuvre, fournis 3 critiques authentiques issues de vrais médias :
- LIVRES : revues parmi *Le Monde des Livres*, *Télérama*, *Libération*, *Babelio*, *Le Figaro Littéraire*, *Lire Magazine*.
- FILMS : notes réelles parmi *Télérama* (notations T, TT, TTT, TTTT), *Cahiers du Cinéma*, *Allociné Presse* (/5), *SensCritique* (/10), *Rotten Tomatoes* (%).
- ALBUMS : notes réelles parmi *Pitchfork* (/10 avec un chiffre après la virgule), *Rolling Stone* (/5), *Les Inrockuptibles*, *AllMusic*.

Renvoie UNIQUEMENT un objet JSON valide (texte brut, aucun balisage ```json) suivant cette structure :
{{
  "accessible": {{
    "themeTitle": "Titre du thème",
    "themeSubtitle": "Phrase d'accroche",
    "items": [
      {{
        "type": "LIVRE", "title": "Titre exact", "creator": "Auteur", "year": "Année", "genre": "Genre",
        "origin": "Pays", "formatMetric": "340 pages", "accessibility": "Populaire & Immédiat",
        "quote": "Citation authentique", "aiSummary": "Résumé", "thematicAnalysis": "Analyse", "anecdote": "Anecdote véridique",
        "tags": ["Tag1", "Tag2"],
        "ratings": [
          {{"source": "Le Monde", "score": "Indispensable", "excerpt": "Synthèse critique.", "iconName": "newspaper.fill"}},
          {{"source": "Babelio", "score": "4.4/5", "excerpt": "Avis critique.", "iconName": "star.fill"}},
          {{"source": "Télérama", "score": "TTT", "excerpt": "Regard critique.", "iconName": "quote.bubble.fill"}}
        ]
      }},
      {{ "type": "FILM", "title": "Titre exact", "creator": "Réalisateur", "year": "Année", "genre": "Genre", "origin": "Pays", "formatMetric": "2h 05m", "accessibility": "Culte & Grand Public", "quote": "Réplique culte", "aiSummary": "Synopsis", "thematicAnalysis": "Analyse", "anecdote": "Anecdote", "tags": ["Tag1", "Tag2"], "ratings": [{{"source": "Télérama", "score": "TTTT", "excerpt": "Synthèse.", "iconName": "film.fill"}}, {{"source": "Cahiers du Cinéma", "score": "5/5", "excerpt": "Mise en scène.", "iconName": "star.fill"}}, {{"source": "Première", "score": "4/5", "excerpt": "Jeu d'acteur.", "iconName": "newspaper.fill"}}] }},
      {{ "type": "ALBUM", "title": "Titre exact", "creator": "Artiste", "year": "Année", "genre": "Genre", "origin": "Pays", "formatMetric": "10 titres", "accessibility": "Écoute Immédiate", "quote": "Citation", "aiSummary": "Présentation", "thematicAnalysis": "Analyse", "anecdote": "Anecdote", "tags": ["Tag1", "Tag2"], "ratings": [{{"source": "Pitchfork", "score": "8.8/10", "excerpt": "Synthèse.", "iconName": "music.note"}}, {{"source": "Rolling Stone", "score": "5/5", "excerpt": "Avis.", "iconName": "star.fill"}}, {{"source": "Les Inrockuptibles", "score": "Indispensable", "excerpt": "Avis.", "iconName": "quote.bubble.fill"}}] }}
    ]
  }},
  "intermediate": {{
    "themeTitle": "Titre intermédiaire",
    "themeSubtitle": "Phrase d'accroche",
    "items": [ ... 1 LIVRE, 1 FILM, 1 ALBUM ... ]
  }},
  "expert": {{
    "themeTitle": "Titre expert",
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
            "temperature": 0.85,
            "topP": 0.95
        }
    }

    max_retries = 3
    data = None
    for attempt in range(1, max_retries + 1):
        print(f"Tentative de génération {attempt}/{max_retries} (Inspiration : {random_seed_theme})...")
        response = requests.post(url, headers=headers, json=payload, timeout=90)
        if response.status_code == 429:
            time.sleep(15 * attempt)
            continue
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

        parsed = json.loads(raw_text)

        # Vérification anti-doublons par le code Python
        has_duplicates = False
        for tier in ["accessible", "intermediate", "expert"]:
            if tier in parsed:
                for it in parsed[tier].get("items", []):
                    if clean_str(it.get("title", "")) in used_titles_set:
                        print(f"Doublon détecté par le filtre : {it.get('title')}. Relance d'une nouvelle génération...")
                        has_duplicates = True
                        break
            if has_duplicates:
                break

        if not has_duplicates:
            data = parsed
            break

    if not data:
        data = parsed  # Fallback si persistance après les 3 essais

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

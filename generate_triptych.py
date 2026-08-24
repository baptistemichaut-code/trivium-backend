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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

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
    "L'art de la fugue et les labyrinthes mentaux",
    "L'illusion du progrès et l'utopie brisée",
    "L'obsession de la création et la folie artistique",
    "Les rituels oubliés et le mysticisme païen",
    "L'intimité à l'épreuve de l'Histoire",
    "La beauté du chaos et la dérive urbaine",
    "L'enfance, les songes et la perte de l'innocence"
]

def clean_str(s):
    if not s:
        return ""
    return re.sub(r'[^a-zA-Z0-9\s]', '', s).lower().strip()

def get_archived_history():
    """Scanne et extrait 100 % des œuvres et de tous les thèmes parus."""
    used_titles = set()
    used_themes = set()
    files = glob.glob("archive/*.json")
    if os.path.exists("today.json"):
        files.append("today.json")

    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
                for tier in ["accessible", "intermediate", "expert"]:
                    if tier in data:
                        t_title = data[tier].get("themeTitle", "")
                        if t_title:
                            used_themes.add(clean_str(t_title))
                        for item in data[tier].get("items", []):
                            t = clean_str(item.get("title", ""))
                            if t:
                                used_titles.add(t)
                if "items" in data:
                    for item in data["items"]:
                        t = clean_str(item.get("title", ""))
                        if t:
                            used_titles.add(t)
        except Exception:
            continue
    return used_titles, used_themes

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
    try:
        clean_target = re.sub(r'[\(\[].*?[\)\]]', '', title).strip()
        norm_target = clean_str(clean_target)
        norm_artist = clean_str(artist)
        query = urllib.parse.quote(f"{clean_target} {artist}")

        for country in ["FR", "US", "GB"]:
            search_url = f"https://itunes.apple.com/search?term={query}&entity=album&limit=25&country={country}"
            res = requests.get(search_url, headers=HEADERS, timeout=12).json()
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

                if not (norm_artist in norm_art or norm_art in norm_artist):
                    continue

                ratio = difflib.SequenceMatcher(None, norm_target, norm_alb).ratio()
                if "tribute" in norm_alb or "karaoke" in norm_alb:
                    ratio -= 0.5

                if ratio > best_score:
                    best_score = ratio
                    best_album = alb

            if best_album and best_score >= 0.35:
                collection_id = best_album.get("collectionId")
                direct_url = best_album.get("collectionViewUrl")
                artwork = best_album.get("artworkUrl100", "").replace("100x100bb.jpg", "600x600bb.jpg")

                lookup_url = f"https://itunes.apple.com/lookup?id={collection_id}&entity=song&limit=60&country={country}"
                lookup_res = requests.get(lookup_url, headers=HEADERS, timeout=12).json()

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
        queries = [
            urllib.parse.quote(f"{clean_title} {director}"),
            urllib.parse.quote(clean_title)
        ]

        for q in queries:
            for country in ["FR", "US"]:
                search_url = f"https://itunes.apple.com/search?term={q}&entity=movie&limit=10&country={country}"
                res = requests.get(search_url, headers=HEADERS, timeout=12).json()
                results = res.get("results", [])
                if results:
                    norm_target = clean_str(clean_title)
                    for movie in results:
                        name = clean_str(movie.get("trackName", ""))
                        if norm_target in name or name in norm_target:
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
        res = requests.get(search_url, headers=HEADERS, timeout=12).json()
        if "items" in res and len(res["items"]) > 0:
            for it in res["items"]:
                vol = it.get("volumeInfo", {})
                imgs = vol.get("imageLinks", {})
                thumb = imgs.get("extraLarge") or imgs.get("large") or imgs.get("medium") or imgs.get("thumbnail") or imgs.get("smallThumbnail")
                if thumb:
                    return thumb.replace("http://", "https://").replace("&edge=curl", "")

        ol_query = urllib.parse.quote(f"{clean_title} {author}")
        ol_url = f"https://openlibrary.org/search.json?q={ol_query}&limit=1"
        ol_res = requests.get(ol_url, headers=HEADERS, timeout=12).json()
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

def validate_payload_uniqueness(parsed, used_titles_set, used_themes_set):
    """Vérifie l'absence absolue de doublons dans l'historique et entre les 3 niveaux."""
    current_titles = []
    current_themes = []

    for tier in ["accessible", "intermediate", "expert"]:
        if tier not in parsed:
            return False, f"Niveau {tier} manquant."

        t_title = parsed[tier].get("themeTitle", "").strip()
        if not t_title:
            return False, f"Thème manquant pour {tier}."

        norm_theme = clean_str(t_title)

        # 1. Vérification du thème contre l'historique
        for past_theme in used_themes_set:
            if difflib.SequenceMatcher(None, norm_theme, past_theme).ratio() > 0.70:
                return False, f"Thème déjà traité dans les archives : « {t_title} »."

        # 2. Vérification d'unicité entre les 3 thèmes du jour
        for existing in current_themes:
            if difflib.SequenceMatcher(None, norm_theme, existing).ratio() > 0.60:
                return False, f"Thèmes trop proches dans la même édition : « {t_title} »."
        current_themes.append(norm_theme)

        items = parsed[tier].get("items", [])
        if len(items) != 3:
            return False, f"{tier} ne contient pas exactement 3 œuvres."

        for item in items:
            raw_title = item.get("title", "").strip()
            norm_title = clean_str(raw_title)

            # 3. Vérification de l'œuvre contre l'historique
            if norm_title in used_titles_set:
                return False, f"Œuvre déjà recommandée dans le passé : « {raw_title} »."

            # 4. Vérification d'unicité parmi les 9 œuvres du jour
            if norm_title in current_titles:
                return False, f"Œuvre en doublon dans la même journée : « {raw_title} »."
            current_titles.append(norm_title)

    return True, "Validé"

def generate_daily_edition():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY manquant.")

    used_titles_set, used_themes_set = get_archived_history()
    random_seed_theme = random.choice(THEME_SEEDS)

    exclusion_titles_text = "\n".join([f"- {t.title()}" for t in sorted(list(used_titles_set))])
    exclusion_themes_text = "\n".join([f"- {t.title()}" for t in sorted(list(used_themes_set))])

    exclusion_block = f"""
LISTE D'EXCLUSION STRICTE (TOUTES CES ŒUVRES ET THÈMES SONT DÉJÀ PARUS — INTERDICTION ABSOLUE DE LES RÉPÉTER) :

[THÈMES DÉJÀ TRAITÉS] :
{exclusion_themes_text}

[ŒUVRES DÉJÀ PARUES] :
{exclusion_titles_text}
"""

    prompt = f"""
Tu es le directeur éditorial de l'application culturelle "Trivium".
Aujourd'hui, crée une édition entièrement inédite guidée par cet angle : « {random_seed_theme} ».

CONSIGNES STRICTES D'UNICITÉ :
1. Crée 3 thèmes DISTINCTS pour chaque niveau :
   - "accessible" (Pop culture, chefs-d'œuvre cultes et universels).
   - "intermediate" (Cinéma d'auteur accessible, pépites littéraires, albums cultes reconnus).
   - "expert" (Underground, avant-garde, cinéma d'art et essai, littérature exigeante).
2. Toutes les œuvres (9 au total : 3 livres, 3 films, 3 albums) doivent être UNIQUES et ABSOLUMENT SANS AUCUN DOUBLON entre les 3 niveaux.
3. Aucune œuvre ni aucun thème listé dans la liste d'exclusion ci-dessous ne doit être proposé.

{exclusion_block}

RÈGLES CRITIQUES STRICTES :
Pour chaque œuvre, fournis 3 critiques authentiques issues de vrais médias :
- LIVRES : revues parmi *Le Monde des Livres*, *Télérama*, *Libération*, *Babelio*, *Le Figaro Littéraire*, *Lire Magazine*.
- FILMS : notes réelles parmi *Télérama* (notations T, TT, TTT, TTTT), *Cahiers du Cinéma*, *Allociné Presse* (/5), *SensCritique* (/10), *Rotten Tomatoes* (%).
- ALBUMS : notes réelles parmi *Pitchfork* (/10 avec un chiffre après la virgule), *Rolling Stone* (/5), *Les Inrockuptibles*, *AllMusic*.

Renvoie UNIQUEMENT un objet JSON valide (texte brut, aucun balisage ```json) suivant cette structure :
{{
  "accessible": {{
    "themeTitle": "Titre du thème accessible inédit",
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
    "themeTitle": "Titre du thème intermédiaire inédit",
    "themeSubtitle": "Phrase d'accroche",
    "items": [ ... 1 LIVRE, 1 FILM, 1 ALBUM ... ]
  }},
  "expert": {{
    "themeTitle": "Titre du thème expert inédit",
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
            "temperature": 0.88,
            "topP": 0.95
        }
    }

    max_retries = 4
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

        try:
            parsed = json.loads(raw_text)
            is_valid, reason = validate_payload_uniqueness(parsed, used_titles_set, used_themes_set)
            if is_valid:
                print("Triptyque validé : zéro doublon détecté.")
                data = parsed
                break
            else:
                print(f"Génération rejetée ({reason}). Nouvelle tentative...")
        except Exception as e:
            print(f"Erreur JSON : {e}")

    if not data:
        data = parsed  # Fallback si persistance après les tentatives

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

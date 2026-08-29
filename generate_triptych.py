import os
import re
import glob
import json
import difflib
import urllib.parse
import urllib.request
from datetime import datetime
import google.generativeai as genai

# MARK: - Configuration API

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY manquante dans les secrets GitHub.")

genai.configure(api_key=GEMINI_API_KEY)

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# MARK: - Normalisation & Filtrage Textuel

STOP_WORDS = {
    "the", "a", "an", "and", "of", "in", "on", "at", "to", "for", "with", "by",
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "et", "en", "au", "aux", "par", "sur"
}

def clean_search_title(title: str) -> str:
    """Nettoie parenthèses, crochets et mentions superflues."""
    t = re.sub(r"\(.*?\)", "", str(title))
    t = re.sub(r"\[.*?\]", "", t)
    if ":" in t:
        t = t.split(":")[0]
    return t.strip()

def normalize_text(text: str) -> str:
    """Minuscules et suppression des caractères spéciaux."""
    t = str(text).lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return " ".join(t.split())

def extract_significant_words(text: str) -> set:
    """Extrait les mots clés en éliminant les mots vides."""
    words = normalize_text(text).split()
    return {w for w in words if w not in STOP_WORDS and len(w) > 1}

def safe_url_encode(text: str) -> str:
    return urllib.parse.quote_plus(str(text).strip())

# MARK: - Déduplication & Historique Renforcé

def load_history_exclusions():
    used_themes = set()
    used_titles = set()
    
    files_to_check = glob.glob("archive/*.json")
    if os.path.exists("today.json"):
        files_to_check.append("today.json")

    for filepath in files_to_check:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                past_data = json.load(f)
                for tier in ["accessible", "intermediate", "expert"]:
                    if tier in past_data and isinstance(past_data[tier], dict):
                        theme = past_data[tier].get("themeTitle")
                        if theme:
                            used_themes.add(theme.strip())
                        for item in past_data[tier].get("items", []):
                            title = item.get("title")
                            creator = item.get("creator")
                            if title and creator:
                                used_titles.add(f"{title.strip()} par {creator.strip()}")
                            elif title:
                                used_titles.add(title.strip())
        except Exception:
            pass

    return list(used_themes), list(used_titles)

# MARK: - Enrichisseurs Médias

def fetch_book_metadata(title: str, author: str):
    image_url = None
    page_count = None
    clean_t = clean_search_title(title)

    # 1. Apple Books
    try:
        q_apple = safe_url_encode(f"{clean_t} {author}")
        apple_url = f"https://itunes.apple.com/search?term={q_apple}&entity=ebook&country=fr&limit=3"
        req = urllib.request.Request(apple_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            for item in data.get("results", []):
                raw_art = item.get("artworkUrl100", "")
                if raw_art:
                    image_url = raw_art.replace("100x100bb", "800x800bb")
                    break
    except Exception:
        pass

    # 2. Google Books
    if not image_url:
        queries = [f"intitle:{clean_t} inauthor:{author}", f"{clean_t} {author}", clean_t]
        for q in queries:
            encoded_q = safe_url_encode(q)
            url = f"https://www.googleapis.com/books/v1/volumes?q={encoded_q}&maxResults=3&printType=books"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    for item in data.get("items", []):
                        info = item.get("volumeInfo", {})
                        images = info.get("imageLinks", {})
                        img = images.get("extraLarge") or images.get("large") or images.get("medium") or images.get("thumbnail") or images.get("smallThumbnail")
                        if img:
                            image_url = img.replace("http://", "https://").replace("&edge=curl", "")
                        if not page_count and info.get("pageCount"):
                            page_count = info.get("pageCount")
                        if image_url:
                            break
            except Exception:
                pass
            if image_url:
                break

    # 3. OpenLibrary
    if not image_url:
        try:
            q_ol = safe_url_encode(f"{clean_t} {author}")
            ol_url = f"https://openlibrary.org/search.json?q={q_ol}&limit=1"
            req = urllib.request.Request(ol_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=5) as response:
                ol_data = json.loads(response.read().decode())
                docs = ol_data.get("docs", [])
                if docs and "cover_i" in docs[0]:
                    cover_id = docs[0]["cover_i"]
                    image_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
        except Exception:
            pass

    return image_url, page_count

def fetch_film_metadata(title: str, director: str):
    clean_t = clean_search_title(title)
    target_words = extract_significant_words(clean_t)
    queries = [clean_t, f"{clean_t} {director}"]

    for country in ["fr", "us"]:
        for q in queries:
            encoded_q = safe_url_encode(q)
            url = f"https://itunes.apple.com/search?term={encoded_q}&entity=movie&limit=8&country={country}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    for item in data.get("results", []):
                        candidate_name = item.get("trackName", "")
                        candidate_words = extract_significant_words(candidate_name)
                        
                        if target_words and target_words.issubset(candidate_words):
                            raw_art = item.get("artworkUrl100", "")
                            if raw_art:
                                return raw_art.replace("100x100bb", "1000x1000bb")
            except Exception:
                pass

    return None

def fetch_album_deezer_fallback(album_title: str, artist: str):
    """Secours Deezer API pour garantir l'affiche HD et les extraits audio."""
    clean_t = clean_search_title(album_title)
    clean_a = clean_search_title(artist)
    q = safe_url_encode(f"{clean_t} {clean_a}")
    
    url = f"https://api.deezer.com/search/album?q={q}&limit=5"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("data", [])
            if not results:
                return None, [], None
            
            first = results[0]
            image_url = first.get("cover_xl") or first.get("cover_big")
            album_id = first.get("id")
            direct_url = first.get("link")
            tracks = []

            if album_id:
                track_url = f"https://api.deezer.com/album/{album_id}/tracks"
                req_t = urllib.request.Request(track_url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req_t, timeout=5) as resp_t:
                    t_data = json.loads(resp_t.read().decode())
                    for idx, tr in enumerate(t_data.get("data", []), start=1):
                        dur = tr.get("duration", 0)
                        minutes = dur // 60
                        seconds = dur % 60
                        tracks.append({
                            "trackNumber": idx,
                            "title": tr.get("title", f"Piste {idx}"),
                            "duration": f"{minutes}:{seconds:02d}",
                            "previewURL": tr.get("preview")
                        })

            return image_url, tracks, direct_url
    except Exception:
        return None, [], None

def fetch_album_metadata(album_title: str, artist: str):
    """Recherche iTunes avec tolérance titres courts + fallback Deezer automatique."""
    clean_t = clean_search_title(album_title)
    clean_a = clean_search_title(artist)

    target_title_words = extract_significant_words(clean_t)
    target_artist_words = extract_significant_words(clean_a)

    queries = [
        f"{clean_t} {clean_a}",
        f"{clean_a} {clean_t}",
        clean_t
    ]

    best_match = None
    best_score = 0.0

    for country in ["fr", "us", "gb"]:
        if best_score >= 0.80:
            break
        for q in queries:
            encoded_q = safe_url_encode(q)
            url = f"https://itunes.apple.com/search?term={encoded_q}&entity=album&media=music&limit=20&country={country}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=6) as response:
                    data = json.loads(response.read().decode())
                    results = data.get("results", [])

                    for item in results:
                        cand_title = item.get("collectionName", "")
                        cand_artist = item.get("artistName", "")

                        cand_title_words = extract_significant_words(cand_title)
                        cand_artist_words = extract_significant_words(cand_artist)

                        # Validation obligatoire de l'artiste
                        artist_overlap = target_artist_words.intersection(cand_artist_words)
                        if not artist_overlap and target_artist_words:
                            continue

                        # Validation du titre
                        if not target_title_words:
                            title_word_ratio = 1.0
                        else:
                            title_overlap = target_title_words.intersection(cand_title_words)
                            title_word_ratio = len(title_overlap) / len(target_title_words)

                        norm_target = normalize_text(clean_t)
                        norm_cand = normalize_text(cand_title.split("(")[0].split("-")[0])
                        text_ratio = difflib.SequenceMatcher(None, norm_target, norm_cand).ratio()

                        score = (title_word_ratio * 0.6) + (text_ratio * 0.4)
                        if target_title_words.issubset(cand_title_words):
                            score += 0.35

                        if score > best_score:
                            best_score = score
                            best_match = item

            except Exception:
                pass
            if best_score >= 0.80:
                break

    # Si iTunes a trouvé le bon album
    if best_match and best_score >= 0.65:
        raw_art = best_match.get("artworkUrl100", "")
        image_url = raw_art.replace("100x100bb", "600x600bb") if raw_art else None
        collection_id = best_match.get("collectionId")
        direct_url = best_match.get("collectionViewUrl")
        tracks = []

        if collection_id:
            for country in ["fr", "us"]:
                lookup_url = f"https://itunes.apple.com/lookup?id={collection_id}&entity=song&country={country}"
                try:
                    req = urllib.request.Request(lookup_url, headers={"User-Agent": USER_AGENT})
                    with urllib.request.urlopen(req, timeout=6) as response:
                        song_data = json.loads(response.read().decode())
                        for r in song_data.get("results", []):
                            if r.get("wrapperType") == "track":
                                millis = r.get("trackTimeMillis", 0)
                                seconds = (millis // 1000) % 60
                                minutes = (millis // (1000 * 60))
                                tracks.append({
                                    "trackNumber": r.get("trackNumber", len(tracks) + 1),
                                    "title": r.get("trackName", "Piste"),
                                    "duration": f"{minutes}:{seconds:02d}",
                                    "previewURL": r.get("previewUrl")
                                })
                    if tracks:
                        break
                except Exception:
                    pass

        if image_url:
            return image_url, tracks, direct_url

    # Fallback Deezer si iTunes a échoué
    print(f"🔄 Relais Deezer activé pour '{album_title}' de '{artist}'...")
    return fetch_album_deezer_fallback(album_title, artist)

def build_safe_platform_links(item_type: str, title: str, creator: str, direct_apple_url: str = None):
    clean_t = clean_search_title(title)
    encoded_search = safe_url_encode(f"{clean_t} {creator}".strip())
    encoded_title = safe_url_encode(clean_t.strip())
    
    t = str(item_type).upper()
    if t == "FILM":
        return [
            {"name": "JustWatch", "category": "Disponibilité légale & Streaming", "urlString": f"https://www.justwatch.com/fr/recherche?q={encoded_search}", "iconName": "play.tv.fill"},
            {"name": "Apple TV", "category": "Location & Achat VOD", "urlString": f"https://tv.apple.com/fr/search?term={encoded_title}", "iconName": "apple.logo"}
        ]
    elif t == "LIVRE":
        return [
            {"name": "Les Libraires", "category": "Librairies indépendantes", "urlString": f"https://www.leslibraires.fr/recherche/?q={encoded_search}", "iconName": "book.fill"},
            {"name": "Fnac", "category": "Achat livre & Ebook", "urlString": f"https://www.fnac.com/SearchResult/ResultList.aspx?SCat=0&Search={encoded_search}", "iconName": "bag.fill"}
        ]
    else:
        apple_link = direct_apple_url if direct_apple_url else f"https://music.apple.com/fr/search?term={encoded_search}"
        return [
            {"name": "Apple Music", "category": "Écoute intégrale & Lossless", "urlString": apple_link, "iconName": "apple.logo"},
            {"name": "Deezer", "category": "Streaming audio & HiFi", "urlString": f"https://www.deezer.com/search/{encoded_search}", "iconName": "music.note"}
        ]

# MARK: - Sanitizer / Structure Garantie (9 Œuvres)

def sanitize_and_fill_defaults(data: dict) -> dict:
    sanitized = {}
    tiers = ["accessible", "intermediate", "expert"]
    default_theme = {"themeTitle": "Édition du jour", "themeSubtitle": "Trois œuvres reliées par un fil invisible", "items": []}

    total_items = 0
    for tier in tiers:
        t_data = data.get(tier, default_theme)
        if not isinstance(t_data, dict):
            t_data = default_theme

        sanitized[tier] = {
            "themeTitle": str(t_data.get("themeTitle") or "Édition du jour"),
            "themeSubtitle": str(t_data.get("themeSubtitle") or "Trois œuvres, un fil invisible."),
            "items": []
        }

        for item in t_data.get("items", []):
            if not isinstance(item, dict):
                continue
            
            s_item = {
                "type": str(item.get("type") or "LIVRE").upper(),
                "title": str(item.get("title") or "Titre"),
                "creator": str(item.get("creator") or "Auteur"),
                "year": str(item.get("year") or "2000"),
                "origin": str(item.get("origin") or "France"),
                "genre": str(item.get("genre") or "Culture"),
                "accessibility": str(item.get("accessibility") or (
                    "Pop Culture" if tier == "accessible" else ("Curieux" if tier == "intermediate" else "Initié")
                )),
                "formatMetric": str(item.get("formatMetric") or ""),
                "quote": str(item.get("quote") or ""),
                "anecdote": str(item.get("anecdote") or ""),
                "tags": item.get("tags") if isinstance(item.get("tags"), list) else ["Classique"],
                "ratings": [],
                "aiSummary": str(item.get("aiSummary") or ""),
                "thematicAnalysis": str(item.get("thematicAnalysis") or ""),
                "imageURL": item.get("imageURL") or None,
                "platformLinks": item.get("platformLinks") or [],
                "tracks": item.get("tracks") or []
            }

            for r in item.get("ratings", []):
                if isinstance(r, dict):
                    s_item["ratings"].append({
                        "source": str(r.get("source") or "Presse"),
                        "score": str(r.get("score") or "5/5"),
                        "iconName": str(r.get("iconName") or "star.fill"),
                        "excerpt": str(r.get("excerpt") or "")
                    })

            sanitized[tier]["items"].append(s_item)
            total_items += 1

    print(f"📊 Nombre total d'œuvres structurées : {total_items}/9")
    return sanitized

# MARK: - Prompt Éditorial Sans Noms Fixes

SYSTEM_PROMPT_TEMPLATE = """Tu es le curateur en chef de TRIVIUM, une application d'élite de recommandation culturelle quotidienne.

LANGUE STRICTE : Tout le contenu généré DOIT ÊTRE EN FRANÇAIS IMPECCABLE.

RÈGLE DU VOLUME :
GÉNÈRE EXACTEMENT 9 ŒUVRES AU TOTAL (3 profils x 3 œuvres) :
1. "accessible" (Pop Culture) : 1 LIVRE, 1 FILM, 1 ALBUM.
2. "intermediate" (Curieux) : 1 LIVRE, 1 FILM, 1 ALBUM.
3. "expert" (Initié) : 1 LIVRE, 1 FILM, 1 ALBUM.

CALIBRATION DES PROFILS :
1. "accessible" : Grands chefs-d'œuvre célèbres et accessibles au grand public.
2. "intermediate" : Pépites indé acclamées, cinéma d'auteur marquant, albums cultes alternatifs.
3. "expert" : Avant-garde, raretés artistiques et œuvres d'essai exigeantes.

RÈGLE CRITIQUE :
Fournis 3 critiques de presse réelles par œuvre ("ratings") avec leurs vrais barèmes (Télérama sur 5, Pitchfork sur 10, Rotten Tomatoes en %, etc.).
Indique l'année de création originale pour "year".

Format JSON STRICT à respecter :
{
  "accessible": {
    "themeTitle": "Titre du thème Pop Culture",
    "themeSubtitle": "Sous-titre poétique reliant les 3 œuvres",
    "items": [
      {
        "type": "LIVRE",
        "title": "Titre exact du livre",
        "creator": "Nom de l'auteur",
        "year": "1960",
        "origin": "Pays",
        "genre": "Genre littéraire",
        "accessibility": "Pop Culture",
        "formatMetric": "350 pages",
        "quote": "Citation marquante",
        "anecdote": "Une anecdote de création",
        "tags": ["Classique"],
        "ratings": [
          {"source": "Le Figaro Littéraire", "score": "5/5", "iconName": "star.fill", "excerpt": "Critique élogieuse."},
          {"source": "Télérama", "score": "5/5", "iconName": "star.fill", "excerpt": "Analyse critique."},
          {"source": "The Times", "score": "5/5", "iconName": "star.fill", "excerpt": "Éloge international."}
        ],
        "aiSummary": "Résumé captivant en 2 phrases.",
        "thematicAnalysis": "Analyse du lien avec le thème."
      },
      {
        "type": "FILM",
        "title": "Titre exact du film",
        "creator": "Nom du réalisateur",
        "year": "1980",
        "origin": "Pays",
        "genre": "Genre cinématographique",
        "accessibility": "Pop Culture",
        "formatMetric": "2h 10m",
        "quote": "Réplique culte",
        "anecdote": "Anecdote de tournage",
        "tags": ["Culte"],
        "ratings": [
          {"source": "Cahiers du Cinéma", "score": "5/5", "iconName": "star.fill", "excerpt": "Mise en scène magistrale."},
          {"source": "Télérama", "score": "5/5", "iconName": "star.fill", "excerpt": "Un film essentiel."},
          {"source": "Rotten Tomatoes", "score": "95%", "iconName": "star.fill", "excerpt": "Plébiscite de la critique."}
        ],
        "aiSummary": "Résumé du film.",
        "thematicAnalysis": "Lien avec le thème."
      },
      {
        "type": "ALBUM",
        "title": "Titre exact de l'album",
        "creator": "Nom de l'artiste ou groupe",
        "year": "1995",
        "origin": "Pays",
        "genre": "Genre musical",
        "accessibility": "Pop Culture",
        "formatMetric": "45 minutes, 11 titres",
        "quote": "Parole ou citation clé",
        "anecdote": "Anecdote de studio",
        "tags": ["Rock"],
        "ratings": [
          {"source": "Rolling Stone", "score": "5/5", "iconName": "star.fill", "excerpt": "Un disque majeur."},
          {"source": "Pitchfork", "score": "9.5/10", "iconName": "star.fill", "excerpt": "Production impeccable."},
          {"source": "Les Inrockuptibles", "score": "5/5", "iconName": "star.fill", "excerpt": "Un incontournable."}
        ],
        "aiSummary": "Résumé de l'album.",
        "thematicAnalysis": "Lien avec le thème."
      }
    ]
  },
  "intermediate": {
    "themeTitle": "Titre du thème Curieux",
    "themeSubtitle": "Sous-titre poétique",
    "items": [
      { "type": "LIVRE", "title": "Titre", "creator": "Auteur", "year": "2005", "origin": "Pays", "genre": "Genre", "accessibility": "Curieux", "formatMetric": "280 pages", "quote": "Citation", "anecdote": "Anecdote", "tags": ["Roman"], "ratings": [{"source": "Le Monde des Livres", "score": "4.5/5", "iconName": "star.fill", "excerpt": "Brillant."},{"source": "Télérama", "score": "4/5", "iconName": "star.fill", "excerpt": "Poignant."},{"source": "Les Inrocks", "score": "4/5", "iconName": "star.fill", "excerpt": "Audacieux."}], "aiSummary": "Résumé.", "thematicAnalysis": "Analyse." },
      { "type": "FILM", "title": "Titre", "creator": "Réalisateur", "year": "2010", "origin": "Pays", "genre": "Genre", "accessibility": "Curieux", "formatMetric": "1h 50m", "quote": "Citation", "anecdote": "Anecdote", "tags": ["Drame"], "ratings": [{"source": "Cahiers du Cinéma", "score": "5/5", "iconName": "star.fill", "excerpt": "Sublime."},{"source": "Positif", "score": "4.5/5", "iconName": "star.fill", "excerpt": "Magistral."},{"source": "Télérama", "score": "4/5", "iconName": "star.fill", "excerpt": "Envoutant."}], "aiSummary": "Résumé.", "thematicAnalysis": "Analyse." },
      { "type": "ALBUM", "title": "Titre", "creator": "Artiste", "year": "2015", "origin": "Pays", "genre": "Genre", "accessibility": "Curieux", "formatMetric": "48 minutes", "quote": "Citation", "anecdote": "Anecdote", "tags": ["Indie"], "ratings": [{"source": "Pitchfork", "score": "8.5/10", "iconName": "star.fill", "excerpt": "Captivant."},{"source": "Les Inrocks", "score": "4.5/5", "iconName": "star.fill", "excerpt": "Incontournable."},{"source": "The Guardian", "score": "4/5", "iconName": "star.fill", "excerpt": "Remarquable."}], "aiSummary": "Résumé.", "thematicAnalysis": "Analyse." }
    ]
  },
  "expert": {
    "themeTitle": "Titre du thème Initié",
    "themeSubtitle": "Sous-titre poétique",
    "items": [
      { "type": "LIVRE", "title": "Titre", "creator": "Auteur", "year": "1975", "origin": "Pays", "genre": "Genre", "accessibility": "Initié", "formatMetric": "210 pages", "quote": "Citation", "anecdote": "Anecdote", "tags": ["Essai"], "ratings": [{"source": "Le Monde des Livres", "score": "4.5/5", "iconName": "star.fill", "excerpt": "Exigeant."},{"source": "Libération", "score": "4.5/5", "iconName": "star.fill", "excerpt": "Radical."},{"source": "Les Inrocks", "score": "4/5", "iconName": "star.fill", "excerpt": "Novateur."}], "aiSummary": "Résumé.", "thematicAnalysis": "Analyse." },
      { "type": "FILM", "title": "Titre", "creator": "Réalisateur", "year": "1985", "origin": "Pays", "genre": "Genre", "accessibility": "Initié", "formatMetric": "2h 20m", "quote": "Citation", "anecdote": "Anecdote", "tags": ["Art & Essai"], "ratings": [{"source": "Cahiers du Cinéma", "score": "5/5", "iconName": "star.fill", "excerpt": "Une claque visuelle."},{"source": "Télérama", "score": "4.5/5", "iconName": "star.fill", "excerpt": "Inoubliable."},{"source": "Positif", "score": "4.5/5", "iconName": "star.fill", "excerpt": "Fascinant."}], "aiSummary": "Résumé.", "thematicAnalysis": "Analyse." },
      { "type": "ALBUM", "title": "Titre", "creator": "Artiste", "year": "1998", "origin": "Pays", "genre": "Genre", "accessibility": "Initié", "formatMetric": "52 minutes", "quote": "Citation", "anecdote": "Anecdote", "tags": ["Expérimental"], "ratings": [{"source": "The Wire", "score": "5/5", "iconName": "star.fill", "excerpt": "Une expérimentation sonore totale."},{"source": "Pitchfork", "score": "8.8/10", "iconName": "star.fill", "excerpt": "Hypnotique et brut."},{"source": "Les Inrocks", "score": "4.5/5", "iconName": "star.fill", "excerpt": "Une intensité rare."}], "aiSummary": "Résumé.", "thematicAnalysis": "Analyse." }
    ]
  }
}
"""

# MARK: - Exécution Principale

def generate_daily_edition():
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"🚀 Génération de l'édition du {today_str}...")

    os.makedirs("archive", exist_ok=True)
    past_themes, past_titles = load_history_exclusions()

    prompt = SYSTEM_PROMPT_TEMPLATE
    if past_themes:
        prompt += f"\n\nTHÈMES STRICTEMENT BANNIS (NE PAS RÉUTILISER) :\n- " + "\n- ".join(past_themes[-60:])
    if past_titles:
        prompt += f"\n\nŒUVRES STRICTEMENT BANNIES (NE PAS RÉUTILISER) :\n- " + "\n- ".join(past_titles[-250:])

    prompt += "\n\nRÈGLE DE RENOUVELLEMENT ABSOLUE : Tu DOIS proposer des œuvres, artistes et auteurs TOTALEMENT DIFFÉRENTS de la liste ci-dessus."

    model = genai.GenerativeModel(
        model_name="gemini-3.6-flash",
        generation_config={"response_mime_type": "application/json", "temperature": 0.85},
        system_instruction=prompt
    )

    response = model.generate_content("Génère l'édition complète avec 3 œuvres uniques pour accessible, 3 pour intermediate et 3 pour expert.")
    raw_data = json.loads(response.text)

    data = sanitize_and_fill_defaults(raw_data)

    for tier in ["accessible", "intermediate", "expert"]:
        for item in data[tier]["items"]:
            item_type = item["type"]
            title = item["title"]
            creator = item["creator"]

            if item_type == "LIVRE":
                item["platformLinks"] = build_safe_platform_links(item_type, title, creator)
                img, pages = fetch_book_metadata(title, creator)
                if img: item["imageURL"] = img
                if pages and not item.get("formatMetric"): item["formatMetric"] = f"{pages} pages"

            elif item_type == "FILM":
                item["platformLinks"] = build_safe_platform_links(item_type, title, creator)
                img = fetch_film_metadata(title, creator)
                if img: item["imageURL"] = img

            elif item_type == "ALBUM":
                img, tracks, direct_url = fetch_album_metadata(title, creator)
                item["platformLinks"] = build_safe_platform_links(item_type, title, creator, direct_apple_url=direct_url)
                if img: item["imageURL"] = img
                if tracks: item["tracks"] = tracks

    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    archive_path = f"archive/{today_str}.json"
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Édition validée et archivée avec succès dans {archive_path}.")

if __name__ == "__main__":
    generate_daily_edition()

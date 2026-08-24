import os
import re
import glob
import json
import urllib.parse
import urllib.request
from datetime import datetime
import google.generativeai as genai

# MARK: - Configuration API

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY manquante dans les secrets GitHub.")

genai.configure(api_key=GEMINI_API_KEY)

# MARK: - Utilitaires de Normalisation & Recherche

def clean_search_title(title: str) -> str:
    """Supprime les parenthèses, crochets et sous-titres superflus."""
    t = re.sub(r"\(.*?\)", "", str(title))
    t = re.sub(r"\[.*?\]", "", t)
    if ":" in t:
        t = t.split(":")[0]
    return t.strip()

def normalize_text(text: str) -> str:
    """Minuscules et suppression des caractères spéciaux pour comparaison."""
    t = text.lower()
    t = re.sub(r"[^\w\s]", "", t)
    return " ".join(t.split())

def safe_url_encode(text: str) -> str:
    return urllib.parse.quote_plus(str(text).strip())

# MARK: - Gestion de l'Historique & Déduplication

def load_history_exclusions():
    used_themes = set()
    used_titles = set()
    
    archive_dir = "archive"
    if os.path.exists(archive_dir):
        for filepath in glob.glob(f"{archive_dir}/*.json"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    past_data = json.load(f)
                    for tier in ["accessible", "intermediate", "expert"]:
                        if tier in past_data:
                            theme = past_data[tier].get("themeTitle")
                            if theme:
                                used_themes.add(theme.strip())
                            for item in past_data[tier].get("items", []):
                                title = item.get("title")
                                creator = item.get("creator")
                                if title and creator:
                                    used_titles.add(f"{title.strip()} ({creator.strip()})")
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
        req = urllib.request.Request(apple_url, headers={"User-Agent": "TriviumApp/2.1"})
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
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
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
            req = urllib.request.Request(ol_url, headers={"User-Agent": "TriviumApp/2.1"})
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
    norm_target = normalize_text(clean_t)
    queries = [clean_t, f"{clean_t} {director}"]

    for country in ["fr", "us"]:
        for q in queries:
            encoded_q = safe_url_encode(q)
            url = f"https://itunes.apple.com/search?term={encoded_q}&entity=movie&limit=5&country={country}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "TriviumApp/2.1"})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    for item in data.get("results", []):
                        name = normalize_text(item.get("trackName", ""))
                        if norm_target in name or name in norm_target:
                            raw_art = item.get("artworkUrl100", "")
                            if raw_art:
                                return raw_art.replace("100x100bb", "1000x1000bb")
            except Exception:
                pass

    return None

def fetch_album_metadata(album_title: str, artist: str):
    clean_t = clean_search_title(album_title)
    clean_a = clean_search_title(artist)
    norm_title = normalize_text(clean_t)
    norm_artist = normalize_text(clean_a)

    queries = [f"{clean_t} {clean_a}", clean_t]
    best_match = None

    for country in ["fr", "us", "gb"]:
        if best_match:
            break
        for q in queries:
            encoded_q = safe_url_encode(q)
            url = f"https://itunes.apple.com/search?term={encoded_q}&entity=album&limit=10&country={country}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "TriviumApp/2.1"})
                with urllib.request.urlopen(req, timeout=6) as response:
                    data = json.loads(response.read().decode())
                    results = data.get("results", [])
                    
                    for item in results:
                        col_name = normalize_text(item.get("collectionName", ""))
                        if norm_title in col_name or col_name in norm_title:
                            best_match = item
                            break
                    
                    if not best_match:
                        title_words = [w for w in norm_title.split() if len(w) > 2]
                        for item in results:
                            col_name = normalize_text(item.get("collectionName", ""))
                            if title_words and all(w in col_name for w in title_words):
                                best_match = item
                                break

                    if not best_match:
                        for item in results:
                            art_name = normalize_text(item.get("artistName", ""))
                            col_name = normalize_text(item.get("collectionName", ""))
                            if (norm_artist in art_name or art_name in norm_artist) and any(w in col_name for w in norm_title.split() if len(w) > 3):
                                best_match = item
                                break
            except Exception:
                pass
            if best_match:
                break

    if not best_match:
        return None, [], None

    raw_art = best_match.get("artworkUrl100", "")
    image_url = raw_art.replace("100x100bb", "600x600bb") if raw_art else None
    collection_id = best_match.get("collectionId")
    direct_url = best_match.get("collectionViewUrl")
    tracks = []

    if collection_id:
        for country in ["fr", "us"]:
            lookup_url = f"https://itunes.apple.com/lookup?id={collection_id}&entity=song&country={country}"
            try:
                req = urllib.request.Request(lookup_url, headers={"User-Agent": "TriviumApp/2.1"})
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

    return image_url, tracks, direct_url

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

def sanitize_and_fill_defaults(data: dict) -> dict:
    sanitized = {}
    tiers = ["accessible", "intermediate", "expert"]
    default_theme = {"themeTitle": "Édition du jour", "themeSubtitle": "Trois œuvres reliées par un fil invisible", "items": []}

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
                "accessibility": str(item.get("accessibility") or "Pop Culture"),
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

    return sanitized

def build_system_prompt(excluded_themes: list, excluded_titles: list) -> str:
    prompt = """Tu es le curateur en chef de TRIVIUM, une application d'élite de recommandation culturelle quotidienne.

LANGUE STRICTE : Tout le contenu généré DOIT ÊTRE EN FRANÇAIS IMPECCABLE.

CALIBRATION DES 3 PROFILS CULTURELS :
1. "accessible" (Pop Culture) : Monuments culturels et chefs-d'œuvre universels (musique : Pink Floyd, Daft Punk, Queen, The Beatles ; cinéma : Miyazaki, Star Wars, Le Parrain ; littérature : Alice au pays des merveilles, 1984, Stephen King).
2. "intermediate" (Curieux) : Pépites indé, cinéma d'auteur marquant, albums cultes alternatifs.
3. "expert" (Initié) : Avant-garde, expérimentations pointues (ex. Xiu Xiu, Faust, cinéma underground), littérature exigeante.

Pour le champ "year", renseigne TOUJOURS L'ANNÉE DE CRÉATION ORIGINALE.
Pour chaque œuvre, fournis EXACTEMENT 3 critiques comparées ("ratings") avec les barèmes authentiques de chaque média (Pitchfork sur 10, Télérama sur 5, Rotten Tomatoes en %, etc.).

RÈGLE D'UNICITÉ :
Interdiction de réutiliser des thèmes ou œuvres passés.
"""
    if excluded_themes:
        prompt += f"\nTHÈMES BANNIS :\n- " + "\n- ".join(excluded_themes[-50:]) + "\n"
    if excluded_titles:
        prompt += f"\nŒUVRES BANNIES :\n- " + "\n- ".join(excluded_titles[-150:]) + "\n"

    prompt += """
Format JSON attendu :
{
  "accessible": {
    "themeTitle": "Titre du thème",
    "themeSubtitle": "Sous-titre poétique",
    "items": [
      {
        "type": "LIVRE",
        "title": "Titre exact",
        "creator": "Nom de l'auteur",
        "year": "1865",
        "origin": "Royaume-Uni",
        "genre": "Littérature fantastique",
        "accessibility": "Pop Culture",
        "formatMetric": "192 pages",
        "quote": "Citation clé",
        "anecdote": "Une anecdote captivante",
        "tags": ["Classique", "Merveilleux"],
        "ratings": [
          {"source": "Le Figaro Littéraire", "score": "5/5", "iconName": "star.fill", "excerpt": "Un chef-d'œuvre intemporel."},
          {"source": "Télérama", "score": "5/5", "iconName": "star.fill", "excerpt": "Une folie littéraire sublime."},
          {"source": "The Guardian", "score": "5/5", "iconName": "star.fill", "excerpt": "Une œuvre fondatrice."}
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
    return prompt

# MARK: - Fonction Principale (gemini-3.6-flash)

def generate_daily_edition():
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"🚀 Génération de l'édition du {today_str} avec gemini-3.6-flash...")

    os.makedirs("archive", exist_ok=True)
    past_themes, past_titles = load_history_exclusions()

    system_prompt = build_system_prompt(past_themes, past_titles)

    model = genai.GenerativeModel(
        model_name="gemini-3.6-flash",
        generation_config={"response_mime_type": "application/json", "temperature": 0.75},
        system_instruction=system_prompt
    )

    response = model.generate_content("Génère un triptyque 100% inédit et calibré en français.")
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

    print(f"✅ Édition du jour générée et archivée dans {archive_path}.")

if __name__ == "__main__":
    generate_daily_edition()

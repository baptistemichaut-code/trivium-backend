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

# MARK: - Nettoyeurs de Titres & Encodage d'URL

def clean_search_title(title: str) -> str:
    t = re.sub(r"\(.*?\)", "", title)
    t = re.sub(r"\[.*?\]", "", t)
    if ":" in t:
        t = t.split(":")[0]
    return t.strip()

def safe_url_encode(text: str) -> str:
    return urllib.parse.quote(text.strip(), safe="")

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

# MARK: - Enrichisseur Livres

def fetch_book_metadata(title: str, author: str):
    image_url = None
    page_count = None
    clean_t = clean_search_title(title)

    # 1. Apple Books
    try:
        q_apple = safe_url_encode(f"{clean_t} {author}")
        apple_url = f"https://itunes.apple.com/search?term={q_apple}&entity=ebook&country=fr&limit=1"
        req = urllib.request.Request(apple_url, headers={"User-Agent": "TriviumApp/2.1"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            if data.get("resultCount", 0) > 0:
                raw_art = data["results"][0].get("artworkUrl100", "")
                if raw_art:
                    image_url = raw_art.replace("100x100bb", "800x800bb")
    except Exception:
        pass

    # 2. Google Books
    if not image_url:
        queries = [
            f"intitle:{clean_t} inauthor:{author}",
            f"{clean_t} {author}",
            clean_t
        ]
        for q in queries:
            encoded_q = safe_url_encode(q)
            url = f"https://www.googleapis.com/books/v1/volumes?q={encoded_q}&maxResults=2&printType=books"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    for item in data.get("items", []):
                        info = item.get("volumeInfo", {})
                        images = info.get("imageLinks", {})
                        img = images.get("extraLarge") or images.get("large") or images.get("medium") or images.get("thumbnail") or images.get("smallThumbnail")
                        
                        if img:
                            secure_img = img.replace("http://", "https://")
                            if "&edge=curl" in secure_img:
                                secure_img = secure_img.replace("&edge=curl", "")
                            image_url = secure_img

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

# MARK: - Enrichisseur Films

def fetch_film_metadata(title: str, director: str):
    image_url = None
    clean_t = clean_search_title(title)
    queries = [clean_t, f"{clean_t} {director}"]

    for q in queries:
        encoded_q = safe_url_encode(q)
        for country in ["fr", "us"]:
            url = f"https://itunes.apple.com/search?term={encoded_q}&entity=movie&limit=1&country={country}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "TriviumApp/2.1"})
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json.loads(response.read().decode())
                    if data.get("resultCount", 0) > 0:
                        raw_art = data["results"][0].get("artworkUrl100", "")
                        if raw_art:
                            image_url = raw_art.replace("100x100bb", "1000x1000bb")
                            return image_url
            except Exception:
                pass

    return image_url

# MARK: - Enrichisseur Albums (Apple Music Direct URL, Jaquette & Pistes)

def fetch_album_metadata(album_title: str, artist: str):
    clean_t = clean_search_title(album_title)
    query = safe_url_encode(f"{clean_t} {artist}")
    url = f"https://itunes.apple.com/search?term={query}&entity=album&limit=1&country=fr"
    image_url, collection_id, tracks, direct_url = None, None, [], None

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TriviumApp/2.1"})
        with urllib.request.urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode())
            if data.get("resultCount", 0) > 0:
                item = data["results"][0]
                raw_art = item.get("artworkUrl100", "")
                if raw_art:
                    image_url = raw_art.replace("100x100bb", "600x600bb")
                collection_id = item.get("collectionId")
                direct_url = item.get("collectionViewUrl")
    except Exception:
        pass

    if collection_id:
        lookup_url = f"https://itunes.apple.com/lookup?id={collection_id}&entity=song&country=fr"
        try:
            req = urllib.request.Request(lookup_url, headers={"User-Agent": "TriviumApp/2.1"})
            with urllib.request.urlopen(req, timeout=8) as response:
                song_data = json.loads(response.read().decode())
                results = song_data.get("results", [])
                for r in results:
                    if r.get("wrapperType") == "track":
                        millis = r.get("trackTimeMillis", 0)
                        seconds = (millis // 1000) % 60
                        minutes = (millis // (1000 * 60))
                        tracks.append({
                            "trackNumber": r.get("trackNumber", len(tracks) + 1),
                            "title": r.get("trackName", "Piste inconnue"),
                            "duration": f"{minutes}:{seconds:02d}",
                            "previewURL": r.get("previewUrl")
                        })
        except Exception:
            pass

    return image_url, tracks, direct_url

# MARK: - Liens Plateformes Utiles (Apple Music Direct & Deezer)

def build_safe_platform_links(item_type: str, title: str, creator: str, direct_apple_url: str = None):
    clean_t = clean_search_title(title)
    search_term = f"{clean_t} {creator}".strip()
    encoded_search = safe_url_encode(search_term)
    encoded_title = safe_url_encode(clean_t.strip())
    
    t = item_type.upper()
    if t == "FILM":
        return [
            {
                "name": "JustWatch",
                "category": "Disponibilité légale & Streaming",
                "urlString": f"https://www.justwatch.com/fr/recherche?q={encoded_search}",
                "iconName": "play.tv.fill"
            },
            {
                "name": "Apple TV",
                "category": "Location & Achat VOD",
                "urlString": f"https://tv.apple.com/fr/search?term={encoded_title}",
                "iconName": "apple.logo"
            }
        ]
    elif t == "LIVRE":
        return [
            {
                "name": "Les Libraires",
                "category": "Librairies indépendantes",
                "urlString": f"https://www.leslibraires.fr/recherche/?q={encoded_search}",
                "iconName": "book.fill"
            },
            {
                "name": "Fnac",
                "category": "Achat livre & Ebook",
                "urlString": f"https://www.fnac.com/SearchResult/ResultList.aspx?SCat=0&Search={encoded_search}",
                "iconName": "bag.fill"
            }
        ]
    else:  # ALBUM
        apple_link = direct_apple_url if direct_apple_url else f"https://music.apple.com/fr/search?term={encoded_search}"
        return [
            {
                "name": "Apple Music",
                "category": "Écoute intégrale & Lossless",
                "urlString": apple_link,
                "iconName": "apple.logo"
            },
            {
                "name": "Deezer",
                "category": "Streaming audio & HiFi",
                "urlString": f"https://www.deezer.com/search/{encoded_search}",
                "iconName": "music.note"
            }
        ]

# MARK: - Prompt Éditorial avec Barèmes Critiques Authentiques

def build_system_prompt(excluded_themes: list, excluded_titles: list) -> str:
    prompt = """Tu es le curateur en chef de TRIVIUM, une application d'élite de recommandation culturelle quotidienne.

LANGUE STRICTE : L'intégralité du contenu généré DOIT ÊTRE EN FRANÇAIS IMPECCABLE (y compris les citations et extraits de presse traduits si la source originale est étrangère).

CALIBRATION TRÈS STRICTE DES 3 PROFILS CULTURELS :
1. "accessible" (Pop Culture) : UNIQUEMENT des monuments culturels et chefs-d'œuvre universellement connus (ex. musique : Queen, Daft Punk, The Beatles, Pink Floyd, Nirvana, Michael Jackson ; cinéma : Le Parrain, Interstellar, Alien, Le Seigneur des Anneaux ; littérature : Le Petit Prince, 1984, Stephen King).
2. "intermediate" (Curieux) : Pépites indé acclamées, cinéma d'auteur marquant, albums cultes alternatifs (Radiohead, Sufjan Stevens, Arcade Fire), littérature contemporaine forte.
3. "expert" (Initié) : Avant-garde, expérimentations pointues, cinéma d'art et essai exigeant, raretés littéraires et musicales.

Pour le champ "year", renseigne TOUJOURS L'ANNÉE DE CRÉATION ORIGINALE de l'œuvre.

RÈGLE D'EXACTITUDE CRITIQUE & DES BARÈMES DE PRESSE (STRICT) :
Pour CHAQUE œuvre, fournis EXACTEMENT 3 critiques comparées ("ratings") de 3 sources distinctes, en respectant impérativement leurs barèmes authentiques et leur réception historique réelle :

1. MUSIQUE :
   - Pitchfork : Note SUR 10 obligatoire (ex. "9.3/10", "10/10", "8.5/10").
   - Rolling Stone / AllMusic / The Guardian / NME : Note SUR 5 (ex. "5/5", "4.5/5", "4/5").
   - Les Inrockuptibles / Télérama : Note SUR 5 ou appréciation officielle.

2. CINÉMA :
   - Télérama / Première / Positif / Les Inrockuptibles / Le Monde : Note SUR 5 (ex. "5/5", "4/5", "3/5").
   - Cahiers du Cinéma : Respecter l'avis réel historique des Cahiers (s'ils ont détesté un blockbuster hollywoodien, attribuer une note réaliste comme "1/5" ou "2/5" plutôt qu'un 5/5 automatique).
   - Rotten Tomatoes : Score en POURCENTAGE (ex. "94%").
   - Metacritic : Score SUR 100 (ex. "88/100").

3. LITTÉRATURE :
   - Le Monde des Livres / Le Figaro / Libération / Télérama / The New York Times : Note SUR 5 représentative ou barème officiel ("5/5", "4.5/5").
   - Pour les œuvres classiques parues avant la création du média, l'extrait doit refléter l'analyse rétrospective ou patrimoniale réelle du journal.

RÈGLE D'UNICITÉ :
Interdiction formelle de réutiliser un thème ou une œuvre passés.
"""
    if excluded_themes:
        prompt += f"\nTHÈMES BANNIS :\n- " + "\n- ".join(excluded_themes[-50:]) + "\n"
    if excluded_titles:
        prompt += f"\nŒUVRES BANNIES :\n- " + "\n- ".join(excluded_titles[-150:]) + "\n"

    prompt += """
Format JSON attendu :
{
  "accessible": {
    "themeTitle": "Titre du thème inédit",
    "themeSubtitle": "Sous-titre poétique expliquant le fil invisible reliant les 3 œuvres",
    "items": [
      {
        "type": "LIVRE",
        "title": "Titre exact",
        "creator": "Nom de l'auteur",
        "year": "1949",
        "origin": "Royaume-Uni",
        "genre": "Roman / Dystopie",
        "accessibility": "Pop Culture",
        "formatMetric": "328 pages",
        "quote": "Citation clé marquante",
        "anecdote": "Anecdote surprenante sur la genèse de l'œuvre",
        "tags": ["Dystopie", "Totalitarisme", "Classique"],
        "ratings": [
          {"source": "Le Monde des Livres", "score": "5/5", "iconName": "star.fill", "excerpt": "Un chef-d'œuvre prophétique absolu du XXe siècle."},
          {"source": "The Times", "score": "5/5", "iconName": "star.fill", "excerpt": "Une mise en garde magistrale qui traverse les époques."},
          {"source": "Télérama", "score": "4.5/5", "iconName": "star.fill", "excerpt": "Une analyse glaçante de la manipulation du langage."}
        ],
        "aiSummary": "Résumé captivant en 2 phrases.",
        "thematicAnalysis": "Analyse du lien profond avec la thématique du triptyque."
      }
    ]
  },
  "intermediate": { ... },
  "expert": { ... }
}
"""
    return prompt

# MARK: - Fonction Principale

def generate_daily_edition():
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"🚀 Génération de l'édition du {today_str}...")

    os.makedirs("archive", exist_ok=True)
    past_themes, past_titles = load_history_exclusions()

    system_prompt = build_system_prompt(past_themes, past_titles)

    model = genai.GenerativeModel(
        model_name="gemini-3.6-flash",
        generation_config={"response_mime_type": "application/json", "temperature": 0.75},
        system_instruction=system_prompt
    )

    response = model.generate_content("Génère un triptyque 100% inédit et calibré en français avec les barèmes de notation authentiques pour chaque média.")
    data = json.loads(response.text)

    for tier in ["accessible", "intermediate", "expert"]:
        if tier not in data:
            continue
        for item in data[tier].get("items", []):
            item_type = item.get("type", "").upper()
            title = item.get("title", "")
            creator = item.get("creator", "")

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

    print(f"✅ Édition enregistrée avec barèmes stricts et archivée dans {archive_path}.")

if __name__ == "__main__":
    generate_daily_edition()

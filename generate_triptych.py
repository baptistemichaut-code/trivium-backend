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

# MARK: - Nettoyeurs de Titres & Encodage d'URL Sécurisé

def clean_search_title(title: str) -> str:
    """Supprime les parenthèses, crochets et sous-titres superflus."""
    t = re.sub(r"\(.*?\)", "", title)
    t = re.sub(r"\[.*?\]", "", t)
    if ":" in t:
        t = t.split(":")[0]
    return t.strip()

def safe_url_encode(text: str) -> str:
    """Encode strictement tous les caractères spéciaux (y compris les slashes) pour éviter les 404."""
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

# MARK: - Enrichisseur Livres Multi-Sources

def fetch_book_metadata(title: str, author: str):
    image_url = None
    page_count = None
    published_year = None

    clean_t = clean_search_title(title)

    # 1. Apple Books / iTunes Ebook
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
                pub = data["results"][0].get("releaseDate", "")
                if len(pub) >= 4:
                    published_year = pub[:4]
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
                        if not published_year and len(info.get("publishedDate", "")) >= 4:
                            published_year = info.get("publishedDate", "")[:4]

                        if image_url:
                            break
            except Exception:
                pass
            if image_url:
                break

    # 3. OpenLibrary Covers
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
                if docs and not published_year and "first_publish_year" in docs[0]:
                    published_year = str(docs[0]["first_publish_year"])
        except Exception:
            pass

    return image_url, page_count, published_year

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

# MARK: - Liens Plateformes Sécurisés

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
                "name": "Spotify",
                "category": "Streaming audio",
                "urlString": f"https://open.spotify.com/search/{encoded_search}",
                "iconName": "waveform"
            },
            {
                "name": "Deezer",
                "category": "Streaming audio & HiFi",
                "urlString": f"https://www.deezer.com/search/{encoded_search}",
                "iconName": "music.note"
            }
        ]

# MARK: - Prompt Éditorial

def build_system_prompt(excluded_themes: list, excluded_titles: list) -> str:
    prompt = """Tu es le curateur en chef de TRIVIUM, une application d'élite de recommandation culturelle quotidienne.

Ta mission est de concevoir l'édition du jour avec UNE THÉMATIQUE COMMUNE FORTE reliant 3 profils :
1. "accessible" (Pop Culture)
2. "intermediate" (Curieux)
3. "expert" (Initié)

Chaque profil doit contenir EXACTEMENT : 1 LIVRE, 1 FILM, 1 ALBUM réels et existants.

RÈGLE D'UNICITÉ ET D'ORIGINALITÉ ABSOLUE :
Trivium renouvelle continuellement sa bibliothèque. Tu as L'INTERDICTION FORMELLE de réutiliser un thème ou une œuvre déjà parus dans les éditions précédentes.
"""
    if excluded_themes:
        prompt += f"\nTHÈMES DÉJÀ TRAITÉS À BANNIR :\n- " + "\n- ".join(excluded_themes[-50:]) + "\n"
    if excluded_titles:
        prompt += f"\nŒUVRES DÉJÀ RECOMMANDÉES À BANNIR :\n- " + "\n- ".join(excluded_titles[-150:]) + "\n"

    prompt += """
RÈGLE STRICTE POUR LA REVUE DE PRESSE :
Pour CHAQUE œuvre sans exception, fournis EXACTEMENT 3 critiques comparées ("ratings") provenant de 3 MÉDIAS DISTINCTS et reconnus (exemples : Le Monde, Télérama, Les Inrockuptibles, Libération, Cahiers du Cinéma, Pitchfork, Rolling Stone, The Guardian...).

Réponds STRICTEMENT sous la forme d'un objet JSON valide :
{
  "accessible": {
    "themeTitle": "Titre du thème inédit",
    "themeSubtitle": "Sous-titre poétique expliquant le fil invisible reliant les 3 œuvres",
    "items": [
      {
        "type": "LIVRE",
        "title": "Titre exact",
        "creator": "Nom de l'auteur",
        "year": "1997",
        "origin": "France",
        "genre": "Genre",
        "accessibility": "Pop Culture",
        "formatMetric": "320 pages",
        "quote": "Citation clé marquante",
        "anecdote": "Anecdote surprenante sur la genèse de l'œuvre",
        "tags": ["Tag1", "Tag2"],
        "ratings": [
          {"source": "Le Monde", "score": "5/5", "iconName": "star.fill", "excerpt": "Une œuvre magistrale."},
          {"source": "Télérama", "score": "4/5", "iconName": "star.fill", "excerpt": "Un regard bouleversant."},
          {"source": "Les Inrockuptibles", "score": "4.5/5", "iconName": "star.fill", "excerpt": "Une écriture d'une grande finesse."}
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
        generation_config={"response_mime_type": "application/json", "temperature": 0.8},
        system_instruction=system_prompt
    )

    response = model.generate_content("Génère un triptyque 100% inédit et original pour aujourd'hui avec 3 revues de presse distinctes par œuvre.")
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
                img, pages, pub_year = fetch_book_metadata(title, creator)
                if img: item["imageURL"] = img
                if pages and not item.get("formatMetric"): item["formatMetric"] = f"{pages} pages"
                if pub_year: item["year"] = pub_year

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

    print(f"✅ Édition générée et archivée dans {archive_path}.")

if __name__ == "__main__":
    generate_daily_edition()

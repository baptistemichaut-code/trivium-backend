import os
import json
import requests
from datetime import datetime

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

SYSTEM_PROMPT = """
Tu es le curateur en chef de TRIVIUM, une application culturelle d'élite.
Chaque jour, tu conçois un triptyque culturel exigeant et fascinant autour d'un thème précis.

Le triptyque DOIT contenir STRICTEMENT :
1. Un LIVRE
2. Un FILM
3. Un ALBUM DE MUSIQUE

RÈGLES ÉDITORIALES :
- Les trois œuvres doivent être réelles, existantes et de grande qualité artistique.
- Les trois œuvres doivent entrer en résonance profonde avec le thème du jour.
- Varie les époques, les pays d'origine et les sensibilités.
- Fournis obligatoirement une anecdote captivante ('anecdote') sur les coulisses de la création (tournage, écriture, enregistrement).
- Les critiques presse ('ratings') doivent citer de vrais médias (Le Monde, Télérama, Les Inrocks, Pitchfork, SensCritique, Cahiers du Cinéma, etc.).

RÉPONDS UNIQUEMENT AVEC UN OBJET JSON STRICT RESPECTANT CE FORMAT :
{
  "themeTitle": "Titre poétique du thème",
  "themeSubtitle": "Explication en une phrase de la résonance entre ces trois œuvres.",
  "items": [
    {
      "type": "LIVRE",
      "title": "Titre du livre",
      "creator": "Nom de l'auteur",
      "year": "1953",
      "origin": "France",
      "genre": "Roman / Essai...",
      "quote": "Une phrase marquante ou célèbre extraite de l'œuvre",
      "aiSummary": "Présentation percutante de l'œuvre en 2 ou 3 phrases.",
      "thematicAnalysis": "Analyse de la résonance avec le thème du jour.",
      "accessibility": "Accessible / Intermédiaire / Exigeant",
      "formatMetric": "Environ 240 pages",
      "tags": ["Philosophie", "Absurde", "Classique"],
      "anecdote": "Anecdote insolite et véridique sur la conception de l'ouvrage.",
      "ratings": [
        {"source": "Le Monde", "score": "Chef-d'œuvre", "excerpt": "Une plume magistrale."},
        {"source": "SensCritique", "score": "8.4/10", "excerpt": "Un monument de la littérature."}
      ]
    },
    {
      "type": "FILM",
      "title": "Titre du film",
      "creator": "Nom du réalisateur",
      "year": "1997",
      "origin": "Japon",
      "genre": "Drame / Sci-Fi...",
      "quote": "Réplique culte ou phrase d'accroche",
      "aiSummary": "Présentation du film en 2 ou 3 phrases.",
      "thematicAnalysis": "Analyse de la résonance avec le thème du jour.",
      "accessibility": "Accessible / Intermédiaire / Exigeant",
      "formatMetric": "2h14",
      "tags": ["Cinéma d'auteur", "Esthétique"],
      "anecdote": "Secret de tournage ou anecdote de production fascinante.",
      "ratings": [
        {"source": "Télérama", "score": "T T T T", "excerpt": "Une mise en scène étourdissante."},
        {"source": "Rotten Tomatoes", "score": "94%", "excerpt": "Un classique instantané."}
      ]
    },
    {
      "type": "ALBUM",
      "title": "Titre exact de l'album",
      "creator": "Nom de l'artiste ou du groupe",
      "year": "1977",
      "origin": "Royaume-Uni",
      "genre": "Art Rock / Jazz / Ambient...",
      "quote": "Parole emblématique ou note de pochette",
      "aiSummary": "Présentation de l'album en 2 ou 3 phrases.",
      "thematicAnalysis": "Analyse de la texture sonore et de la résonance thématique.",
      "accessibility": "Accessible / Intermédiaire / Exigeant",
      "formatMetric": "9 titres • 42 min",
      "tags": ["Incontournable", "Nocturne"],
      "anecdote": "Anecdote sur les sessions d'enregistrement ou la pochette.",
      "ratings": [
        {"source": "Pitchfork", "score": "9.5/10", "excerpt": "Un sommet de créativité."},
        {"source": "Les Inrocks", "score": "Indispensable", "excerpt": "Une atmosphère magnétique."}
      ]
    }
  ]
}
"""

def generate_daily_edition():
    if not GEMINI_API_KEY:
        raise ValueError("La variable d'environnement GEMINI_API_KEY est manquante.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [{"text": f"Génère l'édition Trivium du jour ({datetime.now().strftime('%d %B %Y')}). Sois créatif et inspiré."}]
        }],
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.85
        }
    }

    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    
    result_json = response.json()
    raw_text = result_json["candidates"][0]["content"]["parts"][0]["text"]
    
    # Nettoyage et validation JSON
    parsed_data = json.loads(raw_text)

    # Écriture dans today.json
    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(parsed_data, f, ensure_ascii=False, indent=2)

    print("✨ 'today.json' généré avec succès avec anecdotes et critiques.")

if __name__ == "__main__":
    generate_daily_edition()

import os
import json
import datetime
import requests

def generate_daily_edition():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY introuvable dans les variables d'environnement.")

    prompt = """
Tu es le curateur en chef de l'application culturelle "Trivium".
Génère une édition quotidienne originale composée de 3 œuvres liées par un fil thématique fort :
1. Un Livre (roman, essai ou classique littéraire)
2. Un Film (long-métrage culte ou d'auteur)
3. Un Album (album musical majeur)

Renvoie UNIQUEMENT un objet JSON valide (sans balises markdown ```json, juste le texte JSON brut) avec cette structure exacte :
{
  "themeTitle": "Titre poétique ou percutant du thème",
  "themeSubtitle": "Une phrase d'accroche expliquant le fil invisible reliant ces 3 œuvres",
  "items": [
    {
      "type": "LIVRE",
      "title": "Titre du livre",
      "creator": "Nom de l'auteur",
      "year": "Année",
      "genre": "Genre littéraire",
      "origin": "Pays d'origine",
      "formatMetric": "Ex: 320 pages",
      "accessibility": "Ex: Accessible / Exigeant",
      "quote": "Une citation emblématique ou marquante de l'œuvre",
      "aiSummary": "Résumé captivant en 2-3 phrases",
      "thematicAnalysis": "Analyse de résonance avec le thème du jour",
      "tags": ["Tag1", "Tag2", "Tag3"],
      "ratings": [
        {"source": "Le Monde", "score": "5/5", "excerpt": "Une phrase courte d'éloge critique."}
      ]
    },
    {
      "type": "FILM",
      "title": "Titre du film",
      "creator": "Nom du réalisateur",
      "year": "Année",
      "genre": "Genre cinématographique",
      "origin": "Pays d'origine",
      "formatMetric": "Ex: 2h 14m",
      "accessibility": "Ex: Grand public / Auteur",
      "quote": "Une réplique culte",
      "aiSummary": "Synopsis percutant",
      "thematicAnalysis": "Analyse de résonance avec le thème du jour",
      "tags": ["Tag1", "Tag2", "Tag3"],
      "ratings": [
        {"source": "Télérama", "score": "TTT", "excerpt": "Une critique marquante."}
      ]
    },
    {
      "type": "ALBUM",
      "title": "Titre de l'album",
      "creator": "Nom de l'artiste ou du groupe",
      "year": "Année",
      "genre": "Genre musical",
      "origin": "Pays d'origine",
      "formatMetric": "Ex: 11 titres",
      "accessibility": "Ex: Écoute immédiate",
      "quote": "Une phrase ou vers marquant d'un morceau",
      "aiSummary": "Présentation de l'album",
      "thematicAnalysis": "Analyse de résonance avec le thème du jour",
      "tags": ["Tag1", "Tag2", "Tag3"],
      "ratings": [
        {"source": "Pitchfork", "score": "8.8/10", "excerpt": "Une critique marquante."}
      ]
    }
  ]
}
"""

    url = f"[https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key=](https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key=){api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }

    print("Génération du triptyque en cours avec Gemini 3.6 Flash...")
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()

    result = response.json()
    raw_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()

    # Nettoyage du markdown résiduel
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    raw_text = raw_text.strip()

    data = json.loads(raw_text)

    # Sauvegarde du fichier today.json pour l'application
    with open("today.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("today.json mis à jour.")

    # Archivage automatique dans le dossier archive/
    os.makedirs("archive", exist_ok=True)
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    archive_path = os.path.join("archive", f"{today_str}.json")
    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Archive enregistrée : {archive_path}")

if __name__ == "__main__":
    generate_daily_edition()

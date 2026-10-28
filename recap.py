import os, time, datetime, re
import feedparser, requests

FEEDS = {
    "franceinfo": "https://www.francetvinfo.fr/titres.rss",
    "France 24": "https://www.france24.com/fr/rss",
    "Le Monde": "https://www.lemonde.fr/rss/une.xml",
    "Le Figaro": "https://www.lefigaro.fr/rss/figaro_actualites.xml",
    "BBC World": "https://feeds.bbci.co.uk/news/world/rss.xml",
}

cutoff = time.time() - 24 * 3600
items = []
for source, url in FEEDS.items():
    for e in feedparser.parse(url).entries:
        t = e.get("published_parsed") or e.get("updated_parsed")
        if t and time.mktime(t) >= cutoff:
            resume = re.sub("<[^>]+>", "", e.get("summary", ""))[:300]
            items.append(f"[{source}] {e.get('title','')} — {resume}")

prompt = (
    "Tu es un rédacteur d'agence de presse strictement neutre. "
    "À partir des dépêches ci-dessous (dernières 24 h), rédige en français un récap factuel : "
    "uniquement des faits vérifiables, aucune opinion, aucun adjectif orienté, "
    "ni de droite ni de gauche. Fusionne les doublons entre sources. "
    "Classe par thèmes : France, International, Économie, Sciences et Tech, Sport, Culture. "
    "Une phrase courte par fait, les plus importants d'abord. "
    "Réponds uniquement en HTML simple (balises h2, ul, li), sans balise html ni body.\n\n"
    + "\n".join(items[:250])
)

r = requests.post(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent",
    params={"key": os.environ["GEMINI_API_KEY"]},
    json={"contents": [{"parts": [{"text": prompt}]}]},
    timeout=180,
)
if r.status_code != 200:
    print(r.text)
r.raise_for_status()
corps = r.json()["candidates"][0]["content"]["parts"][0]["text"]
corps = corps.replace("```html", "").replace("```", "")

date = datetime.datetime.now().strftime("%d/%m/%Y")
page = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Récap news du {date}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 760px; margin: 0 auto; padding: 16px; line-height: 1.5; background: #fff; color: #222; }}
h1 {{ color: #1a56db; font-size: 1.5em; }}
h2 {{ color: #1a56db; border-bottom: 2px solid #e5e7eb; padding-bottom: 4px; margin-top: 28px; }}
li {{ margin-bottom: 8px; }}
footer {{ margin-top: 40px; font-size: 0.85em; color: #777; }}
</style>
</head>
<body>
<h1>Récap des news du {date}</h1>
{corps}
<footer>Sources : franceinfo, France 24, Le Monde, Le Figaro, BBC World. Résumé automatique.</footer>
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(page)

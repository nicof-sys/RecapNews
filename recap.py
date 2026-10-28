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
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
    params={"key": os.environ["GEMINI_API_KEY"]},
    json={"contents": [{"parts": [{"text": prompt}]}]},
    timeout=180,
)
r.raise_for_status()
corps = r.json()["candidates"][0]["content"]["parts"][0]["text"]
corps = corps.replace("```html", "").replace("```", "")

date = datetime.datetime.now().strftime("%d/%m/%Y")
page = f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Récap news du {date}</title>
<style>body{{font-family:sans-serif;max-width:760px;margin:auto;padding:16px;line-height:1.5}}
h1,h2{{color:#1a5fb4}} li{{margin-bottom:6px}}</style></head>
<body><h1>Récap news du {date}</h1>{corps}
<p style="color:#888;font-size:small">Sources : {", ".join(FEEDS)}</p></body></html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(page)

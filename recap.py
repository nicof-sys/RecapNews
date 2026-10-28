import os, time, datetime, re
from urllib.parse import quote
import feedparser, requests

FEEDS = {
    # France
    "franceinfo": "https://www.francetvinfo.fr/titres.rss",
    "France 24": "https://www.france24.com/fr/rss",
    "Le Monde": "https://www.lemonde.fr/rss/une.xml",
    "Le Figaro": "https://www.lefigaro.fr/rss/figaro_actualites.xml",
    "Blast": "https://api.blast-info.fr/rss_articles.xml",
    "Taranis News": "https://taranis.news/feed/",
    "Praxis": "https://praxismedia.fr/feed/",
    # Anglais
    "The Guardian": "https://www.theguardian.com/world/rss",
    "Al Jazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "DW": "https://rss.dw.com/rdf/rss-en-all",
    "New York Times": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    # Espagnol
    "El País": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
    # Portugais
    "Público": "https://feeds.feedburner.com/PublicoRSS",
    # Italien
    "ANSA": "https://www.ansa.it/sito/ansait_rss.xml",
}

# Domaines des médias étrangers : leurs liens s'ouvrent traduits en français via Google Traduction
DOMAINES_ETRANGERS = ("theguardian.com", "aljazeera.com", "dw.com", "nytimes.com", "elpais.com", "publico.pt", "ansa.it")

# Plafond par source, pour que les gros flux n'évincent pas les petits
MAX_PAR_SOURCE = 15

cutoff = time.time() - 24 * 3600
items = []
for source, url in FEEDS.items():
    try:
        flux = feedparser.parse(url)
    except Exception:
        print(f"Flux ignoré : {source}")
        continue
    if not flux.entries:
        print(f"Aucun article pour : {source}")
    n = 0
    for e in flux.entries:
        if n >= MAX_PAR_SOURCE:
            break
        t = e.get("published_parsed") or e.get("updated_parsed")
        if t and time.mktime(t) >= cutoff:
            resume = re.sub("<[^>]+>", "", e.get("summary", ""))[:250]
            items.append(f"[{source}] {e.get('title','')} — {resume} — LIEN: {e.get('link','')}")
            n += 1

prompt = (
    "Tu es un rédacteur d'agence de presse strictement neutre. "
    "À partir des dépêches ci-dessous (dernières 24 h), issues de médias français et internationaux "
    "en plusieurs langues (anglais, espagnol, portugais, italien), rédige en français un récap factuel : "
    "uniquement des faits vérifiables, aucune opinion, aucun adjectif orienté, "
    "ni de droite ni de gauche. Traduis fidèlement les dépêches étrangères. "
    "Fusionne les doublons entre sources. "
    "Classe par thèmes : France, International, Économie, Sciences et Tech, Sport, Culture. "
    "Une phrase courte par fait, les plus importants d'abord. "
    "Après chaque fait, ajoute le ou les liens des articles utilisés, sous la forme "
    "<a href=\"LIEN\" target=\"_blank\">Nom du média</a>, en reprenant exactement les liens fournis. "
    "Réponds uniquement en HTML simple (balises h2, ul, li, a), sans balise html ni body.\n\n"
    + "\n".join(items)
)

r = requests.post(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent",
    params={"key": os.environ["GEMINI_API_KEY"]},
    json={"contents": [{"parts": [{"text": prompt}]}]},
    timeout=600,
)
if r.status_code != 200:
    print(r.text)
r.raise_for_status()
corps = r.json()["candidates"][0]["content"]["parts"][0]["text"]
corps = corps.replace("```html", "").replace("```", "")


def traduire_lien(m):
    url = m.group(1)
    if any(d in url for d in DOMAINES_ETRANGERS):
        url = "https://translate.google.com/translate?sl=auto&tl=fr&u=" + quote(url, safe="")
    return f'href="{url}"'


corps = re.sub(r'href="([^"]+)"', traduire_lien, corps)

date = datetime.datetime.now().strftime("%d/%m/%Y")
sources = ", ".join(FEEDS)
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
a {{ color: #1a56db; font-size: 0.85em; margin-left: 4px; }}
footer {{ margin-top: 40px; font-size: 0.85em; color: #777; }}
</style>
</head>
<body>
<h1>Récap des news du {date}</h1>
{corps}
<footer>Sources : {sources}. Résumé automatique.</footer>
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(page)

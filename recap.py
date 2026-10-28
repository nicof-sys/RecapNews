import os, time, datetime, re, json
from html import escape
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
    "Ne classe pas par pays ni par rubriques fixes : dégage 5 à 9 thèmes propres à l'actualité du jour "
    "(par exemple « Catastrophe ferroviaire en Espagne », « Législatives en Israël », « Prix de l'énergie »), "
    "chacun regroupant des faits liés entre eux, quel que soit le pays concerné. "
    "Donne à chaque thème un titre court et une phrase de contexte. "
    "Classe les thèmes du plus important au moins important (gravité, nombre de sources qui en parlent). "
    "Les faits isolés vont dans un dernier thème intitulé « En bref ». "
    "Une phrase courte par fait, les plus importants d'abord. "
    "Pour chaque fait, indique le ou les articles utilisés (nom du média et lien), "
    "en reprenant exactement les liens fournis.\n\n"
    + "\n".join(items)
)

# Structure imposée à la réponse de Gemini : thèmes > faits > liens
LIEN = {
    "type": "OBJECT",
    "properties": {"media": {"type": "STRING"}, "url": {"type": "STRING"}},
    "required": ["media", "url"],
}
FAIT = {
    "type": "OBJECT",
    "properties": {"texte": {"type": "STRING"}, "liens": {"type": "ARRAY", "items": LIEN}},
    "required": ["texte", "liens"],
}
THEME = {
    "type": "OBJECT",
    "properties": {
        "titre": {"type": "STRING"},
        "contexte": {"type": "STRING"},
        "faits": {"type": "ARRAY", "items": FAIT},
    },
    "required": ["titre", "contexte", "faits"],
}
SCHEMA = {
    "type": "OBJECT",
    "properties": {"themes": {"type": "ARRAY", "items": THEME}},
    "required": ["themes"],
}

r = requests.post(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent",
    params={"key": os.environ["GEMINI_API_KEY"]},
    json={
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": SCHEMA},
    },
    timeout=600,
)
if r.status_code != 200:
    print(r.text)
r.raise_for_status()
themes = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])["themes"]


def traduire_lien(url):
    if any(d in url for d in DOMAINES_ETRANGERS):
        url = "https://translate.google.com/translate?sl=auto&tl=fr&u=" + quote(url, safe="")
    return url


# Barre de navigation (un bouton par thème) puis une section par thème
nav = ['<button class="actif" data-theme="tous">Tous</button>']
sections = []
for i, theme in enumerate(themes, 1):
    titre = escape(theme["titre"])
    nav.append(f'<button data-theme="t{i}">{titre} <span>{len(theme["faits"])}</span></button>')
    faits = []
    for fait in theme["faits"]:
        liens = " ".join(
            f'<a href="{escape(traduire_lien(l["url"]))}" target="_blank">{escape(l["media"])}</a>'
            for l in fait["liens"]
        )
        faits.append(f"<li>{escape(fait['texte'])} {liens}</li>")
    sections.append(
        f'<section id="t{i}">\n<h2>{titre}</h2>\n<p class="contexte">{escape(theme["contexte"])}</p>\n'
        "<ul>\n" + "\n".join(faits) + "\n</ul>\n</section>"
    )
corps = "<nav>\n" + "\n".join(nav) + "\n</nav>\n" + "\n".join(sections)

# Filtrage par thème côté lecteur ; le thème choisi est gardé dans l'URL (ex. #t2)
SCRIPT = """<script>
const boutons = document.querySelectorAll("nav button");
function afficher(id) {
  if (!document.getElementById(id)) id = "tous";
  boutons.forEach(b => b.classList.toggle("actif", b.dataset.theme === id));
  document.querySelectorAll("section").forEach(s => s.hidden = id !== "tous" && s.id !== id);
}
boutons.forEach(b => b.addEventListener("click", () => {
  history.replaceState(null, "", b.dataset.theme === "tous" ? location.pathname : "#" + b.dataset.theme);
  afficher(b.dataset.theme);
}));
afficher(location.hash.slice(1) || "tous");
</script>"""

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
h2 {{ color: #1a56db; border-bottom: 2px solid #e5e7eb; padding-bottom: 4px; margin-top: 28px; margin-bottom: 4px; }}
nav {{ position: sticky; top: 0; background: #fff; padding: 8px 0; display: flex; flex-wrap: wrap; gap: 6px; border-bottom: 1px solid #e5e7eb; }}
nav button {{ font: inherit; font-size: 0.85em; border: 1px solid #c7d2fe; background: #eef2ff; color: #1a56db; border-radius: 999px; padding: 4px 12px; cursor: pointer; }}
nav button span {{ opacity: 0.6; }}
nav button.actif {{ background: #1a56db; color: #fff; border-color: #1a56db; }}
.contexte {{ color: #555; font-style: italic; margin-top: 0; }}
li {{ margin-bottom: 8px; }}
a {{ color: #1a56db; font-size: 0.85em; margin-left: 4px; }}
footer {{ margin-top: 40px; font-size: 0.85em; color: #777; }}
</style>
</head>
<body>
<h1>Récap des news du {date}</h1>
{corps}
<footer>Sources : {sources}. Résumé automatique.</footer>
{SCRIPT}
</body>
</html>"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(page)

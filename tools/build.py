#!/usr/bin/env python3
"""Construit le site statique et les flux RSS Pinterest dans _site/.
Seules les épingles dont publish_at est passé sont publiées (file d'attente automatique).
Usage :
  python3 tools/build.py                 -> construit _site/
  python3 tools/build.py --schedule      -> donne une date aux épingles sans publish_at
Bibliothèque standard uniquement (tourne aussi dans GitHub Actions).
"""
import json, os, re, shutil, sys, html
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "_site")
UTC = timezone.utc
# Créneaux de sortie (heure UTC) ; l'action tourne 3 fois par jour.
SLOTS_UTC = ["07:40", "15:40", "11:40"]


def load(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
        return json.load(f)


def save(name, obj):
    with open(os.path.join(ROOT, "data", name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


def schedule(pins, site):
    per_day = int(site.get("pins_per_day", 1))
    dated = [parse_dt(p["publish_at"]) for p in pins if p.get("publish_at")]
    now = datetime.now(UTC)
    start = max(dated + [now]).date() + timedelta(days=1)
    day, slot = start, 0
    for p in pins:
        if not p.get("in_feed", True) or p.get("publish_at"):
            continue
        hh, mm = map(int, SLOTS_UTC[slot].split(":"))
        p["publish_at"] = datetime(day.year, day.month, day.day, hh, mm, tzinfo=UTC).isoformat().replace("+00:00", "Z")
        slot += 1
        if slot >= per_day:
            slot, day = 0, day + timedelta(days=1)
    return pins


def is_live(p, now):
    if not p.get("in_feed", True):
        return True  # page seule (épingle publiée par un autre moyen)
    return bool(p.get("publish_at")) and parse_dt(p["publish_at"]) <= now


def esc(s):
    return html.escape(s, quote=True)


CSS = """
:root{--sage:#8A9A7B;--sage-d:#5F6E54;--cream:#F7F4EE;--ink:#2F3A2F;--grey:#686E64;--line:#E2DCD0}
*{box-sizing:border-box}body{margin:0;background:var(--cream);color:var(--ink);font:17px/1.65 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--sage-d)}header{background:var(--sage);color:#fff;padding:28px 16px;text-align:center}
header a{color:#fff;text-decoration:none}header h1{margin:0;font:600 30px/1.2 Georgia,serif}header p{margin:6px 0 0;opacity:.9}
main{max-width:760px;margin:0 auto;padding:28px 16px 48px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:18px}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;text-decoration:none;color:var(--ink)}
.card img{width:100%;display:block;aspect-ratio:2/3;object-fit:cover}.card span{display:block;padding:10px 12px;font-weight:600;font-size:15px;line-height:1.35}
article img{width:100%;height:auto;max-width:520px;display:block;margin:0 auto 24px;border-radius:10px}
article h1{font:600 30px/1.25 Georgia,serif;margin:0 0 16px}ol{padding-left:22px}li{margin:0 0 10px}
.note{font-size:14px;color:var(--grey);border-top:1px solid var(--line);margin-top:28px;padding-top:14px}
.products{background:#fff;border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin-top:24px}
footer{text-align:center;font-size:14px;color:var(--grey);padding:24px 16px;border-top:1px solid var(--line)}
"""


def page(site, title, body, desc="", extra_head="", path=""):
    verify = site.get("pinterest_verify", "").strip()
    meta_verify = f'<meta name="p:domain_verify" content="{esc(verify)}">' if verify else ""
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc or site['tagline'])}">
{meta_verify}{extra_head}
<link rel="canonical" href="{site['base_url']}/{path}">
<style>{CSS}</style></head><body>
<header><a href="{site['base_url']}/"><h1>{esc(site['name'])}</h1></a><p>{esc(site['tagline'])}</p></header>
<main>{body}</main>
<footer><a href="{site['pinterest_profile']}">Suivre Chez Soi Rangé sur Pinterest</a> · <a href="{site['base_url']}/a-propos/">À propos</a></footer>
</body></html>
"""


def img_url(site, p):
    return f"{site['base_url']}/{p['image']}"


def pin_url(site, p):
    return f"{site['base_url']}/epingles/{p['slug']}/"


def article(site, p):
    tips = "".join(f"<li><strong>{esc(t['t'])}</strong> : {esc(t['d'])}</li>" for t in p["tips"])
    prods = ""
    if p.get("products"):
        items = "".join(
            f'<li><a href="{esc(x["url"])}" rel="sponsored nofollow">{esc(x["name"])}</a> : {esc(x.get("why",""))}</li>'
            for x in p["products"])
        prods = (f'<div class="products"><strong>Pour s\'équiper (produits similaires à l\'illustration)</strong><ul>{items}</ul>'
                 f'<p class="note">Contient des liens affiliés. {esc(site["amazon_disclosure"])}</p></div>')
    ai = "Illustration générée par IA, à titre d'inspiration." if p.get("ai_visual") else "Illustration Chez Soi Rangé."
    og = (f'<meta property="og:title" content="{esc(p["title"])}"><meta property="og:image" content="{img_url(site,p)}">'
          f'<meta property="og:description" content="{esc(p["description"])}"><meta property="og:type" content="article">')
    body = (f'<article><h1>{esc(p["title"]).replace(" :", "&nbsp;:")}</h1><img src="{img_url(site,p)}" alt="{esc(p["title"])}" width="1000" height="1500">'
            f'<p>{esc(p["intro"])}</p><ol>{tips}</ol>{prods}<p class="note">{ai}</p></article>')
    return page(site, f'{p["title"]} | {site["name"]}', body, p["description"], og, f"epingles/{p['slug']}/")


def rss(site, items, title, path):
    out = []
    for p in items:
        u, iu = pin_url(site, p), img_url(site, p)
        size = os.path.getsize(os.path.join(ROOT, p["image"]))
        mime = "image/png" if p["image"].endswith(".png") else "image/jpeg"
        desc = p["description"] + (" Visuel généré par IA." if p.get("ai_visual") else "")
        if p.get("products"):
            desc += " Contient un lien affilié."
        out.append(f"""<item><title>{esc(p['title'])}</title><link>{u}</link><guid isPermaLink="true">{u}</guid>
<pubDate>{format_datetime(parse_dt(p['publish_at']))}</pubDate>
<description><![CDATA[<img src="{iu}" alt="{esc(p['title'])}"/><p>{desc}</p>]]></description>
<enclosure url="{iu}" length="{size}" type="{mime}"/><media:content url="{iu}" medium="image" type="{mime}" width="1000" height="1500"/></item>""")
    now = format_datetime(datetime.now(UTC))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/" xmlns:atom="http://www.w3.org/2005/Atom"><channel>
<title>{esc(title)}</title><link>{site['base_url']}/</link><description>{esc(site['tagline'])}</description><language>fr</language>
<atom:link href="{site['base_url']}/{path}" rel="self" type="application/rss+xml"/><lastBuildDate>{now}</lastBuildDate>
{chr(10).join(out)}
</channel></rss>
"""


def build():
    site, pins = load("site.json"), load("pins.json")
    now = datetime.now(UTC)
    live = [p for p in pins if is_live(p, now) and p.get("image") and os.path.exists(os.path.join(ROOT, p["image"]))]
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "img"))
    for p in live:
        shutil.copy(os.path.join(ROOT, p["image"]), os.path.join(OUT, p["image"]))
        d = os.path.join(OUT, "epingles", p["slug"])
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "index.html"), "w", encoding="utf-8").write(article(site, p))
    newest = sorted(live, key=lambda p: p.get("publish_at", ""), reverse=True)
    cards = "".join(f'<a class="card" href="{pin_url(site,p)}"><img src="{img_url(site,p)}" alt="" loading="lazy"><span>{esc(p["title"])}</span></a>' for p in newest)
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(
        page(site, f"{site['name']} | {site['tagline']}", f'<div class="grid">{cards}</div>'))
    about = ("<h1>À propos</h1><p>Chez Soi Rangé partage des idées simples de rangement et d'organisation pour les petits espaces : "
             "cuisine, chambre, salle de bain, entrée. Certaines illustrations sont générées par IA, à titre d'inspiration. "
             "Certaines pages peuvent contenir des liens affiliés, toujours signalés.</p><p>Ce site n'utilise ni cookies ni outil de suivi.</p>")
    os.makedirs(os.path.join(OUT, "a-propos"))
    open(os.path.join(OUT, "a-propos", "index.html"), "w", encoding="utf-8").write(page(site, "À propos | Chez Soi Rangé", about, path="a-propos/"))
    os.makedirs(os.path.join(OUT, "feeds"))
    feed_items = [p for p in newest if p.get("in_feed", True)]
    for key, b in site["boards"].items():
        items = [p for p in feed_items if p["board"] == key][:50]
        open(os.path.join(OUT, "feeds", f"{key}.xml"), "w", encoding="utf-8").write(
            rss(site, items, f"{site['name']} · {b['label']}", f"feeds/{key}.xml"))
    open(os.path.join(OUT, ".nojekyll"), "w").close()
    urls = [site["base_url"] + "/", site["base_url"] + "/a-propos/"] + [pin_url(site, p) for p in newest]
    sm = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    open(os.path.join(OUT, "sitemap.xml"), "w", encoding="utf-8").write(
        f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>\n')
    open(os.path.join(OUT, "robots.txt"), "w", encoding="utf-8").write(f"User-agent: *\nAllow: /\nSitemap: {site['base_url']}/sitemap.xml\n")
    queue = [p["id"] for p in pins if p.get("in_feed", True) and not is_live(p, now)]
    status = {"built_at": now.isoformat(), "live": [p["id"] for p in newest], "queue": queue,
              "next_release": min([p["publish_at"] for p in pins if p["id"] in queue and p.get("publish_at")] or [None]),
              "undated": [p["id"] for p in pins if p.get("in_feed", True) and not p.get("publish_at")]}
    open(os.path.join(OUT, "status.json"), "w", encoding="utf-8").write(json.dumps(status, ensure_ascii=False, indent=1))
    print(json.dumps(status, ensure_ascii=False))


if __name__ == "__main__":
    if "--schedule" in sys.argv:
        save("pins.json", schedule(load("pins.json"), load("site.json")))
    build()

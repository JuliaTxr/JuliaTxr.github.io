#!/usr/bin/env python3
"""Synchronise data/pins.json depuis la feuille Google Sheets « Chez Soi Rangé – Contenus (publics) ».
Règles de sécurité :
- une épingle déjà publiée (date passée) garde son adresse (slug) et sa date ;
- une ligne supprimée de la feuille ne supprime jamais une épingle déjà publiée ;
- si la feuille est illisible, rien n'est modifié (le site continue avec les données existantes).
"""
import csv, hashlib, io, json, os, sys, urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
UTC = timezone.utc


def parse_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


def live(p, now):
    return p.get("publish_at") and parse_dt(p["publish_at"]) <= now


def visual_hash(p):
    key = json.dumps([p["title"], p.get("kicker", ""), p["board"], p["tips"]], ensure_ascii=False)
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def main():
    site = json.load(open(os.path.join(DATA, "site.json"), encoding="utf-8"))
    url = site.get("content_csv")
    if not url:
        print("pas de content_csv : rien à synchroniser")
        return
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            text = r.read().decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(text)))
        if not rows or "id" not in rows[0]:
            raise ValueError("feuille vide ou en-têtes absents (la feuille est-elle partagée par lien ?)")
    except Exception as e:
        print("ERREUR lecture feuille :", e)
        sys.exit(0)  # ne casse pas la publication de la file existante

    # Lignes de réglage : id "_config:cle", valeur dans la colonne title
    allowed = {"pinterest_verify", "pins_per_day"}
    cfg_changed = False
    for r in rows:
        pid = (r.get("id") or "").strip()
        if pid.startswith("_config:"):
            k, v = pid.split(":", 1)[1], (r.get("title") or "").strip()
            if k in allowed:
                v = int(v) if k == "pins_per_day" and v.isdigit() else v
                if site.get(k) != v:
                    site[k] = v
                    cfg_changed = True
    if cfg_changed:
        with open(os.path.join(DATA, "site.json"), "w", encoding="utf-8") as f:
            json.dump(site, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("réglages mis à jour")

    path = os.path.join(DATA, "pins.json")
    old = {p["id"]: p for p in json.load(open(path, encoding="utf-8"))}
    now = datetime.now(UTC)
    new = {}
    for r in rows:
        pid = (r.get("id") or "").strip()
        if not pid or pid.startswith("_") or not r.get("title", "").strip() or r.get("board") not in site["boards"]:
            continue
        tips = [{"t": r[f"t{i}"].strip(), "d": r.get(f"d{i}", "").strip()} for i in range(1, 6) if r.get(f"t{i}", "").strip()]
        p = {
            "id": pid, "slug": r["slug"].strip(), "board": r["board"].strip(),
            "kicker": r.get("kicker", "").strip() or "Astuce rangement",
            "title": r["title"].strip(), "description": r["description"].strip(),
            "intro": r.get("intro", "").strip(), "tips": tips,
            "visual": (r.get("visual") or "render").strip(),
            "ai_visual": r.get("ai_visual", "").strip().lower() == "oui",
            "in_feed": r.get("in_feed", "oui").strip().lower() != "non",
        }
        if r.get("publish_at", "").strip():
            p["publish_at"] = r["publish_at"].strip()
        if r.get("products_json", "").strip():
            try:
                p["products"] = json.loads(r["products_json"])
            except ValueError:
                print("products_json invalide pour", pid)
        p["image"] = f"img/{pid}.png" if p["visual"] == "canva" else f"img/{pid}.jpg"
        if p["visual"] == "canva" and r.get("image_url", "").strip():
            p["image_url"] = r["image_url"].strip()
        o = old.get(pid)
        if o and (live(o, now) or not o.get("in_feed", True)):
            p["slug"] = o["slug"]  # adresse publique figée
            if o.get("publish_at"):
                p["publish_at"] = o["publish_at"]
        if p["visual"] == "render":
            h = visual_hash(p)
            img = os.path.join(ROOT, p["image"])
            if o and o.get("render_hash") != h and os.path.exists(img) and not (o and live(o, now)):
                os.remove(img)  # contenu modifié avant publication : nouveau visuel
            p["render_hash"] = h if (not o or not live(o, now)) else o.get("render_hash", h)
        if o and o.get("fetch_error") and "image_url" in p:
            p["fetch_error"] = o["fetch_error"]
        new[pid] = p
    for pid, o in old.items():  # épingles publiées absentes de la feuille : conservées
        if pid not in new and (live(o, now) or not o.get("in_feed", True)):
            new[pid] = o
    out = sorted(new.values(), key=lambda p: p["id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"synchronisé : {len(out)} épingles")


if __name__ == "__main__":
    main()

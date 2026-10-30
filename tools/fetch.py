#!/usr/bin/env python3
"""Télécharge les visuels Canva exportés (liens temporaires) vers img/ avant leur expiration.
Lancé par GitHub Actions. Écrit la liste des fichiers ajoutés sur la sortie standard."""
import json, os, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(ROOT, "data", "pins.json")
pins = json.load(open(path, encoding="utf-8"))
changed = False
for p in pins:
    purl = p.get("photo_url")
    if purl:
        raw = os.path.join(ROOT, "img", "raw", p["id"] + ".jpg")
        if not os.path.exists(raw):
            try:
                req = urllib.request.Request(purl, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = r.read()
                if len(data) < 10000 or data[:1] == b"<":
                    raise ValueError("pas une image (fichier Drive non partagé par lien ?)")
                os.makedirs(os.path.dirname(raw), exist_ok=True)
                open(raw, "wb").write(data)
                p.pop("fetch_error", None)
                print("photo", p["id"], len(data))
            except Exception as e:
                p["fetch_error"] = str(e)[:200]
                print("erreur photo", p["id"], e)
            changed = True
    url = p.get("image_url")
    if not url or not p.get("image"):
        continue
    dest = os.path.join(ROOT, p["image"])
    if os.path.exists(dest):
        p.pop("image_url")
        changed = True
        continue
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            data = r.read()
        if len(data) < 10000:
            raise ValueError(f"fichier trop petit ({len(data)} octets)")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, "wb").write(data)
        p.pop("image_url")
        p.pop("fetch_error", None)
        changed = True
        print("telecharge", p["id"], p["image"], len(data))
    except Exception as e:  # lien expiré ou réseau
        p["fetch_error"] = str(e)[:200]
        changed = True
        print("erreur", p["id"], e)
if changed:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pins, f, ensure_ascii=False, indent=2)
        f.write("\n")
# Compose tout de suite les photos fraîchement téléchargées (un seul passage suffit)
import subprocess, sys
subprocess.run([sys.executable, os.path.join(ROOT, "tools", "render.py")], check=False)

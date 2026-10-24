#!/usr/bin/env python3
"""Génère les visuels d'épingles (1000x1500 JPG) pour les épingles visual == "render".
Usage : python3 tools/render.py [ID ...]   (sans argument : toutes celles dont l'image manque)
"""
import json, os, re, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "tools", "fonts")
W, H = 1000, 1500
SAGE, SAGE_DARK = (138, 154, 123), (95, 110, 84)
CREAM, INK, GREY = (247, 244, 238), (47, 58, 47), (104, 110, 100)


def font(name, size, variation=None):
    f = ImageFont.truetype(os.path.join(FONTS, name), size)
    if variation:
        f.set_variation_by_name(variation)
    return f


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def wrap(draw, text, fnt, maxw):
    words, lines, cur = re.sub(r"(\b\d+) ", "\\1\u00a0", text).replace(" :", "\u00a0:").replace(" »", "\u00a0»").replace("« ", "«\u00a0").split(" "), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=fnt) <= maxw:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_title(draw, text, maxw, maxh):
    for size in range(84, 40, -2):
        f = font("Lora-Variable.ttf", size, b"Bold")
        lines = wrap(draw, text, f, maxw)
        lh = int(size * 1.18)
        if len(lines) * lh <= maxh:
            return f, lines, lh
    return f, lines, lh


def render(pin, site):
    accent = hex2rgb(site["boards"][pin["board"]]["accent"])
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    # Bandeau titre
    band_h = 560
    d.rectangle([0, 0, W, band_h], fill=SAGE)
    d.rectangle([0, band_h, W, band_h + 14], fill=accent)
    kick = font("Poppins-Medium.ttf", 30)
    ktxt = pin.get("kicker", "Astuce rangement").upper()
    ktxt = " ".join(ktxt)  # espacement des lettres
    kw = d.textlength(ktxt, font=kick)
    d.text(((W - kw) / 2, 70), ktxt, font=kick, fill=(240, 244, 236))
    tf, tlines, lh = fit_title(d, pin["title"], W - 140, band_h - 190)
    y = 140 + (band_h - 190 - len(tlines) * lh) / 2
    for ln in tlines:
        lw = d.textlength(ln, font=tf)
        d.text(((W - lw) / 2, y), ln, font=tf, fill=(255, 255, 255))
        y += lh
    # Astuces
    tips = pin["tips"][:5]
    top, bottom = band_h + 60, H - 170
    slot = (bottom - top) / len(tips)
    tfont = font("Poppins-Bold.ttf", 36 if len(tips) > 4 else 40)
    dfont = font("Poppins-Regular.ttf", 28 if len(tips) > 4 else 31)
    nfont = font("Poppins-Bold.ttf", 34)
    for i, tip in enumerate(tips):
        cy = top + i * slot
        r = 36
        cx0, cy0 = 70, cy + 6
        d.ellipse([cx0, cy0, cx0 + 2 * r, cy0 + 2 * r], fill=SAGE)
        n = str(i + 1)
        nw = d.textlength(n, font=nfont)
        d.text((cx0 + r - nw / 2, cy0 + r - 24), n, font=nfont, fill=(255, 255, 255))
        x = cx0 + 2 * r + 30
        maxw = W - x - 60
        tl = wrap(d, tip["t"], tfont, maxw)
        yy = cy
        for ln in tl[:2]:
            d.text((x, yy), ln, font=tfont, fill=INK)
            yy += int(tfont.size * 1.25)
        for ln in wrap(d, tip["d"], dfont, maxw)[:2]:
            d.text((x, yy), ln, font=dfont, fill=GREY)
            yy += int(dfont.size * 1.3)
    # Pied
    d.line([70, H - 130, W - 70, H - 130], fill=(214, 208, 196), width=2)
    brand = font("Lora-Variable.ttf", 44, b"SemiBold")
    bt = "chezsoirange"
    bw = d.textlength(bt, font=brand)
    d.text(((W - bw) / 2, H - 110), bt, font=brand, fill=SAGE_DARK)
    sub = font("Poppins-Regular.ttf", 24)
    st = "Idées de rangement pour petits espaces"
    sw = d.textlength(st, font=sub)
    d.text(((W - sw) / 2, H - 52), st, font=sub, fill=GREY)
    return img


def main():
    site = json.load(open(os.path.join(ROOT, "data", "site.json"), encoding="utf-8"))
    pins = json.load(open(os.path.join(ROOT, "data", "pins.json"), encoding="utf-8"))
    wanted = set(sys.argv[1:])
    changed = False
    for p in pins:
        if p.get("visual") != "render":
            continue
        rel = p.get("image") or f"img/{p['id']}.jpg"
        out = os.path.join(ROOT, rel)
        if (wanted and p["id"] not in wanted) or (not wanted and os.path.exists(out)):
            continue
        render(p, site).save(out, "JPEG", quality=88, optimize=True, progressive=True)
        p["image"] = rel
        changed = True
        print("rendu", p["id"], rel)
    if changed:
        json.dump(pins, open(os.path.join(ROOT, "data", "pins.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

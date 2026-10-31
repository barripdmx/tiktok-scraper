"""Portada del hilo de Blocus: la palabra BLOCUS enorme, con efecto glitch en rojo y cian TikTok."""

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SALIDA = ROOT / "data/blocus/graficas/portada_blocus.png"
FUENTE = "C:/Windows/Fonts/impact.ttf"
W, H = 1600, 900
ROJO, CIAN, BLANCO, NEGRO = (254, 44, 85), (37, 244, 238), (255, 255, 255), (1, 1, 1)


def texto(color, dx=0, dy=0, tam=420):
    capa = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    f = ImageFont.truetype(FUENTE, tam)
    x0, y0, x1, y1 = d.textbbox((0, 0), "BLOCUS", font=f)
    d.text(((W - (x1 - x0)) / 2 - x0 + dx, (H - (y1 - y0)) / 2 - y0 + dy - 20), "BLOCUS", font=f, fill=color)
    return capa


def main():
    random.seed(7)
    img = Image.new("RGB", (W, H), NEGRO)
    d = ImageDraw.Draw(img)
    for x in range(-H, W, 90):  # rayas diagonales de fondo
        d.line([(x, H), (x + H, 0)], fill=(18, 18, 18), width=34)
    d.rectangle([0, 0, W, 38], fill=ROJO)
    d.rectangle([0, H - 38, W, H], fill=ROJO)

    base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for color, dx in ((CIAN, -16), (ROJO, 16), (BLANCO, 0)):
        base = Image.alpha_composite(base, texto(color, dx))
    for y, dx in ((300, 28), (405, -34), (500, 22)):  # pocos cortes desplazados (glitch), la palabra sigue legible
        franja = base.crop((0, y, W, y + 16))
        base.paste((0, 0, 0, 0), (0, y, W, y + 16))
        base.paste(franja, (dx, y))
    img.paste(base, (0, 0), base)

    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FUENTE, 54)
    d.text((W / 2, 720), "INVESTIGACIÓN OSINT  ·  HILO  ↓", font=f, fill=CIAN, anchor="mm")
    d.text((W - 60, H - 62), "@barripdmx", font=ImageFont.truetype(FUENTE, 28), fill=BLANCO, anchor="rm")
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    img.save(SALIDA)
    print(SALIDA)


if __name__ == "__main__":
    main()

"""Mascote Eco: arte externa (assets/eco/*.png) com loop de fala.
Fallback: desenho PIL caso os PNGs não existam.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from . import config as C

CYAN = (34, 211, 238)
NAVY = (10, 22, 52)
WHITE = (255, 255, 255)
BLUSH = (255, 150, 180)

NFRAMES = 8
FPS_LOOP = 6
ECO_DIR = C.ASSETS / "eco"
ECO_SEQ = ["base", "open", "half", "open", "base", "half", "blink", "base"]


def _draw_eco(d: ImageDraw.ImageDraw, u: float, dy: float,
              mouth_open: bool, blink: bool) -> None:
    # medalhão
    d.ellipse([40*u, 40*u, 760*u, 760*u], fill=NAVY + (255,))
    d.ellipse([40*u, 40*u, 760*u, 760*u], outline=CYAN + (255,), width=int(14*u))
    d.ellipse([70*u, 70*u, 730*u, 730*u], outline=(CYAN[0]//3, CYAN[1]//3, CYAN[2]//3, 255),
              width=int(4*u))
    # linhas de velocidade
    for i, (x0, ln) in enumerate([(120, 130), (100, 170), (120, 130)]):
        y = (330 + i*55) * u
        d.rounded_rectangle([x0*u, y, (x0+ln)*u, y+22*u], radius=11*u, fill=CYAN + (255,))
    # bracinho joinha (direita): antebraço diagonal + mão + polegar
    d.line([(555*u, (450+dy)*u), (645*u, (350+dy)*u)], fill=CYAN + (255,), width=int(30*u))
    d.ellipse([618*u, (300+dy)*u, 672*u, (354+dy)*u], fill=CYAN + (255,))
    d.rounded_rectangle([632*u, (262+dy)*u, 662*u, (312+dy)*u], radius=15*u, fill=CYAN + (255,))
    # cesto (trapézio)
    d.polygon([(250*u, (430+dy)*u), (590*u, (430+dy)*u),
               (530*u, (600+dy)*u), (310*u, (600+dy)*u)], fill=WHITE + (255,))
    for i in range(1, 4):
        x = (250 + i*85) * u
        d.line([(x, (438+dy)*u), (x-14*u, (592+dy)*u)], fill=CYAN + (255,), width=int(16*u))
    d.line([(250*u, (430+dy)*u), (590*u, (430+dy)*u)], fill=CYAN + (255,), width=int(20*u))
    # rodinhas
    for wx in (350, 500):
        d.ellipse([(wx-32)*u, (600+dy)*u, (wx+32)*u, (664+dy)*u], fill=CYAN + (255,))
        d.ellipse([(wx-13)*u, (619+dy)*u, (wx+13)*u, (645+dy)*u], fill=NAVY + (255,))
    # olhos (ou piscada)
    for ex in (370, 470):
        if blink:
            d.line([((ex-24)*u, (500+dy)*u), ((ex+24)*u, (500+dy)*u)],
                   fill=NAVY + (255,), width=int(12*u))
        else:
            d.ellipse([(ex-30)*u, (470+dy)*u, (ex+30)*u, (530+dy)*u], fill=WHITE + (255,))
            d.ellipse([(ex-12)*u, (488+dy)*u, (ex+12)*u, (522+dy)*u], fill=NAVY + (255,))
            d.ellipse([(ex-12)*u, (488+dy)*u, (ex-2)*u, (502+dy)*u], fill=WHITE + (255,))
    # bochechas
    for bx in (315, 525):
        d.ellipse([(bx-20)*u, (530+dy)*u, (bx+20)*u, (562+dy)*u], fill=BLUSH + (200,))
    # boca: sorriso ou aberta (falando)
    if mouth_open:
        d.ellipse([388*u, (522+dy)*u, 452*u, (578+dy)*u], fill=(120, 20, 30, 255))
        d.ellipse([398*u, (556+dy)*u, 442*u, (572+dy)*u], fill=(255, 120, 140, 255))
    else:
        d.arc([390*u, (520+dy)*u, 450*u, (580+dy)*u], start=15, end=165,
              fill=NAVY + (255,), width=int(12*u))


def eco_frame(size: int, phase: int) -> Image.Image:
    """Frame do loop: quique senoidal + boca alternada + piscada periódica."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = size / 800
    dy = 14 * math.sin(2 * math.pi * phase / NFRAMES)
    _draw_eco(d, u, dy, mouth_open=(phase % 4 in (0, 1)), blink=(phase == 6))
    return img


def eco_png(size: int = 800, dest: Path | None = None) -> Image.Image:
    img = eco_frame(size, 2)
    if dest:
        img.save(dest)
    return img


def _clean(sprite: Image.Image) -> Image.Image:
    """Apaga o brilho Gemini do canto inferior direito."""
    d = ImageDraw.Draw(sprite)
    w, h = sprite.size
    d.rectangle([w*0.84, h*0.84, w, h], fill=(sprite.getpixel((0, 0))[:3] + (255,)))
    return sprite


def _badge(sprite: Image.Image, size: int) -> Image.Image:
    """Recorta círculo no personagem + anel cyan + fundo transparente."""
    sprite = _clean(sprite.convert("RGBA"))
    # fundo chapado → alpha (floodfill dos 4 cantos)
    bg = sprite.getpixel((0, 0))[:3]
    for corner in [(0, 0), (sprite.width - 1, 0), (0, sprite.height - 1),
                   (sprite.width - 1, sprite.height - 1)]:
        ImageDraw.floodfill(sprite, corner, (0, 0, 0, 0), thresh=60)
    bbox = sprite.getbbox()
    if not bbox:
        return sprite.resize((size, size), Image.LANCZOS)
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    r = max(bbox[2] - bbox[0], bbox[3] - bbox[1]) / 2 * 1.04
    side = int(r * 2 + 36)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(sprite, (int(side / 2 - cx), int(side / 2 - cy)), sprite)
    mask = Image.new("L", (side, side), 0)
    ImageDraw.Draw(mask).ellipse([18, 18, side - 18, side - 18], fill=255)
    badge = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    badge.paste(canvas, (0, 0), mask)
    ring = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse([18, 18, side - 18, side - 18],
                                 outline=CYAN + (255,), width=max(6, side // 60))
    badge.alpha_composite(ring)
    # sombra navy atrás p/ fundir com o bg do vídeo
    glow = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([18, 18, side - 18, side - 18], fill=NAVY + (255,))
    return Image.alpha_composite(glow, badge).resize((size, size), Image.LANCZOS)


def _float(sprite: Image.Image, size: int) -> Image.Image:
    """Só o personagem (contorno branco sticker separa do fundo)."""
    sprite = _clean(sprite.convert("RGBA"))
    for corner in [(0, 0), (sprite.width - 1, 0), (0, sprite.height - 1),
                   (sprite.width - 1, sprite.height - 1)]:
        ImageDraw.floodfill(sprite, corner, (0, 0, 0, 0), thresh=60)
    bbox = sprite.getbbox()
    if bbox:
        pad = 12
        bbox = (max(0, bbox[0]-pad), max(0, bbox[1]-pad),
                min(sprite.width, bbox[2]+pad), min(sprite.height, bbox[3]+pad))
        sprite = sprite.crop(bbox)
    w, h = sprite.size
    s = size / max(w, h)
    return sprite.resize((int(w*s), int(h*s)), Image.LANCZOS)


def eco_loop(outdir: Path, size: int = 440, badge: bool = True) -> Path:
    """Monta eco_00..07.png. badge=False → flutuante sem fundo."""
    outdir.mkdir(parents=True, exist_ok=True)
    if (ECO_DIR / "base.png").exists():
        if badge:
            sprites = {n: _badge(Image.open(ECO_DIR / f"{n}.png"), size) for n in
                       ("base", "open", "half", "blink")}
        else:
            sprites = {n: _float(Image.open(ECO_DIR / f"{n}.png"), size) for n in
                       ("base", "open", "half", "blink")}
        seq = [sprites[n] for n in ECO_SEQ]
    else:
        seq = [eco_frame(size, p) for p in range(NFRAMES)]
    amp = size * (0.05 if not badge else 0.035)
    for p in range(NFRAMES):
        spr = seq[p]
        dy = int(amp * math.sin(2 * math.pi * p / NFRAMES))
        canvas = Image.new("RGBA", (size, size + int(amp * 2) + 8), (0, 0, 0, 0))
        canvas.alpha_composite(spr, ((canvas.width - spr.width) // 2, int(amp) + 4 + dy))
        canvas.save(outdir / f"eco_{p:02d}.png")
    return outdir


if __name__ == "__main__":
    import sys
    eco_png(800, Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/eco.png"))
    print("ECO OK")

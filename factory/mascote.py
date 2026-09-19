"""Mascote Eco: carrinho cartoon 100% local (PIL, zero IA/zero custo).

eco_frame(): 1 frame do loop de fala (quique + boca + piscada).
eco_loop(): sequência eco_00..07.png p/ overlay animado no ffmpeg.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

CYAN = (34, 211, 238)
NAVY = (10, 22, 52)
WHITE = (255, 255, 255)
BLUSH = (255, 150, 180)

NFRAMES = 8
FPS_LOOP = 6


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


def eco_loop(outdir: Path, size: int = 440) -> Path:
    """Gera eco_00..07.png (fundo transparente). Retorna o dir."""
    outdir.mkdir(parents=True, exist_ok=True)
    for p in range(NFRAMES):
        eco_frame(size, p).save(outdir / f"eco_{p:02d}.png")
    return outdir


if __name__ == "__main__":
    import sys
    eco_png(800, Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/eco.png"))
    print("ECO OK")

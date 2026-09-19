"""Mascote Eco: carrinho cartoon 100% local (PIL, zero IA/zero custo)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

CYAN = (34, 211, 238)
NAVY = (10, 22, 52)
WHITE = (255, 255, 255)
BLUSH = (255, 150, 180)


def eco_png(size: int = 800, dest: Path | None = None) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = size / 800  # unidade
    cx = size / 2
    # medalhão
    d.ellipse([40*u, 40*u, 760*u, 760*u], fill=NAVY + (255,))
    d.ellipse([40*u, 40*u, 760*u, 760*u], outline=CYAN + (255,), width=int(14*u))
    d.ellipse([70*u, 70*u, 730*u, 730*u], outline=(CYAN[0]//3, CYAN[1]//3, CYAN[2]//3, 255),
              width=int(4*u))
    # linhas de velocidade
    for i, (x0, ln) in enumerate([(120, 130), (100, 170), (120, 130)]):
        y = (330 + i*55) * u
        d.rounded_rectangle([x0*u, y, (x0+ln)*u, y+22*u], radius=11*u, fill=CYAN + (255,))
    # (sem alça branca: o bracinho ocupa o espaço)
    # cesto (trapézio)
    basket = [(250*u, 430*u), (590*u, 430*u), (530*u, 600*u), (310*u, 600*u)]
    d.polygon(basket, fill=WHITE + (255,))
    # barras do cesto
    for i in range(1, 4):
        x = (250 + i*85) * u
        d.line([(x, 438*u), (x-14*u, 592*u)], fill=CYAN + (255,), width=int(16*u))
    d.line([(250*u, 430*u), (590*u, 430*u)], fill=CYAN + (255,), width=int(20*u))
    # bracinho joinha (direita): antebraço diagonal + mão + polegar
    d.line([(555*u, 450*u), (645*u, 350*u)], fill=CYAN + (255,), width=int(30*u))
    d.ellipse([618*u, 300*u, 672*u, 354*u], fill=CYAN + (255,))  # mão
    d.rounded_rectangle([632*u, 262*u, 662*u, 312*u], radius=15*u, fill=CYAN + (255,))  # polegar
    # rodinhas
    for wx in (350, 500):
        d.ellipse([(wx-32)*u, 600*u, (wx+32)*u, 664*u], fill=CYAN + (255,))
        d.ellipse([(wx-13)*u, 619*u, (wx+13)*u, 645*u], fill=NAVY + (255,))
    # olhos
    for ex in (370, 470):
        d.ellipse([(ex-30)*u, 470*u, (ex+30)*u, 530*u], fill=WHITE + (255,))
        d.ellipse([(ex-12)*u, 488*u, (ex+12)*u, 522*u], fill=NAVY + (255,))
        d.ellipse([(ex-12)*u, 488*u, (ex-2)*u, 502*u], fill=WHITE + (255,))
    # bochechas
    for bx in (315, 525):
        d.ellipse([(bx-20)*u, 530*u, (bx+20)*u, 562*u], fill=BLUSH + (200,))
    # sorriso
    d.arc([390*u, 520*u, 450*u, 580*u], start=15, end=165, fill=NAVY + (255,), width=int(12*u))
    if dest:
        img.save(dest)
    return img


if __name__ == "__main__":
    import sys
    eco_png(800, Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/eco.png"))
    print("ECO OK")

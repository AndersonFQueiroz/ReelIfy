"""Vídeo chamada pro canal: promo t.me/cacaofertasofcBR com QR code. Uso: python3 -m factory.video_chamada"""
from __future__ import annotations

import sys
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw

from . import config as C
from . import render as R
from .video_cinetico import base_scene, handle_footer

LINK = "https://t.me/cacaofertasofcBR"


def qr_card(size: int = 560) -> Image.Image:
    qr = qrcode.QRCode(box_size=20, border=2)
    qr.add_data(LINK)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((size, size), Image.LANCZOS)
    card = Image.new("RGB", (size + 60, size + 60), (6, 12, 34))
    card.paste(img, (30, 30))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([0, 0, card.width - 1, card.height - 1], radius=40, outline=R.CYAN, width=8)
    return card


def build(outdir: Path) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    defs = []
    # S1 hook
    bg = base_scene(41)
    y = R.draw_display(bg, R.W // 2, 480, "CANSADO DE", 104)
    y = R.draw_display(bg, R.W // 2, y + 10, "PAGAR CARO?", 104, accent="CARO?")
    R.draw_center_text(bg, R.W // 2, y + 50, "nas mesmas coisas de sempre", 48)
    handle_footer(bg)
    defs.append((bg, "Cansado de pagar caro nas mesmas coisas de sempre?", "CANSADO DE PAGAR CARO?"))
    # S2 pitch
    bg = base_scene(42)
    y = R.draw_display(bg, R.W // 2, 400, "CAÇA-OFERTAS", 100, accent="OFERTAS")
    for b in ["Mercado Livre + Shopee", "Preço verificado todo dia", "Cupons direto no post"]:
        y = R.draw_center_text(bg, R.W // 2, y + 55, f"» {b}", 50, fill=R.WHITE)
    handle_footer(bg)
    defs.append((bg, "No canal Caça Ofertas eu caço os menores preços do Mercado Livre e da Shopee, todo santo dia.",
                 "OFERTAS TODO DIA"))
    # S3 prova
    bg = base_scene(43)
    y = R.draw_center_text(bg, R.W // 2, 420, "DESCONTOS REAIS", 54, fill=R.MUTED, bold=True)
    y = R.draw_display(bg, R.W // 2, y + 10, "-63%", 130, accent="-63%")
    y = R.draw_display(bg, R.W // 2, y + 10, "-48%  -75%", 110, accent="-75%")
    R.draw_center_text(bg, R.W // 2, y + 40, "e muito mais, de verdade", 48)
    handle_footer(bg)
    defs.append((bg, "Sessenta e três, quarenta e oito, setenta e cinco por cento de desconto. De verdade.",
                 "DESCONTOS REAIS"))
    # S4 CTA + QR
    bg = base_scene(44)
    y = R.draw_display(bg, R.W // 2, 330, "ENTRA NO CANAL", 96, accent="CANAL")
    card = qr_card().convert("RGBA")
    bg.alpha_composite(card, ((R.W - card.width) // 2, y + 40))
    R.draw_center_text(bg, R.W // 2, y + 740, "Aponta a câmera. É de graça!", 50, fill=R.WHITE, bold=True)
    handle_footer(bg)
    defs.append((bg, "Aponta a câmera pro código e entra agora. É de graça! Te espero lá.",
                 "ENTRA NO CANAL »"))
    scenes = []
    for i, (bg, nar, cap) in enumerate(defs):
        png = outdir / f"ch{i+1}.png"
        bg.convert("RGB").save(png)
        mp3 = outdir / f"ch{i+1}.mp3"
        R.tts_save(nar, mp3)
        scenes.append({"png": png, "mp3": mp3, "caption": cap})
    out = outdir / "chamada-canal.mp4"
    R.assemble(scenes, out, outdir / "work_ch")
    (outdir / "chamada-canal-capa.png").write_bytes((outdir / "ch4.png").read_bytes())
    return out


def main(argv: list[str]) -> int:
    import datetime as _dt
    day = argv[0] if argv and len(argv[0]) == 10 else _dt.date.today().isoformat()
    outdir = C.FACTORY_DATA / day
    out = build(outdir)
    print(f"OK {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

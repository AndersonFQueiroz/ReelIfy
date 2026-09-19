"""Vitrine: capa + 3 cards produto + QR final. Molde da referência, cores CaçaOfertas.

Card: nome em caps espaçadas + pílula creme (preço + LINK NO CANAL) + foto.
Uso: build(offers[3], outdir, key) -> mp4
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import config as C
from . import render as R
from .mascote import eco_loop
from .video_chamada import qr_card
from .video_cinetico import base_scene, handle_footer, short_name

# Eco animado (coords saída 720x1280): capa canto sup-direito, cards sticker
# na pílula, final à esquerda do QR. Longe da logo (centro) e das legendas.
ECO_POS = {"cover": {"x": 575, "y": 600, "size": 120},
           "card": {"x": 470, "y": 330, "size": 120},
           "final": {"x": 20, "y": 500, "size": 130}}

CREAM = (250, 243, 228)
NAVY_INK = (18, 28, 60)


def spaced_kicker(base: Image.Image, cx: int, y: int, text: str) -> int:
    """Nome em caps espaçadas (estilo referência). Encolhe até caber."""
    t = " ".join(text.upper())
    size = 44
    while size > 24:
        f = ImageFont.truetype(str(C.FONT_TEXT_BOLD), size)
        d = ImageDraw.Draw(base)
        if d.textbbox((0, 0), t, font=f)[2] <= 920:
            break
        size -= 4
    f = ImageFont.truetype(str(C.FONT_TEXT_BOLD), size)
    d = ImageDraw.Draw(base)
    bb = d.textbbox((0, 0), t, font=f)
    d.text((cx - (bb[2] - bb[0]) / 2, y), t, font=f, fill=R.WHITE)
    return y + (bb[3] - bb[1]) + 10


def price_pill(base: Image.Image, cx: int, y: int, price_label: str) -> int:
    disp = ImageFont.truetype(str(C.FONT_DISPLAY), 72)
    small = ImageFont.truetype(str(C.FONT_TEXT_BOLD), 34)
    d = ImageDraw.Draw(base)
    b1 = d.textbbox((0, 0), price_label, font=disp)
    b2 = d.textbbox((0, 0), "LINK NO CANAL", font=small)
    w = max(b1[2] - b1[0], b2[2] - b2[0]) + 110
    h = (b1[3] - b1[1]) + (b2[3] - b2[1]) + 90
    x0, y0 = cx - w / 2, y
    # sombra suave
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([x0, y0 + 14, x0 + w, y0 + h + 14], radius=44, fill=(0, 0, 0, 110))
    base.alpha_composite(sh)
    d = ImageDraw.Draw(base)
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=44, fill=CREAM)
    d.text((cx - (b1[2] - b1[0]) / 2, y0 + 30), price_label, font=disp, fill=NAVY_INK)
    d.text((cx - (b2[2] - b2[0]) / 2, y0 + 30 + (b1[3] - b1[1]) + 16),
           "LINK NO CANAL", font=small, fill=NAVY_INK)
    return int(y0 + h)


def photo_shadow(base: Image.Image, photo: Path, cx_top: tuple[int, int], w: int, h: int) -> int:
    x, y = cx_top
    sh = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([x, y + 16, x + w, y + h + 16], radius=36, fill=(0, 0, 0, 120))
    base.alpha_composite(sh)
    base.alpha_composite(R.fit_photo(photo, w, h).convert("RGBA"), (x, y))
    return y + h


def card_scene(offer: dict, seed: int) -> tuple[Image.Image, str, str | None]:
    name = short_name(offer["title"])
    bg = base_scene(seed)
    y = spaced_kicker(bg, R.W // 2, 300, name)
    y = price_pill(bg, R.W // 2, y + 30, offer["price_label"])
    photo = Path(offer["photos_local"][0])
    photo_shadow(bg, photo, ((R.W - 860) // 2, y + 40), 860, 820)
    handle_footer(bg)
    nar = f"{name}, {offer['price_label']}, link no canal!"
    return bg, nar, None  # sem legenda queimada: preço/nome já estão no card


WEEKDAYS = ["SEGUNDA-FEIRA", "TERÇA-FEIRA", "QUARTA-FEIRA", "QUINTA-FEIRA",
            "SEXTA-FEIRA", "SÁBADO", "DOMINGO"]
MONTHS = ["JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO", "JULHO",
          "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
PART = {"v1": 1, "v2": 2, "v3": 3}


def cover_scene(seed: int, key: str = "v1", day: str = "2026-09-19",
                edition: int = 1) -> tuple[Image.Image, str, str]:
    import datetime as _dt
    d = _dt.date.fromisoformat(day)
    wd = WEEKDAYS[d.weekday()]
    dateline = f"{wd} • {d.day} DE {MONTHS[d.month - 1]}"
    bg = base_scene(seed)
    y = R.kicker(bg, R.W // 2, 330, f"EDIÇÃO #{edition}")
    y = R.draw_display(bg, R.W // 2, y + 30, "ACHADINHOS", 104)
    y = R.draw_display(bg, R.W // 2, y + 10, "DO DIA", 104, accent="DIA")
    y = R.draw_center_text(bg, R.W // 2, y + 30, f"PARTE {PART.get(key, 1)} DE 3", 48,
                           fill=R.WHITE, bold=True)
    y = R.draw_center_text(bg, R.W // 2, y + 8, dateline, 40)
    R.paste_logo(bg, R.W // 2, 1200, 480)
    handle_footer(bg)
    nar = (f"Oi! Eu sou o Eco! Achadinhos desta {wd.lower()}, "
           f"parte {PART.get(key, 1)}!")
    return bg, nar, "ACHADINHOS DO DIA"


def final_scene(seed: int) -> tuple[Image.Image, str, str]:
    bg = base_scene(seed)
    y = R.draw_display(bg, R.W // 2, 300, "ENTRA NO CANAL", 92, accent="CANAL")
    card = qr_card().convert("RGBA")
    cw, ch = card.size
    scale = 560 / cw
    card = card.resize((560, int(ch * scale)), Image.LANCZOS)
    bg.alpha_composite(card, ((R.W - 560) // 2, y + 40))
    R.draw_center_text(bg, R.W // 2, y + 40 + card.height + 30,
                       "Aponta a câmera. É de graça!", 50, fill=R.WHITE, bold=True)
    handle_footer(bg)
    return bg, "Aponta a câmera pro código e entra no canal. É de graça! Te espero lá.", "ENTRA NO CANAL »"


def build(offers: list[dict], outdir: Path, key: str, seed_base: int,
          day: str = "2026-09-19", edition: int = 1) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    loopdir = eco_loop(outdir / f"eco_loop_{key}")
    parts = [cover_scene(seed_base, key, day, edition)] + \
            [card_scene(o, seed_base + 1 + i) for i, o in enumerate(offers)] + \
            [final_scene(seed_base + 5)]
    roles = ["cover", "card", "card", "card", "final"]
    scenes = []
    for i, ((bg, nar, cap), role) in enumerate(zip(parts, roles)):
        png = outdir / f"{key}s{i+1}.png"
        bg.convert("RGB").save(png)
        mp3 = outdir / f"{key}s{i+1}.mp3"
        R.tts_save(nar, mp3)
        item = {"png": png, "mp3": mp3}
        if cap:
            item["caption"] = cap
        item["mascot"] = {**ECO_POS[role], "loopdir": str(loopdir)}
        scenes.append(item)
    out = outdir / f"{key}-vitrine.mp4"
    return R.assemble(scenes, out, outdir / f"work_{key}")

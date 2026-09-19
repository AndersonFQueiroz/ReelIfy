"""Vídeos 2 (relâmpago) e 3 (achadinho): 100% locais, identidade travada."""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw

from . import config as C
from . import render as R

_EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF☀-➿⬅-⬏⚡🔥👀👇*＊#]+")


def clean_title(title: str) -> str:
    t = _EMOJI_RE.sub("", title).strip(" *-_")
    return re.sub(r"\s+", " ", t)[:80] or "Oferta do dia"


def short_name(title: str) -> str:
    t = clean_title(title)
    words = t.split()
    drop = {"olha", "esse", "essa", "preço", "preco", "oferta", "ofertaaaa",
            "imperdível", "promoção", "super"}
    kept = [w for w in words if w.lower() not in drop]
    return " ".join(kept[:6]) or t[:40]


def base_scene(seed: int) -> Image.Image:
    return R.make_bg(seed).convert("RGBA")


def price_card(base: Image.Image, y: int, offer: dict) -> int:
    d = ImageDraw.Draw(base)
    _, txt = R.fonts(60, 54)
    bb = d.textbbox((0, 0), f"de {offer['original_label']}", font=txt)
    d.text(((R.W - (bb[2] - bb[0])) / 2, y), f"de {offer['original_label']}", font=txt, fill=R.MUTED)
    y += (bb[3] - bb[1]) + 6
    y = R.draw_display(base, R.W // 2, y, offer["price_label"], 120, accent=None)
    save = offer["original_price"] - offer["price"]
    if save > 0:
        y = R.draw_center_text(base, R.W // 2, y + 14,
                               f"ECONOMIA DE R$ {save:,.0f}".replace(",", "."),
                               46, fill=R.CYAN, bold=True)
    return y


HOOKS_FLASH = ["{hook} {name}, com {disc} por cento de desconto!",
               "Segura essa: {name} com {disc} por cento OFF!",
               "Achado de verdade: {name}, {disc} por cento mais barato!"]


def handle_footer(base: Image.Image) -> None:
    R.draw_center_text(base, R.W // 2, R.SAFE_BOT - 130, f"👇 {C.HANDLE}", 44, fill=R.CYAN, bold=True)


def scene_png(offer: dict, kind: str, idx: int, outdir: Path, off: int = 0) -> tuple[Path, str, str]:
    """Retorna (png, narração, legenda)."""
    name = short_name(offer["title"])
    disc = offer["discount_pct"]
    ben = offer.get("benefits") or []
    photo = Path(offer["photos_local"][min(idx, len(offer["photos_local"]) - 1)])

    if kind == "flash":
        if idx == 0:
            bg = base_scene(11 + off)
            y = R.kicker(bg, R.W // 2, 420, "⚡ OFERTA RELÂMPAGO")
            y = R.draw_display(bg, R.W // 2, y + 60, f"-{disc}% HOJE", 110, accent=f"{disc}%")
            R.draw_center_text(bg, R.W // 2, y + 40, name, 46, fill=R.WHITE, bold=True)
            handle_footer(bg)
            nar = HOOKS_FLASH[off % 3].format(hook=offer["hook"], name=name, disc=disc)
            cap = f"🔥 -{disc}% HOJE"
        elif idx == 1:
            bg = base_scene(12 + off)
            y = R.draw_center_text(bg, R.W // 2, 300, name, 44, fill=R.WHITE, bold=True)
            bg.alpha_composite(R.fit_photo(photo, 880, 760).convert("RGBA"), (100, y + 30))
            y = price_card(bg, y + 830, offer)
            handle_footer(bg)
            btxt = (" " + ben[0]) if ben else ""
            nar = f"De {offer['original_label']} por apenas {offer['price_label']}.{btxt}"
            cap = f"De {offer['original_label']} → {offer['price_label']}"
        else:
            bg = base_scene(13 + off)
            y = R.draw_display(bg, R.W // 2, 560, "SÓ ENQUANTO", 96)
            y = R.draw_display(bg, R.W // 2, y + 20, "DURAR O ESTOQUE", 96, accent="ESTOQUE")
            R.draw_center_text(bg, R.W // 2, y + 60, "Link com desconto tá no canal,\ncorre que acaba!", 48, fill=R.WHITE)
            handle_footer(bg)
            nar = "Só enquanto durar o estoque! Link com desconto tá no canal, corre que acaba!"
            cap = "Corre que acaba! 👇"
    else:  # top
        if idx == 0:
            bg = base_scene(21 + off)
            y = R.kicker(bg, R.W // 2, 400, "ACHADINHO DO DIA 🔥")
            bg.alpha_composite(R.fit_photo(photo, 880, 720).convert("RGBA"), (100, y + 50))
            y = R.draw_center_text(bg, R.W // 2, y + 820, name, 46, fill=R.WHITE, bold=True)
            handle_footer(bg)
            nar = f"Achadinho do dia: {name}!"
            cap = "ACHADINHO DO DIA 🔥"
        elif idx == 1:
            bg = base_scene(22 + off)
            y = R.draw_display(bg, R.W // 2, 380, "POR QUE VALE", 92, accent="VALE")
            bullets = ben[:3] if ben else [f"{disc}% de desconto", "Oferta verificada hoje"]
            for b in bullets:
                y = R.draw_center_text(bg, R.W // 2, y + 50, f"✓ {b}", 48, fill=R.WHITE)
            bg.alpha_composite(R.fit_photo(photo, 700, 560).convert("RGBA"), (190, y + 50))
            handle_footer(bg)
            nar = "Olha por que vale a pena: " + ". ".join(bullets) + "."
            cap = "Vale cada centavo ✓"
        else:
            bg = base_scene(23 + off)
            y = R.draw_center_text(bg, R.W // 2, 420, "MENOR PREÇO", 54, fill=R.MUTED, bold=True)
            y = price_card(bg, y + 20, offer)
            R.draw_center_text(bg, R.W // 2, y + 40, "Link com desconto tá no canal!", 50, fill=R.WHITE, bold=True)
            handle_footer(bg)
            nar = f"Menor preço: de {offer['original_label']} por {offer['price_label']}. Link tá no canal!"
            cap = offer["price_label"]
    png = outdir / f"{kind}{idx}.png"
    bg.convert("RGB").save(png)
    return png, nar, cap


def build(offer: dict, kind: str, outdir: Path) -> Path:
    import datetime as _dt
    off = _dt.date.fromisoformat(offer.get('day', '2026-01-01')).toordinal() % 50
    """kind: 'flash' (V2) ou 'top' (V3)."""
    outdir.mkdir(parents=True, exist_ok=True)
    scenes = []
    for i in range(3):
        png, nar, cap = scene_png(offer, kind, i, outdir, off)
        mp3 = outdir / f"{kind}{i}.mp3"
        R.tts_save(nar, mp3)
        scenes.append({"png": png, "mp3": mp3, "caption": cap})
    out = outdir / ("video2-relampago.mp4" if kind == "flash" else "video3-achadinho.mp4")
    return R.assemble(scenes, out, outdir / "work")

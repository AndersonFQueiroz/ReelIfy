"""Monta pack.json: legendas, hashtags, link afiliado, 1º comentário, capas.

REGRA DURA: sem affiliate_url válido → exit 2 (nada é entregue).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from . import config as C
from .video_cinetico import clean_title, short_name

TAGS_BASE = ["achadinhos", "ofertas", "promocao", "desconto", "ofertasdodia", "barato"]
TAGS_MKT = {"mercadolivre": ["mercadolivre", "achadinhosml"],
            "shopee": ["shopee", "achadinhosshopee"]}


def build_pack(day_dir: Path, videos: dict[str, Path]) -> Path:
    offer = json.loads((day_dir / "offer.json").read_text(encoding="utf-8"))
    aff = (offer.get("affiliate_url") or "").strip()
    if not aff.startswith("http"):
        print("FALHA DURA: pack sem link de afiliado.", file=sys.stderr)
        raise SystemExit(2)
    name = short_name(offer["title"])
    tags = " ".join(f"#{t}" for t in [*TAGS_BASE, *TAGS_MKT.get(offer["marketplace"], [])])
    caption = (
        f"🔥 ACHADINHO DO DIA — {name}\n"
        f"✅ De {offer['original_label']} por {offer['price_label']} (-{offer['discount_pct']}%)\n"
        f"👉 Link com desconto: {aff}\n"
        f"📲 Mais ofertas no canal: t.me/cacaofertasofcBR\n"
        f"{tags}\n{C.HANDLE}")
    first_comment = (f"⚠️ O preço pode mudar a qualquer hora! Garante o teu aqui 👉 {aff}")
    covers = {}
    for key, mp4 in videos.items():
        src = None
        for cand in [day_dir / f"v1s1.png", day_dir / f"{'flash' if key=='v2' else 'top'}0.png"]:
            if cand.exists():
                src = cand
                break
        dst = day_dir / f"capa-{key}.png"
        if src:
            shutil.copy(src, dst)
            covers[key] = str(dst)
    pack = {"day": offer["day"], "caption": caption, "first_comment": first_comment,
            "affiliate_url": aff, "videos": {k: str(v) for k, v in videos.items()},
            "covers": covers, "title": clean_title(offer["title"])[:80]}
    (day_dir / "pack.json").write_text(json.dumps(pack, ensure_ascii=False, indent=1), encoding="utf-8")
    return day_dir / "pack.json"

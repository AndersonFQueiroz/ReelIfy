"""Pack triplo: cada vídeo tem sua legenda (3 produtos + 3 links) + 1º comentário.

REGRA DURA: 9 links distintos válidos ou exit 2.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from . import config as C
from .video_cinetico import short_name

TAGS_BASE = ["achadinhos", "ofertas", "promocao", "desconto", "ofertasdodia", "barato"]
TAGS_MKT = {"mercadolivre": ["mercadolivre", "achadinhosml"],
            "shopee": ["shopee", "achadinhosshopee"]}


def caption_for(offers: list[dict]) -> tuple[str, str]:
    lines = ["🔥 ACHADINHOS DO DIA"]
    for i, o in enumerate(offers, 1):
        lines.append(f"{i}⃣ {short_name(o['title'])} — {o['price_label']} (-{o['discount_pct']}%)\n👉 {o['affiliate_url']}")
    tags = set(TAGS_BASE)
    for o in offers:
        tags.update(TAGS_MKT.get(o["marketplace"], []))
    lines.append("📲 Mais ofertas: t.me/cacaofertasofcBR")
    lines.append(" ".join(f"#{t}" for t in sorted(tags)))
    lines.append(C.HANDLE)
    first = "⚠️ Preços podem mudar! Garante aqui:\n" + "\n".join(
        f"{i}⃣ {o['affiliate_url']}" for i, o in enumerate(offers, 1))
    return "\n".join(lines), first


def build_pack(day_dir: Path, videos: dict[str, Path]) -> Path:
    data = json.loads((day_dir / "offers_day.json").read_text(encoding="utf-8"))
    groups = data["groups"]
    links = [o["affiliate_url"] for v in groups.values() for o in v]
    if len(links) != len(set(links)) or not all(l.startswith("http") for l in links):
        print("FALHA DURA: links duplicados ou inválidos.", file=sys.stderr)
        raise SystemExit(2)
    captions, firsts, covers = {}, {}, {}
    for key in videos:
        cap, first = caption_for(groups[key])
        captions[key], firsts[key] = cap, first
        cand = day_dir / f"{key}s1.png"
        src = cand if cand.exists() else None
        if src and src.exists():
            dst = day_dir / f"capa-{key}.png"
            shutil.copy(src, dst)
            covers[key] = str(dst)
    pack = {"day": data["day"], "captions": captions, "first_comments": firsts,
            "videos": {k: str(v) for k, v in videos.items()}, "covers": covers,
            "affiliates": {k: [o["affiliate_url"] for o in groups[k]] for k in videos}}
    (day_dir / "pack.json").write_text(json.dumps(pack, ensure_ascii=False, indent=1), encoding="utf-8")
    return day_dir / "pack.json"

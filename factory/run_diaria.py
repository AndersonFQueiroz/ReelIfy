"""Orquestrador: 3 vitrines (9 produtos) → pack triplo → QC → Telegram.

Buffer SÓ com aprovação explícita (post_buffer --only). Nunca auto.
Uso: python3 -m factory.run_diaria [--date AAAA-MM-DD]
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
import time
from pathlib import Path

from . import config as C
from . import oferta_do_dia, pack_redes, pack_telegram, qc, video_vitrine

T0 = time.time()
LABELS = {"v1": "VITRINE 1", "v2": "VITRINE 2", "v3": "VITRINE 3"}


def log(msg: str) -> None:
    print(f"[+{time.time()-T0:6.1f}s] {msg}", flush=True)


def main(argv: list[str]) -> int:
    day = argv[0] if argv and len(argv[0]) == 10 else _dt.date.today().isoformat()
    log(f"Fábrica vitrine — {day}")
    if oferta_do_dia.main([day]) != 0:
        return 1
    day_dir = C.FACTORY_DATA / day
    groups = json.loads((day_dir / "offers_day.json").read_text(encoding="utf-8"))["groups"]
    seed_base = _dt.date.fromisoformat(day).toordinal() % 50

    videos = {}
    for key in ("v1", "v2", "v3"):
        if key not in groups:
            continue
        log(f"{LABELS[key]}: " + " | ".join(o["title"][:28] for o in groups[key]))
        videos[key] = video_vitrine.build(groups[key], day_dir, key, seed_base + 10 * int(key[1]))
        log(f"{key} pronto: {videos[key].name}")
    if not videos:
        return 1
    for p in videos.values():
        if not (p.exists() and p.stat().st_size > 100_000):
            print(f"FALHA: vídeo inválido {p}", file=sys.stderr)
            return 1
    pack = pack_redes.build_pack(day_dir, videos)
    log(f"Pack: {pack.name}")
    log("Portão QC...")
    if qc.main(day) != 0:
        log("QC FALHOU — nada enviado.")
        return 1
    rc_tg = pack_telegram.main(day)
    log(f"Telegram rc={rc_tg} (aguardando aprovação)")
    log(f"FIM rc={rc_tg}")
    return 0 if rc_tg in (0, 3) else rc_tg


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

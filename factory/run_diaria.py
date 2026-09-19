"""Orquestrador da fábrica diária. Uso: python3 -m factory.run_diaria [--date AAAA-MM-DD]"""
from __future__ import annotations

import datetime as _dt
import json
import sys
import time
from pathlib import Path

from . import config as C
from . import oferta_do_dia, pack_redes, pack_telegram, post_buffer, video_cinetico, video_ia

T0 = time.time()


def log(msg: str) -> None:
    print(f"[+{time.time()-T0:6.1f}s] {msg}", flush=True)


def main(argv: list[str]) -> int:
    day = argv[0] if argv and len(argv[0]) == 10 else _dt.date.today().isoformat()
    log(f"Fábrica iniciada — {day}")
    rc = oferta_do_dia.main([day])
    if rc != 0:
        return rc
    day_dir = C.FACTORY_DATA / day
    offer = json.loads((day_dir / "offer.json").read_text(encoding="utf-8"))
    log(f"Oferta: {offer['title'][:50]} -{offer['discount_pct']}% [{offer['origem']}]")

    log("Vídeo 1 (POV/IA)...")
    v1, modo = video_ia.build(offer, day_dir)
    log(f"V1 pronto ({modo}): {v1.name}")
    log("Vídeo 2 (relâmpago)...")
    v2 = video_cinetico.build(offer, "flash", day_dir)
    log(f"V2 pronto: {v2.name}")
    log("Vídeo 3 (achadinho)...")
    v3 = video_cinetico.build(offer, "top", day_dir)
    log(f"V3 pronto: {v3.name}")

    for p in (v1, v2, v3):
        if not (p.exists() and p.stat().st_size > 100_000):
            print(f"FALHA: vídeo inválido {p}", file=sys.stderr)
            return 1
    pack = pack_redes.build_pack(day_dir, {"v1": v1, "v2": v2, "v3": v3})
    log(f"Pack: {pack.name}")
    rc_tg = pack_telegram.main(day)
    log(f"Telegram rc={rc_tg} (cobre Kwai + backup)")
    log("Auto-post Buffer (IG/TikTok/YouTube)...")
    rc_buf = post_buffer.main(day)
    log(f"Buffer rc={rc_buf}")
    rc = 0 if rc_buf in (0, 3) else rc_buf
    log(f"FIM rc={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

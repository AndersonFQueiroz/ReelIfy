"""Portão de qualidade: bloqueia o envio ao Telegram se algo estiver fora do padrão.

Checa: specs do mp4 (720x1280, h264+aac, 15-90s, >100KB), oferta
(desconto >=5%, afiliado válido), pack (legenda com link, vídeos existem),
narração (texto auditável, sem emoji/URL).
Uso: python3 -m factory.qc --date AAAA-MM-DD | exit 0 ok / 1 falha
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from . import config as C

_ERRORS: list[str] = []


def fail(msg: str) -> None:
    _ERRORS.append(msg)
    print(f"QC FALHA: {msg}")


def ffprobe(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-hide_banner", "-loglevel", "error", "-show_entries",
         "format=duration,size:stream=width,height,codec_name,codec_type",
         "-of", "json", str(path)], capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout or "{}")


def check_video(key: str, path: Path) -> None:
    if not path.exists() or path.stat().st_size < 100_000:
        fail(f"{key}: arquivo ausente ou minúsculo")
        return
    try:
        info = ffprobe(path)
    except Exception as exc:
        fail(f"{key}: ffprobe erro ({exc})")
        return
    dur = float((info.get("format") or {}).get("duration") or 0)
    if not 15 <= dur <= 90:
        fail(f"{key}: duração {dur:.1f}s fora de 15-90s")
    streams = {(s.get("codec_type"), s.get("codec_name")) for s in info.get("streams", [])}
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
    if (v.get("width"), v.get("height")) != (720, 1280):
        fail(f"{key}: resolução {v.get('width')}x{v.get('height')} ≠ 720x1280")
    if v.get("codec_name") != "h264":
        fail(f"{key}: vídeo {v.get('codec_name')} ≠ h264")
    if a.get("codec_name") != "aac":
        fail(f"{key}: áudio {a.get('codec_name')} ≠ aac")


def check_narration(day_dir: Path) -> None:
    for txt in sorted(day_dir.glob("*.txt")) + sorted(day_dir.glob("v*.txt")):
        t = txt.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"[\U0001F000-\U0001FAFF☀-➿]", t):
            fail(f"narração {txt.name}: contém emoji")
        if "http" in t:
            fail(f"narração {txt.name}: contém URL")
        if len(t.split()) > 40:
            fail(f"narração {txt.name}: longa demais ({len(t.split())} palavras)")


def main(day: str) -> int:
    day_dir = C.FACTORY_DATA / day
    _ERRORS.clear()
    try:
        offer = json.loads((day_dir / "offer.json").read_text(encoding="utf-8"))
    except Exception:
        fail("offer.json ausente/ilegível")
        return 1
    if (offer.get("discount_pct") or 0) < 5:
        fail(f"desconto {offer.get('discount_pct')}% < 5%")
    if not str(offer.get("affiliate_url") or "").startswith("http"):
        fail("affiliate_url inválido")
    if not list(day_dir.glob("foto*.jpg")):
        fail("sem fotos do anúncio")
    try:
        pack = json.loads((day_dir / "pack.json").read_text(encoding="utf-8"))
    except Exception:
        fail("pack.json ausente/ilegível — rode pack antes do QC")
        return 1
    if offer.get("affiliate_url") not in pack.get("caption", ""):
        fail("legenda sem o link afiliado")
    for key, vpath in (pack.get("videos") or {}).items():
        check_video(key, Path(vpath))
    check_narration(day_dir)
    if _ERRORS:
        print(f"QC: {len(_ERRORS)} falha(s) — ENVIO BLOQUEADO.")
        return 1
    print("QC OK — liberado p/ Telegram.")
    return 0


if __name__ == "__main__":
    day = sys.argv[sys.argv.index("--date") + 1] if "--date" in sys.argv else sys.argv[1]
    raise SystemExit(main(day))

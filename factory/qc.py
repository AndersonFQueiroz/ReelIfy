"""Portão de qualidade: 9 links distintos + specs + narração. Bloqueia envio se falhar."""
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
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), {})
    if (v.get("width"), v.get("height")) != (720, 1280):
        fail(f"{key}: resolução {v.get('width')}x{v.get('height')} ≠ 720x1280")
    if v.get("codec_name") != "h264":
        fail(f"{key}: vídeo {v.get('codec_name')} ≠ h264")
    if a.get("codec_name") != "aac":
        fail(f"{key}: áudio {a.get('codec_name')} ≠ aac")


def main(day: str) -> int:
    day_dir = C.FACTORY_DATA / day
    _ERRORS.clear()
    try:
        data = json.loads((day_dir / "offers_day.json").read_text(encoding="utf-8"))
        groups = data["groups"]
    except Exception:
        fail("offers_day.json ausente/ilegível")
        return 1
    offers = [o for v in groups.values() for o in v]
    links = [o.get("affiliate_url", "") for o in offers]
    if len(links) < 3 or len(set(links)) != len(links):
        fail("links duplicados ou poucos")
    for o in offers:
        if not str(o.get("affiliate_url", "")).startswith("http"):
            fail(f"link inválido: {o.get('title', '')[:30]}")
        if (o.get("discount_pct") or 0) < 5:
            fail(f"desconto <5%: {o.get('title', '')[:30]}")
        if not (day_dir / Path(o.get("photos_local", [""])[0]).name).exists():
            fail(f"foto ausente: {o.get('title', '')[:30]}")
    try:
        pack = json.loads((day_dir / "pack.json").read_text(encoding="utf-8"))
    except Exception:
        fail("pack.json ausente — rode pack antes do QC")
        return 1
    for key, vpath in (pack.get("videos") or {}).items():
        check_video(key, Path(vpath))
        for link in (pack.get("affiliates") or {}).get(key, []):
            if link not in pack.get("captions", {}).get(key, ""):
                fail(f"legenda {key} sem link")
    for txt in sorted(day_dir.glob("*.txt")):
        t = txt.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"[\U0001F000-\U0001FAFF☀-➿]", t):
            fail(f"narração {txt.name}: emoji")
        if "http" in t:
            fail(f"narração {txt.name}: URL")
        if len(t.split()) > 40:
            fail(f"narração {txt.name}: longa ({len(t.split())} palavras)")
    if _ERRORS:
        print(f"QC: {len(_ERRORS)} falha(s) — ENVIO BLOQUEADO.")
        return 1
    print("QC OK — liberado p/ Telegram.")
    return 0


if __name__ == "__main__":
    day = sys.argv[sys.argv.index("--date") + 1] if "--date" in sys.argv else sys.argv[1]
    raise SystemExit(main(day))

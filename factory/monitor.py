"""Monitor pós-slot: confere se o Short do YouTube entrou no ar.

Compara os videoIds da aba /shorts com os já conhecidos. Uso:
  python3 -m factory.monitor --expect 6aaee4f1  # checa se há vídeo novo
Retorna 0 (novo no ar) / 1 (nada novo — investigar/repostar).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}
STATE = Path(__file__).resolve().parent.parent / "data" / "factory" / "yt_known.json"


def known_ids() -> set[str]:
    try:
        return set(json.loads(STATE.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_ids(ids: set[str]) -> None:
    STATE.write_text(json.dumps(sorted(ids)), encoding="utf-8")


def channel_shorts(handle: str = "cacaofertasofcBR1") -> set[str]:
    r = requests.get(f"https://www.youtube.com/@{handle}/shorts", headers=UA, timeout=30)
    r.raise_for_status()
    return set(re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', r.text))


def main() -> int:
    current = channel_shorts()
    known = known_ids()
    new = current - known
    print(f"conhecidos={len(known)} atuais={len(current)} novos={len(new)}")
    if new:
        print("NOVO NO AR:", sorted(new))
        save_ids(current)
        return 0
    print("Nada novo — se passou do slot, republicar.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

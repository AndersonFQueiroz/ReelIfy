"""Sobe mp4 para URL pública (Buffer exige link público, não upload direto).

Catbox (permanente) → fallback Litterbox (72h, suficiente p/ publicar).
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

from . import config as C

_TIMEOUT = 120


def _post(files: dict, data: dict, url: str) -> str | None:
    try:
        r = requests.post(url, files=files, data=data, timeout=_TIMEOUT)
        body = r.text.strip()
        if r.ok and body.startswith("https://"):
            return body
        print(f"host falhou ({url}): {r.status_code} {body[:100]}")
    except Exception as exc:
        print(f"host erro ({url}): {exc}")
    return None


def upload(path: Path) -> str | None:
    with open(path, "rb") as f:
        blob = f.read()
    url = _post({"fileToUpload": (path.name, blob, "video/mp4")},
                {"reqtype": "fileupload"}, "https://catbox.moe/user/api.php")
    if url:
        return url
    url = _post({"fileToUpload": (path.name, blob, "video/mp4")},
                {"reqtype": "fileupload", "time": "72h"}, "https://litterbox.catbox.moe/resources/internals/api.php")
    return url


if __name__ == "__main__":
    out = upload(Path(sys.argv[1]))
    print(out or "FALHA")
    raise SystemExit(0 if out else 1)

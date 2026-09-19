"""Entrega o pack no Telegram privado do dono via Bot API.

Requer: TELEGRAM_BOT_TOKEN + TELEGRAM_OWNER_CHAT_ID no .env.
Sem credenciais: só salva o pack e imprime o caminho (exit 3, não é erro fatal).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

from . import config as C

ORDER = [("v1", "🎬 VÍDEO 1 — POV apresentando"),
         ("v2", "⚡ VÍDEO 2 — Oferta relâmpago"),
         ("v3", "🔥 VÍDEO 3 — Top achadinho")]


def main(day: str) -> int:
    day_dir = C.FACTORY_DATA / day
    pack = json.loads((day_dir / "pack.json").read_text(encoding="utf-8"))
    token, chat = C.env("TELEGRAM_BOT_TOKEN"), C.env("TELEGRAM_OWNER_CHAT_ID")
    if not (token and chat):
        print(f"SEM TELEGRAM configurado — pack pronto em {day_dir}/pack.json (exit 3).")
        return 3
    api = f"https://api.telegram.org/bot{token}"
    s = requests.Session()
    msg_ids: dict[str, int] = {}

    def _send(payload: dict, files: dict | None = None) -> int:
        if files:
            r = s.post(f"{api}/sendVideo", data=payload, files=files, timeout=180)
        else:
            r = s.post(f"{api}/sendMessage", json=payload, timeout=30)
        r.raise_for_status()
        return r.json()["result"]["message_id"]

    msg_ids["header"] = _send({"chat_id": chat, "text": head, "parse_mode": "Markdown",
                               "disable_web_page_preview": True}) if (head := (
        f"📦 *Pack 3 vídeos — {pack['day']}*\n{pack['title']}\n"
        f"🔗 {pack['affiliate_url']}")) else 0
    for key, label in ORDER:
        vpath = pack["videos"][key]
        with open(vpath, "rb") as f:
            msg_ids[key] = _send(
                {"chat_id": chat, "caption": f"{label}\n\n{pack['caption'][:900]}"},
                {"video": (Path(vpath).name, f, "video/mp4")})
    msg_ids["comment"] = _send(
        {"chat_id": chat,
         "text": f"📌 *Texto do 1º comentário* (colar após postar):\n{pack['first_comment']}"})
    pack["telegram_msg_ids"] = msg_ids
    (day_dir / "pack.json").write_text(json.dumps(pack, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Pack entregue no Telegram.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))

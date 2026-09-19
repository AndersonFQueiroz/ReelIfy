"""Config compartilhada da fábrica (lê .env do repo, sem novas dependências)."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "assets"
FONTS = ASSETS / "fonts"
FACTORY_DATA = REPO_ROOT / "data" / "factory"

FONT_DISPLAY = FONTS / "ArchivoBlack.ttf"
FONT_TEXT = FONTS / "Poppins-Regular.ttf"
FONT_TEXT_MED = FONTS / "Poppins-Medium.ttf"
FONT_TEXT_BOLD = FONTS / "Poppins-SemiBold.ttf"

HANDLE = "@cacaofertasofcbr"
VOICE_MAIN = "pt-BR-FranciscaNeural"
VOICE_FALLBACKS = ("pt-BR-ThalitaMultilingualNeural", "pt-BR-AntonioNeural")


def _load_dotenv() -> None:
    env = REPO_ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()


def _prefer_ipv4() -> None:
    """Rede local com IPv6 pendurado: força IPv4 em todo requests."""
    import socket
    _orig = socket.getaddrinfo

    def _patched(host, port, *args, **kwargs):
        try:
            infos = _orig(host, port, *args, **kwargs)
        except Exception:
            return _orig(host, port, *args, **kwargs)
        v4 = [i for i in infos if i[0] == socket.AF_INET]
        return v4 or infos

    socket.getaddrinfo = _patched


_prefer_ipv4()


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)

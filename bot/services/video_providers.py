"""Registro do único motor de vídeo suportado: YouTube Create via ADB."""
from __future__ import annotations

from dataclasses import dataclass
import shutil
from typing import Any, Protocol

from config.settings import settings


class VideoProvider(Protocol):
    provider_id: str
    display_name: str

    def is_available(self) -> bool: ...

    def supports(self, job: Any) -> bool: ...


@dataclass(frozen=True)
class ADBYouTubeCreateProvider:
    provider_id: str = "adb_youtube_create"
    display_name: str = "YouTube Create no celular"

    def is_available(self) -> bool:
        # O MockDevice mantém os testes independentes do hardware físico.
        return settings.mock_device or bool(settings.adb_device_serial) or shutil.which("adb") is not None

    def supports(self, job: Any) -> bool:
        return True


def available_video_providers() -> list[VideoProvider]:
    provider = ADBYouTubeCreateProvider()
    return [provider] if provider.is_available() else []


def provider_names() -> dict[str, str]:
    return {provider.provider_id: provider.display_name for provider in available_video_providers()}


def is_provider_available(provider_id: str) -> bool:
    return provider_id == "adb_youtube_create" and bool(provider_names())

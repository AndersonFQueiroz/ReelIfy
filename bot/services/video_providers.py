"""Registro de motores de vídeo com política explícita de custo."""
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
        # Em modo mock, o pipeline atual continua sendo testável sem hardware.
        return settings.mock_device or bool(settings.adb_device_serial) or shutil.which("adb") is not None

    def supports(self, job: Any) -> bool:
        return True


@dataclass(frozen=True)
class LocalFFmpegProvider:
    provider_id: str = "local_ffmpeg"
    display_name: str = "Renderização local"

    def is_available(self) -> bool:
        return shutil.which("ffmpeg") is not None

    def supports(self, job: Any) -> bool:
        return self.is_available()


def available_video_providers() -> list[VideoProvider]:
    providers: list[VideoProvider] = [ADBYouTubeCreateProvider(), LocalFFmpegProvider()]
    return [provider for provider in providers if provider.is_available()]


def provider_names() -> dict[str, str]:
    return {provider.provider_id: provider.display_name for provider in available_video_providers()}


def is_provider_available(provider_id: str) -> bool:
    return provider_id in provider_names()

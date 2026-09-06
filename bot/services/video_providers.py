"""Registro de motores de vídeo com política explícita de custo."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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


@dataclass(frozen=True)
class PollinationsVideoProvider:
    """Gera um clipe MP4 via Pollinations; requer chave configurada pelo operador."""

    provider_id: str = "pollinations_video"
    display_name: str = "Pollinations AI (API)"

    def is_available(self) -> bool:
        return bool(settings.pollinations_api_key)

    def supports(self, job: Any) -> bool:
        return self.is_available()

    def render(self, job: Any, output_path: Any) -> None:
        from urllib.error import HTTPError, URLError
        from urllib.parse import quote, urlencode
        from urllib.request import Request, urlopen

        if not self.is_available():
            raise RuntimeError("POLLINATIONS_API_KEY não configurada.")

        prompt = (
            "Vídeo vertical 9:16 para um anúncio curto de produto. "
            f"Produto: {job.product.name}. "
            f"Benefícios: {job.product.description}. "
            f"Estilo: {job.style_id}. "
            f"Cenas e texto-base: {job.script.full_text}. "
            "Mostre o produto em uso de forma comercial, natural e realista; "
            "não invente marcas, selos, avaliações ou características que não foram informadas; "
            "não exiba texto ilegível nem marcas de água."
        )
        params = urlencode({
            "model": settings.pollinations_video_model,
            "duration": settings.pollinations_video_duration,
            "aspectRatio": "9:16",
        })
        url = f"https://gen.pollinations.ai/video/{quote(prompt, safe='')}?{params}"
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {settings.pollinations_api_key}",
                "User-Agent": "ReelIfy/1.0",
            },
        )
        try:
            with urlopen(request, timeout=settings.pollinations_timeout_seconds) as response:
                content_type = response.headers.get("Content-Type", "")
                video_bytes = response.read()
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Pollinations HTTP {error.code}: {details}") from error
        except URLError as error:
            raise RuntimeError(f"Falha de conexão com Pollinations: {error.reason}") from error

        if len(video_bytes) < 1024 or ("video" not in content_type and b"ftyp" not in video_bytes[:512]):
            raise RuntimeError("Pollinations não retornou um MP4 válido.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(video_bytes)


@dataclass(frozen=True)
class HuggingFaceVideoProvider:
    """Gera vídeo image-to-video pelo Hugging Face Inference Providers."""
    provider_id: str = "huggingface_video"
    display_name: str = "Hugging Face (Wan 2.2)"
    def is_available(self) -> bool:
        return bool(settings.huggingface_token)
    def supports(self, job: Any) -> bool:
        return self.is_available()
    def render(self, job: Any, output_path: Any) -> None:
        try:
            from huggingface_hub import InferenceClient
        except ImportError as error:
            raise RuntimeError("Dependência huggingface_hub não instalada.") from error
        if not self.is_available():
            raise RuntimeError("HF_TOKEN não configurado.")
        prompt = (
            "Vídeo vertical 9:16 para anúncio curto de produto. "
            f"Mostre o produto {job.product.name} em uso de forma natural e comercial. "
            f"Benefícios: {job.product.description}. "
            f"Estilo: {job.style_id}. "
            f"Roteiro visual: {job.script.full_text}. "
            "Preserve a aparência, cores, embalagem e marca visíveis na imagem; "
            "não invente características, selos, avaliações ou texto ilegível."
        )
        client = InferenceClient(
            provider=settings.huggingface_video_provider,
            api_key=settings.huggingface_token,
            timeout=settings.huggingface_timeout_seconds,
        )
        image_path = next(
            (Path(path) for path in (job.product.photos_local_paths or [job.product.photo_local_path])
             if path and Path(path).exists()),
            None,
        )
        if image_path:
            video_bytes = client.image_to_video(
                str(image_path),
                model=settings.huggingface_video_model,
                prompt=prompt,
                num_frames=settings.huggingface_video_frames,
            )
        else:
            video_bytes = client.text_to_video(
                prompt,
                model=settings.huggingface_video_model,
                num_frames=settings.huggingface_video_frames,
            )
        if not isinstance(video_bytes, (bytes, bytearray)) or len(video_bytes) < 1024:
            raise RuntimeError("Hugging Face não retornou um vídeo válido.")
        if b"ftyp" not in bytes(video_bytes[:2048]):
            raise RuntimeError("Hugging Face não retornou um MP4 compatível.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(bytes(video_bytes))
def available_video_providers() -> list[VideoProvider]:
    providers: list[VideoProvider] = [ADBYouTubeCreateProvider(), LocalFFmpegProvider(), PollinationsVideoProvider(), HuggingFaceVideoProvider()]
    return [provider for provider in providers if provider.is_available()]


def provider_names() -> dict[str, str]:
    return {provider.provider_id: provider.display_name for provider in available_video_providers()}


def is_provider_available(provider_id: str) -> bool:
    return provider_id in provider_names()

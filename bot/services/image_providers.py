"""Provedores de imagem do agente, sem habilitar cobrança automaticamente."""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional, Protocol
import uuid

from config.settings import settings
from bot.services.gemini_service import gemini_service


class ImageProvider(Protocol):
    provider_id: str

    def is_available(self) -> bool: ...

    async def generate(self, prompt: str) -> Optional[str]: ...


class GeminiImageProvider:
    provider_id = "gemini_image"

    def is_available(self) -> bool:
        return bool(settings.gemini_image_model and gemini_service._client)

    async def generate(self, prompt: str) -> Optional[str]:
        if not self.is_available():
            return None
        try:
            response = await gemini_service._client.aio.models.generate_content(
                model=settings.gemini_image_model,
                contents=prompt,
                config={"response_modalities": ["IMAGE"]},
            )
            for candidate in getattr(response, "candidates", []) or []:
                for part in getattr(getattr(candidate, "content", None), "parts", []) or []:
                    inline = getattr(part, "inline_data", None)
                    data = getattr(inline, "data", None) if inline else None
                    if data:
                        if isinstance(data, str):
                            data = base64.b64decode(data)
                        output = settings.media_inputs_dir / f"generated_{uuid.uuid4().hex[:8]}.png"
                        output.write_bytes(data)
                        return str(output)
        except Exception:
            return None
        return None


image_provider: ImageProvider = GeminiImageProvider()

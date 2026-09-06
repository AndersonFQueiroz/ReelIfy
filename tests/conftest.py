"""
ReelIfy — Configuração global de testes.
Detecta automaticamente a disponibilidade de hardware (celular slave + notebook 24/7).
"""
import os
import pytest


HARDWARE_AVAILABLE = os.getenv("MOCK_DEVICE", "True").lower() in ("false", "0", "no")


def hardware_required(reason=""):
    """Decorator para pular testes que exigem hardware físico."""
    default_msg = (
        "⚠️  HARDWARE NÃO DISPONÍVEL — Este teste requer o celular Android (slave) "
        "conectado via ADB e o notebook 24/7 ligado. "
        "No momento, apenas o roteiro gerado pela IA está disponível. "
        "A geração completa de vídeos será habilitada quando o setup físico estiver pronto."
    )
    return pytest.mark.skipif(
        not HARDWARE_AVAILABLE,
        reason=reason or default_msg,
    )

"""
Emulador / Mock de Dispositivo Android via ADB.
Permite testar 100% do pipeline de automação sem necessidade de celular físico ou notebook conectado.
"""
import logging
import time
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)


class MockDevice:
    """Simula um aparelho celular conectado via ADB."""

    def __init__(self, serial: str = "mock-emulator-1080x2400"):
        self.serial = serial
        self.is_screen_on = True
        self.current_app = None
        logger.info(f"[MOCK ADB] Dispositivo virtual inicializado ({self.serial})")

    def wake_and_unlock(self) -> bool:
        logger.info("[MOCK ADB] Acordando tela e destrancando aparelho virtual...")
        self.is_screen_on = True
        time.sleep(0.5)
        return True

    def push_file(self, local_path: str, remote_path: str) -> bool:
        logger.info(f"[MOCK ADB] Transferindo arquivo (adb push): {local_path} -> {remote_path}")
        time.sleep(0.5)
        return True

    def pull_file(self, remote_path: str, local_path: str) -> bool:
        logger.info(f"[MOCK ADB] Baixando vídeo gerado (adb pull): {remote_path} -> {local_path}")
        time.sleep(1.0)
        # Criar um arquivo MP4 fictício para validar o pipeline de entrega
        dest = Path(local_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            with open(dest, "wb") as f:
                # Cabeçalho MP4 mínimo para teste
                f.write(b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2mp41\x00\x00\x00\x08free")
        return True

    def launch_app(self, package_name: str) -> bool:
        logger.info(f"[MOCK ADB] Abrindo aplicativo: {package_name}")
        self.current_app = package_name
        time.sleep(1.0)
        return True

    def stop_app(self, package_name: str) -> bool:
        logger.info(f"[MOCK ADB] Fechando aplicativo: {package_name}")
        if self.current_app == package_name:
            self.current_app = None
        time.sleep(0.3)
        return True

    def tap(self, x: int, y: int) -> bool:
        logger.info(f"[MOCK ADB] Toque na tela (tap): Coordenadas [{x}, {y}]")
        time.sleep(0.5)
        return True

    def input_text(self, text: str) -> bool:
        preview = (text[:30] + "...") if len(text) > 30 else text
        logger.info(f"[MOCK ADB] Inserindo texto/roteiro no campo: '{preview}'")
        time.sleep(0.8)
        return True

    def dump_ui_xml(self) -> str:
        """Simula a árvore XML com o status de conclusão."""
        return """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
        <hierarchy rotation="0">
            <node text="Concluído" resource-id="com.google.android.apps.youtube.creator:id/export_done" bounds="[100,200][900,300]" />
        </hierarchy>"""

    def take_screenshot(self, output_path: str) -> bool:
        logger.info(f"[MOCK ADB] Capturando screenshot de diagnóstico para {output_path}")
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.touch(exist_ok=True)
        return True

    def clean_remote_files(self, remote_paths: list) -> bool:
        for p in remote_paths:
            logger.info(f"[MOCK ADB] Removendo arquivo temporário no celular: {p}")
        return True

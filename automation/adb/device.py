"""
Wrapper de Controle do Aparelho Android via ADB.
Alterna transparentemente entre o dispositivo físico real e o MockDevice conforme configurado em .env.
"""
import logging
import subprocess
import time
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, List

from config.settings import settings
from automation.mock.mock_device import MockDevice

logger = logging.getLogger(__name__)


class AndroidDevice:
    """Interface de alto nível para controle do celular via ADB."""

    def __init__(self, serial: Optional[str] = None):
        self.serial = serial or settings.adb_device_serial
        self._mock = MockDevice(self.serial) if settings.mock_device else None
        if not settings.mock_device:
            logger.info(f"Dispositivo Android Físico configurado (Serial: {self.serial or 'padrão'})")

    def _run_adb(self, cmd: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """Executa um comando ADB via subprocess no sistema."""
        base_cmd = ["adb"]
        if self.serial:
            base_cmd.extend(["-s", self.serial])
        full_cmd = base_cmd + cmd
        return subprocess.run(full_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=check)

    def is_connected(self) -> bool:
        """Verifica se o aparelho celular está conectado e respondendo ao ADB."""
        if self._mock:
            return True
        try:
            res = self._run_adb(["devices"], check=False)
            lines = [
                line.strip()
                for line in res.stdout.strip().split("\n")[1:]
                if line.strip() and not line.startswith("*")
            ]
            active_devices = [l.split()[0] for l in lines if "\tdevice" in l]
            if self.serial:
                return self.serial in active_devices
            return len(active_devices) > 0
        except Exception:
            return False

    def wake_and_unlock(self) -> bool:
        if self._mock:
            return self._mock.wake_and_unlock()
        try:
            # Acordar tela
            self._run_adb(["shell", "input", "keyevent", "KEYCODE_WAKEUP"])
            # Destravar tela
            self._run_adb(["shell", "wm", "dismiss-keyguard"])
            # Manter ligado enquanto conectado
            self._run_adb(["shell", "svc", "power", "stayon", "true"])
            return True
        except Exception as e:
            logger.error(f"Erro ao acordar celular: {e}")
            return False

    def push_file(self, local_path: str, remote_path: str) -> bool:
        if self._mock:
            return self._mock.push_file(local_path, remote_path)
        try:
            # Criar diretório remoto se não existir
            remote_dir = remote_path.rsplit("/", 1)[0] or "/"
            self._run_adb(["shell", "mkdir", "-p", remote_dir])
            # Transferir
            self._run_adb(["push", local_path, remote_path])
            # Forçar escaneamento de mídia para a foto aparecer imediatamente na galeria
            self._run_adb(["shell", "am", "broadcast", "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE", "-d", f"file://{remote_path}"])
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar arquivo para o celular: {e}")
            return False

    def pull_file(self, remote_path: str, local_path: str) -> bool:
        if self._mock:
            return self._mock.pull_file(remote_path, local_path)
        try:
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            self._run_adb(["pull", remote_path, local_path])
            return Path(local_path).exists() and Path(local_path).stat().st_size > 0
        except Exception as e:
            logger.error(f"Erro ao baixar arquivo do celular: {e}")
            return False

    def launch_app(self, package_name: str) -> bool:
        if self._mock:
            return self._mock.launch_app(package_name)
        try:
            self._run_adb(["shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"])
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"Erro ao abrir app {package_name}: {e}")
            return False

    def stop_app(self, package_name: str) -> bool:
        if self._mock:
            return self._mock.stop_app(package_name)
        try:
            self._run_adb(["shell", "am", "force-stop", package_name])
            return True
        except Exception as e:
            logger.error(f"Erro ao fechar app {package_name}: {e}")
            return False

    def tap(self, x: int, y: int) -> bool:
        if self._mock:
            return self._mock.tap(x, y)
        try:
            self._run_adb(["shell", "input", "tap", str(x), str(y)])
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"Erro ao clicar em [{x}, {y}]: {e}")
            return False

    def tap_ui(
        self,
        *,
        resource_id: Optional[str] = None,
        content_desc: Optional[str] = None,
        text: Optional[str] = None,
        contains: bool = False,
    ) -> bool:
        """Toca no centro de um elemento encontrado na árvore UI do Android."""
        if self._mock:
            return self._mock.tap_ui(
                resource_id=resource_id,
                content_desc=content_desc,
                text=text,
                contains=contains,
            )

        xml = self.dump_ui_xml()
        if not xml:
            return False
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as exc:
            logger.warning("Árvore UI inválida: %s", exc)
            return False

        def matches(value: str, expected: Optional[str]) -> bool:
            if expected is None:
                return True
            return expected in value if contains else value == expected

        for node in root.iter("node"):
            attrs = node.attrib
            if resource_id is not None and attrs.get("resource-id") != resource_id:
                continue
            if content_desc is not None and not matches(attrs.get("content-desc", ""), content_desc):
                continue
            if text is not None and not matches(attrs.get("text", ""), text):
                continue
            if attrs.get("enabled", "true") != "true":
                continue
            bounds = re.fullmatch(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", attrs.get("bounds", ""))
            if not bounds:
                continue
            left, top, right, bottom = map(int, bounds.groups())
            if right <= left or bottom <= top:
                continue
            return self.tap((left + right) // 2, (top + bottom) // 2)
        return False

    def list_remote_files(self, remote_dir: str, suffix: str = "") -> List[str]:
        """Lista nomes de arquivos em uma pasta remota, sem depender de shell glob."""
        if self._mock:
            return self._mock.list_remote_files(remote_dir, suffix=suffix)
        try:
            result = self._run_adb(["shell", "ls", "-1t", remote_dir], check=False)
            if result.returncode != 0:
                return []
            names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            return [name for name in names if not suffix or name.lower().endswith(suffix.lower())]
        except Exception as exc:
            logger.warning("Erro ao listar arquivos remotos em %s: %s", remote_dir, exc)
            return []
    def input_text(self, text: str) -> bool:
        if self._mock:
            return self._mock.input_text(text)
        try:
            # Tratamento de espaços e aspas para o adb input text
            safe_text = text.replace(" ", "%s").replace("'", "\\'")
            self._run_adb(["shell", "input", "text", safe_text])
            return True
        except Exception as e:
            logger.error(f"Erro ao inserir texto no celular: {e}")
            return False

    def dump_ui_xml(self) -> str:
        if self._mock:
            return self._mock.dump_ui_xml()
        try:
            self._run_adb(["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"])
            res = self._run_adb(["shell", "cat", "/sdcard/window_dump.xml"])
            return res.stdout
        except Exception as e:
            logger.error(f"Erro ao ler árvore de UI: {e}")
            return ""

    def take_screenshot(self, output_path: str) -> bool:
        if self._mock:
            return self._mock.take_screenshot(output_path)
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                subprocess.run(["adb", "exec-out", "screencap", "-p"], stdout=f, check=True)
            return True
        except Exception as e:
            logger.error(f"Erro ao capturar screenshot: {e}")
            return False

    def clean_remote_files(self, remote_paths: List[str]) -> bool:
        if self._mock:
            return self._mock.clean_remote_files(remote_paths)
        try:
            for p in remote_paths:
                self._run_adb(["shell", "rm", "-f", p], check=False)
            return True
        except Exception as e:
            logger.error(f"Erro ao limpar arquivos remotos: {e}")
            return False


# Fábrica do dispositivo
def get_device() -> AndroidDevice:
    return AndroidDevice()

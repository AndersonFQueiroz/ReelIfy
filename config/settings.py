"""
Módulo de Configuração Central do Sistema.
Carrega variáveis do arquivo .env e fornece tipagem e valores padrão.
"""
from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv
import yaml

# Carregar variáveis de ambiente do .env na raiz do projeto
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass
class Settings:
    # Diretório raiz
    base_dir: Path = BASE_DIR

    # Telegram
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    allowed_chat_ids: List[int] = field(
        default_factory=lambda: [
            int(cid.strip())
            for cid in os.getenv("ALLOWED_CHAT_IDS", "").split(",")
            if cid.strip().isdigit()
        ]
    )

    admin_chat_ids: List[int] = field(
        default_factory=lambda: [
            int(cid.strip())
            for cid in os.getenv("ADMIN_CHAT_IDS", "").split(",")
            if cid.strip().isdigit()
        ]
    )
    magic_word: str = os.getenv("MAGIC_WORD", "")

    # Google Gemini API
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    gemini_image_model: str = os.getenv("GEMINI_IMAGE_MODEL", "")
    agent_db_path: Path = BASE_DIR / os.getenv("AGENT_DB_PATH", "data/agent.db")
    video_provider_policy: str = os.getenv("VIDEO_PROVIDER_POLICY", "free_only")


    # Fila e Armazenamento
    queue_file_path: Path = BASE_DIR / os.getenv("QUEUE_FILE_PATH", "data/queue.json")
    media_inputs_dir: Path = BASE_DIR / os.getenv("MEDIA_INPUTS_DIR", "data/media/inputs")
    media_outputs_dir: Path = BASE_DIR / os.getenv("MEDIA_OUTPUTS_DIR", "data/media/outputs")
    logs_dir: Path = BASE_DIR / os.getenv("LOGS_DIR", "data/logs")

    # Automação e ADB
    mock_device: bool = os.getenv("MOCK_DEVICE", "True").lower() in ("true", "1", "t", "yes")
    worker_poll_interval: int = int(os.getenv("WORKER_POLL_INTERVAL", "15"))
    adb_device_serial: str = os.getenv("ADB_DEVICE_SERIAL", "")

    # Configuração de Coordenadas YAML
    coordinates_file_path: Path = BASE_DIR / "config/coordinates.yaml"

    def load_coordinates(self) -> dict:
        """Lê as coordenadas de tela a partir do arquivo YAML."""
        if not self.coordinates_file_path.exists():
            return {}
        with open(self.coordinates_file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def ensure_directories(self) -> None:
        """Garante que os diretórios necessários existam no disco."""
        self.media_inputs_dir.mkdir(parents=True, exist_ok=True)
        self.media_outputs_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file_path.parent.mkdir(parents=True, exist_ok=True)


# Instância global de configuração
settings = Settings()
settings.ensure_directories()

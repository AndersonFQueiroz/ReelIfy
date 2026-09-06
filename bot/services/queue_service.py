"""
Serviço de Fila Persistente (QueueService).
Gerencia a persistência e transição de estados dos pedidos (Jobs) em formato JSON.
Desenvolvido com schema padronizado para fácil migração futura para SQLite ou PostgreSQL.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
import json
import logging
from pathlib import Path
import threading
from typing import List, Optional, Dict, Any
import uuid

from config.settings import settings

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class ProductData:
    name: str
    description: str
    target_audience: str
    affiliate_link: str
    photo_local_path: str
    photo_telegram_file_id: Optional[str] = None


@dataclass
class ScriptData:
    hook: str
    problem: str
    solution: str
    proof: str
    cta: str
    full_text: str


@dataclass
class Job:
    job_id: str
    chat_id: int
    user_name: str
    product: ProductData
    script: ScriptData
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    output_video_path: Optional[str] = None
    error_details: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, JobStatus) else self.status
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        product_dict = data.get("product", {})
        script_dict = data.get("script", {})
        product = ProductData(**product_dict)
        script = ScriptData(**script_dict)

        raw_status = data.get("status", JobStatus.PENDING.value)
        status = JobStatus(raw_status) if raw_status in JobStatus._value2member_map_ else JobStatus.PENDING

        return cls(
            job_id=data["job_id"],
            chat_id=data["chat_id"],
            user_name=data.get("user_name", ""),
            product=product,
            script=script,
            status=status,
            attempts=data.get("attempts", 0),
            max_attempts=data.get("max_attempts", 3),
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            output_video_path=data.get("output_video_path"),
            error_details=data.get("error_details"),
        )


class QueueService:
    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or settings.queue_file_path
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Cria o arquivo de fila vazio se não existir."""
        if not self.file_path.exists():
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)

    def _read_all(self) -> List[Job]:
        self._ensure_file()
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [Job.from_dict(item) for item in data]
        except Exception as e:
            logger.error(f"Erro ao ler arquivo da fila {self.file_path}: {e}")
            return []

    def _write_all(self, jobs: List[Job]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.file_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump([j.to_dict() for j in jobs], f, indent=2, ensure_ascii=False)
        temp_file.replace(self.file_path)

    def create_job(
        self,
        chat_id: int,
        user_name: str,
        product: ProductData,
        script: ScriptData,
    ) -> Job:
        """Adiciona um novo pedido à fila com status PENDING."""
        with self._lock:
            jobs = self._read_all()
            new_job = Job(
                job_id=str(uuid.uuid4()),
                chat_id=chat_id,
                user_name=user_name,
                product=product,
                script=script,
                status=JobStatus.PENDING,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            jobs.append(new_job)
            self._write_all(jobs)
            logger.info(f"Job {new_job.job_id} criado com sucesso para o chat {chat_id}.")
            return new_job

    def get_next_pending_job(self) -> Optional[Job]:
        """Recupera o próximo pedido PENDING e o altera para PROCESSING de forma atômica."""
        with self._lock:
            jobs = self._read_all()
            for job in jobs:
                if job.status == JobStatus.PENDING:
                    job.status = JobStatus.PROCESSING
                    job.started_at = datetime.now(timezone.utc).isoformat()
                    job.attempts += 1
                    self._write_all(jobs)
                    logger.info(f"Job {job.job_id} assumido pelo worker (Status: PROCESSING).")
                    return job
            return None

    def get_job_by_id(self, job_id: str) -> Optional[Job]:
        """Busca um pedido específico pelo seu UUID."""
        with self._lock:
            for job in self._read_all():
                if job.job_id == job_id:
                    return job
            return None

    def get_jobs_by_chat_id(self, chat_id: int) -> List[Job]:
        """Retorna todos os pedidos de um determinado usuário."""
        with self._lock:
            return [job for job in self._read_all() if job.chat_id == chat_id]

    def mark_completed(self, job_id: str, output_video_path: str) -> Optional[Job]:
        """Marca o pedido como COMPLETED e salva o caminho do vídeo gerado."""
        with self._lock:
            jobs = self._read_all()
            for job in jobs:
                if job.job_id == job_id:
                    job.status = JobStatus.COMPLETED
                    job.completed_at = datetime.now(timezone.utc).isoformat()
                    job.output_video_path = output_video_path
                    self._write_all(jobs)
                    logger.info(f"Job {job_id} concluído com sucesso!")
                    return job
            return None

    def mark_failed(self, job_id: str, error_details: str) -> Optional[Job]:
        """Marca o pedido como FAILED e registra os detalhes do erro."""
        with self._lock:
            jobs = self._read_all()
            for job in jobs:
                if job.job_id == job_id:
                    job.status = JobStatus.FAILED
                    job.completed_at = datetime.now(timezone.utc).isoformat()
                    job.error_details = error_details
                    self._write_all(jobs)
                    logger.warning(f"Job {job_id} marcado como FALHO: {error_details}")
                    return job
            return None


# Instância singleton global do serviço de fila
queue_service = QueueService()

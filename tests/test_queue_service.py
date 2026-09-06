"""
Testes unitários para o QueueService.
"""
from pathlib import Path
import tempfile
import pytest

from bot.services.queue_service import QueueService, ProductData, ScriptData, JobStatus


@pytest.fixture
def temp_queue_service():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        temp_path = Path(tf.name)
    service = QueueService(file_path=temp_path)
    yield service
    if temp_path.exists():
        temp_path.unlink()


def test_create_and_get_job(temp_queue_service):
    product = ProductData(
        name="Fone Bluetooth Pro",
        description="Bateria de 30 horas, cancelamento de ruído",
        target_audience="Estudantes e trabalhadores remotos",
        affiliate_link="https://shopee.com.br/fone-bluetooth",
        photo_local_path="/tmp/fone.jpg",
    )
    script = ScriptData(
        hook="Barulho tirando sua concentração?",
        problem="Trabalhar ou estudar com barulho ao redor é um pesadelo.",
        solution="O Fone Pro tem cancelamento de ruído e 30h de bateria.",
        proof="Mais de 5 mil avaliações 5 estrelas.",
        cta="Clique no link da bio e garanta o seu com frete grátis!",
        full_text="Barulho tirando sua concentração? Trabalhar ou estudar com barulho ao redor é um pesadelo. O Fone Pro tem cancelamento de ruído e 30h de bateria. Mais de 5 mil avaliações 5 estrelas. Clique no link da bio e garanta o seu com frete grátis!",
    )

    job = temp_queue_service.create_job(
        chat_id=123456,
        user_name="test_user",
        product=product,
        script=script,
    )

    assert job.job_id is not None
    assert job.status == JobStatus.PENDING
    assert job.chat_id == 123456

    # Teste de polling (transição PENDING -> PROCESSING)
    polled_job = temp_queue_service.get_next_pending_job()
    assert polled_job is not None
    assert polled_job.job_id == job.job_id
    assert polled_job.status == JobStatus.PROCESSING

    # Não deve haver outro pending
    assert temp_queue_service.get_next_pending_job() is None

    # Teste de conclusão
    completed_job = temp_queue_service.mark_completed(job.job_id, "/tmp/video_final.mp4")
    assert completed_job.status == JobStatus.COMPLETED
    assert completed_job.output_video_path == "/tmp/video_final.mp4"

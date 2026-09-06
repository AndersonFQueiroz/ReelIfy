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


def test_cleanup_expired_jobs(temp_queue_service):
    """Verifica que pedidos pendentes com mais de 24h são excluídos junto com suas fotos."""
    from datetime import datetime, timezone, timedelta

    # Cria uma foto temporária para testar exclusão em disco
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
        tf.write(b"imagem_antiga")
        old_photo = tf.name

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf2:
        tf2.write(b"imagem_recente")
        recent_photo = tf2.name

    product_old = ProductData(
        name="Produto Antigo (+24h)",
        description="Descrição",
        target_audience="Público",
        affiliate_link="",
        photo_local_path=old_photo,
    )
    product_recent = ProductData(
        name="Produto Recente (1h)",
        description="Descrição",
        target_audience="Público",
        affiliate_link="",
        photo_local_path=recent_photo,
    )
    script = ScriptData(
        hook="H", problem="P", solution="S", proof="Pr", cta="C", full_text="Texto"
    )

    # Cria 2 jobs
    job_old = temp_queue_service.create_job(111, "antigo", product_old, script)
    job_recent = temp_queue_service.create_job(222, "recente", product_recent, script)

    # Forçar a data do job_old para 25 horas atrás
    now = datetime.now(timezone.utc)
    old_time = (now - timedelta(hours=25)).isoformat()
    jobs = temp_queue_service._read_all()
    for j in jobs:
        if j.job_id == job_old.job_id:
            j.created_at = old_time
    temp_queue_service._write_all(jobs)

    # Executar limpeza de pedidos > 24h
    removed = temp_queue_service.cleanup_expired_jobs(max_age_hours=24)
    assert removed == 1

    # Verificar que o job_old sumiu da fila
    remaining_jobs = temp_queue_service._read_all()
    assert len(remaining_jobs) == 1
    assert remaining_jobs[0].job_id == job_recent.job_id

    # Verificar que a foto do job antigo foi excluída do disco
    assert not Path(old_photo).exists()
    # A foto recente deve continuar intacta
    assert Path(recent_photo).exists()

    # Limpeza
    Path(recent_photo).unlink(missing_ok=True)


def test_product_multi_photo_support(temp_queue_service):
    """Verifica suporte a até 3 fotos por produto e persistência na fila."""
    photos = ["/tmp/photo1.jpg", "/tmp/photo2.jpg", "/tmp/photo3.jpg"]
    product = ProductData(
        name="Kit 3 Ângulos",
        description="Frente, lado e detalhes",
        target_audience="Compradores",
        affiliate_link="https://shopee.com.br/kit",
        photos_local_paths=photos,
    )
    # Deve automaticamente preencher photo_local_path com a primeira foto
    assert product.photo_local_path == "/tmp/photo1.jpg"
    assert len(product.photos_local_paths) == 3

    script = ScriptData(
        hook="H", problem="P", solution="S", proof="Pr", cta="C", full_text="Texto"
    )
    job = temp_queue_service.create_job(123, "multi_user", product, script)

    # Recupera da fila e valida persistência
    saved_job = temp_queue_service.get_job_by_id(job.job_id)
    assert saved_job is not None
    assert len(saved_job.product.photos_local_paths) == 3
    assert saved_job.product.photos_local_paths == photos
    assert saved_job.product.photo_local_path == "/tmp/photo1.jpg"

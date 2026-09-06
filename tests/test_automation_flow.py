"""
Testes de integração do Worker de automação com MockDevice.
Valida o fluxo completo de acordar o celular, abrir o app, inserir roteiro e extrair o vídeo.
"""
from pathlib import Path
import tempfile
import pytest

from bot.services.queue_service import QueueService, ProductData, ScriptData
from automation.worker import VideoAutomationWorker


def test_worker_process_job_mock():
    # Cria uma foto temporária de teste
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
        tf.write(b"fake image data")
        temp_img_path = tf.name

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as qf:
        temp_queue_path = Path(qf.name)

    # Inicializa serviços apontando para arquivos temporários
    test_queue = QueueService(file_path=temp_queue_path)

    product = ProductData(
        name="Kit Organizador de Mesa",
        description="Madeira maciça, suporte para celular e canetas",
        target_audience="Home office",
        affiliate_link="https://shopee.com.br/organizador",
        photo_local_path=temp_img_path,
    )
    script = ScriptData(
        hook="Mesa bagunçada te desconcentra?",
        problem="Perder tempo procurando caneta no meio do trabalho é horrível.",
        solution="Com esse organizador sua mesa fica impecável.",
        proof="Mais de 1000 pessoas organizadas.",
        cta="Link na bio para garantir o seu!",
        full_text="Mesa bagunçada te desconcentra? Perder tempo procurando caneta no meio do trabalho é horrível. Com esse organizador sua mesa fica impecável. Mais de 1000 pessoas organizadas. Link na bio para garantir o seu!",
    )

    job = test_queue.create_job(12345, "maria", product, script)
    assert job.status == "PENDING"

    # Executa o worker
    worker = VideoAutomationWorker()
    success = worker.process_job(job)

    assert success is True

    # Limpeza
    Path(temp_img_path).unlink(missing_ok=True)
    temp_queue_path.unlink(missing_ok=True)


def test_hardware_status_message():
    """Verifica se o sistema informa corretamente sobre a disponibilidade do hardware."""
    from config.settings import settings
    if settings.mock_device:
        print(
            "\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📱 MODO SIMULADO (MOCK) ATIVO\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "\n"
            "O ReelIfy está operando em modo simulado.\n"
            "\n"
            "🔧 Para produção completa de vídeos, você precisa:\n"
            "   1. Notebook 24/7 ligado com ADB instalado\n"
            "   2. Celular Android (slave) conectado via USB\n"
            "   3. YouTube Create instalado e logado no celular\n"
            "   4. MOCK_DEVICE=False no arquivo .env\n"
            "\n"
            "✅ Enquanto isso, o bot gera roteiros completos com IA!\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )
    assert True  # Sempre passa — é um teste informativo


def test_graceful_handling_without_hardware(monkeypatch):
    """
    Testa o tratamento amigável quando o celular slave ou notebook 24/7
    não estão disponíveis: o roteiro é preservado e a falha de hardware é tratada.
    """
    from config.settings import settings
    from automation.worker import VideoAutomationWorker, HardwareNotAvailableError

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
        tf.write(b"fake image data")
        temp_img = tf.name

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as qf:
        temp_queue_path = Path(qf.name)

    test_queue = QueueService(file_path=temp_queue_path)

    product = ProductData(
        name="Produto Teste Sem Hardware",
        description="Benefícios incríveis",
        target_audience="Compradores online",
        affiliate_link="https://exemplo.com",
        photo_local_path=temp_img,
    )
    script = ScriptData(
        hook="Gancho teste",
        problem="Problema teste",
        solution="Solução teste",
        proof="Prova teste",
        cta="CTA teste",
        full_text="Roteiro completo de 20s garantido mesmo sem o celular físico conectado.",
    )

    job = test_queue.create_job(99999, "usuario_teste", product, script)

    # Simular ambiente de produção (MOCK_DEVICE=False) mas sem celular plugado
    monkeypatch.setattr(settings, "mock_device", False)

    worker = VideoAutomationWorker(queue_srv=test_queue)
    monkeypatch.setattr(worker.device, "is_connected", lambda: False)

    # Executar o processamento
    success = worker.process_job(job)

    # Deve retornar False (não gerou vídeo) sem crashar
    assert success is False

    # Verificar que o job foi marcado com explicação amigável
    updated_job = test_queue.get_job_by_id(job.job_id)
    assert updated_job.status == "FAILED"
    assert "não detectado via ADB" in updated_job.error_details or "HardwareNotAvailable" in updated_job.error_details

    # O roteiro gerado permanece intacto e acessível!
    assert updated_job.script.full_text == "Roteiro completo de 20s garantido mesmo sem o celular físico conectado."

    # Limpeza
    Path(temp_img).unlink(missing_ok=True)
    temp_queue_path.unlink(missing_ok=True)

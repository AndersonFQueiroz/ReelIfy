import asyncio
import json
from pathlib import Path

from bot.services import agent_service as agent_module
from bot.services.agent_service import AgentService
from bot.services.gemini_service import gemini_service
from bot.services.queue_service import QueueService, ScriptData
from config.settings import settings


def test_rag_removes_links_and_numeric_ids(tmp_path):
    service = AgentService(tmp_path / "agent.db")
    with service._connect() as db:
        service._add_learning(db, "Preferência do usuário https://example.com para o chat 123456789")
    with service._connect() as db:
        row = db.execute("SELECT content FROM rag_documents WHERE category='learning'").fetchone()
    assert row is not None
    assert "https://" not in row[0]
    assert "123456789" not in row[0]


def test_free_conversation_creates_job_with_style_and_placeholder(tmp_path, monkeypatch):
    async def fake_script(**kwargs):
        assert kwargs["style"] == "pov"
        assert kwargs["link_destination"] == "youtube_description"
        return ScriptData("Gancho", "Problema", "Solução", "Prova", "Link abaixo", "Gancho. Problema. Solução. Prova. Link abaixo.")

    queue = QueueService(tmp_path / "queue.json")
    monkeypatch.setattr(agent_module, "queue_service", queue)
    monkeypatch.setattr(settings, "mock_device", True)
    monkeypatch.setattr(gemini_service, "_client", None)
    monkeypatch.setattr(gemini_service, "generate_script", fake_script)

    async def run():
        service = AgentService(tmp_path / "agent.db")
        chat_id = 321
        for message in (
            "Quero divulgar uma churrasqueira",
            "Prepara carnes com praticidade",
            "Para pais",
            "sem link",
            "usar placeholder",
            "POV",
            "YouTube Create no celular",
            "descrição do YouTube",
        ):
            await service.handle_message(chat_id, message)
        reply = await service.handle_message(chat_id, "sim")
        return reply

    reply = asyncio.run(run())
    assert reply.job is not None
    assert reply.job.style_id == "pov"
    assert reply.job.provider_id == "adb_youtube_create"
    assert reply.job.media_source == "placeholder"
    assert Path(reply.job.product.photo_local_path).exists()


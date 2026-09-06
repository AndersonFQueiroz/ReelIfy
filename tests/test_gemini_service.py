"""
Testes unitários para o GeminiService (modo offline/fallback).
"""
import asyncio
from bot.services.gemini_service import GeminiService


def test_gemini_service_fallback():
    # Instanciado sem API key para testar o gerador local resiliente
    service = GeminiService(api_key=None)

    script = asyncio.run(
        service.generate_script(
            product_name="Garrafa Térmica Inteligente",
            description="Mantém quente por 24h e mostra temperatura no visor LED",
            target_audience="Quem treina na academia ou trabalha em escritório",
            affiliate_link="https://shopee.com.br/garrafa-led",
        )
    )

    assert script is not None
    assert len(script.hook) > 0
    assert len(script.problem) > 0
    assert len(script.solution) > 0
    assert len(script.proof) > 0
    assert len(script.cta) > 0
    assert len(script.full_text) > 0
    assert "Garrafa Térmica Inteligente" in script.solution


def test_fallback_uses_natural_audience_and_varies_regeneration():
    service = GeminiService(api_key=None)

    first = asyncio.run(service.generate_script("Churrasqueira", "prepara carnes com praticidade", "pais", ""))
    regenerated = asyncio.run(service.generate_script("Churrasqueira", "prepara carnes com praticidade", "pais", "", variation_index=1))

    assert "faz parte de pais" not in first.full_text.lower()
    assert "pais" in first.problem.lower()
    assert first.full_text != regenerated.full_text

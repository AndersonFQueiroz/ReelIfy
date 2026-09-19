"""Testes da fábrica diária (sem rede, sem segredos)."""
import json

import pytest

from factory import render as R
from factory.video_cinetico import clean_title, short_name


def test_safe_text_tira_emoji_mantem_texto():
    out = R.safe_text("🔥 -48% HOJE 👇 @cacaofertasofcbr")
    assert "🔥" not in out and "👇" not in out
    assert "-48% HOJE" in out and "@cacaofertasofcbr" in out


def test_safe_text_idempotente():
    assert R.safe_text(R.safe_text("✓ 5L • Frete")) == R.safe_text("✓ 5L • Frete")


def test_clean_title():
    assert clean_title("*OLHA ESSE PREÇO* 🔥👀") == "OLHA ESSE PREÇO"


def test_short_name_preserva_frase():
    assert short_name("*TÁ DE GRAÇA, GENTE* 😱🤩") == "TÁ DE GRAÇA, GENTE"


def test_pack_barra_sem_link(tmp_path, monkeypatch):
    from factory import pack_redes
    day = tmp_path / "d"
    day.mkdir()
    (day / "offer.json").write_text(json.dumps({
        "day": "2026-09-19", "title": "X", "price": 10, "original_price": 20,
        "discount_pct": 50, "marketplace": "shopee", "affiliate_url": "",
        "original_label": "R$ 20", "price_label": "R$ 10"}))
    with pytest.raises(SystemExit) as exc:
        pack_redes.build_pack(day, {})
    assert exc.value.code == 2


def test_out_specs():
    assert (R.OUT_W, R.OUT_H) == (720, 1280)
    assert R.FPS == 30


def test_buffer_sem_chave_pula(monkeypatch):
    import os
    from factory import post_buffer
    monkeypatch.delenv("BUFFER_API_KEY", raising=False)
    assert post_buffer.main("2000-01-01") == 3


def test_qc_bloqueia_sem_oferta(tmp_path, monkeypatch):
    from factory import qc, config as C
    monkeypatch.setattr(C, "FACTORY_DATA", tmp_path)
    assert qc.main("2000-01-01") == 1


def test_sanitize_narracao():
    from factory.render import sanitize_narration
    out = sanitize_narration("Olha 🔥 https://exemplo.com/x TOP!")
    assert "🔥" not in out and "http" not in out and "TOP!" in out

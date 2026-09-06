"""Agente conversacional do Reelify.

O agente mantém apenas o estado temporário da conversa e grava no RAG somente
aprendizados generalizados. A execução de qualquer ação sensível continua sob
controle desta aplicação, nunca sob controle direto do modelo.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import base64
import logging
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any, Optional
import uuid

from config.settings import settings
from bot.services.gemini_service import gemini_service
from bot.services.queue_service import Job, ProductData, ScriptData, queue_service
from bot.services.video_providers import is_provider_available, provider_names
from bot.services.image_providers import image_provider

logger = logging.getLogger(__name__)

DB_PATH = settings.agent_db_path
MAX_HISTORY = 30
MAX_RAG_ITEMS = 120

STYLE_TEMPLATES = {
    "pov": "POV em primeira pessoa, mostrando a situação e o produto em uso.",
    "unboxing": "Unboxing com descoberta progressiva, detalhes visuais e reação natural.",
    "before_after": "Antes e depois, deixando clara a transformação causada pelo produto.",
    "product_demo": "Demonstração objetiva do produto e dos seus benefícios.",
    "comparison": "Comparação simples entre a rotina sem o produto e com o produto.",
    "testimonial": "Depoimento curto e natural, sem inventar avaliações ou números.",
    "problem_solution": "Problema cotidiano seguido por uma solução prática.",
    "offer": "Oferta direta, com benefício, urgência moderada e CTA claro.",
    "custom": "Estilo personalizado definido pelo usuário.",
}

PROVIDER_LABELS = {
    "adb_youtube_create": "YouTube Create no celular",
    "local_ffmpeg": "renderização local",
}


@dataclass
class AgentReply:
    text: str
    job: Optional[Job] = None
    generated_image_path: Optional[str] = None
    script: Optional[ScriptData] = None
    awaiting_approval: bool = False


class AgentService:
    """Coordena sessão, RAG, Gemini e criação segura de jobs."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._lock = threading.RLock()
        self._ensure_database()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=15)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_database(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    chat_id INTEGER PRIMARY KEY,
                    state TEXT NOT NULL DEFAULT 'COLLECTING',
                    brief_json TEXT NOT NULL DEFAULT '{}',
                    history_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rag_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    keywords TEXT NOT NULL DEFAULT '',
                    weight REAL NOT NULL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS rag_search USING fts5(
                    doc_id UNINDEXED, content, keywords, category
                );
                """
            )
            count = db.execute("SELECT COUNT(*) FROM rag_documents").fetchone()[0]
            if not count:
                self._seed_rag(db)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _seed_rag(self, db: sqlite3.Connection) -> None:
        seeds = [
            ("persona", "Fale em português brasileiro, com naturalidade, clareza e simpatia. Seja objetivo, mas explique o próximo passo.", "tom persona português"),
            ("quality", "Nunca invente avaliações, números, características ou resultados que o usuário não informou. Peça confirmação quando faltar informação.", "qualidade fatos segurança"),
            ("audience", "Use o público-alvo em frases naturais. Para pais, prefira 'pais sabem', 'para pais' ou 'se você é pai ou mãe'; nunca use 'se você faz parte de pais'.", "público pais gramática"),
            ("cta", "Para Shopee e afiliados, prefira link abaixo, link na descrição ou comentário fixado. Não recomende link na bio como padrão.", "cta link descrição shopee"),
            ("media", "Se não houver foto, explique a diferença entre imagem real, imagem gerada por IA e placeholder. Imagem sintética deve ser informada ao usuário.", "foto imagem ia placeholder"),
            ("learning", "Correções do usuário devem melhorar o briefing atual imediatamente e só viram aprendizado futuro depois de serem generalizadas e anonimizadas.", "correção aprendizado"),
        ]
        now = self._now()
        for category, content, keywords in seeds:
            cursor = db.execute(
                "INSERT INTO rag_documents(category, content, keywords, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (category, content, keywords, now, now),
            )
            db.execute(
                "INSERT INTO rag_search(doc_id, content, keywords, category) VALUES (?, ?, ?, ?)",
                (cursor.lastrowid, content, keywords, category),
            )

    def start_session(self, chat_id: int) -> None:
        now = self._now()
        with self._lock, self._connect() as db:
            db.execute(
                "INSERT INTO agent_sessions(chat_id, state, brief_json, history_json, created_at, updated_at) "
                "VALUES (?, 'COLLECTING', '{}', '[]', ?, ?) "
                "ON CONFLICT(chat_id) DO UPDATE SET state='COLLECTING', brief_json='{}', history_json='[]', updated_at=?",
                (chat_id, now, now, now),
            )

    def cancel_session(self, chat_id: int) -> None:
        with self._lock, self._connect() as db:
            row = db.execute("SELECT history_json, brief_json FROM agent_sessions WHERE chat_id=?", (chat_id,)).fetchone()
            if row:
                self._learn_from_session(db, json.loads(row[0]), json.loads(row[1]), "abandoned")
            db.execute("DELETE FROM agent_sessions WHERE chat_id=?", (chat_id,))

    def _get_session(self, chat_id: int) -> tuple[dict[str, Any], list[dict[str, str]], str]:
        with self._connect() as db:
            row = db.execute("SELECT brief_json, history_json, state FROM agent_sessions WHERE chat_id=?", (chat_id,)).fetchone()
        if not row:
            self.start_session(chat_id)
            return {}, [], "COLLECTING"
        return json.loads(row[0] or "{}"), json.loads(row[1] or "[]"), row[2]

    def _save_session(self, chat_id: int, brief: dict[str, Any], history: list[dict[str, str]], state: str = "COLLECTING") -> None:
        now = self._now()
        history = history[-MAX_HISTORY:]
        with self._lock, self._connect() as db:
            db.execute(
                "UPDATE agent_sessions SET state=?, brief_json=?, history_json=?, updated_at=? WHERE chat_id=?",
                (state, json.dumps(brief, ensure_ascii=False), json.dumps(history, ensure_ascii=False), now, chat_id),
            )

    def retrieve(self, query: str, limit: int = 8) -> list[str]:
        words = re.findall(r"[\wÀ-ÿ]{3,}", query.lower())[:12]
        with self._connect() as db:
            rows = []
            if words:
                match = " OR ".join(words).replace('"', "")
                try:
                    rows = db.execute(
                        "SELECT d.content FROM rag_search s JOIN rag_documents d ON d.id=CAST(s.doc_id AS INTEGER) "
                        "WHERE rag_search MATCH ? AND d.active=1 ORDER BY d.weight DESC, d.updated_at DESC LIMIT ?",
                        (match, limit),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
            if not rows:
                rows = db.execute(
                    "SELECT content FROM rag_documents WHERE active=1 ORDER BY weight DESC, updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [row[0] for row in rows]

    def _add_learning(self, db: sqlite3.Connection, content: str, category: str = "learning") -> None:
        content = re.sub(r"https?://\S+", "[link removido]", content)
        content = re.sub(r"\b\d{5,}\b", "[id removido]", content)
        content = re.sub(r"\s+", " ", content).strip()[:500]
        if len(content) < 20:
            return
        normalized = re.sub(r"\W+", " ", content.lower()).strip()
        with db:
            duplicate = db.execute(
                "SELECT id FROM rag_documents WHERE active=1 AND lower(replace(replace(content, '.', ''), ',', '')) LIKE ? LIMIT 1",
                (f"%{normalized[:80]}%",),
            ).fetchone()
            if duplicate:
                db.execute("UPDATE rag_documents SET updated_at=?, weight=MIN(weight+0.1, 3) WHERE id=?", (self._now(), duplicate[0]))
                return
            now = self._now()
            cursor = db.execute(
                "INSERT INTO rag_documents(category, content, keywords, weight, created_at, updated_at) VALUES (?, ?, ?, 1.2, ?, ?)",
                (category, content, category, now, now),
            )
            db.execute("INSERT INTO rag_search(doc_id, content, keywords, category) VALUES (?, ?, ?, ?)", (cursor.lastrowid, content, category, category))
            self._compact_if_needed(db)

    def _compact_if_needed(self, db: sqlite3.Connection) -> None:
        count = db.execute("SELECT COUNT(*) FROM rag_documents WHERE active=1").fetchone()[0]
        if count <= MAX_RAG_ITEMS:
            return
        ids = db.execute(
            "SELECT id FROM rag_documents WHERE category='learning' ORDER BY weight ASC, updated_at ASC LIMIT ?",
            (count - MAX_RAG_ITEMS + 10,),
        ).fetchall()
        for row in ids:
            db.execute("DELETE FROM rag_search WHERE doc_id=?", (row[0],))
            db.execute("DELETE FROM rag_documents WHERE id=?", (row[0],))

    def _learn_from_session(self, db: sqlite3.Connection, history: list[dict[str, str]], brief: dict[str, Any], outcome: str) -> None:
        corrections = [m["text"] for m in history if m.get("role") == "user" and any(word in m["text"].lower() for word in ("corrija", "não é", "nao e", "prefiro", "mude", "troque", "mais natural", "robótico", "robotico", "mais curto"))]
        for correction in corrections[:3]:
            lowered = correction.lower()
            if any(word in lowered for word in ("natural", "robótico", "robotico")):
                learning = "Usuários preferem roteiros naturais, conversados e sem frases artificiais ou genéricas."
            elif "mais curto" in lowered or "resum" in lowered:
                learning = "Quando solicitado, reduzir o roteiro mantendo benefício concreto e CTA claro."
            elif "público" in lowered or "publico" in lowered:
                learning = "Correções de público devem substituir o público anterior em todas as frases do roteiro."
            elif "cta" in lowered or "link" in lowered:
                learning = "Correções de CTA devem respeitar o destino escolhido e evitar link na bio como padrão."
            else:
                learning = "Usuários podem corrigir o roteiro livremente; aplicar a correção na próxima versão antes de enfileirar."
            self._add_learning(db, learning, "user_correction")
        if brief.get("link_destination") in {"youtube_description", "youtube_comment"}:
            self._add_learning(db, "Para publicação no YouTube, preparar o link em bloco copiável para descrição ou comentário fixado.", "link")
        if outcome in {"completed", "failed"} and brief.get("style"):
            self._add_learning(db, f"Pedidos concluídos usam o estilo {brief['style']} quando solicitado pelo usuário.", "style")

    @staticmethod
    def _style_from_text(text: str) -> Optional[str]:
        lowered = text.lower()
        aliases = {
            "pov": "pov", "unboxing": "unboxing", "desembalar": "unboxing",
            "antes e depois": "before_after", "antes/depois": "before_after", "comparativo": "comparison",
            "comparação": "comparison", "depoimento": "testimonial", "demonstração": "product_demo",
            "oferta": "offer",
        }
        return next((value for key, value in aliases.items() if key in lowered), None)

    @staticmethod
    def _is_yes(text: str) -> bool:
        return text.lower().strip() in {"sim", "s", "ok", "pode", "confirmo", "confirmar", "aprovar", "aprovado", "vamos"}

    @staticmethod
    def _is_regenerate(text: str) -> bool:
        lowered = text.lower().strip()
        return any(value in lowered for value in ("regenerar", "gerar de novo", "fazer outro", "outra versão", "outra versao"))

    @staticmethod
    def _is_no_photo(text: str) -> bool:
        lowered = text.lower()
        return any(value in lowered for value in ("sem foto", "não tenho foto", "nao tenho foto", "sem imagem", "não tenho imagem", "nao tenho imagem"))

    def _infer_brief(self, brief: dict[str, Any], text: str) -> None:
        clean = text.strip()
        lowered = clean.lower()
        style = self._style_from_text(clean)
        if style:
            brief["style"] = style
        if "youtube" in lowered and "descri" in lowered:
            brief["link_destination"] = "youtube_description"
        elif "comentário" in lowered or "comentario" in lowered:
            brief["link_destination"] = "youtube_comment"
        elif "só o link" in lowered or "so o link" in lowered or "copiar" in lowered:
            brief["link_destination"] = "manual_copy"
        if "adb" in lowered or "celular" in lowered or "youtube create" in lowered:
            brief["provider_id"] = "adb_youtube_create"
        elif "local" in lowered:
            brief["provider_id"] = "local_ffmpeg"
        if self._is_no_photo(clean):
            brief["media_source"] = "placeholder"
        if lowered in {"gerar imagem", "imagem ia", "gerar uma imagem", "quero imagem de ia"} or "imagem gerada" in lowered:
            brief["media_source"] = "generated"
        elif "placeholder" in lowered or "ilustra" in lowered:
            brief["media_source"] = "placeholder"
        elif "continuar sem foto" in lowered or "sem mídia" in lowered or "sem midia" in lowered:
            brief["media_source"] = "none"
        if clean.startswith("http://") or clean.startswith("https://"):
            brief["affiliate_link"] = clean
        elif any(token in lowered for token in ("sem link", "não tenho link", "nao tenho link", "sem afiliado")):
            brief["affiliate_link"] = ""
            brief["link_declined"] = True
        # Extrações simples para quando a API estiver indisponível. Elas evitam
        # transformar uma mensagem inteira em nome do produto.
        product_match = re.search(
            r"(?:produto\s*:\s*|produto\s+|vídeo\s+(?:sobre|de)\s+|video\s+(?:sobre|de)\s+|(?:quero|vou)\s+(?:divulgar|promover|vender)\s+)(?:uma?\s+|o\s+|a\s+)?(.+?)(?=\s+(?:para|com|que)\s+|$)",
            clean,
            re.IGNORECASE,
        )
        audience_match = re.search(r"\bpara\s+([^,.!?]+)", clean, re.IGNORECASE)
        benefits_match = re.search(r"(?:benefícios?|beneficios?|diferenciais?)\s*:\s*(.+)$", clean, re.IGNORECASE)
        if product_match and not brief.get("product_name"):
            brief["product_name"] = product_match.group(1).strip()
        if audience_match and not brief.get("target_audience"):
            brief["target_audience"] = audience_match.group(1).strip()
        if benefits_match and not brief.get("benefits"):
            brief["benefits"] = benefits_match.group(1).strip()

        # Coleta livre de fallback quando o modelo não estiver disponível.
        if not brief.get("product_name"):
            if clean and not self._is_yes(clean) and not self._is_regenerate(clean):
                brief["product_name"] = clean[:160]
        elif not brief.get("benefits"):
            control_message = (
                self._is_yes(clean)
                or self._is_regenerate(clean)
                or self._is_no_photo(clean)
                or style
                or clean.startswith(("http://", "https://"))
                or any(token in lowered for token in ("sem link", "não tenho link", "nao tenho link", "placeholder", "imagem ia"))
            )
            if benefits_match:
                brief["benefits"] = benefits_match.group(1).strip()[:500]
            elif not control_message and not product_match:
                brief["benefits"] = clean[:500]

    def _apply_defaults(self, brief: dict[str, Any]) -> None:
        """Preenche escolhas seguras que não precisam virar perguntas."""
        brief.setdefault("style", "product_demo")
        brief.setdefault("link_destination", "manual_copy")
        if brief.get("product_name") and brief.get("benefits") and not brief.get("target_audience"):
            brief["target_audience"] = "pessoas interessadas no produto"
        if brief.get("product_name") and brief.get("benefits") and not brief.get("media_paths") and not brief.get("media_source"):
            # A foto é opcional; o usuário pode substituí-la enviando uma imagem
            # depois. Assim, não bloqueamos a conversa com uma escolha técnica.
            brief["media_source"] = "placeholder"
        if not brief.get("provider_id"):
            providers = provider_names()
            if len(providers) == 1:
                brief["provider_id"] = next(iter(providers))

    def _missing_question(self, brief: dict[str, Any]) -> Optional[str]:
        if not brief.get("product_name"):
            return "Que produto você quer transformar em vídeo? Pode me contar do seu jeito."
        if not brief.get("benefits"):
            return f"Entendi: {brief['product_name']}. Quais são os principais benefícios ou diferenciais dele?"
        if brief.get("media_source") in {None, "pending_choice"}:
            return "Você pode enviar uma foto do produto ou escolher: gerar imagem, usar placeholder ou continuar sem foto."
        if not brief.get("provider_id") or not is_provider_available(brief.get("provider_id", "")):
            names = provider_names()
            options = " ou ".join(name for name in names.values()) or "nenhum motor está disponível agora"
            return f"Qual motor você prefere: {options}? Vou mostrar apenas os que estiverem disponíveis."
        return None

    def _fallback_reply(self, brief: dict[str, Any], text: str) -> str:
        if brief.get("confirmed"):
            return "Vou preparar seu pedido agora."
        question = self._missing_question(brief)
        return question or "Pode me dizer o que você gostaria de ajustar no roteiro?"

    async def _gemini_turn(self, brief: dict[str, Any], history: list[dict[str, str]], text: str, rag: list[str]) -> tuple[str, list[dict[str, Any]]]:
        client = getattr(gemini_service, "_client", None)
        if not client:
            return "", []
        tools = [{"function_declarations": [
            {"name": "update_brief", "description": "Atualiza informações fornecidas pelo usuário.", "parameters": {"type": "object", "properties": {"product_name": {"type": "string"}, "benefits": {"type": "string"}, "target_audience": {"type": "string"}, "affiliate_link": {"type": "string"}, "style": {"type": "string"}, "link_destination": {"type": "string"}, "media_source": {"type": "string"}, "provider_id": {"type": "string"}}}},
            {"name": "record_user_correction", "description": "Registra uma correção feita pelo usuário para o briefing atual.", "parameters": {"type": "object", "properties": {"correction": {"type": "string"}}, "required": ["correction"]}},
            {"name": "finalize_video_request", "description": "Dispara a criação do vídeo somente quando o briefing estiver completo e confirmado.", "parameters": {"type": "object", "properties": {"confirmed": {"type": "boolean"}}, "required": ["confirmed"]}},
            {"name": "generate_product_image", "description": "Solicita uma imagem ilustrativa quando o usuário não tem foto.", "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}, "confirmed": {"type": "boolean"}}, "required": ["confirmed"]}},
            {"name": "select_video_provider", "description": "Seleciona somente um provedor que a aplicação informou como disponível.", "parameters": {"type": "object", "properties": {"provider_id": {"type": "string"}}, "required": ["provider_id"]}},
        ]}]
        rag_text = "\n- ".join(rag)
        style_text = json.dumps(STYLE_TEMPLATES, ensure_ascii=False)
        system = (
            "Você é o atendente natural deste bot. Nunca invente ou repita um nome de marca; "
            "use a identidade que aparecer na mensagem do Telegram. Converse em português brasileiro. "
            "Não repita formulário nem faça várias perguntas de uma vez. Use o RAG abaixo. "
            "Nunca invente dados. Use update_brief ao extrair informações. Só chame finalize_video_request "
            "quando o usuário confirmar e o briefing estiver completo.\n\n"
            f"RAG:\n- {rag_text}\n\nEstilos disponíveis:\n{style_text}\n\nBriefing atual:\n{json.dumps(brief, ensure_ascii=False)}\n"
        )
        transcript = "\n".join(f"{item['role']}: {item['text']}" for item in history[-12:])
        prompt = f"{system}\nHistórico:\n{transcript}\nusuário: {text}"
        try:
            response = await client.aio.models.generate_content(
                model=gemini_service.model_name,
                contents=prompt,
                config={"system_instruction": system, "tools": tools, "temperature": 0.7},
            )
            calls = []
            output = []
            for candidate in getattr(response, "candidates", []) or []:
                for part in getattr(getattr(candidate, "content", None), "parts", []) or []:
                    if getattr(part, "function_call", None):
                        call = part.function_call
                        calls.append({"name": call.name, "args": dict(call.args or {})})
                    if getattr(part, "text", None):
                        output.append(part.text)
            return "\n".join(output).strip(), calls
        except Exception:
            logger.exception("Falha na conversa com Gemini; usando orquestração local.")
            return "", []

    @staticmethod
    def _script_to_dict(script: ScriptData) -> dict[str, str]:
        return {
            "hook": script.hook,
            "problem": script.problem,
            "solution": script.solution,
            "proof": script.proof,
            "cta": script.cta,
            "full_text": script.full_text,
        }

    @staticmethod
    def _script_from_dict(data: dict[str, Any]) -> ScriptData:
        return ScriptData(
            hook=str(data.get("hook", "")),
            problem=str(data.get("problem", "")),
            solution=str(data.get("solution", "")),
            proof=str(data.get("proof", "")),
            cta=str(data.get("cta", "")),
            full_text=str(data.get("full_text", "")),
        )

    def _preview_text(self, brief: dict[str, Any], script: ScriptData) -> str:
        style_name = STYLE_TEMPLATES.get(brief.get("style", "product_demo"), brief.get("style", "product_demo"))
        media_name = {
            "real_photo": "foto real enviada",
            "generated_placeholder": "imagem de IA/placeholder (ainda não configurada)",
            "placeholder": "placeholder visual",
        }.get(brief.get("media_source", ""), "mídia escolhida")
        return (
            f"🎬 Prévia do roteiro para {brief.get('product_name', 'seu produto')}\n\n"
            f"Estilo: {style_name}\n"
            f"Visual: {media_name}\n\n"
            f"🪝 Gancho (0–3s):\n{script.hook}\n\n"
            f"⚠️ Problema (3–8s):\n{script.problem}\n\n"
            f"💡 Solução (8–14s):\n{script.solution}\n\n"
            f"⭐ Diferencial (14–17s):\n{script.proof}\n\n"
            f"👉 CTA (17–20s):\n{script.cta}\n\n"
            "🗣 Texto completo para copiar:\n"
            f"{script.full_text}\n\n"
            "Revise com calma. Você pode aprovar, pedir uma correção escrevendo o que mudar, "
            "ou tocar em regenerar. O pedido só entra na fila depois da aprovação."
        )

    async def _generate_preview(self, chat_id: int, brief: dict[str, Any], history: list[dict[str, str]]) -> AgentReply:
        style = brief.get("style", "product_demo")
        script = await gemini_service.generate_script(
            product_name=brief["product_name"],
            description=brief.get("benefits", ""),
            target_audience=brief.get("target_audience", "pessoas interessadas no produto"),
            affiliate_link=brief.get("affiliate_link", ""),
            photos_count=len(brief.get("media_paths", [])) or 1,
            variation_index=int(brief.get("variation_index", 0)),
            style=style,
            link_destination=brief.get("link_destination", "manual_copy"),
            correction=brief.get("last_correction", ""),
        )
        brief["script"] = self._script_to_dict(script)
        brief["awaiting_approval"] = True
        preview = self._preview_text(brief, script)
        history.append({"role": "assistant", "text": preview})
        self._save_session(chat_id, brief, history, "WAITING_APPROVAL")
        return AgentReply(text=preview, script=script, awaiting_approval=True)

    async def approve(self, chat_id: int) -> AgentReply:
        brief, history, state = self._get_session(chat_id)
        if state != "WAITING_APPROVAL" or not brief.get("script"):
            return AgentReply("Não encontrei uma prévia aguardando aprovação. Use /novo_video para começar.")
        brief["awaiting_approval"] = False
        return await self._finalize(chat_id, brief, history)

    async def regenerate(self, chat_id: int) -> AgentReply:
        brief, history, state = self._get_session(chat_id)
        if state != "WAITING_APPROVAL" or not brief.get("script"):
            return AgentReply("Ainda não há um roteiro para regenerar. Use /novo_video para começar.")
        brief["awaiting_approval"] = False
        brief["variation_index"] = int(brief.get("variation_index", 0)) + 1
        return await self._generate_preview(chat_id, brief, history)

    def _apply_correction(self, brief: dict[str, Any], text: str) -> None:
        """Aplica correções óbvias imediatamente e deixa o restante no prompt."""
        lowered = text.lower()
        style = self._style_from_text(text)
        if style:
            brief["style"] = style
        audience_match = re.search(r"(?:público|publico|para)\s*[:\-]?\s*(.+?)(?:\.|$)", text, re.IGNORECASE)
        if audience_match and "estilo" not in lowered:
            brief["target_audience"] = audience_match.group(1).strip()
        benefits_match = re.search(r"(?:benefícios?|beneficios?|diferenciais?)\s*[:\-]?\s*(.+)$", text, re.IGNORECASE)
        if benefits_match:
            brief["benefits"] = benefits_match.group(1).strip()
        brief["last_correction"] = text

    async def _finalize(self, chat_id: int, brief: dict[str, Any], history: list[dict[str, str]]) -> AgentReply:
        style = brief.get("style", "product_demo")
        link = brief.get("affiliate_link", "")
        script = self._script_from_dict(brief["script"])
        product = ProductData(
            name=brief["product_name"],
            description=brief.get("benefits", ""),
            target_audience=brief.get("target_audience", ""),
            affiliate_link=link,
            photo_local_path=(brief.get("media_paths") or [""])[0],
            photos_local_paths=brief.get("media_paths", []),
        )
        job = queue_service.create_job(
            chat_id=chat_id,
            user_name=str(chat_id),
            product=product,
            script=script,
            provider_id=brief.get("provider_id", "adb_youtube_create"),
            style_id=style,
            media_source=brief.get("media_source", "real_photo"),
            link_destination=brief.get("link_destination", "manual_copy"),
            agent_session_id=str(chat_id),
        )
        with self._lock, self._connect() as db:
            self._learn_from_session(db, history, brief, "completed")
            db.execute("DELETE FROM agent_sessions WHERE chat_id=?", (chat_id,))
        return AgentReply(
            text=(f"✅ Entendi tudo sobre {brief['product_name']}.\n\n"
                  f"Escolhi o estilo {style} e o motor {PROVIDER_LABELS.get(job.provider_id, job.provider_id)}.\n"
                  f"Seu pedido {job.job_id[:8]} entrou na fila. Vou te avisar aqui quando o vídeo estiver pronto.\n\n"
                  "🗣 O roteiro completo continua acima para você copiar quando quiser."),
            job=job,
            script=script,
        )

    async def handle_message(self, chat_id: int, text: str, media_path: Optional[str] = None) -> AgentReply:
        brief, history, state = self._get_session(chat_id)
        text = text.strip()
        history.append({"role": "user", "text": text})

        # Depois da prévia, qualquer texto vira correção/regeneração; nunca
        # volta a abrir um formulário nem cria pedido sem aprovação explícita.
        if state == "WAITING_APPROVAL" and not media_path:
            if self._is_yes(text):
                return await self.approve(chat_id)
            if self._is_regenerate(text):
                brief["awaiting_approval"] = False
                brief["variation_index"] = int(brief.get("variation_index", 0)) + 1
                return await self._generate_preview(chat_id, brief, history)
            self._apply_correction(brief, text)
            brief["awaiting_approval"] = False
            brief["variation_index"] = int(brief.get("variation_index", 0)) + 1
            return await self._generate_preview(chat_id, brief, history)

        if media_path:
            brief.setdefault("media_paths", []).append(media_path)
            brief["media_source"] = "real_photo"

        rag = self.retrieve(text + " " + json.dumps(brief, ensure_ascii=False))
        try:
            model_text, calls = await asyncio.wait_for(
                self._gemini_turn(brief, history, text, rag), timeout=12
            )
        except asyncio.TimeoutError:
            logger.warning("Gemini excedeu o limite de 12s na conversa; usando fallback local.")
            model_text, calls = "", []
        for call in calls:
            name, args = call["name"], call["args"]
            if name == "update_brief":
                for key, value in args.items():
                    if value is not None and key in {"product_name", "benefits", "target_audience", "affiliate_link", "style", "link_destination", "media_source", "provider_id"}:
                        brief[key] = value
            elif name == "generate_product_image" and args.get("confirmed") is True:
                brief["media_source"] = "generated"
            elif name == "select_video_provider":
                provider_id = str(args.get("provider_id", ""))
                if is_provider_available(provider_id):
                    brief["provider_id"] = provider_id
            elif name == "record_user_correction":
                brief["last_correction"] = str(args.get("correction", ""))

        # O parser local só completa o que o Gemini não conseguiu extrair.
        self._infer_brief(brief, text)
        self._apply_defaults(brief)
        if brief.get("media_source") in {"generated", "placeholder"} and not brief.get("media_paths"):
            image_path = None
            if brief.get("media_source") == "generated":
                image_path = await image_provider.generate(
                    f"Imagem vertical comercial e fiel de {brief.get('product_name', 'produto')}. "
                    f"Não invente embalagem nem características; use visual ilustrativo sem texto."
                )
            if image_path is None:
                image_path = self._create_placeholder(brief.get("product_name", "produto"))
                brief["media_source"] = "generated_placeholder" if brief.get("media_source") == "generated" else "placeholder"
            brief.setdefault("media_paths", []).append(image_path)
        if brief.get("media_source") == "none" and brief.get("provider_id") == "adb_youtube_create":
            brief["media_source"] = "placeholder"
            brief.setdefault("media_paths", []).append(self._create_placeholder(brief.get("product_name", "produto")))
        if brief.get("provider_id") and not is_provider_available(brief["provider_id"]):
            brief.pop("provider_id", None)
        self._apply_defaults(brief)
        if self._missing_question(brief) is None:
            return await self._generate_preview(chat_id, brief, history)
        reply = model_text or self._fallback_reply(brief, text)
        history.append({"role": "assistant", "text": reply})
        self._save_session(chat_id, brief, history)
        return AgentReply(text=reply)

    def _create_placeholder(self, product_name: str) -> str:
        """Cria um PNG mínimo válido sem depender de Pillow ou ImageMagick."""
        output = settings.media_inputs_dir / f"placeholder_{uuid.uuid4().hex[:8]}.png"
        png_data = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        output.write_bytes(base64.b64decode(png_data))
        logger.info("Placeholder visual criado para o produto: %s", product_name)
        return str(output)


agent_service = AgentService()

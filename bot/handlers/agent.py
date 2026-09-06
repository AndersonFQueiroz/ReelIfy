"""Handlers do agente conversacional multimodal."""
from __future__ import annotations

import logging
import uuid

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

from config.settings import settings
from bot.handlers.start import is_user_authorized
from bot.services.agent_service import agent_service

logger = logging.getLogger(__name__)


def _denied_text(chat_id: int) -> str:
    return (
        "⛔ Você não possui autorização para usar este bot.\n"
        f"Seu ID do Telegram é: `{chat_id}`\n\n"
        "Se você recebeu a palavra mágica, use `/liberar SUA_SENHA`."
    )


async def start_agent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia ou reinicia uma sessão conversacional."""
    chat_id = update.effective_chat.id
    if not is_user_authorized(chat_id):
        await update.message.reply_text(_denied_text(chat_id), parse_mode="Markdown")
        return ConversationHandler.END
    agent_service.start_session(chat_id)
    await update.message.reply_text(
        "🎬 Vamos criar seu vídeo. Pode me contar naturalmente qual produto quer divulgar? "
        "Você pode enviar texto, link e foto na ordem que preferir.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


async def cancel_agent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    if is_user_authorized(chat_id):
        agent_service.cancel_session(chat_id)
        await update.message.reply_text("🚫 Conversa cancelada. Quando quiser, é só me chamar novamente.")
    else:
        await update.message.reply_text(_denied_text(chat_id), parse_mode="Markdown")
    return ConversationHandler.END


async def agent_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not is_user_authorized(chat_id):
        await update.message.reply_text(_denied_text(chat_id), parse_mode="Markdown")
        return
    reply = await agent_service.handle_message(chat_id, update.message.text)
    await update.message.reply_text(reply.text)


async def agent_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not is_user_authorized(chat_id):
        await update.message.reply_text(_denied_text(chat_id), parse_mode="Markdown")
        return
    try:
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
        else:
            file_id = update.message.document.file_id
        telegram_file = await context.bot.get_file(file_id)
        local_path = settings.media_inputs_dir / f"agent_{uuid.uuid4().hex[:10]}.jpg"
        await telegram_file.download_to_drive(custom_path=local_path)
        reply = await agent_service.handle_message(chat_id, "Enviei uma foto real do produto.", str(local_path))
        await update.message.reply_text(reply.text)
    except Exception:
        logger.exception("Falha ao receber mídia na conversa do agente.")
        await update.message.reply_text("❌ Não consegui baixar essa imagem. Tente enviá-la novamente.")

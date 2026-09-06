"""Handlers do agente conversacional multimodal."""
from __future__ import annotations

import logging
import uuid

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler

from config.settings import settings
from bot.handlers.start import is_user_authorized
from bot.services.agent_service import agent_service

logger = logging.getLogger(__name__)


def _review_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Aprovar e colocar na fila", callback_data="agent:approve"),
        ],
        [
            InlineKeyboardButton("✏️ Corrigir escrevendo", callback_data="agent:edit"),
            InlineKeyboardButton("🔄 Regenerar", callback_data="agent:regenerate"),
        ],
        [InlineKeyboardButton("❌ Cancelar", callback_data="agent:cancel")],
    ])


async def _send_agent_reply(message, reply) -> None:
    await message.reply_text(
        reply.text,
        reply_markup=_review_keyboard() if reply.awaiting_approval else None,
    )


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
    await _send_agent_reply(update.message, reply)


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
        await _send_agent_reply(update.message, reply)
    except Exception:
        logger.exception("Falha ao receber mídia na conversa do agente.")
        await update.message.reply_text("❌ Não consegui baixar essa imagem. Tente enviá-la novamente.")


async def agent_review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa as ações da prévia sem permitir enfileiramento acidental."""
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    if not is_user_authorized(chat_id):
        await query.edit_message_text(_denied_text(chat_id), parse_mode="Markdown")
        return

    action = query.data.split(":", 1)[-1]
    if action == "approve":
        reply = await agent_service.approve(chat_id)
        # Mantém a prévia integral no histórico para cópia; apenas remove os
        # botões e envia a confirmação em uma nova mensagem.
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(reply.text)
    elif action == "regenerate":
        reply = await agent_service.regenerate(chat_id)
        await query.edit_message_text(
            reply.text,
            reply_markup=_review_keyboard() if reply.awaiting_approval else None,
        )
    elif action == "edit":
        await query.edit_message_text(
            "✏️ Escreva agora, em uma mensagem, o que você quer mudar no roteiro. "
            "Exemplo: “troque o público para pais e deixe o gancho mais natural”."
        )
    elif action == "cancel":
        agent_service.cancel_session(chat_id)
        await query.edit_message_text("🚫 Pedido cancelado. Quando quiser, use /novo_video novamente.")

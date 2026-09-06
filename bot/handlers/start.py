"""
Handler para os comandos /start e /ajuda.
Inclui verificação de autorização (whitelist).
"""
import hmac
import json
import logging
from telegram import Update
from telegram.helpers import escape_markdown
from telegram.ext import ContextTypes

from config.settings import settings

logger = logging.getLogger(__name__)
def _md(value) -> str:
    """Escapa valores dinâmicos para o Markdown legado do Telegram."""
    return escape_markdown(str(value), version=1)


AUTHORIZED_USERS_FILE = settings.base_dir / "data" / "authorized_chat_ids.json"


def _load_persistent_authorized_ids() -> set[int]:
    try:
        with AUTHORIZED_USERS_FILE.open("r", encoding="utf-8") as file:
            values = json.load(file)
        return {int(value) for value in values if str(value).lstrip("-").isdigit()}
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        return set()


def _save_persistent_authorized_ids(chat_ids: set[int]) -> None:
    AUTHORIZED_USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = AUTHORIZED_USERS_FILE.with_suffix(".tmp")
    with temp_file.open("w", encoding="utf-8") as file:
        json.dump(sorted(chat_ids), file, indent=2)
    temp_file.replace(AUTHORIZED_USERS_FILE)


async def get_bot_display_name(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Obtém o nome atual do bot diretamente do Telegram."""
    try:
        bot_profile = await context.bot.get_me()
        return bot_profile.first_name or bot_profile.username or "este bot"
    except Exception:
        return "este bot"


def _is_admin(chat_id: int) -> bool:
    return chat_id in settings.admin_chat_ids


def _grant_access(chat_id: int) -> None:
    authorized_ids = _load_persistent_authorized_ids()
    authorized_ids.add(chat_id)
    _save_persistent_authorized_ids(authorized_ids)


def _revoke_access(chat_id: int) -> bool:
    authorized_ids = _load_persistent_authorized_ids()
    if chat_id not in authorized_ids:
        return False
    authorized_ids.remove(chat_id)
    _save_persistent_authorized_ids(authorized_ids)
    return True


def is_user_authorized(chat_id: int) -> bool:
    """Verifica acesso pela whitelist do .env ou pela autorização persistente."""
    return chat_id in settings.allowed_chat_ids or chat_id in _load_persistent_authorized_ids()


async def liberate_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Libera o próprio chat usando a palavra mágica configurada."""
    supplied_word = " ".join(context.args).strip()
    if not settings.magic_word or not supplied_word or not hmac.compare_digest(supplied_word, settings.magic_word):
        await update.message.reply_text("⛔ Palavra mágica inválida.")
        return

    _grant_access(update.effective_chat.id)
    bot_name = await get_bot_display_name(context)

    await update.message.reply_text(
        "✅ *Acesso liberado permanentemente!*\n\n"
        f"Agora você já pode criar vídeos pelo {_md(bot_name)}.\n\n"
        "📌 *Comandos principais:*\n"
        "• `/novo_video` — cria um pedido com revisão e aprovação do roteiro.\n"
        "• `/status` — consulta o andamento dos seus pedidos.\n"
        "• `/ajuda` — mostra as instruções completas do bot.\n"
        "• `/cancelar` — cancela a operação atual.\n\n"
        "🧭 *Como funciona:*\n"
        "1. Use `/novo_video` e converse comigo do seu jeito: texto, link e foto podem ser enviados em qualquer ordem.\n"
        "2. Eu identifico o produto e só pergunto o que realmente estiver faltando. Público, estilo e destino do link têm padrões inteligentes.\n"
        "3. Você pode enviar uma foto real ou continuar com imagem gerada/placeholder, sempre identificado.\n"
        "4. Eu mostro o roteiro completo no chat para você copiar, corrigir ou regenerar.\n"
        "5. Só depois de você aprovar o roteiro o pedido entra na fila de produção.\n\n"
        "💡 *Dica:* use `/ajuda` a qualquer momento para rever todas as etapas.\n"
        "",
        parse_mode="Markdown",
    )


async def authorize_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Autoriza outro chat sem editar o .env."""
    if not _is_admin(update.effective_chat.id):
        await update.message.reply_text("⛔ Comando restrito ao administrador.")
        return
    if len(context.args) != 1 or not context.args[0].lstrip("-").isdigit():
        await update.message.reply_text("Uso: /autorizar ID_DO_TELEGRAM")
        return

    target_chat_id = int(context.args[0])
    _grant_access(target_chat_id)
    await update.message.reply_text(f"✅ Chat {target_chat_id} autorizado permanentemente.")


async def revoke_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Revoga uma autorização persistente."""
    if not _is_admin(update.effective_chat.id):
        await update.message.reply_text("⛔ Comando restrito ao administrador.")
        return
    if len(context.args) != 1 or not context.args[0].lstrip("-").isdigit():
        await update.message.reply_text("Uso: /revogar ID_DO_TELEGRAM")
        return

    target_chat_id = int(context.args[0])
    if target_chat_id in settings.allowed_chat_ids:
        await update.message.reply_text("⚠️ Esse ID está no .env e deve ser removido manualmente de ALLOWED_CHAT_IDS.")
        return
    if _revoke_access(target_chat_id):
        await update.message.reply_text(f"✅ Acesso do chat {target_chat_id} revogado.")
    else:
        await update.message.reply_text("ℹ️ Esse chat não possuía autorização persistente.")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensagem de boas-vindas e verificação de acesso."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    if not is_user_authorized(chat_id):
        logger.warning(f"Acesso negado para o chat_id: {chat_id} (Usuário: {user.username})")
        await update.message.reply_text(
            f"⛔ Olá, {_md(user.first_name)}! Você não possui autorização para utilizar este robô.\n"
            f"Seu ID do Telegram é: `{chat_id}`\n\n"
            f"Se você recebeu a palavra mágica, use /liberar PALAVRA.",
            parse_mode="Markdown"
        )
        return

    logger.info(f"Usuário autorizado acessou /start: {chat_id} ({user.username})")
    bot_name = await get_bot_display_name(context)
    await update.message.reply_text(
        f"👋 Olá, *{_md(user.first_name)}*! Eu sou o {_md(bot_name)}.\n\n"
        "Sou seu assistente de criação de vídeos curtos com IA. Você pode me mandar uma ideia, produto, benefícios, link ou foto em qualquer ordem.\n\n"
        "Eu organizo as informações, escolho padrões seguros quando algo opcional não for informado, mostro o roteiro para revisão e só envio para a fila depois da sua aprovação.\n\n"
        "📌 *Comandos:*\n"
        "• `/novo_video` — iniciar uma criação\n"
        "• `/status` — acompanhar pedidos\n"
        "• `/ajuda` — ver o guia de uso\n"
        "• `/cancelar` — cancelar a conversa atual\n\n"
        "Para começar, use `/novo_video` ou envie uma mensagem com a ideia do vídeo.",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Exibe instruções de uso do robô."""
    chat_id = update.effective_chat.id
    if not is_user_authorized(chat_id):
        await update.message.reply_text(
            "⛔ Você não possui autorização para usar este bot.\n"
            f"Seu ID do Telegram é: `{chat_id}`\n\n"
            "Se você recebeu a palavra mágica, use `/liberar SUA_SENHA`.",
            parse_mode="Markdown",
        )
        return

    bot_name = await get_bot_display_name(context)
    await update.message.reply_text(
        f"📖 *Como usar o {_md(bot_name)}:*\n\n"
        "1. Use `/novo_video`. Você pode explicar tudo em uma mensagem ou ir enviando aos poucos.\n"
        "2. Informe o produto e, se souber, os benefícios. Eu só perguntarei o indispensável.\n"
        "3. Link de afiliado é opcional. Quando existir, o CTA prioriza link abaixo, descrição ou comentário fixado — não link na bio.\n"
        "4. Foto real é opcional: você pode enviar uma, pedir imagem por IA quando houver um provedor configurado ou usar placeholder.\n"
        "5. O estilo padrão é demonstração, mas você pode pedir POV, unboxing, comparativo, antes e depois, oferta ou outro estilo.\n"
        "6. Antes de produzir, receba o roteiro completo no chat. Você pode copiar, escrever correções ou tocar em regenerar.\n"
        "7. O pedido só entra na fila quando você tocar em *Aprovar e colocar na fila*.\n\n"
        "📌 *Comandos disponíveis:*\n"
        "• `/novo_video` — iniciar uma criação\n"
        "• `/status` — acompanhar seus pedidos\n"
        "• `/cancelar` — cancelar a conversa atual\n"
        "• `/ajuda` — abrir este guia novamente\n\n"
        "Se o Gemini estiver temporariamente indisponível, o bot mantém a conversa e usa um fallback seguro; você não perde o briefing nem tem pedido criado sem aprovação.",
        parse_mode="Markdown"
    )

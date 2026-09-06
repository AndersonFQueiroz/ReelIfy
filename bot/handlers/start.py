"""
Handler para os comandos /start e /ajuda.
Inclui verificação de autorização (whitelist).
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from config.settings import settings

logger = logging.getLogger(__name__)


def is_user_authorized(chat_id: int) -> bool:
    """Verifica se o usuário está na whitelist configurada no .env."""
    if not settings.allowed_chat_ids:
        # Se nenhuma whitelist estiver configurada, permite em modo dev
        return True
    return chat_id in settings.allowed_chat_ids


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensagem de boas-vindas e verificação de acesso."""
    user = update.effective_user
    chat_id = update.effective_chat.id

    if not is_user_authorized(chat_id):
        logger.warning(f"Acesso negado para o chat_id: {chat_id} (Usuário: {user.username})")
        await update.message.reply_text(
            f"⛔ Olá, {user.first_name}! Você não possui autorização para utilizar este robô.\n"
            f"Seu ID do Telegram é: `{chat_id}`\n\n"
            f"Solicite autorização ao administrador para liberar seu acesso.",
            parse_mode="Markdown"
        )
        return

    logger.info(f"Usuário autorizado acessou /start: {chat_id} ({user.username})")
    await update.message.reply_text(
        f"👋 Olá, *{user.first_name}*! Seja bem-vinda ao ReelIfy — Gerador Automático de Vídeos!\n\n"
        f"Com este robô, você pode transformar fotos e links de produtos em vídeos curtos persuasivos (20s) prontos para o YouTube Shorts, Reels e TikTok.\n\n"
        f"📌 *Comandos Disponíveis:*\n"
        f"• `/novo_video` - Iniciar o pedido de um novo vídeo\n"
        f"• `/status` - Consultar o andamento dos seus pedidos\n"
        f"• `/ajuda` - Ver instruções detalhadas\n"
        f"• `/cancelar` - Interromper o pedido atual a qualquer momento\n\n"
        f"Para começar agora mesmo, clique ou digite `/novo_video`!",
        parse_mode="Markdown"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Exibe instruções de uso do robô."""
    chat_id = update.effective_chat.id
    if not is_user_authorized(chat_id):
        return

    await update.message.reply_text(
        "📖 *Como funciona o fluxo de criação de vídeos:*\n\n"
        "1. Digite `/novo_video`.\n"
        "2. O bot solicitará:\n"
        "   - *Nome do produto*\n"
        "   - *Benefícios principais* (o que ele faz de melhor)\n"
        "   - *Público-alvo* (ex: quem quer economizar tempo, mães, gamers, etc.)\n"
        "   - *Seu link de afiliado*\n"
        "   - *Uma boa foto do produto* (fundo limpo e boa iluminação)\n"
        "3. A inteligência artificial (Google Gemini) cria um roteiro magnético de 20s dividido em Gancho, Problema, Solução, Prova Social e CTA.\n"
        "4. O pedido entra na fila de produção no celular.\n"
        "5. O celular automatizado gera o vídeo no *YouTube Create* e o robô te entrega o arquivo final em vídeo MP4 aqui no chat!\n\n"
        "Dúvidas ou travamentos? Use `/status` para acompanhar.",
        parse_mode="Markdown"
    )

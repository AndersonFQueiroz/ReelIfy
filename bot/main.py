"""
Ponto de Entrada Principal do ReelIfy Bot do Telegram.
Inicializa o bot, registra os handlers e inicia o pooling assíncrono.
"""
import logging
import sys
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from config.settings import settings
from bot.handlers.start import start_command, help_command, liberate_command, authorize_command, revoke_command
from bot.handlers.status import status_command
from bot.handlers.agent import start_agent, cancel_agent, agent_text, agent_photo

# Configuração de Logging Central
logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(settings.logs_dir / "bot.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("bot.main")


async def error_handler(update, context):
    """Registra falhas de handlers e informa o usuário quando possível."""
    error = context.error
    logger.error(
        "Erro não tratado ao processar uma atualização: %s",
        error,
        exc_info=(type(error), error, error.__traceback__) if error else None,
    )
    message = getattr(update, "effective_message", None)
    if message:
        try:
            await message.reply_text(
                "⚠️ Não consegui concluir esse comando agora. Tente novamente em alguns segundos."
            )
        except Exception:
            logger.exception("Também não foi possível enviar a mensagem de erro ao usuário.")


def create_bot_app():
    """Cria e configura a aplicação do Telegram Bot."""
    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN não configurado no arquivo .env!")
        print("\n[ERRO CRÍTICO] Por favor configure o TELEGRAM_BOT_TOKEN no seu arquivo .env antes de rodar o bot.")
        return None

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    # Registro de Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("ajuda", help_command))
    app.add_handler(CommandHandler("liberar", liberate_command))
    app.add_handler(CommandHandler("autorizar", authorize_command))
    app.add_handler(CommandHandler("revogar", revoke_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("pedidos", status_command))
    app.add_handler(CommandHandler("novo_video", start_agent))
    app.add_handler(CommandHandler("cancelar", cancel_agent))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, agent_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, agent_text))
    app.add_error_handler(error_handler)

    return app


def main():
    """Inicia o Bot do Telegram via Polling."""
    logger.info("Iniciando ReelIfy Bot...")
    app = create_bot_app()
    if not app:
        sys.exit(1)

    logger.info("Bot conectado e aguardando comandos no Telegram!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

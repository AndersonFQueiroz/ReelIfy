"""
Ponto de Entrada Principal do ReelIfy Bot do Telegram.
Inicializa o bot, registra os handlers e inicia o pooling assíncrono.
"""
import logging
import sys
from telegram.ext import ApplicationBuilder, CommandHandler

from config.settings import settings
from bot.handlers.start import start_command, help_command
from bot.handlers.status import status_command
from bot.handlers.order import order_conversation_handler

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
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("pedidos", status_command))
    app.add_handler(order_conversation_handler)

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

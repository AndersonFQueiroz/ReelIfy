"""
Handler para o comando /status.
Permite ao usuário acompanhar o progresso dos seus vídeos enfileirados e concluídos.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from config.settings import settings
from bot.handlers.start import is_user_authorized
from bot.services.queue_service import queue_service, JobStatus

logger = logging.getLogger(__name__)

STATUS_EMOJIS = {
    JobStatus.PENDING: "⏳ Na Fila (aguardando celular)",
    JobStatus.PROCESSING: "⚙️ Em Produção no YouTube Create",
    JobStatus.COMPLETED: "✅ Concluído e Entregue",
    JobStatus.FAILED: "❌ Falhou no processamento",
}


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lista todos os pedidos recentes do usuário solicitante."""
    chat_id = update.effective_chat.id
    if not is_user_authorized(chat_id):
        return

    jobs = queue_service.get_jobs_by_chat_id(chat_id)

    if not jobs:
        await update.message.reply_text(
            "📭 Você ainda não solicitou nenhum vídeo.\n\n"
            "Digite `/novo_video` para criar o seu primeiro vídeo com o ReelIfy!",
            parse_mode="Markdown"
        )
        return

    # Exibir os últimos 5 pedidos (mais recentes primeiro)
    recent_jobs = sorted(jobs, key=lambda j: j.created_at, reverse=True)[:5]

    lines = ["📊 *Status dos Seus Pedidos Recentes:*\n"]
    for idx, job in enumerate(recent_jobs, 1):
        status_label = STATUS_EMOJIS.get(job.status, str(job.status))
        lines.append(
            f"*{idx}. {job.product.name}*\n"
            f"• *ID:* `{job.job_id[:8]}`\n"
            f"• *Situação:* {status_label}\n"
            f"• *Criado em:* {job.created_at[:19].replace('T', ' ')}"
        )
        if job.status == JobStatus.FAILED and job.error_details:
            lines.append(f"• *Erro:* _{job.error_details}_")
        lines.append("")

    if settings.mock_device:
        lines.append(
            "\nℹ️ *Hardware:* Operando em modo simulado. O roteiro com IA está 100% funcional. "
            "A geração dos vídeos no celular iniciará quando o notebook 24/7 e o celular slave forem conectados via USB."
        )
    else:
        lines.append("💡 _Os vídeos são produzidos um a um no aparelho físico._")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

"""
Handler de Conversação para criação de novos pedidos de vídeo.

DOIS MODOS DE OPERAÇÃO:
  /novo_video  → Modo INTERATIVO: coleta dados, gera roteiro, exibe para aprovação com
                 botões inline [✅ Aprovar] [🔄 Regerar] [❌ Cancelar]. Só enfileira após
                 confirmação explícita do usuário.

  /auto        → Modo AUTÔNOMO: coleta os mesmos dados, gera roteiro e enfileira
                 automaticamente SEM pedir confirmação alguma.
"""
import logging
from pathlib import Path
import uuid
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import escape_markdown
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from config.settings import settings
from bot.handlers.start import is_user_authorized
from bot.services.gemini_service import gemini_service
from bot.services.queue_service import queue_service, ProductData

logger = logging.getLogger(__name__)
def _md(value) -> str:
    """Escapa valores dinâmicos para o Markdown legado do Telegram."""
    return escape_markdown(str(value), version=1)


# Estados da conversação
(
    STATE_NAME,
    STATE_DESCRIPTION,
    STATE_AUDIENCE,
    STATE_LINK,
    STATE_PHOTO_COUNT,
    STATE_PHOTO,
    STATE_CONFIRM_SCRIPT,
) = range(7)


# ─── Funções auxiliares ─────────────────────────────────────────────────────

def _format_script_preview(script_data) -> str:
    """Formata o roteiro gerado para exibição bonita no chat."""
    return (
        "📝 *Roteiro de 20s Gerado pela IA:*\n\n"
        f"🪝 *Gancho (0-3s):*\n_{_md(script_data.hook)}_\n\n"
        f"⚠️ *Problema (3-8s):*\n_{_md(script_data.problem)}_\n\n"
        f"💡 *Solução (8-14s):*\n_{_md(script_data.solution)}_\n\n"
        f"⭐ *Prova Social (14-17s):*\n_{_md(script_data.proof)}_\n\n"
        f"👉 *CTA (17-20s):*\n_{_md(script_data.cta)}_\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🗣️ *Texto completo para narração:*\n_{_md(script_data.full_text)}_"
    )


async def _generate_and_save_script(update, context):
    """Gera o roteiro via Gemini e armazena no contexto do usuário."""
    product_name = context.user_data["product_name"]
    description = context.user_data["description"]
    target_audience = context.user_data["target_audience"]
    affiliate_link = context.user_data.get("affiliate_link", "")
    photos_count = len(context.user_data.get("photos_local_paths", [])) or 1
    variation_index = context.user_data.get("script_variation", 0)

    script_data = await gemini_service.generate_script(
        product_name=product_name,
        description=description,
        target_audience=target_audience,
        affiliate_link=affiliate_link,
        photos_count=photos_count,
        variation_index=variation_index,
    )
    context.user_data["script_data"] = script_data
    return script_data


async def _enqueue_job(update, context) -> str:
    """Cria o job na fila e retorna a mensagem de confirmação."""
    chat_id = update.effective_chat.id
    user_name = update.effective_user.username or update.effective_user.first_name
    script_data = context.user_data["script_data"]

    photos_local = context.user_data.get("photos_local_paths", [])
    primary_photo = photos_local[0] if photos_local else context.user_data.get("photo_local_path", "")
    photos_ids = context.user_data.get("photos_file_ids", [])
    primary_id = photos_ids[0] if photos_ids else context.user_data.get("photo_file_id")

    product = ProductData(
        name=context.user_data["product_name"],
        description=context.user_data["description"],
        target_audience=context.user_data["target_audience"],
        affiliate_link=context.user_data.get("affiliate_link", ""),
        photo_local_path=primary_photo,
        photo_telegram_file_id=primary_id,
        photos_local_paths=photos_local,
        photos_telegram_file_ids=photos_ids,
    )

    job = queue_service.create_job(
        chat_id=chat_id,
        user_name=user_name,
        product=product,
        script=script_data,
    )

    hardware_msg = ""
    if settings.mock_device:
        hardware_msg = (
            "\n\n⏰ *Prazo da Fila (Apenas 1 Dia):*\n"
            "O roteiro com IA está salvo com sucesso! 📝\n"
            "Os pedidos aguardando conexão com o notebook/celular ficam guardados "
            "na fila por no máximo *1 dia (24 horas)*.\n"
            "Conecte o notebook e o celular com YouTube Create dentro de 24h para renderizar o vídeo automaticamente.\n"
            "⚠️ *Aviso:* Após 24h sem conexão, pedidos pendentes são excluídos automaticamente para evitar acúmulo e sobrecarga."
        )
    else:
        hardware_msg = (
            "\n\n⏰ *Nota sobre a Fila:* Pedidos pendentes são mantidos na fila por até *1 dia (24 horas)* "
            "aguardando a produção no celular físico."
        )

    return (
        f"🎉 *Pedido Enfileirado com Sucesso!*\n\n"
        f"🆔 *ID:* `{job.job_id[:8]}`\n"
        f"📦 *Produto:* {_md(product.name)}\n"
        f"📊 *Status:* Na fila de geração\n\n"
        f"📱 Assim que o vídeo for renderizado no YouTube Create, "
        f"enviaremos o MP4 aqui!\n\n"
        f"Acompanhe com `/status`.{hardware_msg}"
    )


# ─── Comandos de entrada (/novo_video e /auto) ─────────────────────────────

async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia a coleta no modo INTERATIVO (com confirmação de roteiro)."""
    chat_id = update.effective_chat.id
    if not is_user_authorized(chat_id):
        await update.message.reply_text("⛔ Você não tem permissão para usar este comando.")
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["auto_mode"] = False

    await update.message.reply_text(
        "🎬 *Modo Interativo — Novo Vídeo de 20s*\n\n"
        "Você vai informar os dados do produto e, após a IA criar o roteiro, "
        "poderá *aprovar*, *regerar* ou *cancelar* antes de enviar para produção.\n\n"
        "Qual é o *Nome do Produto*?\n"
        "_(Ex: Fritadeira Sem Óleo Air Fryer Digital 4.5L)_\n\n"
        "*(Cancele a qualquer momento com /cancelar)*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return STATE_NAME


async def start_auto_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia a coleta no modo AUTÔNOMO (sem confirmação, enfileira direto)."""
    chat_id = update.effective_chat.id
    if not is_user_authorized(chat_id):
        await update.message.reply_text("⛔ Você não tem permissão para usar este comando.")
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["auto_mode"] = True

    await update.message.reply_text(
        "🚀 *Modo Autônomo — Vídeo Express*\n\n"
        "Informe os dados do produto. Assim que a IA criar o roteiro, ele será "
        "enfileirado *automaticamente* para produção no celular, sem pedir confirmação.\n\n"
        "Qual é o *Nome do Produto*?\n"
        "_(Ex: Copo Térmico Stanley 40oz com Canudo)_\n\n"
        "*(Cancele a qualquer momento com /cancelar)*",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return STATE_NAME


# ─── Estados de coleta de dados (compartilhados por ambos os modos) ────────

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    product_name = update.message.text.strip()
    if len(product_name) < 3:
        await update.message.reply_text("Por favor, digite um nome de produto válido (mínimo 3 caracteres).")
        return STATE_NAME

    context.user_data["product_name"] = product_name
    await update.message.reply_text(
        f"✅ Produto: *{_md(product_name)}*\n\n"
        "Agora descreva os *principais benefícios e diferenciais*.\n"
        "_(Ex: Cozinha sem óleo, 4.5L, painel digital, limpa em 1 minuto)_",
        parse_mode="Markdown",
    )
    return STATE_DESCRIPTION


async def receive_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["description"] = update.message.text.strip()
    await update.message.reply_text(
        "🎯 Para quem é esse produto? Quem é o *Público-Alvo*?\n"
        "_(Ex: Mães ocupadas, quem mora sozinho, quem quer emagrecer)_",
        parse_mode="Markdown",
    )
    return STATE_AUDIENCE


async def receive_audience(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["target_audience"] = update.message.text.strip()
    await update.message.reply_text(
        "🔗 Envie o seu *Link de Afiliado* *(OPCIONAL)*:\n"
        "_(Ex: https://shopee.com.br/seu-link-de-afiliado)_\n\n"
        "💡 *Para que serve este link?*\n"
        "• O bot monta a legenda completa para você só copiar e postar junto com o vídeo.\n"
        "• Ajuda a IA a criar a chamada final do roteiro (ex: 'link abaixo ou na descrição').\n\n"
        "👉 *É 100% opcional!* Se você não tiver o link em mãos agora ou preferir adicionar depois, "
        "basta digitar *pular*, *nenhum* ou enviar apenas um ponto `.`",
        parse_mode="Markdown",
    )
    return STATE_LINK


async def receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw_text = update.message.text.strip()
    # Verifica se o usuário optou por pular o link
    if raw_text.lower() in ["pular", "skip", "nenhum", "nenhuma", ".", "-", "nao", "não", "sem link", "sem"]:
        context.user_data["affiliate_link"] = ""
        link_feedback = "⏩ *Link de afiliado pulado!* (Usaremos 'link abaixo ou na descrição' no roteiro)"
    else:
        context.user_data["affiliate_link"] = raw_text
        link_feedback = f"✅ *Link registrado:* `{raw_text}`"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ 1 Foto (Rápido)", callback_data="photo_count_1"),
            InlineKeyboardButton("📸 2 Fotos", callback_data="photo_count_2"),
            InlineKeyboardButton("🎬 3 Fotos (Recomendado)", callback_data="photo_count_3"),
        ]
    ])

    await update.message.reply_text(
        f"{link_feedback}\n\n"
        "📸 *Quantas fotos do produto você quer usar no vídeo?*\n"
        "💡 _O YouTube Create aceita até 3 fotos. Usar 2 ou 3 fotos permite alternar ângulos, detalhes e embalagem, tornando o vídeo muito mais dinâmico e vendedor!_\n\n"
        "Toque em uma opção abaixo (ou digite 1, 2 ou 3):",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )
    return STATE_PHOTO_COUNT


async def callback_photo_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback do clique nos botões [ 1 Foto ] [ 2 Fotos ] [ 3 Fotos ]."""
    query = update.callback_query
    await query.answer()
    count = int(query.data.split("_")[-1])
    return await _init_photo_collection(query.message, context, count, is_callback=True)


async def message_photo_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Caso o usuário digite o número '1', '2' ou '3' em vez de clicar no botão."""
    text = update.message.text.strip()
    if text in ["1", "2", "3"]:
        count = int(text)
        return await _init_photo_collection(update.message, context, count, is_callback=False)
    else:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("⚡ 1 Foto", callback_data="photo_count_1"),
                InlineKeyboardButton("📸 2 Fotos", callback_data="photo_count_2"),
                InlineKeyboardButton("🎬 3 Fotos", callback_data="photo_count_3"),
            ]
        ])
        await update.message.reply_text(
            "⚠️ Por favor, selecione quantas fotos deseja enviar tocando em uma das opções abaixo:",
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        return STATE_PHOTO_COUNT


async def _init_photo_collection(message, context, count: int, is_callback: bool = False) -> int:
    """Inicializa a estrutura de coleta e envia as instruções claras para o usuário."""
    context.user_data["target_photo_count"] = count
    context.user_data["photos_local_paths"] = []
    context.user_data["photos_file_ids"] = []

    if count == 1:
        text = (
            "📸 *Envie 1 FOTO de alta qualidade do produto!*\n\n"
            "Dicas:\n"
            "• Foto nítida e bem iluminada\n"
            "• Fundo limpo, formato vertical funciona melhor no Reels/TikTok\n\n"
            "Envie a imagem agora (como foto ou arquivo):"
        )
        reply_markup = None
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Concluir com as fotos enviadas", callback_data="photo_done_early")]
        ])
        text = (
            f"📸 *Envie as {count} FOTOS do produto!*\n\n"
            f"👉 *Dica:* Você pode selecionar as {count} fotos juntas de uma só vez na galeria do seu Telegram, "
            f"ou pode enviar uma por uma separadamente.\n\n"
            f"📊 *Progresso:* [ 0 de {count} fotos recebidas ]\n\n"
            f"Envie as fotos agora:"
        )
        reply_markup = keyboard

    if is_callback:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

    return STATE_PHOTO


async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recebe fotos do produto (individual ou em lote) até atingir a meta."""
    chat_id = update.effective_chat.id

    # Obter arquivo de imagem
    if update.message.photo:
        photo_obj = update.message.photo[-1]
        file_id = photo_obj.file_id
    elif update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith("image/"):
        photo_obj = update.message.document
        file_id = photo_obj.file_id
    else:
        await update.message.reply_text("⚠️ Envie uma imagem válida (JPEG ou PNG). Tente novamente.")
        return STATE_PHOTO

    target_count = context.user_data.get("target_photo_count", 1)
    photos_local = context.user_data.setdefault("photos_local_paths", [])
    photos_ids = context.user_data.setdefault("photos_file_ids", [])

    # Evita ultrapassar a meta caso cheguem fotos a mais
    if len(photos_local) >= target_count:
        return STATE_PHOTO

    try:
        idx = len(photos_local) + 1
        unique_name = f"{uuid.uuid4().hex[:8]}_p{idx}.jpg"
        local_photo_path = settings.media_inputs_dir / unique_name
        settings.ensure_directories()

        telegram_file = await context.bot.get_file(file_id)
        await telegram_file.download_to_drive(custom_path=local_photo_path)

        photos_local.append(str(local_photo_path))
        photos_ids.append(file_id)

        context.user_data["photo_local_path"] = photos_local[0]
        context.user_data["photo_file_id"] = photos_ids[0]
    except Exception as e:
        logger.error(f"Erro ao baixar imagem enviada: {e}", exc_info=True)
        await update.message.reply_text("❌ Falha ao baixar a foto. Tente enviá-la novamente.")
        return STATE_PHOTO

    current_count = len(photos_local)

    # Se ainda faltam fotos
    if current_count < target_count:
        remaining = target_count - current_count
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Concluir com as fotos enviadas até agora", callback_data="photo_done_early")]
        ])
        await update.message.reply_text(
            f"✅ *Foto [{current_count}/{target_count}] recebida!*\n\n"
            f"Aguardando mais {remaining} foto(s)...\n"
            f"_(Ou toque no botão abaixo para concluir com as fotos atuais)_",
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        return STATE_PHOTO

    # Meta de fotos atingida!
    if target_count > 1:
        await update.message.reply_text(
            f"🎉 *Todas as {target_count} fotos foram recebidas com sucesso!* 🚀\n"
            "⏳ *Gerando roteiro magnético com IA...*",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "⏳ *Foto recebida! Gerando roteiro magnético com IA...*",
            parse_mode="Markdown",
        )

    return await _finish_photo_step_and_process(update, context)


async def callback_photo_done_early(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Usuário tocou para concluir o envio antes de mandar todas as fotos."""
    query = update.callback_query
    await query.answer()
    photos_local = context.user_data.get("photos_local_paths", [])

    if not photos_local:
        await query.message.reply_text("⚠️ Você ainda não enviou nenhuma foto. Por favor, envie pelo menos 1 foto.")
        return STATE_PHOTO

    await query.edit_message_text(
        f"✅ *Concluindo com {len(photos_local)} foto(s) enviada(s)!*\n"
        "⏳ *Gerando roteiro magnético com IA...*",
        parse_mode="Markdown",
    )
    return await _finish_photo_step_and_process(update, context)


async def _finish_photo_step_and_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gera o roteiro com a IA e avança para modo autônomo ou interativo."""
    target_message = update.callback_query.message if update.callback_query else update.message

    try:
        script_data = await _generate_and_save_script(update, context)
        is_auto = context.user_data.get("auto_mode", False)

        if is_auto:
            confirmation_msg = await _enqueue_job(update, context)
            preview = _format_script_preview(script_data)
            await target_message.reply_text(
                f"🚀 *Modo Autônomo — Enfileirado automaticamente!*\n\n"
                f"{preview}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"{confirmation_msg}",
                parse_mode="Markdown",
            )
            context.user_data.clear()
            return ConversationHandler.END
        else:
            preview = _format_script_preview(script_data)
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Aprovar e Produzir", callback_data="script_approve"),
                    InlineKeyboardButton("🔄 Regerar Roteiro", callback_data="script_regen"),
                ],
                [
                    InlineKeyboardButton("❌ Cancelar Pedido", callback_data="script_cancel"),
                ],
            ])
            await target_message.reply_text(
                f"{preview}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👆 *O que deseja fazer com este roteiro?*",
                parse_mode="Markdown",
                reply_markup=keyboard,
            )
            return STATE_CONFIRM_SCRIPT

    except Exception as e:
        logger.error(f"Erro ao processar pedido: {e}", exc_info=True)
        await target_message.reply_text(
            f"❌ Erro ao registrar seu pedido: {e}\n"
            f"Tente novamente com `/novo_video` ou `/auto`."
        )
        context.user_data.clear()
        return ConversationHandler.END


# ─── Callbacks inline para confirmação de roteiro (modo interativo) ─────────

async def callback_approve_script(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Usuário aprovou o roteiro → enfileira para produção."""
    query = update.callback_query
    await query.answer()

    try:
        confirmation_msg = await _enqueue_job(update, context)
        await query.edit_message_text(
            f"✅ *Roteiro Aprovado!*\n\n{confirmation_msg}",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"Erro ao enfileirar após aprovação: {e}", exc_info=True)
        await query.edit_message_text(f"❌ Erro ao enfileirar: {e}")

    context.user_data.clear()
    return ConversationHandler.END


async def callback_regen_script(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Usuário quer um novo roteiro → roda o Gemini novamente."""
    query = update.callback_query
    await query.answer("🔄 Regenerando roteiro...")

    try:
        await query.edit_message_text("⏳ *Gerando um novo roteiro com a IA...*", parse_mode="Markdown")

        context.user_data["script_variation"] = context.user_data.get("script_variation", 0) + 1
        script_data = await _generate_and_save_script(update, context)
        preview = _format_script_preview(script_data)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Aprovar e Produzir", callback_data="script_approve"),
                InlineKeyboardButton("🔄 Regerar Roteiro", callback_data="script_regen"),
            ],
            [
                InlineKeyboardButton("❌ Cancelar Pedido", callback_data="script_cancel"),
            ],
        ])
        await query.edit_message_text(
            f"🔄 *Novo Roteiro Gerado:*\n\n"
            f"{preview}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👆 *O que deseja fazer com este roteiro?*",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        return STATE_CONFIRM_SCRIPT

    except Exception as e:
        logger.error(f"Erro ao regerar roteiro: {e}", exc_info=True)
        await query.edit_message_text(f"❌ Erro ao gerar novo roteiro: {e}")
        context.user_data.clear()
        return ConversationHandler.END


async def callback_cancel_script(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Usuário cancelou o pedido."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🚫 *Pedido cancelado.*\n\n"
        "Quando quiser, use `/novo_video` ou `/auto` para criar outro vídeo.",
        parse_mode="Markdown",
    )
    context.user_data.clear()
    return ConversationHandler.END


# ─── Cancelar a qualquer momento ───────────────────────────────────────────

async def cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "🚫 Operação cancelada.\n\n"
        "• `/novo_video` — Modo interativo (com aprovação do roteiro)\n"
        "• `/auto` — Modo autônomo (enfileira sem perguntar)",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


# ─── ConversationHandler unificado (exportado para main.py) ─────────────────

# Estados de coleta compartilhados
_shared_states = {
    STATE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
    STATE_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_description)],
    STATE_AUDIENCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_audience)],
    STATE_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link)],
    STATE_PHOTO_COUNT: [
        CallbackQueryHandler(callback_photo_count, pattern="^photo_count_[1-3]$"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_photo_count),
    ],
    STATE_PHOTO: [
        CallbackQueryHandler(callback_photo_done_early, pattern="^photo_done_early$"),
        MessageHandler(filters.PHOTO | filters.Document.IMAGE, receive_photo),
    ],
    STATE_CONFIRM_SCRIPT: [
        CallbackQueryHandler(callback_approve_script, pattern="^script_approve$"),
        CallbackQueryHandler(callback_regen_script, pattern="^script_regen$"),
        CallbackQueryHandler(callback_cancel_script, pattern="^script_cancel$"),
    ],
}

order_conversation_handler = ConversationHandler(
    entry_points=[
        CommandHandler("novo_video", start_order),
        CommandHandler("auto", start_auto_order),
    ],
    states=_shared_states,
    fallbacks=[CommandHandler("cancelar", cancel_order)],
)

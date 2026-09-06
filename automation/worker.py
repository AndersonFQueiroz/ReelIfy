"""
Worker de Automação Local.
Realiza polling contínuo na fila de pedidos, orquestra o controle do celular via ADB (ou Mock),
extrai o vídeo gerado e entrega diretamente ao usuário no Telegram.
"""
import asyncio
import logging
from pathlib import Path
import sys
import time
from typing import Optional
import aiohttp

from config.settings import settings
from telegram.helpers import escape_markdown
from bot.services.queue_service import queue_service, Job, JobStatus
from automation.adb.device import get_device

logging.basicConfig(
    format="%(asctime)s - [%(levelname)s] - [WORKER] - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(settings.logs_dir / "worker.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("automation.worker")
def _md(value: object) -> str:
    return escape_markdown(str(value), version=1)



class HardwareNotAvailableError(Exception):
    """Exceção levantada quando o notebook 24/7 ou celular slave não estão conectados."""
    pass


class VideoAutomationWorker:
    def __init__(self, queue_srv=None):
        self.queue_service = queue_srv or queue_service
        self.device = get_device()
        self.coords_config = settings.load_coordinates()
        self.coords = self.coords_config.get("coordinates", {})
        self.device_config = self.coords_config.get("device", {})
        self.package_name = self.device_config.get("package_name", "com.google.android.apps.youtube.creator")
        self.remote_temp_dir = self.device_config.get("temp_phone_dir", "/sdcard/Download/reelify_temp/")

    async def send_telegram_video(self, chat_id: int, video_path: Path, caption: str) -> bool:
        """Envia o vídeo MP4 finalizado para o chat do usuário no Telegram."""
        if not settings.telegram_bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN não configurado. Vídeo não pôde ser enviado.")
            return False

        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendVideo"
        try:
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field("chat_id", str(chat_id))
                data.add_field("caption", caption, content_type="text/plain")
                data.add_field("parse_mode", "Markdown")
                data.add_field(
                    "video",
                    open(video_path, "rb"),
                    filename=video_path.name,
                    content_type="video/mp4"
                )

                async with session.post(url, data=data) as resp:
                    if resp.status == 200:
                        logger.info(f"Vídeo entregue com sucesso no Telegram para chat_id {chat_id}!")
                        return True
                    else:
                        resp_text = await resp.text()
                        logger.error(f"Erro Telegram ({resp.status}): {resp_text}")
                        return False
        except Exception as e:
            logger.error(f"Exceção ao enviar vídeo via Telegram: {e}")
            return False

    async def send_telegram_alert(self, chat_id: int, message: str) -> None:
        """Envia um alerta de erro ou atualização de status para o usuário."""
        if not settings.telegram_bot_token:
            return
        url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown"
                }
                await session.post(url, json=payload)
        except Exception as e:
            logger.error(f"Falha ao enviar mensagem de alerta: {e}")

    def _tap_point(self, point_name: str) -> bool:
        """Toca em um botão a partir do nome definido no arquivo coordinates.yaml."""
        point = self.coords.get(point_name)
        if not point or len(point) != 2:
            logger.warning(f"Coordenada '{point_name}' não encontrada ou inválida em coordinates.yaml.")
            return False
        x, y = point[0], point[1]
        logger.info(f"Executando toque: {point_name} em [{x}, {y}]")
        return self.device.tap(x, y)

    def process_job(self, job: Job) -> bool:
        """Executa o ciclo completo de automação para um pedido."""
        logger.info(f"==> Iniciando processamento do Job {job.job_id} ({_md(job.product.name)})")

        photos_to_send = job.product.photos_local_paths or ([job.product.photo_local_path] if job.product.photo_local_path else [])
        remote_photo_paths = [
            f"{self.remote_temp_dir}product_photo_{i + 1}{Path(local_p).suffix or '.jpg'}"
            for i, local_p in enumerate(photos_to_send)
        ]
        remote_video_path = f"/sdcard/Movies/YouTubeCreate/final_{job.job_id[:8]}.mp4"
        local_video_output = settings.media_outputs_dir / f"video_{job.job_id[:8]}.mp4"

        try:
            # 0. Verificação prévia de hardware físico (celular slave + notebook via ADB)
            if not settings.mock_device and not self.device.is_connected():
                raise HardwareNotAvailableError(
                    "Celular Android (slave) ou notebook 24/7 de automação não detectado via ADB. "
                    "O roteiro do produto foi mantido seguro na fila! Conecte o aparelho físico para renderizar o vídeo."
                )

            # 1. Acordar e destravar celular
            self.device.wake_and_unlock()

            # 2. Transferir as fotos para o celular
            logger.info(f"Enviando {len(photos_to_send)} foto(s) do produto para o celular...")
            for local_p, rem_p in zip(photos_to_send, remote_photo_paths):
                if not self.device.push_file(local_p, rem_p):
                    raise RuntimeError(f"Falha ao transferir foto {local_p} para o armazenamento do celular.")

            # 3. Iniciar o app YouTube Create
            logger.info(f"Iniciando {self.package_name}...")
            self.device.stop_app(self.package_name)
            if not self.device.launch_app(self.package_name):
                raise RuntimeError("Falha ao abrir o aplicativo YouTube Create.")

            time.sleep(2)

            # 4. Navegação pela interface
            self._tap_point("btn_new_project")
            time.sleep(1)
            self._tap_point("tab_images")
            time.sleep(1)

            # Seleciona as miniaturas das fotos (até 3 fotos para múltiplos ângulos)
            thumbnail_points = ["first_image_thumbnail", "second_image_thumbnail", "third_image_thumbnail"]
            for idx in range(min(len(photos_to_send), 3)):
                self._tap_point(thumbnail_points[idx])
                time.sleep(0.5)

            self._tap_point("btn_import_media")
            time.sleep(2)

            # 5. Adicionar narração / roteiro
            self._tap_point("btn_add_voice_or_ai")
            time.sleep(1)
            self._tap_point("input_text_script")
            time.sleep(0.5)

            # Inserir o roteiro
            logger.info("Inserindo roteiro de 20 segundos...")
            self.device.input_text(job.script.full_text)
            time.sleep(1)

            # 6. Gerar e aguardar
            self._tap_point("btn_generate")
            logger.info("Geração acionada. Aguardando conclusão da renderização...")

            # Polling de conclusão (máximo 5 minutos)
            max_wait_seconds = 300
            start_wait = time.time()
            completed = False

            while (time.time() - start_wait) < max_wait_seconds:
                xml_dump = self.device.dump_ui_xml()
                if "Concluído" in xml_dump or "Exportar" in xml_dump or settings.mock_device:
                    logger.info("Geração de vídeo detectada como concluída!")
                    completed = True
                    break
                time.sleep(5)

            if not completed:
                raise TimeoutError("Tempo limite de renderização atingido no YouTube Create.")

            # 7. Exportar vídeo
            self._tap_point("btn_export_menu")
            time.sleep(1)
            self._tap_point("btn_export_confirm")
            time.sleep(3)

            # 8. Download do vídeo para o PC
            logger.info("Baixando vídeo renderizado do celular (adb pull)...")
            if not self.device.pull_file(remote_video_path, str(local_video_output)):
                raise RuntimeError("Falha ao puxar o arquivo de vídeo do celular.")

            # 9. Limpar arquivos remotos do celular
            self.device.clean_remote_files(remote_photo_paths + [remote_video_path])
            self.device.stop_app(self.package_name)

            # 10. Sucesso
            self.queue_service.mark_completed(job.job_id, str(local_video_output))
            logger.info(f"Job {job.job_id} concluído com sucesso localmente!")
            return True

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Erro durante execução do Job {job.job_id}: {error_msg}", exc_info=True)

            # Captura de screenshot e encerramento de app apenas se o device responder
            if self.device.is_connected():
                try:
                    error_screenshot = settings.logs_dir / f"error_{job.job_id[:8]}.png"
                    self.device.take_screenshot(str(error_screenshot))
                    self.device.stop_app(self.package_name)
                except Exception:
                    pass

            self.queue_service.mark_failed(job.job_id, error_msg)
            return False

    async def step_and_deliver(self) -> None:
        """Processa um job pendente e realiza a entrega no Telegram."""
        job = self.queue_service.get_next_pending_job()
        if not job:
            return

        success = self.process_job(job)
        if success:
            local_video = Path(job.output_video_path) if job.output_video_path else None
            affiliate_text = (
                f"🔗 *Link de Afiliado:* {_md(job.product.affiliate_link)}\n\n"
                if job.product.affiliate_link
                else "🔗 *Link de Afiliado:* não informado. Você pode adicionar um link depois.\n\n"
            )
            caption = (
                f"🎉 *Seu vídeo de 20s está pronto!*\n\n"
                f"📦 *Produto:* {_md(job.product.name)}\n"
                f"🎨 *Estilo:* {_md(job.style_id)}\n"
                f"⚙️ *Motor:* {_md(job.provider_id)}\n"
                f"{affiliate_text}"
                f"📝 *Roteiro Usado:*\n_{_md(job.script.full_text)}_\n\n"
                f"🚀 Prontinho para postar no YouTube Shorts, Reels e TikTok!"
            )
            if local_video and local_video.exists():
                await self.send_telegram_video(job.chat_id, local_video, caption)
        else:
            is_hw_missing = (
                "HardwareNotAvailable" in (job.error_details or "")
                or "não detectado via ADB" in (job.error_details or "")
            )
            if is_hw_missing:
                alert = (
                    f"📝 *Roteiro Pronto para:* *{_md(job.product.name)}*\n\n"
                    f"_{_md(job.script.full_text)}_\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"ℹ️ *Aviso sobre a Produção do Vídeo:*\n"
                    f"O notebook 24/7 e o celular slave ainda não estão conectados ao sistema.\n"
                    f"Por enquanto, você já tem o *roteiro completo gerado acima* para utilizar!\n\n"
                    f"⏰ *Prazo de Espera da Fila (Apenas 1 Dia):*\n"
                    f"O pedido fica guardado na fila por no máximo *1 dia (24 horas)*. "
                    f"Conecte o celular com YouTube Create via USB dentro desse prazo para gerar o vídeo automaticamente.\n\n"
                    f"⚠️ *Nota:* Após 24h sem conexão, pedidos pendentes são excluídos para evitar acúmulo e consumo excessivo de recursos."
                )
            else:
                alert = (
                    f"⚠️ *Atenção:* Ocorreu um problema ao produzir o vídeo do produto *{_md(job.product.name)}* no celular.\n\n"
                    f"🔍 *Detalhe técnico:* _{_md(job.error_details)}_\n\n"
                    f"O suporte foi alertado. Você pode tentar novamente com `/novo_video`."
                )
            await self.send_telegram_alert(job.chat_id, alert)

    async def run_loop(self) -> None:
        """Loop contínuo de polling da fila de trabalho."""
        logger.info(f"Worker ativo! Modo Mock={settings.mock_device}. Polling a cada {settings.worker_poll_interval}s...")
        while True:
            try:
                self.queue_service.cleanup_expired_jobs(max_age_hours=24)
                await self.step_and_deliver()
            except Exception as e:
                logger.error(f"Erro no loop do worker: {e}", exc_info=True)
            await asyncio.sleep(settings.worker_poll_interval)


def main():
    worker = VideoAutomationWorker()
    asyncio.run(worker.run_loop())


if __name__ == "__main__":
    main()

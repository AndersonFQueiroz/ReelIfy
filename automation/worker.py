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
        self.package_name = self.device_config.get("package_name", "com.google.android.apps.youtube.producer")
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

    def _tap_ui_or_point(self, *, fallback_name: str, resource_id: str = None, content_desc: str = None, text: str = None, contains: bool = False) -> bool:
        """Usa o seletor exposto pelo YouTube Create e recorre à coordenada calibrada."""
        if self.device.tap_ui(resource_id=resource_id, content_desc=content_desc, text=text, contains=contains):
            return True
        return self._tap_point(fallback_name)

    def _wait_for_ui(self, *, timeout: float, resource_id: str = None, content_desc: str = None, text: str = None, contains: bool = False) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if settings.mock_device:
                return True
            xml = self.device.dump_ui_xml()
            if not xml:
                time.sleep(1)
                continue
            if resource_id and f'resource-id="{resource_id}"' in xml:
                return True
            if content_desc:
                needle = content_desc if contains else f'content-desc="{content_desc}"'
                if needle in xml:
                    return True
            if text:
                needle = text if contains else f'text="{text}"'
                if needle in xml:
                    return True
            time.sleep(1)
        return False
    def process_job(self, job: Job) -> bool:
        """Gera o vídeo pela tela Gerar vídeo do YouTube Create e baixa o MP4 exportado."""
        logger.info(f"==> Iniciando processamento do Job {job.job_id} ({_md(job.product.name)})")

        photos_to_send = job.product.photos_local_paths or ([job.product.photo_local_path] if job.product.photo_local_path else [])
        photos_to_send = photos_to_send[:3]
        if not photos_to_send:
            raise ValueError("O YouTube Create exige pelo menos uma imagem para Gerar vídeo.")

        remote_photo_paths = [
            f"{self.remote_temp_dir}product_photo_{i + 1}{Path(local_p).suffix or '.jpg'}"
            for i, local_p in enumerate(photos_to_send)
        ]
        remote_video_dir = "/sdcard/Download"
        existing_videos = set(self.device.list_remote_files(remote_video_dir, suffix=".mp4"))
        local_video_output = settings.media_outputs_dir / f"video_{job.job_id[:8]}.mp4"

        try:
            if not settings.mock_device and not self.device.is_connected():
                raise HardwareNotAvailableError(
                    "Celular Android ou notebook de automação não detectado via ADB. "
                    "Conecte o aparelho físico para renderizar o vídeo."
                )

            self.device.wake_and_unlock()
            logger.info("Enviando %s foto(s) para o celular...", len(photos_to_send))
            for local_p, remote_p in zip(photos_to_send, remote_photo_paths):
                if not self.device.push_file(local_p, remote_p):
                    raise RuntimeError(f"Falha ao transferir foto {local_p} para o celular.")

            logger.info("Iniciando YouTube Create...")
            self.device.stop_app(self.package_name)
            if not self.device.launch_app(self.package_name):
                raise RuntimeError("Falha ao abrir o aplicativo YouTube Create.")
            time.sleep(2)

            # Tela inicial -> Gerar vídeo (R2V).
            if not self._tap_ui_or_point(fallback_name="btn_generate_video", resource_id="r2v"):
                raise RuntimeError("Botão Gerar vídeo não encontrado no YouTube Create.")
            if not self._wait_for_ui(timeout=10, resource_id="storygen_prompt_input"):
                raise RuntimeError("Tela Geração de vídeos não abriu.")

            if not self._tap_ui_or_point(fallback_name="input_text_script", resource_id="storygen_prompt_input"):
                raise RuntimeError("Campo de roteiro não encontrado.")
            logger.info("Inserindo roteiro no YouTube Create...")
            if not self.device.input_text(job.script.full_text):
                raise RuntimeError("Falha ao inserir o roteiro no YouTube Create.")

            if not self._tap_ui_or_point(
                fallback_name="btn_upload_images",
                content_desc="Fazer upload de até 3 imagens",
            ):
                raise RuntimeError("Botão de upload de imagens não encontrado.")
            if not self._wait_for_ui(timeout=10, resource_id="mediaThumbnail-0"):
                raise RuntimeError("Galeria do YouTube Create não abriu.")

            thumbnail_fallbacks = ["media_thumbnail_1", "media_thumbnail_2", "media_thumbnail_3"]
            for idx, fallback_name in enumerate(thumbnail_fallbacks[:len(photos_to_send)]):
                if not self._tap_ui_or_point(
                    fallback_name=fallback_name,
                    resource_id=f"mediaThumbnail-{idx}",
                ):
                    raise RuntimeError(f"Miniatura {idx + 1} não encontrada na galeria.")
                time.sleep(0.4)

            if not self._tap_ui_or_point(fallback_name="btn_finish_media_selection", content_desc="Concluído"):
                raise RuntimeError("Botão Concluído da galeria não encontrado.")
            if not self._wait_for_ui(timeout=10, content_desc="Gerar"):
                raise RuntimeError("Botão Gerar não apareceu após o upload.")
            if not self._tap_ui_or_point(fallback_name="btn_generate", content_desc="Gerar"):
                raise RuntimeError("Não foi possível iniciar a geração.")

            logger.info("Geração acionada; aguardando resultado do YouTube Create...")
            deadline = time.time() + 300
            generated = False
            while time.time() < deadline:
                xml = self.device.dump_ui_xml()
                if settings.mock_device or "Usar vídeo" in xml or "Vídeo gerado" in xml:
                    generated = True
                    break
                if any(token in xml.lower() for token in ("não foi possível", "falha", "erro ao gerar")):
                    raise RuntimeError("O YouTube Create informou falha na geração.")
                time.sleep(5)
            if not generated:
                raise TimeoutError("Tempo limite de geração atingido no YouTube Create.")

            if not settings.mock_device:
                if not self._tap_ui_or_point(fallback_name="btn_use_video", content_desc="Usar vídeo"):
                    raise RuntimeError("Botão Usar vídeo não encontrado.")
                if not self._wait_for_ui(timeout=20, content_desc="Exportar"):
                    raise RuntimeError("Editor não apresentou o botão Exportar.")
                if not self._tap_ui_or_point(fallback_name="btn_export_menu", content_desc="Exportar"):
                    raise RuntimeError("Não foi possível abrir Exportar.")
                if not self._wait_for_ui(timeout=10, content_desc="Salvar no dispositivo"):
                    raise RuntimeError("Opção Salvar no dispositivo não apareceu.")
                if not self._tap_ui_or_point(fallback_name="btn_save_to_device", content_desc="Salvar no dispositivo"):
                    raise RuntimeError("Não foi possível salvar o vídeo no dispositivo.")

                # O nome é criado pelo app; aguarda um MP4 novo em Downloads.
                deadline = time.time() + 60
                remote_video_name = None
                while time.time() < deadline:
                    candidates = [
                        name for name in self.device.list_remote_files(remote_video_dir, suffix=".mp4")
                        if name not in existing_videos
                    ]
                    if candidates:
                        remote_video_name = candidates[0]
                        break
                    time.sleep(2)
                if not remote_video_name:
                    raise RuntimeError("O vídeo foi exportado, mas nenhum MP4 novo foi encontrado em /sdcard/Download.")
                remote_video_path = f"{remote_video_dir}/{remote_video_name}"
            else:
                remote_video_path = f"{self.remote_temp_dir}final_{job.job_id[:8]}.mp4"

            logger.info("Baixando vídeo renderizado do celular...")
            if not self.device.pull_file(remote_video_path, str(local_video_output)):
                raise RuntimeError("Falha ao puxar o MP4 do celular.")

            self.device.clean_remote_files(remote_photo_paths + [remote_video_path])
            self.device.stop_app(self.package_name)
            self.queue_service.mark_completed(job.job_id, str(local_video_output))
            logger.info("Job %s concluído com sucesso.", job.job_id)
            return True

        except Exception as e:
            error_msg = str(e)
            logger.error("Erro durante execução do Job %s: %s", job.job_id, error_msg, exc_info=True)
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
                f"🎉 *Seu vídeo está pronto!*\n\n"
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
                    f"⚠️ *Atenção:* Ocorreu um problema ao produzir o vídeo do produto *{_md(job.product.name)}* pelo motor selecionado.\n\n"
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

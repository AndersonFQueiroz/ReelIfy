"""Painel de gestao do Click Shop Oficial.

Uso:
  python3 -m tools.reelify_dashboard
  python3 -m tools.reelify_dashboard --once
  python3 -m tools.reelify_dashboard --status PENDING
  python3 -m tools.reelify_dashboard --pedido ID_OU_PREFIXO
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen
import sys

from bot.handlers.start import _grant_access, _load_persistent_authorized_ids, _revoke_access
from bot.services.queue_service import Job, JobStatus, queue_service
from config.settings import settings

RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"


def paint(value: str, code: str) -> str:
    return f"{code}{value}{RESET}" if sys.stdout.isatty() else value


def jobs() -> list[Job]:
    return queue_service.get_all_jobs()


def short_id(value: str) -> str:
    return value[:8] if value else "-"


def date_text(value: str | None) -> str:
    return value.replace("T", " ")[:19] if value else "-"


def status_text(status: JobStatus | str) -> str:
    value = status.value if isinstance(status, JobStatus) else str(status)
    colors = {"PENDING": YELLOW, "PROCESSING": CYAN, "COMPLETED": GREEN, "FAILED": RED}
    return paint(value, colors.get(value, RESET))


def process_exists(fragment: str) -> bool:
    try:
        for entry in Path("/proc").iterdir():
            if entry.name.isdigit():
                try:
                    command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="ignore")
                except OSError:
                    continue
                if fragment in command and "reelify_dashboard" not in command:
                    return True
    except OSError:
        pass
    return False


def bot_display_name() -> str:
    if not settings.telegram_bot_token:
        return "BOT"
    try:
        with urlopen(f"https://api.telegram.org/bot{settings.telegram_bot_token}/getMe", timeout=5) as response:
            result = json.load(response).get("result", {})
        return result.get("first_name") or result.get("username") or "BOT"
    except Exception:
        return "BOT"


def title(value: str) -> None:
    print("\n" + paint("=" * 78, CYAN))
    print(paint(f"  {value}", BOLD))
    print(paint("=" * 78, CYAN))


def overview() -> None:
    items = jobs()
    counts = Counter(job.status.value if isinstance(job.status, JobStatus) else str(job.status) for job in items)
    persistent = _load_persistent_authorized_ids()
    authorized = set(settings.allowed_chat_ids) | persistent
    title(f"{bot_display_name().upper()} - PAINEL DE OPERACAO")
    print(f"  Bot Telegram : {paint('ATIVO', GREEN) if process_exists('bot.main') else paint('PARADO', RED)}")
    print(f"  Worker video : {paint('ATIVO', GREEN) if process_exists('automation.worker') else paint('PARADO', YELLOW)}")
    print(f"  Fila         : {settings.queue_file_path}")
    print(f"  Atualizado   : {datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    print(f"  PEDIDOS: total={len(items)} | PENDING={counts['PENDING']} | PROCESSING={counts['PROCESSING']} | COMPLETED={counts['COMPLETED']} | FAILED={counts['FAILED']}")
    print(f"  ACESSOS: usuarios={len(authorized)} | administradores={len(settings.admin_chat_ids)}")
    print(f"  Arquivo de acessos: {Path('data/authorized_chat_ids.json')}")


def list_orders(filter_status: str | None = None) -> None:
    items = sorted(jobs(), key=lambda job: job.created_at or "", reverse=True)
    if filter_status:
        items = [job for job in items if str(job.status.value if isinstance(job.status, JobStatus) else job.status) == filter_status]
    title(f"PEDIDOS{f' - {filter_status}' if filter_status else ''}")
    if not items:
        print("  Nenhum pedido encontrado.")
        return
    print(f"  {'ID':<10} {'STATUS':<14} {'PRODUTO':<26} {'CHAT ID':<14} CRIADO")
    print("  " + "-" * 76)
    for job in items:
        print(f"  {short_id(job.job_id):<10} {status_text(job.status):<23} {job.product.name[:24]:<26} {job.chat_id:<14} {date_text(job.created_at)}")


def get_job(prefix: str) -> Job | None:
    matches = [job for job in jobs() if job.job_id.startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    print("  " + ("Mais de um pedido: " if matches else "Pedido nao encontrado: ") + (", ".join(short_id(job.job_id) for job in matches) if matches else prefix))
    return None


def order_details(prefix: str) -> None:
    job = get_job(prefix)
    if not job:
        return
    title(f"DETALHES {short_id(job.job_id)}")
    print(f"  UUID: {job.job_id}")
    print(f"  Status: {status_text(job.status)}")
    print(f"  Produto: {job.product.name}")
    print(f"  Usuario: {job.user_name or '-'} | Chat ID: {job.chat_id}")
    print(f"  Criado: {date_text(job.created_at)} | Iniciado: {date_text(job.started_at)} | Concluido: {date_text(job.completed_at)}")
    print(f"  Tentativas: {job.attempts}/{job.max_attempts}")
    print(f"  Link: {job.product.affiliate_link or '-'}")
    print(f"  Fotos: {len(job.product.photos_local_paths)}")
    for index, photo in enumerate(job.product.photos_local_paths, 1):
        print(f"    {index}. {'OK' if Path(photo).exists() else 'AUSENTE'} - {photo}")
    if job.output_video_path:
        print(f"  Video: {'OK' if Path(job.output_video_path).exists() else 'AUSENTE'} - {job.output_video_path}")
    if job.error_details:
        print(f"  Erro: {job.error_details}")
    print("\n  ROTEIRO")
    for label, value in (("Gancho", job.script.hook), ("Problema", job.script.problem), ("Solucao", job.script.solution), ("Prova", job.script.proof), ("CTA", job.script.cta)):
        print(f"  {label:<9}: {value}")
    print(f"  Palavras: {len(job.script.full_text.split())}")
    print(f"  Completo: {job.script.full_text}")


def users() -> None:
    persistent = _load_persistent_authorized_ids()
    env_ids = set(settings.allowed_chat_ids)
    all_ids = sorted(env_ids | persistent | set(job.chat_id for job in jobs()))
    counts = Counter(job.chat_id for job in jobs())
    title("USUARIOS, IDS E ACESSOS")
    print(f"  {'CHAT ID':<16} {'TIPO':<18} {'PEDIDOS':<8} ADMIN")
    print("  " + "-" * 60)
    if not all_ids:
        print("  Nenhum usuario autorizado.")
    for chat_id in all_ids:
        kind = []
        if chat_id in env_ids:
            kind.append(".env")
        if chat_id in persistent:
            kind.append("persistente")
        if chat_id not in env_ids and chat_id not in persistent:
            kind.append("tem pedido")
        print(f"  {chat_id:<16} {', '.join(kind):<18} {counts[chat_id]:<8} {'SIM' if chat_id in settings.admin_chat_ids else 'NAO'}")
    print(f"\n  Administradores: {', '.join(map(str, settings.admin_chat_ids)) or 'nenhum'}")
    print(f"  Palavra magica: {'configurada' if settings.magic_word else 'nao configurada'}")


def authorize() -> None:
    raw = input("  ID do Telegram para autorizar (vazio cancela): ").strip()
    if raw and raw.lstrip("-").isdigit():
        _grant_access(int(raw))
        print(paint(f"  Chat {raw} autorizado permanentemente.", GREEN))
    else:
        print("  ID invalido ou operacao cancelada.")


def revoke() -> None:
    raw = input("  ID do Telegram para revogar (vazio cancela): ").strip()
    if not raw or not raw.lstrip("-").isdigit():
        print("  ID invalido ou operacao cancelada.")
        return
    chat_id = int(raw)
    if chat_id in settings.allowed_chat_ids:
        print("  Esse ID esta no .env; remova-o de ALLOWED_CHAT_IDS.")
    elif _revoke_access(chat_id):
        print(paint(f"  Acesso do chat {chat_id} revogado.", GREEN))
    else:
        print("  Esse chat nao possui autorizacao persistente.")


def cleanup() -> None:
    if input("  Remover PENDING com mais de 24h e suas fotos? [s/N] ").strip().lower() == "s":
        print(f"  {queue_service.cleanup_expired_jobs(max_age_hours=24)} pedido(s) removido(s).")
    else:
        print("  Operacao cancelada.")


def logs() -> None:
    log_file = settings.logs_dir / "bot.log"
    title("ULTIMOS LOGS DO BOT")
    if log_file.exists():
        print("\n".join(log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]))
    else:
        print("  Log ainda nao existe.")


def menu() -> None:
    while True:
        overview()
        title("MENU")
        print("  [1] Listar pedidos")
        print("  [2] Filtrar por status")
        print("  [3] Detalhes de pedido")
        print("  [4] Usuarios, IDs e acessos")
        print("  [5] Autorizar usuario")
        print("  [6] Revogar usuario")
        print("  [7] Ultimos logs")
        print("  [8] Limpar pedidos expirados")
        print("  [r] Atualizar")
        print("  [q] Sair")
        choice = input("\n  Escolha: ").strip().lower()
        if choice == "1":
            list_orders()
        elif choice == "2":
            list_orders(input("  Status (PENDING, PROCESSING, COMPLETED, FAILED): ").strip().upper())
        elif choice == "3":
            order_details(input("  ID ou prefixo: ").strip())
        elif choice == "4":
            users()
        elif choice == "5":
            authorize()
        elif choice == "6":
            revoke()
        elif choice == "7":
            logs()
        elif choice == "8":
            cleanup()
        elif choice == "q":
            return
        elif choice != "r":
            print("  Opcao invalida.")
        if choice != "r":
            input("\n  Pressione Enter para voltar...")


def main() -> None:
    parser = argparse.ArgumentParser(description="Painel de gestao do Click Shop Oficial")
    parser.add_argument("--once", action="store_true", help="mostra resumo e encerra")
    parser.add_argument("--status", choices=[status.value for status in JobStatus])
    parser.add_argument("--pedido", metavar="ID")
    args = parser.parse_args()
    if args.once:
        overview()
    elif args.status:
        list_orders(args.status)
    elif args.pedido:
        order_details(args.pedido)
    else:
        menu()


if __name__ == "__main__":
    main()

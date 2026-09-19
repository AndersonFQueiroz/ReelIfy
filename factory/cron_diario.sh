#!/bin/bash
# Fábrica diária CaçaOfertas — gera 3 vídeos + pack Telegram.
# Cron sugerido (todo dia 08h): 0 8 * * * /root/linux/projetos/Reelify/factory/cron_diario.sh
set -u
cd /root/linux/projetos/Reelify || exit 1
DAY=$(date +%F)
LOG="data/factory/$DAY/fabrica.log"
mkdir -p "data/factory/$DAY"
python3 -m factory.run_diaria --date "$DAY" >> "$LOG" 2>&1
echo "rc=$? ($DAY)" >> "$LOG"

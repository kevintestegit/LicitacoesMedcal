#!/bin/bash
# Script para iniciar o agendador de buscas automáticas
# Executa em background e mantém logs

cd "$(dirname "$0")"
LOGFILE="logs/scheduler_$(date +%Y%m%d).log"

# Cria diretório de logs se não existir
mkdir -p logs

echo "[$(date)] Iniciando scheduler..." | tee -a "$LOGFILE"

# Executa o scheduler
../.venv/bin/python scripts/scheduler.py 2>&1 | tee -a "$LOGFILE"

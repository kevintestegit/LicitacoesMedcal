#!/bin/bash
# Inicia a API FastAPI em segundo plano
cd "$(dirname "$0")"
source ../.venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

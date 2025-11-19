#!/bin/bash
set -e

echo "Starting initialization..."
# Qdrant 초기화 실행 (실패해도 서버는 계속 동작)
python /app/scripts/init_qdrant.py || echo "Init skipped or failed"

echo "Starting Server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000


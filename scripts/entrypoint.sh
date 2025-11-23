#!/bin/bash
set -e

# 환경변수 RUN_INIT이 true일 때만 초기화 스크립트 실행
if [ "$RUN_INIT" = "true" ]; then
    echo "🚀 Running Qdrant Initialization..."
    python /app/scripts/init_qdrant.py || echo "⚠️ Init script failed or skipped"
else
    echo "⏩ Skipping Qdrant Initialization (Set RUN_INIT=true to run)"
fi

echo "Starting Server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
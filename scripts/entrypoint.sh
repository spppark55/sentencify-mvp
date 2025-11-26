#!/bin/bash
set -e

# 환경변수 RUN_INIT이 true일 때만 초기화 스크립트 실행
if [ "$RUN_INIT" = "true" ]; then
    echo "🚀 Running Qdrant Initialization..."
    python /app/scripts/init_qdrant.py || echo "⚠️ Init script failed or skipped"
    
    echo "🚀 Running User Profile Vector Upload..."
    python /app/scripts/phase3/step3_upload_to_qdrant.py || echo "⚠️ User Profile Upload failed or skipped"
else
    echo "⏩ Skipping Qdrant Initialization (Set RUN_INIT=true to run)"
fi

# 인자가 있으면(예: python -m app.consumer) 그 명령어를 실행
if [ "$#" -gt 0 ]; then
    echo "🚀 Executing command: $@"
    exec "$@"
else
    # 인자가 없으면 기본적으로 API 서버 실행
    echo "🚀 Starting API Server..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
fi
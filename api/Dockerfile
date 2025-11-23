FROM python:3.11-slim

# 로그 버퍼링 비활성화 (print 즉시 출력)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN chmod +x /app/scripts/entrypoint.sh

ENTRYPOINT ["/bin/bash", "/app/scripts/entrypoint.sh"]

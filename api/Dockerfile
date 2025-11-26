FROM python:3.11-slim

# 로그 버퍼링 비활성화 (print 즉시 출력)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/app ./app
COPY scripts ./scripts
COPY api/train_data.csv ./train_data.csv
COPY data/import/user_profile.json /app/data/import/user_profile.json

# Copy entrypoint to a location not overridden by volume mount and fix line endings
COPY scripts/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]

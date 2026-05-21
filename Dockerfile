# FinTrack v2.0 — Dockerfile (single-stage, slim)
# Backend serves API + static frontend on $PORT (default 3000)

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps for pandas/numpy/pdfplumber + nginx for static serving
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        nginx \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache layer)
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt

# Copy backend + frontend
COPY backend/ /app/backend/
COPY frontend/ /var/www/html/

# Create data + logs dirs
RUN mkdir -p /app/backend/data /app/backend/logs

# Nginx config: serve frontend + proxy /api → backend
RUN printf '%s\n' \
'server {' \
'    listen 3000 default_server;' \
'    root /var/www/html;' \
'    index index.html;' \
'    location / {' \
'        try_files $uri $uri/ /index.html;' \
'    }' \
'    location /api {' \
'        proxy_pass http://127.0.0.1:8000;' \
'        proxy_set_header Host $host;' \
'        proxy_set_header X-Real-IP $remote_addr;' \
'        proxy_read_timeout 120s;' \
'    }' \
'    location /openapi.json {' \
'        proxy_pass http://127.0.0.1:8000;' \
'    }' \
'    location /docs {' \
'        proxy_pass http://127.0.0.1:8000;' \
'    }' \
'}' > /etc/nginx/sites-available/default

# Migration on first boot is idempotent (init_db creates tables; legacy migration is safe to re-run if CSV exists)
RUN printf '#!/bin/bash\nset -e\n\
cd /app/backend\n\
# Run legacy migration if a positions.csv is shipped and DB is empty\n\
if [ -f data/positions.csv ] && [ ! -f data/fintrack.db ]; then\n\
    echo "[startup] running legacy migration"\n\
    python -m app.scripts.migrate_legacy || echo "[startup] migration skipped"\n\
fi\n\
# Start backend\n\
uvicorn main:app --host 0.0.0.0 --port 8000 &\n\
BACKEND_PID=$!\n\
# Start nginx in foreground\n\
nginx -g "daemon off;" &\n\
NGINX_PID=$!\n\
# Wait for either to exit\n\
wait -n $BACKEND_PID $NGINX_PID\n\
' > /start.sh && chmod +x /start.sh

EXPOSE 3000

CMD ["/start.sh"]

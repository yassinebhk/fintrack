# FinTrack - Multi-stage Dockerfile for production deployment

# Stage 1: Backend
FROM python:3.11-slim as backend

WORKDIR /app/backend

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir httpx

# Copy backend code
COPY backend/ .

# Create data directory
RUN mkdir -p data

# Stage 2: Combined (using nginx for static files)
FROM python:3.11-slim

WORKDIR /app

# Install nginx
RUN apt-get update && apt-get install -y nginx && rm -rf /var/lib/apt/lists/*

# Copy backend
COPY --from=backend /app/backend /app/backend

# Install Python dependencies
COPY backend/requirements.txt /app/backend/
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
RUN pip install --no-cache-dir httpx

# Copy frontend
COPY frontend/ /var/www/html/

# Create data directory
RUN mkdir -p /app/backend/data

# Copy default positions file
COPY backend/data/positions.csv /app/backend/data/

# Configure nginx
RUN echo 'server { \
    listen 3000; \
    root /var/www/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location /api { \
        proxy_pass http://127.0.0.1:8000; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
    } \
}' > /etc/nginx/sites-available/default

# Create start script
RUN echo '#!/bin/bash\n\
cd /app/backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 &\n\
nginx -g "daemon off;"' > /start.sh && chmod +x /start.sh

EXPOSE 3000

CMD ["/start.sh"]


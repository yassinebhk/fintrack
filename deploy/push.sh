#!/usr/bin/env bash
# Despliega FinTrack a la VM desde el Mac. Uso CANÓNICO (el que corre en vivo):
#   bash deploy/push.sh 34.123.238.158 ~/.ssh/google_compute_engine
# El servicio systemd corre como usuario 'yassinebouhaikbouhoussaine' desde
# /home/yassinebouhaikbouhoussaine/fintrack, así que ese es el destino por
# defecto. NO usar SSH_USER=fintrack (deja una copia huérfana que NO se ejecuta).
# Para desplegar a otro usuario: SSH_USER=<otro> bash deploy/push.sh <IP> <key>.
set -euo pipefail

IP="${1:?Falta IP pública de la VM}"
KEY="${2:?Falta ruta al SSH key}"
USER="${SSH_USER:-yassinebouhaikbouhoussaine}"
REMOTE="$USER@$IP"
SSH_OPTS="-o StrictHostKeyChecking=accept-new"

echo "==> Copiando código (rsync, sin .venv/datos locales/git)…"
rsync -az --delete \
  --exclude '.venv' --exclude '.venv_dbg' --exclude 'venv' \
  --exclude '__pycache__' --exclude '*.pyc' \
  --exclude '.git' --exclude 'backend/data' --exclude 'backend/logs' \
  --exclude 'backend/.env' \
  -e "ssh -i $KEY $SSH_OPTS" \
  ./ "$REMOTE:~/fintrack/"

echo "==> Copiando backend/.env (secretos)…"
ssh -i "$KEY" $SSH_OPTS "$REMOTE" "mkdir -p ~/fintrack/backend"
scp -i "$KEY" $SSH_OPTS backend/.env "$REMOTE:~/fintrack/backend/.env"

echo "==> Ejecutando setup en la VM…"
ssh -i "$KEY" $SSH_OPTS "$REMOTE" "cd ~/fintrack && bash deploy/setup.sh"

echo "✅ Desplegado. FinTrack corre 24/7 en la VM (systemd, sobrevive reinicios)."

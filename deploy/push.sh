#!/usr/bin/env bash
# Despliega FinTrack a la VM desde el Mac. Uso:
#   bash deploy/push.sh <IP_PUBLICA> <ruta-al-ssh-key.key>
# Copia el código + backend/.env, instala todo y arranca el servicio.
# Vuelve a ejecutarse igual para cada redeploy futuro tras cambios de código.
set -euo pipefail

IP="${1:?Falta IP pública de la VM}"
KEY="${2:?Falta ruta al SSH key}"
USER="${SSH_USER:-ubuntu}"
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

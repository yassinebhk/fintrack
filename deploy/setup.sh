#!/usr/bin/env bash
# Setup de FinTrack en una VM Ubuntu (Oracle Cloud Always Free, ARM o x86).
# Se ejecuta EN la VM, después de copiar el código a ~/fintrack (vía push.sh).
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/fintrack}"
BACKEND_DIR="$APP_DIR/backend"

echo "==> 0/6 Zona horaria → Europe/Madrid ..."
sudo timedatectl set-timezone Europe/Madrid 2>/dev/null || sudo ln -sf /usr/share/zoneinfo/Europe/Madrid /etc/localtime
date

echo "==> 1/6 Paquetes del sistema (Python, build tools)"
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip build-essential curl

echo "==> 2/6 Entorno virtual + dependencias de FinTrack"
cd "$BACKEND_DIR"
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

echo "==> 3/6 Instalando Caddy (repo oficial, HTTPS automático)"
if ! command -v caddy &>/dev/null; then
  sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
  sudo apt-get update -y
  sudo apt-get install -y caddy
fi

echo "==> 4/6 Generando Caddyfile con la IP pública de esta VM (sslip.io, sin DNS que tocar)"
PUBLIC_IP="$(curl -s https://ifconfig.me || curl -s https://icanhazip.com)"
IP_DASHED="$(echo "$PUBLIC_IP" | tr '.' '-')"
HOSTNAME="fintrack.${IP_DASHED}.sslip.io"
sudo tee /etc/caddy/Caddyfile > /dev/null <<EOF
${HOSTNAME} {
    reverse_proxy localhost:8000
}
EOF
echo "    URL pública: https://${HOSTNAME}"

echo "==> 5/6 Instalando el servicio systemd de FinTrack"
sudo cp "$APP_DIR/deploy/fintrack.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fintrack
sudo systemctl restart fintrack

echo "==> 6/6 Recargando Caddy"
sudo systemctl enable --now caddy
sudo systemctl reload caddy || sudo systemctl restart caddy

sleep 2
echo ""
echo "✅ Setup completo."
echo "   FinTrack:  $(sudo systemctl is-active fintrack)"
echo "   Caddy:     $(sudo systemctl is-active caddy)"
echo "   URL:       https://${HOSTNAME}"

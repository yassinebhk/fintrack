#!/usr/bin/env bash
# Setup de FinTrack en una VM Ubuntu (Oracle Cloud Always Free, ARM o x86).
# Se ejecuta EN la VM, después de copiar el código a ~/fintrack (vía push.sh).
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/fintrack}"
BACKEND_DIR="$APP_DIR/backend"

echo "==> 0/9 Zona horaria → Europe/Madrid ..."
sudo timedatectl set-timezone Europe/Madrid 2>/dev/null || sudo ln -sf /usr/share/zoneinfo/Europe/Madrid /etc/localtime
date

echo "==> 1/9 Swap de 2GB (red de seguridad para VMs de poca RAM tipo e2-micro/E2.1.Micro)"
if [ ! -f /swapfile ]; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi
free -h

echo "==> 2/9 Paquetes del sistema (Python, build tools)"
echo "         Nota: esta imagen trae Python muy reciente sin ruedas precompiladas todavía"
echo "         para pandas/numpy en PyPI, así que pip compila desde código fuente — con la"
echo "         swap del paso anterior esto tarda pero ya no se cuelga por falta de memoria."
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-pip build-essential curl

echo "==> 3/9 Postgres local (evita depender de la cuota gratuita de un Postgres externo:"
echo "         ya se agotó tres veces seguidas con Render Postgres, CockroachDB y Neon)"
if ! command -v psql &>/dev/null; then
  sudo apt-get install -y postgresql postgresql-contrib
fi
sudo systemctl enable --now postgresql
FINTRACK_DB_PASSWORD="${FINTRACK_DB_PASSWORD:-}"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='fintrack'" | grep -q 1; then
  if [ -z "$FINTRACK_DB_PASSWORD" ]; then
    FINTRACK_DB_PASSWORD="$(openssl rand -base64 24 | tr -d '/+=')"
    echo "    ⚠️  Generada contraseña nueva para el usuario 'fintrack' de Postgres:"
    echo "        $FINTRACK_DB_PASSWORD"
    echo "        Guárdala en backend/.env como DATABASE_URL=postgresql://fintrack:<esa contraseña>@localhost:5432/fintrack"
  fi
  sudo -u postgres psql -c "CREATE USER fintrack WITH PASSWORD '${FINTRACK_DB_PASSWORD}';"
  sudo -u postgres createdb -O fintrack fintrack
fi

echo "==> 4/9 Backup diario de Postgres (cron 03:17, retiene 7 días)"
mkdir -p "$HOME/backups"
cat > "$HOME/backup_db.sh" <<'BACKUP_EOF'
#!/usr/bin/env bash
set -euo pipefail
BACKUP_DIR="$HOME/backups"
mkdir -p "$BACKUP_DIR"
DB_URL="$(grep -m1 '^DATABASE_URL=' "$HOME/fintrack/backend/.env" | cut -d= -f2-)"
pg_dump -Fc "$DB_URL" -f "$BACKUP_DIR/fintrack-$(date +%Y%m%d).pgdump"
find "$BACKUP_DIR" -name "fintrack-*.pgdump" -mtime +7 -delete
BACKUP_EOF
chmod +x "$HOME/backup_db.sh"
(crontab -l 2>/dev/null | grep -v backup_db.sh || true; echo "17 3 * * * $HOME/backup_db.sh >> $HOME/backups/backup.log 2>&1") | crontab -

echo "==> 5/9 Entorno virtual + dependencias de FinTrack"
cd "$BACKEND_DIR"
python3 -m venv .venv
# /tmp en esta imagen es tmpfs (RAM) de ~477MB con cuota de usuario — compilar pandas desde
# código fuente genera más archivos temporales de los que caben ahí. El disco real (/) tiene
# de sobra, así que redirigimos ahí los temporales de pip/gcc.
mkdir -p "$HOME/pip-tmp"
export TMPDIR="$HOME/pip-tmp"
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt
rm -rf "$HOME/pip-tmp"

echo "==> 6/9 Instalando Caddy (repo oficial, HTTPS automático)"
if ! command -v caddy &>/dev/null; then
  sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
  sudo apt-get update -y
  sudo apt-get install -y caddy
fi

echo "==> 7/9 Generando Caddyfile con la IP pública de esta VM (sslip.io, sin DNS que tocar)"
PUBLIC_IP="$(curl -s https://ifconfig.me || curl -s https://icanhazip.com)"
IP_DASHED="$(echo "$PUBLIC_IP" | tr '.' '-')"
HOSTNAME="fintrack.${IP_DASHED}.sslip.io"
sudo tee /etc/caddy/Caddyfile > /dev/null <<EOF
${HOSTNAME} {
    reverse_proxy localhost:8000
}
EOF
echo "    URL pública: https://${HOSTNAME}"

echo "==> 8/9 Instalando el servicio systemd de FinTrack (usuario real: $(whoami))"
sudo tee /etc/systemd/system/fintrack.service > /dev/null <<EOF
[Unit]
Description=FinTrack API
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${BACKEND_DIR}
EnvironmentFile=${BACKEND_DIR}/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=${BACKEND_DIR}/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now fintrack
sudo systemctl restart fintrack

echo "==> 9/9 Recargando Caddy"
sudo systemctl enable --now caddy
sudo systemctl reload caddy || sudo systemctl restart caddy

sleep 2
echo ""
echo "✅ Setup completo."
echo "   FinTrack:  $(sudo systemctl is-active fintrack)"
echo "   Caddy:     $(sudo systemctl is-active caddy)"
echo "   URL:       https://${HOSTNAME}"

# Crear la VM en Oracle Cloud (Always Free)

Sigue estos pasos en el navegador. Cuando termines, pásame la **IP pública** y la **ruta del SSH
key** y ejecuto el despliegue.

## 1. Cuenta

1. https://www.oracle.com/cloud/free/ → "Start for free"
2. Rellena datos. Pide tarjeta para verificar identidad — **NO cobra** (es Always Free).
3. Elige una región cercana (ej. Spain Central / Frankfurt).

## 2. Crear la instancia (VM)

1. Menú ☰ → **Compute → Instances → Create instance**
2. **Name**: `fintrack`
3. **Image & shape** → Edit:
   - Image: **Canonical Ubuntu 24.04**
   - Shape: **Ampere (VM.Standard.A1.Flex)** → 2 OCPU / 12 GB (dentro del Always Free de 4/24)
     - Si no hay disponibilidad de Ampere en tu región, usa **VM.Standard.E2.1.Micro** (más
       lento pero también gratis para siempre).
4. **SSH keys**: "Generate a key pair for me" → **Download private key** (guárdalo, ej.
   `~/Downloads/fintrack.key`)
5. **Create**. Espera a que esté "Running" y copia la **Public IP address**.

## 3. Abrir los puertos HTTP y HTTPS

FinTrack necesita servir web pública (a diferencia de un bot sin tráfico entrante), así que hay
que abrir los puertos **80** (HTTP, para el certificado automático) y **443** (HTTPS):

1. Instancia → **Virtual Cloud Network** → Security Lists → Default Security List
2. **Add Ingress Rule** (repetir para cada puerto):
   - Source: `0.0.0.0/0`, IP Protocol: TCP, Destination port: **80**
   - Source: `0.0.0.0/0`, IP Protocol: TCP, Destination port: **443**

## 4. Permisos del key (en tu Mac)

```
chmod 600 ~/Downloads/fintrack.key
```

## 5. Dámelo

Pásame:

- **IP pública** (ej. 140.238.x.x)
- **Ruta del key** (ej. ~/Downloads/fintrack.key)

Y ejecuto: `bash deploy/push.sh <IP> <key>` → instala Python, dependencias, Caddy (HTTPS
automático), copia tus secretos (`backend/.env`, que preparamos antes) y arranca FinTrack como
servicio 24/7 con `systemd`.

La URL final será `https://fintrack.<IP-con-guiones>.sslip.io` (por ejemplo, si tu IP es
140.238.55.12, la URL es `https://fintrack.140-238-55-12.sslip.io`) — funciona sola, sin tocar
ningún DNS.

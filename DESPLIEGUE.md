# 🚀 Guía de Despliegue de FinTrack

Esta guía explica cómo hacer que tu dashboard FinTrack sea accesible públicamente para que otros puedan verlo desde cualquier lugar.

## 📋 Opciones de Despliegue

| Plataforma | Coste | Dificultad | Ventajas |
|------------|-------|------------|----------|
| **Railway** | Gratis (500h/mes) | ⭐ Fácil | Todo en uno, desde GitHub |
| **Render** | Gratis (con límites) | ⭐ Fácil | Perfecto para proyectos pequeños |
| **Vercel + Railway** | Gratis | ⭐⭐ Media | Frontend rápido en Vercel |
| **VPS propio** | ~5€/mes | ⭐⭐⭐ Avanzado | Control total |

---

## 🚂 Opción 1: Railway (Recomendada)

Railway es la opción más sencilla. Un clic y está funcionando.

### Paso 1: Sube tu código a GitHub
```bash
# Si no tienes Git inicializado
cd ~/personal-finance-dashboard
git init
git add .
git commit -m "Initial commit"

# Crea un repositorio en GitHub y conecta
git remote add origin https://github.com/TU_USUARIO/fintrack.git
git push -u origin main
```

### Paso 2: Despliega en Railway
1. Ve a [railway.app](https://railway.app) y crea una cuenta con GitHub
2. Clic en **"New Project"** → **"Deploy from GitHub repo"**
3. Selecciona tu repositorio `fintrack`
4. Railway detectará automáticamente el `Dockerfile`
5. Espera ~3 minutos a que se despliegue

### Paso 3: Configura las variables de entorno
1. En Railway, ve a tu proyecto → **Variables**
2. Añade:
   - `GROQ_API_KEY` = tu clave de Groq (para el asesor IA)
   - `PORT` = 3000

### Paso 4: Obtén tu URL pública
- Railway te asigna una URL tipo: `fintrack-xxx.up.railway.app`
- ¡Ya puedes compartirla con quien quieras!

---

## 🎨 Opción 2: Render

### Backend (API)
1. Ve a [render.com](https://render.com) y crea cuenta
2. **New** → **Web Service**
3. Conecta tu repositorio de GitHub
4. Configuración:
   - **Name**: fintrack-api
   - **Root Directory**: backend
   - **Build Command**: `pip install -r requirements.txt && pip install httpx`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Añade variable: `GROQ_API_KEY`
6. Clic en **Create Web Service**

### Frontend (Static Site)
1. **New** → **Static Site**
2. Conecta el mismo repositorio
3. Configuración:
   - **Name**: fintrack-frontend
   - **Root Directory**: frontend
   - **Publish Directory**: `.` (directorio actual)
4. Clic en **Create Static Site**

### Conectar Frontend con Backend
En tu frontend, actualiza la URL del API en `js/app.js`:
```javascript
const API_BASE = 'https://fintrack-api.onrender.com';
```

---

## 🐳 Opción 3: Docker (VPS propio)

Si tienes un servidor VPS (DigitalOcean, Hetzner, etc.):

### Construir y ejecutar
```bash
# En tu servidor
git clone https://github.com/TU_USUARIO/fintrack.git
cd fintrack

# Construir imagen
docker build -t fintrack .

# Ejecutar
docker run -d -p 80:3000 \
  -e GROQ_API_KEY=tu_api_key \
  --name fintrack \
  fintrack
```

### Con Docker Compose (recomendado)
```yaml
# docker-compose.yml
version: '3.8'
services:
  fintrack:
    build: .
    ports:
      - "80:3000"
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
    volumes:
      - ./data:/app/backend/data
    restart: unless-stopped
```

```bash
docker-compose up -d
```

---

## 🔒 Seguridad en Producción

### 1. Variables de entorno
NUNCA subas claves API a GitHub. Usa variables de entorno:
```bash
# .env (NO subir a Git)
GROQ_API_KEY=sk-xxxxx
```

### 2. HTTPS
- Railway y Render proporcionan HTTPS automático
- En VPS, usa Caddy o nginx con Let's Encrypt

### 3. CORS
En producción, actualiza `main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tu-dominio.com"],  # Solo tu dominio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 🌐 Dominio Personalizado

### En Railway/Render
1. Ve a la configuración de tu proyecto
2. Sección **Custom Domains**
3. Añade tu dominio (ej: `fintrack.tudominio.com`)
4. Configura los DNS en tu registrador:
   - Tipo: CNAME
   - Nombre: fintrack
   - Valor: (el que te indique Railway/Render)

---

## 💰 Costes Estimados

| Opción | Coste mensual | Límites |
|--------|---------------|---------|
| Railway Free | 0€ | 500 horas/mes, duerme tras inactividad |
| Railway Pro | 5$ | Sin límites de tiempo |
| Render Free | 0€ | 750 horas/mes, duerme tras 15min |
| Render Paid | 7$ | Siempre activo |
| VPS básico | 4-6€ | Sin límites |

---

## ❓ FAQ

**¿Mis datos están seguros en la nube?**
Sí, pero recuerda que tus posiciones se guardan en el servidor. Si no quieres que nadie acceda, añade autenticación.

**¿Puedo usar un dominio propio?**
Sí, todas las plataformas permiten dominios personalizados.

**¿Qué pasa si supero los límites del plan gratuito?**
El servicio se pausará hasta el siguiente mes, o puedes upgradearte al plan de pago.

**¿Cómo actualizo la versión desplegada?**
Simplemente haz `git push` a tu repositorio y Railway/Render redesplegarán automáticamente.

---

## 🆘 ¿Necesitas Ayuda?

Si tienes problemas con el despliegue:
1. Revisa los logs en la plataforma
2. Verifica que las variables de entorno estén configuradas
3. Asegúrate de que el puerto sea el correcto


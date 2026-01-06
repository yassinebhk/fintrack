# 📊 FinTrack - Dashboard Financiero Personal v2.0

Un dashboard financiero personal **moderno y profesional** para visualizar y gestionar tu cartera de inversiones.

![Dashboard Preview](https://via.placeholder.com/800x400/0a0e17/00d4aa?text=FinTrack+Dashboard)

## ✨ Características Principales

### 📈 Dashboard
- **Valor total de cartera** en tiempo real
- **Rentabilidad diaria y acumulada** con colores semánticos
- **KPIs avanzados**: CAGR, Max Drawdown, Volatilidad, Sharpe Ratio
- **Gráfico de evolución** histórica interactivo
- **Distribución** por tipo de activo, broker y divisa
- **Tabla de posiciones** ordenable, filtrable y con búsqueda

### 📊 Análisis
- Comparativa con benchmark (S&P 500)
- Distribución de riesgo
- Top movers del mes
- Estadísticas de rendimiento

### 💸 Transacciones
- Registro de compras, ventas y dividendos
- Historial completo de operaciones
- Filtrado por fecha y tipo

### 🎯 Objetivos
- Creación de metas financieras
- Seguimiento visual del progreso
- Proyección de patrimonio futuro

### 🔔 Alertas
- Alertas de precio personalizadas
- Notificaciones de cambio porcentual
- Estado de alertas en tiempo real

### 🧮 Calculadoras Financieras
- **Interés Compuesto**: Proyección de crecimiento
- **FIRE**: Independencia financiera y retiro temprano
- **DCA**: Simulación de inversión periódica
- **Dividendos**: Estimación de ingresos pasivos

### 📚 Centro de Aprendizaje
- Guía completa de inversión
- Conceptos básicos explicados
- Métricas y KPIs detallados
- Estrategias de inversión (DCA, FIRE, diversificación)
- Gestión de riesgos
- Fiscalidad básica (España)

### 📖 Documentación
- Guía de instalación
- Configuración del sistema
- API Reference completo
- Preguntas frecuentes

## 🛠️ Tecnologías

### Backend
- **FastAPI** - API REST de alto rendimiento
- **Python 3.10+** - Lógica de negocio
- **yfinance** - Datos de acciones y ETFs
- **CoinGecko API** - Datos de criptomonedas
- **Pandas/NumPy** - Análisis de datos

### Frontend
- **HTML5/CSS3/JavaScript** - Vanilla, sin frameworks
- **Chart.js** - Gráficas interactivas
- **Diseño responsivo** - Mobile-first

## 📁 Estructura del Proyecto

```
personal-finance-dashboard/
├── backend/
│   ├── main.py                 # API FastAPI principal
│   ├── requirements.txt        # Dependencias Python
│   ├── models.py              # Modelos Pydantic
│   ├── data/
│   │   ├── positions.csv      # Tus posiciones
│   │   └── historical_values.json
│   └── services/
│       ├── yahoo_finance.py   # Servicio Yahoo Finance
│       ├── coingecko.py       # Servicio CoinGecko
│       ├── exchange_rates.py  # Tipos de cambio
│       └── portfolio.py       # Cálculos de cartera
├── frontend/
│   ├── index.html             # Dashboard HTML
│   ├── css/
│   │   └── styles.css         # Estilos
│   └── js/
│       ├── app.js             # Lógica principal
│       ├── calculators.js     # Calculadoras
│       └── pages.js           # Navegación y contenido
├── start.sh                   # Script de inicio
└── README.md
```

## 🚀 Instalación Rápida

### 1. Configurar el Backend

```bash
cd ~/personal-finance-dashboard/backend

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar tus Posiciones

Edita `backend/data/positions.csv`:

```csv
ticker,quantity,avg_price,type,currency,broker
AAPL,10,145,stock,USD,TradeRepublic
MSFT,5,280,stock,USD,MyInvestor
VWCE.DE,12,98,etf,EUR,MyInvestor
BTC,0.3,25000,crypto,USD,Kraken
ETH,2,1800,crypto,USD,Kraken
```

### 3. Iniciar los Servidores

**Opción 1: Script automático**
```bash
./start.sh
```

**Opción 2: Manual**
```bash
# Terminal 1: Backend
cd backend && source venv/bin/activate && python main.py

# Terminal 2: Frontend
cd frontend && python3 -m http.server 3000
```

### 4. Acceder al Dashboard

- 📊 **Dashboard**: http://localhost:3000
- 📡 **API**: http://localhost:8000
- 📚 **API Docs**: http://localhost:8000/docs

## 📡 APIs y Fuentes de Datos

| Fuente | Tipo de Activo | API Key | Límite |
|--------|----------------|---------|--------|
| Yahoo Finance | Acciones, ETFs | No requerida | Ilimitado* |
| CoinGecko | Criptomonedas | No requerida | 50 calls/min |
| ExchangeRate-API | Tipos de cambio | No requerida | Básico gratis |

## 🎨 Funcionalidades Avanzadas

### Navegación por Teclado
- Presiona `R` para refrescar datos

### Exportación
- Exportar posiciones a CSV desde el botón 📥

### Filtros y Búsqueda
- Buscar por ticker o nombre
- Filtrar por tipo de activo
- Filtrar por broker
- Ordenar por cualquier columna

## 📊 KPIs Explicados

| KPI | Descripción |
|-----|-------------|
| **CAGR** | Tasa de Crecimiento Anual Compuesto |
| **Max Drawdown** | Máxima caída desde un pico |
| **Volatilidad** | Desviación estándar anualizada |
| **Sharpe Ratio** | Rentabilidad ajustada al riesgo |

## 🔒 Seguridad

- ✅ Todos los datos se almacenan **localmente**
- ✅ No se envían datos sensibles a terceros
- ⚠️ El archivo `positions.csv` contiene información privada

## 📝 Tickers Especiales

- **Acciones europeas**: Añadir sufijo (VWCE**.DE**, SAP**.DE**)
- **Acciones españolas**: Ticker + .MC (SAN**.MC**)
- **Criptomonedas**: Usar símbolo estándar (BTC, ETH, SOL)

## 🤝 Contribuciones

¡Pull requests bienvenidos! Para cambios mayores, abre un issue primero.

## 📄 Licencia

MIT License - Uso personal libre.

---

**Hecho con ❤️ para inversores que quieren controlar su patrimonio**

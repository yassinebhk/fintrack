# 📊 Guía: Cómo Importar Tus Datos Reales

Esta guía te explica paso a paso cómo añadir tus inversiones reales al dashboard.

## 📋 Índice
1. [Exportar datos de MyInvestor](#myinvestor)
2. [Exportar datos de Trade Republic](#trade-republic)
3. [Conectar Kraken (API)](#kraken)
4. [Formato del archivo CSV](#formato-csv)
5. [Actualizar datos manualmente](#actualizar-manualmente)

---

## <a name="myinvestor"></a>🏦 MyInvestor

MyInvestor **no tiene API pública**, por lo que necesitas exportar manualmente.

### Paso 1: Accede a tu cartera
1. Entra en [myinvestor.es](https://myinvestor.es) o la app móvil
2. Ve a **"Mi Cartera"** o **"Posiciones"**

### Paso 2: Anota tus posiciones
Para cada fondo/acción necesitas:
- **Nombre del fondo/acción** (ej: "Vanguard Global Stock Index")
- **ISIN o Ticker** (ej: IE00B03HCZ61)
- **Número de participaciones**
- **Precio medio de compra**
- **Valor actual**

### Paso 3: Encuentra el ticker
Los fondos indexados de MyInvestor son principalmente Vanguard:

| Fondo MyInvestor | Ticker para Yahoo Finance |
|------------------|---------------------------|
| Vanguard Global Stock Index | VWCE.DE |
| Vanguard S&P 500 | VUAA.DE |
| Vanguard Emerging Markets | VFEM.DE |
| Vanguard Euro Stoxx 50 | VEUR.DE |

### Ejemplo de entrada CSV:
```csv
ticker,quantity,avg_price,type,currency,broker
VWCE.DE,25.5,98.50,etf,EUR,MyInvestor
VUAA.DE,10,75.20,etf,EUR,MyInvestor
```

---

## <a name="trade-republic"></a>📱 Trade Republic

Trade Republic tampoco tiene API pública, pero puedes exportar movimientos.

### Opción 1: Exportar desde la app
1. Abre la app de Trade Republic
2. Ve a **"Perfil"** → **"Documentos"**
3. Descarga el **"Informe de cartera"** o **"Extracto"**
4. Convierte los datos al formato CSV

### Opción 2: Anotación manual
En la sección **"Cartera"** de la app verás cada posición con:
- Nombre del activo
- Cantidad de acciones/participaciones
- Precio medio de compra
- Valor actual

### Tickers para Trade Republic
Los activos de Trade Republic cotizan en varios mercados:

| Activo | Ticker Yahoo Finance |
|--------|---------------------|
| Acciones USA (Apple, Tesla...) | AAPL, TSLA |
| Acciones alemanas | SAP.DE, BMW.DE |
| ETFs iShares | CSPX.DE, EUNL.DE |

### Ejemplo de entrada CSV:
```csv
ticker,quantity,avg_price,type,currency,broker
AAPL,10,145.00,stock,USD,TradeRepublic
TSLA,5,220.00,stock,USD,TradeRepublic
CSPX.DE,15,480.00,etf,EUR,TradeRepublic
```

---

## <a name="kraken"></a>🔐 Kraken (API Automática)

Kraken **SÍ tiene API pública** para lectura. Puedes automatizar la importación.

### Paso 1: Crear API Keys (solo lectura)
1. Entra en [kraken.com](https://kraken.com)
2. Ve a **"Seguridad"** → **"API"**
3. Crea una nueva clave con permisos:
   - ✅ Query Funds
   - ✅ Query Open Orders & Trades
   - ❌ NO actives permisos de trading

### Paso 2: Configurar en el dashboard
Copia tus claves al archivo `.env`:

```bash
# backend/.env
KRAKEN_API_KEY=tu_api_key_aqui
KRAKEN_API_SECRET=tu_api_secret_aqui
```

### Paso 3: El dashboard importará automáticamente
Una vez configurado, el dashboard obtendrá:
- Balances de todas tus criptos
- Precios actuales
- Historial de operaciones

### Opción alternativa: Manual
Si prefieres no usar la API, exporta desde Kraken:
1. Ve a **"Historial"** → **"Exportar"**
2. Selecciona **"Balances"** o **"Ledger"**
3. Descarga el CSV y convierte al formato del dashboard

### Ejemplo de entrada CSV:
```csv
ticker,quantity,avg_price,type,currency,broker
BTC,0.35,25000,crypto,USD,Kraken
ETH,2.5,1800,crypto,USD,Kraken
SOL,50,95,crypto,USD,Kraken
```

---

## <a name="formato-csv"></a>📄 Formato del Archivo CSV

El archivo `backend/data/positions.csv` debe tener este formato exacto:

### Columnas requeridas

| Columna | Descripción | Ejemplos |
|---------|-------------|----------|
| `ticker` | Símbolo del activo | AAPL, BTC, VWCE.DE |
| `quantity` | Cantidad de unidades | 10, 0.5, 25.75 |
| `avg_price` | Precio medio de compra | 145.50, 25000 |
| `type` | Tipo de activo | stock, etf, crypto |
| `currency` | Moneda del activo | USD, EUR |
| `broker` | Nombre del broker | MyInvestor, TradeRepublic, Kraken |

### Ejemplo completo

```csv
ticker,quantity,avg_price,type,currency,broker
AAPL,10,145,stock,USD,TradeRepublic
MSFT,5,280,stock,USD,MyInvestor
GOOGL,3,140,stock,USD,TradeRepublic
AMZN,4,175,stock,USD,MyInvestor
NVDA,6,480,stock,USD,TradeRepublic
TSLA,2,220,stock,USD,TradeRepublic
VWCE.DE,25,98.50,etf,EUR,MyInvestor
VUAA.DE,15,420,etf,EUR,MyInvestor
CSPX.DE,10,480,etf,EUR,TradeRepublic
BTC,0.35,25000,crypto,USD,Kraken
ETH,2.5,1800,crypto,USD,Kraken
SOL,50,95,crypto,USD,Kraken
```

### Cómo encontrar el ticker correcto

1. **Acciones USA**: Usa el símbolo directo (AAPL, MSFT, GOOGL)
2. **Acciones Europa**: Añade el sufijo del mercado
   - Alemania: `.DE` (SAP.DE, BMW.DE)
   - España: `.MC` (SAN.MC, ITX.MC)
   - Francia: `.PA` (MC.PA, OR.PA)
3. **ETFs Europa**: Generalmente `.DE` o `.AS`
4. **Criptomonedas**: Símbolo estándar (BTC, ETH, SOL)

### Verificar ticker
Puedes verificar que el ticker es correcto en:
- [Yahoo Finance](https://finance.yahoo.com) - Busca el símbolo
- [CoinGecko](https://coingecko.com) - Para criptomonedas

---

## <a name="actualizar-manualmente"></a>🔄 Actualizar Datos Manualmente

### Opción 1: Editar el CSV directamente
1. Abre `backend/data/positions.csv` con Excel, Numbers o cualquier editor de texto
2. Modifica las cantidades o añade nuevas filas
3. Guarda el archivo
4. Pulsa el botón de **"Refrescar"** en el dashboard

### Opción 2: Usar la página de Transacciones
1. Ve a la sección **"Transacciones"** del dashboard
2. Haz clic en **"+ Nueva Transacción"**
3. Registra compras, ventas o dividendos
4. El sistema actualizará automáticamente tus posiciones

### Opción 3: API REST
```bash
# Añadir nueva posición
curl -X POST "http://localhost:8000/api/positions" \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "GOOGL",
    "quantity": 5,
    "avg_price": 140,
    "type": "stock",
    "currency": "USD",
    "broker": "TradeRepublic"
  }'

# Actualizar posición existente
curl -X PUT "http://localhost:8000/api/positions/GOOGL" \
  -H "Content-Type: application/json" \
  -d '{"quantity": 10, "avg_price": 135}'

# Eliminar posición
curl -X DELETE "http://localhost:8000/api/positions/GOOGL"
```

---

## ❓ Preguntas Frecuentes

### ¿Cada cuánto debo actualizar mis datos?
- **Posiciones**: Cuando hagas compras/ventas
- **Precios**: El dashboard los actualiza automáticamente

### ¿Puedo tener el mismo ticker en varios brokers?
Sí. El dashboard los mostrará como posiciones separadas y sumará el total.

### ¿Qué pasa si el ticker no se encuentra?
- Verifica que el símbolo es correcto en Yahoo Finance
- Añade el sufijo del mercado si es necesario (.DE, .MC, etc.)

### ¿Mis datos son seguros?
Sí. Todo se almacena **localmente en tu ordenador**. No se envía información personal a ningún servidor.

---

## 🚀 ¿Quieres que configure tu cartera?

Si me proporcionas tus posiciones reales (puedes hacerlo en este chat), puedo:
1. Crear el archivo CSV correcto
2. Verificar que todos los tickers funcionan
3. Configurar la integración de Kraken si tienes las API keys

**Solo necesito saber:**
- Qué activos tienes (nombre o ticker)
- Cuántas unidades de cada uno
- Precio medio de compra (aproximado está bien)
- En qué broker está cada uno


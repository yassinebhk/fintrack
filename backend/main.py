"""
Personal Finance Dashboard - API Server
FastAPI backend for portfolio management and analysis
"""
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import os
import io
import json
from pathlib import Path
import pandas as pd

# Change to script directory for relative imports
os.chdir(Path(__file__).parent)

from services.portfolio import PortfolioService
from services.yahoo_finance import YahooFinanceService
from services.coingecko import CoinGeckoService
from services.exchange_rates import ExchangeRateService
from services.news import NewsService


# Initialize FastAPI app
app = FastAPI(
    title="Personal Finance Dashboard API",
    description="API for tracking personal investment portfolio",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
portfolio_service = PortfolioService(
    positions_file="data/positions.csv",
    historical_file="data/historical_values.json",
    base_currency="EUR"
)
news_service = NewsService()


# Pydantic models for requests
class PositionCreate(BaseModel):
    ticker: str
    quantity: float
    avg_price: float
    type: str  # stock, etf, crypto
    currency: str
    broker: str


class PositionUpdate(BaseModel):
    quantity: Optional[float] = None
    avg_price: Optional[float] = None


# API Endpoints

@app.get("/")
async def root():
    """API health check"""
    return {
        "status": "online",
        "service": "Personal Finance Dashboard",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/portfolio")
async def get_portfolio():
    """
    Get complete portfolio overview with all metrics
    Returns: total value, positions, distributions, KPIs
    """
    try:
        portfolio = await portfolio_service.calculate_portfolio()
        return portfolio
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio/summary")
async def get_portfolio_summary():
    """Get portfolio summary (lighter endpoint)"""
    try:
        portfolio = await portfolio_service.calculate_portfolio()
        return {
            'total_value': portfolio['total_value'],
            'total_cost': portfolio['total_cost'],
            'total_gain_loss': portfolio['total_gain_loss'],
            'total_gain_loss_pct': portfolio['total_gain_loss_pct'],
            'daily_change': portfolio['daily_change'],
            'daily_change_pct': portfolio['daily_change_pct'],
            'base_currency': portfolio['base_currency'],
            'positions_count': len(portfolio['positions']),
            'last_updated': portfolio['last_updated']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio/history")
async def get_portfolio_history(days: int = Query(default=365, ge=1, le=3650)):
    """Get historical portfolio values"""
    try:
        history = await portfolio_service.get_portfolio_history(days)
        return {"history": history, "days": days}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/portfolio/kpis")
async def get_portfolio_kpis():
    """Get portfolio KPIs (CAGR, drawdown, etc.)"""
    try:
        portfolio = await portfolio_service.calculate_portfolio()
        return portfolio['kpis']
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/asset/{ticker}/history")
async def get_asset_history(
    ticker: str, 
    period: str = Query(default="1y", regex="^(1d|5d|1mo|3mo|6mo|1y|2y|5y|max)$"),
    asset_type: str = Query(default="auto")
):
    """
    Get historical price data for a specific asset.
    
    - ticker: Asset symbol (BTC, ETH, AAPL, SGLD.L, etc.)
    - period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
    - asset_type: auto, crypto, stock, etf, fund
    """
    try:
        from services.yahoo_finance import YahooFinanceService
        from services.coingecko import CoinGeckoService
        
        yahoo = YahooFinanceService()
        coingecko = CoinGeckoService()
        
        # Auto-detect asset type if not specified
        if asset_type == "auto":
            positions = portfolio_service.load_positions()
            pos = positions[positions['ticker'].str.upper() == ticker.upper()]
            if not pos.empty:
                asset_type = pos.iloc[0]['type']
            else:
                # Guess based on ticker format
                if ticker.upper() in ['BTC', 'ETH', 'SOL', 'DOGE', 'PEPE', 'XRP', 'ADA']:
                    asset_type = "crypto"
                else:
                    asset_type = "stock"
        
        # Fetch history based on asset type
        history = None
        if asset_type == "crypto":
            # Convert period to days for CoinGecko
            period_days = {
                "1d": 1, "5d": 5, "1mo": 30, "3mo": 90, 
                "6mo": 180, "1y": 365, "2y": 730, "5y": 1825, "max": 2000
            }
            days = period_days.get(period, 365)
            history = await coingecko.get_history(ticker, days=days, vs_currency="eur")
        else:
            history = await yahoo.get_history(ticker, period=period)
        
        if not history:
            raise HTTPException(status_code=404, detail=f"No historical data found for {ticker}")
        
        # Get current info
        current_info = None
        if asset_type == "crypto":
            current_info = await coingecko.get_price(ticker, vs_currency="eur")
        else:
            current_info = await yahoo.get_price(ticker)
        
        return {
            "ticker": ticker.upper(),
            "type": asset_type,
            "period": period,
            "history": history,
            "current": current_info,
            "data_points": len(history)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/positions")
async def get_positions():
    """Get all positions"""
    try:
        positions = portfolio_service.load_positions()
        return positions.to_dict('records')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/positions")
async def add_position(position: PositionCreate):
    """Add a new position"""
    try:
        positions = portfolio_service.load_positions()
        
        # Check if position already exists
        existing = positions[positions['ticker'] == position.ticker]
        if not existing.empty:
            raise HTTPException(
                status_code=400, 
                detail=f"Position {position.ticker} already exists. Use PUT to update."
            )
        
        new_row = {
            'ticker': position.ticker.upper(),
            'quantity': position.quantity,
            'avg_price': position.avg_price,
            'type': position.type.lower(),
            'currency': position.currency.upper(),
            'broker': position.broker
        }
        
        positions = positions._append(new_row, ignore_index=True)
        portfolio_service.save_positions(positions)
        
        return {"message": "Position added", "position": new_row}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/positions/{ticker}")
async def update_position(ticker: str, update: PositionUpdate):
    """Update an existing position"""
    try:
        positions = portfolio_service.load_positions()
        ticker = ticker.upper()
        
        mask = positions['ticker'] == ticker
        if not mask.any():
            raise HTTPException(status_code=404, detail=f"Position {ticker} not found")
        
        if update.quantity is not None:
            positions.loc[mask, 'quantity'] = update.quantity
        if update.avg_price is not None:
            positions.loc[mask, 'avg_price'] = update.avg_price
        
        portfolio_service.save_positions(positions)
        
        return {"message": "Position updated", "ticker": ticker}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/positions/{ticker}")
async def delete_position(ticker: str):
    """Delete a position"""
    try:
        positions = portfolio_service.load_positions()
        ticker = ticker.upper()
        
        if ticker not in positions['ticker'].values:
            raise HTTPException(status_code=404, detail=f"Position {ticker} not found")
        
        positions = positions[positions['ticker'] != ticker]
        portfolio_service.save_positions(positions)
        
        return {"message": "Position deleted", "ticker": ticker}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/distributions")
async def get_distributions():
    """Get portfolio distributions (by type, broker, currency)"""
    try:
        portfolio = await portfolio_service.calculate_portfolio()
        return {
            'by_type': portfolio['by_type'],
            'by_broker': portfolio['by_broker'],
            'by_currency': portfolio['by_currency']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/asset/{ticker}/history")
async def get_asset_history(
    ticker: str, 
    asset_type: str = Query(default="stock"),
    days: int = Query(default=365, ge=1, le=3650)
):
    """Get historical prices for a specific asset"""
    try:
        history = await portfolio_service.get_asset_history(ticker, asset_type, days)
        if history is None:
            raise HTTPException(status_code=404, detail=f"No history found for {ticker}")
        return {"ticker": ticker, "history": history}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/price/{ticker}")
async def get_price(ticker: str, asset_type: str = Query(default="stock")):
    """Get current price for a specific asset"""
    try:
        if asset_type == "crypto":
            price = await CoinGeckoService().get_price(ticker)
        else:
            price = await YahooFinanceService().get_price(ticker)
        
        if price is None:
            raise HTTPException(status_code=404, detail=f"Price not found for {ticker}")
        
        return price
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fx/rates")
async def get_fx_rates():
    """Get current exchange rates"""
    try:
        fx = ExchangeRateService("EUR")
        rates = await fx.fetch_rates()
        return {"base": "EUR", "rates": rates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/refresh")
async def refresh_data():
    """Force refresh all data (clear caches)"""
    try:
        # Reinitialize services to clear caches
        global portfolio_service
        portfolio_service = PortfolioService(
            positions_file="data/positions.csv",
            historical_file="data/historical_values.json",
            base_currency="EUR"
        )
        
        # Fetch fresh data
        portfolio = await portfolio_service.calculate_portfolio()
        
        return {
            "message": "Data refreshed successfully",
            "timestamp": datetime.now().isoformat(),
            "total_value": portfolio['total_value']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# CSV Import Endpoints
# ============================================

class CSVMapping(BaseModel):
    """Mapping for CSV columns to our format"""
    ticker_col: str = "ticker"
    quantity_col: str = "quantity"
    price_col: str = "avg_price"
    type_col: Optional[str] = None
    currency_col: Optional[str] = None
    default_type: str = "stock"
    default_currency: str = "EUR"
    default_broker: str = "Manual"


@app.post("/api/import/csv")
async def import_csv(
    file: UploadFile = File(...),
    broker: str = Form(default="Manual"),
    merge_existing: bool = Form(default=True)
):
    """
    Import positions from a CSV file.
    Supports various formats from different brokers.
    """
    try:
        # Read file content
        content = await file.read()
        
        # Try to detect encoding and parse
        try:
            df = pd.read_csv(io.StringIO(content.decode('utf-8')))
        except:
            df = pd.read_csv(io.StringIO(content.decode('latin-1')))
        
        # Process the CSV based on detected format
        processed = process_csv_import(df, broker)
        
        if processed.empty:
            raise HTTPException(status_code=400, detail="No valid positions found in CSV")
        
        # Load existing positions
        existing = portfolio_service.load_positions()
        
        if merge_existing:
            # Merge with existing - update quantities for same ticker+broker
            for _, row in processed.iterrows():
                mask = (existing['ticker'] == row['ticker']) & (existing['broker'] == row['broker'])
                if mask.any():
                    # Update existing
                    existing.loc[mask, 'quantity'] = row['quantity']
                    existing.loc[mask, 'avg_price'] = row['avg_price']
                else:
                    # Add new
                    existing = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
        else:
            # Replace all positions from this broker
            existing = existing[existing['broker'] != broker]
            existing = pd.concat([existing, processed], ignore_index=True)
        
        # Save
        portfolio_service.save_positions(existing)
        
        return {
            "message": f"Successfully imported {len(processed)} positions",
            "positions_imported": len(processed),
            "broker": broker,
            "positions": processed.to_dict('records')
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")


def process_csv_import(df: pd.DataFrame, broker: str) -> pd.DataFrame:
    """Process CSV from various broker formats"""
    
    # Normalize column names
    df.columns = df.columns.str.lower().str.strip()
    
    result = []
    
    # Try to detect format based on columns
    columns = set(df.columns)
    
    # Format 1: Standard FinTrack format
    if {'ticker', 'quantity', 'avg_price', 'type', 'currency'}.issubset(columns):
        return df[['ticker', 'quantity', 'avg_price', 'type', 'currency']].assign(broker=broker)
    
    # Format 2: Trade Republic style (German)
    if {'isin', 'stück', 'kaufkurs'}.issubset(columns) or {'isin', 'anzahl', 'kurs'}.issubset(columns):
        for _, row in df.iterrows():
            qty_col = 'stück' if 'stück' in columns else 'anzahl'
            price_col = 'kaufkurs' if 'kaufkurs' in columns else 'kurs'
            result.append({
                'ticker': row.get('isin', row.get('symbol', '')),
                'quantity': float(str(row.get(qty_col, 0)).replace(',', '.')),
                'avg_price': float(str(row.get(price_col, 0)).replace(',', '.').replace('€', '').strip()),
                'type': 'stock',
                'currency': 'EUR',
                'broker': broker
            })
    
    # Format 3: Generic with common column names
    elif any(col in columns for col in ['symbol', 'ticker', 'isin', 'name']):
        ticker_col = next((c for c in ['ticker', 'symbol', 'isin', 'name'] if c in columns), None)
        qty_col = next((c for c in ['quantity', 'qty', 'shares', 'units', 'amount', 'anzahl'] if c in columns), None)
        price_col = next((c for c in ['avg_price', 'price', 'cost', 'purchase_price', 'kaufkurs'] if c in columns), None)
        type_col = next((c for c in ['type', 'asset_type', 'category'] if c in columns), None)
        currency_col = next((c for c in ['currency', 'ccy'] if c in columns), None)
        
        for _, row in df.iterrows():
            if ticker_col and qty_col:
                entry = {
                    'ticker': str(row.get(ticker_col, '')).upper().strip(),
                    'quantity': float(str(row.get(qty_col, 0)).replace(',', '.')),
                    'avg_price': float(str(row.get(price_col, 0)).replace(',', '.').replace('€', '').replace('$', '').strip()) if price_col else 0,
                    'type': str(row.get(type_col, 'stock')).lower() if type_col else 'stock',
                    'currency': str(row.get(currency_col, 'EUR')).upper() if currency_col else 'EUR',
                    'broker': broker
                }
                if entry['ticker'] and entry['quantity'] > 0:
                    result.append(entry)
    
    # Format 4: Kraken format
    elif {'asset', 'balance'}.issubset(columns):
        for _, row in df.iterrows():
            asset = str(row.get('asset', '')).upper()
            # Skip fiat and staking tokens
            if asset in ['EUR', 'USD', 'GBP'] or '.S' in asset:
                continue
            # Remove Kraken prefixes (X, Z)
            if asset.startswith('X') or asset.startswith('Z'):
                asset = asset[1:]
            balance = float(str(row.get('balance', 0)).replace(',', '.'))
            if balance > 0:
                result.append({
                    'ticker': asset,
                    'quantity': balance,
                    'avg_price': 0,  # Kraken doesn't provide avg price
                    'type': 'crypto',
                    'currency': 'USD',
                    'broker': broker
                })
    
    if not result:
        # Last resort: try any numeric columns
        for col in df.columns:
            if df[col].dtype in ['int64', 'float64'] and df[col].sum() > 0:
                # Found some numeric data, try to use first text column as ticker
                text_cols = [c for c in df.columns if df[c].dtype == 'object']
                if text_cols:
                    for _, row in df.iterrows():
                        result.append({
                            'ticker': str(row[text_cols[0]]).upper().strip()[:10],
                            'quantity': float(row[col]),
                            'avg_price': 0,
                            'type': 'stock',
                            'currency': 'EUR',
                            'broker': broker
                        })
                    break
    
    return pd.DataFrame(result) if result else pd.DataFrame()


@app.post("/api/import/preview")
async def preview_csv_import(file: UploadFile = File(...)):
    """Preview CSV import without saving"""
    try:
        content = await file.read()
        try:
            df = pd.read_csv(io.StringIO(content.decode('utf-8')))
        except:
            df = pd.read_csv(io.StringIO(content.decode('latin-1')))
        
        return {
            "columns": list(df.columns),
            "rows": len(df),
            "preview": df.head(10).to_dict('records'),
            "detected_format": detect_csv_format(df)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def detect_csv_format(df: pd.DataFrame) -> dict:
    """Detect the format of the CSV"""
    columns = set(df.columns.str.lower().str.strip())
    
    if {'ticker', 'quantity', 'avg_price'}.issubset(columns):
        return {"format": "fintrack", "confidence": "high"}
    elif {'isin', 'stück'}.issubset(columns) or {'isin', 'anzahl'}.issubset(columns):
        return {"format": "trade_republic", "confidence": "high"}
    elif {'asset', 'balance'}.issubset(columns):
        return {"format": "kraken", "confidence": "high"}
    elif 'symbol' in columns or 'ticker' in columns:
        return {"format": "generic", "confidence": "medium"}
    else:
        return {"format": "unknown", "confidence": "low"}


# ============================================
# Transaction History
# ============================================

TRANSACTIONS_FILE = Path("data/transactions.json")


class Transaction(BaseModel):
    type: str  # buy, sell, dividend
    ticker: str
    quantity: float
    price: float
    date: str
    broker: str
    notes: Optional[str] = None


@app.get("/api/transactions")
async def get_transactions():
    """Get all transactions"""
    try:
        if TRANSACTIONS_FILE.exists():
            with open(TRANSACTIONS_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/transactions")
async def add_transaction(tx: Transaction):
    """Add a new transaction and update positions"""
    try:
        # Load existing transactions
        transactions = []
        if TRANSACTIONS_FILE.exists():
            with open(TRANSACTIONS_FILE, 'r') as f:
                transactions = json.load(f)
        
        # Add new transaction with ID
        new_tx = tx.dict()
        new_tx['id'] = len(transactions) + 1
        new_tx['created_at'] = datetime.now().isoformat()
        transactions.append(new_tx)
        
        # Save transactions
        TRANSACTIONS_FILE.parent.mkdir(exist_ok=True)
        with open(TRANSACTIONS_FILE, 'w') as f:
            json.dump(transactions, f, indent=2)
        
        # Update positions based on transaction
        positions = portfolio_service.load_positions()
        ticker = tx.ticker.upper()
        
        mask = (positions['ticker'] == ticker) & (positions['broker'] == tx.broker)
        
        if tx.type == 'buy':
            if mask.any():
                # Update existing position (calculate new avg price)
                old_qty = positions.loc[mask, 'quantity'].values[0]
                old_price = positions.loc[mask, 'avg_price'].values[0]
                new_qty = old_qty + tx.quantity
                new_avg_price = ((old_qty * old_price) + (tx.quantity * tx.price)) / new_qty
                positions.loc[mask, 'quantity'] = new_qty
                positions.loc[mask, 'avg_price'] = new_avg_price
            else:
                # Create new position
                new_row = pd.DataFrame([{
                    'ticker': ticker,
                    'quantity': tx.quantity,
                    'avg_price': tx.price,
                    'type': 'stock',  # Default, can be updated
                    'currency': 'EUR',
                    'broker': tx.broker
                }])
                positions = pd.concat([positions, new_row], ignore_index=True)
        
        elif tx.type == 'sell':
            if mask.any():
                old_qty = positions.loc[mask, 'quantity'].values[0]
                new_qty = old_qty - tx.quantity
                if new_qty <= 0:
                    positions = positions[~mask]
                else:
                    positions.loc[mask, 'quantity'] = new_qty
        
        portfolio_service.save_positions(positions)
        
        return {"message": "Transaction added", "transaction": new_tx}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/transactions/{tx_id}")
async def delete_transaction(tx_id: int):
    """Delete a transaction"""
    try:
        if not TRANSACTIONS_FILE.exists():
            raise HTTPException(status_code=404, detail="No transactions found")
        
        with open(TRANSACTIONS_FILE, 'r') as f:
            transactions = json.load(f)
        
        transactions = [t for t in transactions if t.get('id') != tx_id]
        
        with open(TRANSACTIONS_FILE, 'w') as f:
            json.dump(transactions, f, indent=2)
        
        return {"message": f"Transaction {tx_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# AI Advisor Endpoint
# ============================================

class AIQuestion(BaseModel):
    question: str
    include_portfolio: bool = True


# System prompt for the AI advisor
AI_SYSTEM_PROMPT = """Eres un asesor financiero experto y educador. Tu nombre es FinBot.

IMPORTANTE:
- Hablas SIEMPRE en español
- Eres amable, cercano y pedagógico
- Explicas conceptos complejos de forma simple
- Nunca das consejos específicos de compra/venta (por regulación)
- Recomiendas diversificación y inversión a largo plazo
- Adviertes sobre los riesgos de cada inversión
- Si te preguntan sobre la cartera del usuario, analizas sus posiciones de forma educativa

Cuando analices una cartera:
1. Comenta la diversificación (por tipo, geografía, sectores)
2. Identifica concentraciones de riesgo
3. Sugiere mejoras generales (nunca tickers específicos)
4. Explica métricas como P/L, volatilidad, etc.

DISCLAIMER que debes mencionar en preguntas sobre inversión:
"Recuerda que esto es información educativa, no asesoramiento financiero personalizado. Consulta con un profesional antes de tomar decisiones de inversión."
"""


@app.post("/api/ai/chat")
async def ai_chat(question: AIQuestion):
    """Chat with AI financial advisor"""
    try:
        import httpx
        
        # Try to get API key from environment
        groq_key = os.getenv('GROQ_API_KEY', '')
        
        # If no key, return a helpful message
        if not groq_key:
            return {
                "response": """¡Hola! Soy FinBot, tu asesor financiero virtual. 🤖

Para activarme necesitas configurar una API key gratuita de Groq:

1. Ve a https://console.groq.com y crea una cuenta gratis
2. Genera una API key
3. Añádela al archivo `.env` en el backend:
   ```
   GROQ_API_KEY=tu_api_key_aqui
   ```
4. Reinicia el servidor

¡Es completamente gratis y te permite hacer muchas preguntas!

Mientras tanto, puedes explorar la sección "Aprender" donde encontrarás guías completas sobre inversión.""",
                "model": "none",
                "tokens_used": 0
            }
        
        # Build context with portfolio data if requested
        context = ""
        if question.include_portfolio:
            try:
                portfolio = await portfolio_service.calculate_portfolio()
                context = f"""
DATOS DE LA CARTERA DEL USUARIO:
- Valor total: {portfolio['total_value']:.2f} {portfolio['base_currency']}
- Ganancia/Pérdida total: {portfolio['total_gain_loss']:.2f} ({portfolio['total_gain_loss_pct']:.2f}%)
- Cambio hoy: {portfolio['daily_change']:.2f} ({portfolio['daily_change_pct']:.2f}%)

POSICIONES:
"""
                for pos in portfolio['positions'][:15]:  # Limit to 15 positions
                    context += f"- {pos['ticker']} ({pos['type']}): {pos['quantity']} unidades, P/L: {pos['gain_loss_pct']:.1f}%, Peso: {pos['weight']:.1f}%\n"
                
                context += f"\nDISTRIBUCIÓN POR TIPO: {portfolio['by_type']}\n"
                context += f"DISTRIBUCIÓN POR BROKER: {list(portfolio['by_broker'].keys())}\n"
            except:
                context = "No se pudo cargar la información de la cartera."
        
        # Call Groq API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-70b-versatile",
                    "messages": [
                        {"role": "system", "content": AI_SYSTEM_PROMPT},
                        {"role": "user", "content": f"{context}\n\nPREGUNTA DEL USUARIO: {question.question}"}
                    ],
                    "max_tokens": 1500,
                    "temperature": 0.7
                },
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise Exception(f"Groq API error: {response.text}")
            
            data = response.json()
            ai_response = data['choices'][0]['message']['content']
            tokens = data.get('usage', {}).get('total_tokens', 0)
            
            return {
                "response": ai_response,
                "model": "llama-3.1-70b",
                "tokens_used": tokens
            }
            
    except Exception as e:
        return {
            "response": f"Lo siento, ha ocurrido un error al procesar tu pregunta: {str(e)}. Por favor, inténtalo de nuevo.",
            "model": "error",
            "tokens_used": 0
        }


# =============================================================================
# NEWS ENDPOINTS
# =============================================================================

@app.get("/api/news")
async def get_news(
    category: str = Query(default="all", description="Filter by category: all, stocks, crypto, economy, politics"),
    limit: int = Query(default=30, ge=1, le=100, description="Number of news items to return")
):
    """
    Get real-time financial news from RSS feeds.
    
    Categories:
    - all: All news
    - stocks: Stock market news
    - crypto: Cryptocurrency news
    - economy: Economic news
    - politics: Political/geopolitical news affecting markets
    """
    try:
        news = await news_service.get_news(category=category, limit=limit)
        return {
            "news": news,
            "count": len(news),
            "category": category,
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/news/asset/{ticker}")
async def get_news_for_asset(
    ticker: str,
    limit: int = Query(default=10, ge=1, le=50)
):
    """Get news related to a specific asset/ticker"""
    try:
        news = await news_service.get_news_for_asset(ticker=ticker, limit=limit)
        return {
            "ticker": ticker.upper(),
            "news": news,
            "count": len(news)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Run server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


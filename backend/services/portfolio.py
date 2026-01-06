"""
Portfolio Service
Manages portfolio data, calculations, and KPIs
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
from .yahoo_finance import YahooFinanceService
from .coingecko import CoinGeckoService
from .exchange_rates import ExchangeRateService


class PortfolioService:
    """Service for portfolio management and analysis"""
    
    def __init__(self, positions_file: str = "data/positions.csv", 
                 historical_file: str = "data/historical_values.json",
                 base_currency: str = "EUR"):
        self.positions_file = Path(positions_file)
        self.historical_file = Path(historical_file)
        self.base_currency = base_currency
        
        self.yahoo = YahooFinanceService()
        self.coingecko = CoinGeckoService()
        self.fx = ExchangeRateService(base_currency)
        
        self._positions_cache = None
        self._prices_cache = None
        self._last_update = None
    
    def load_positions(self) -> pd.DataFrame:
        """Load positions from CSV file"""
        if not self.positions_file.exists():
            return pd.DataFrame(columns=['ticker', 'quantity', 'avg_price', 'type', 'currency', 'broker'])
        
        df = pd.read_csv(self.positions_file)
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
        df['avg_price'] = pd.to_numeric(df['avg_price'], errors='coerce')
        return df
    
    def save_positions(self, positions: pd.DataFrame):
        """Save positions to CSV file"""
        positions.to_csv(self.positions_file, index=False)
    
    def load_historical_values(self) -> Dict:
        """Load historical portfolio values"""
        if not self.historical_file.exists():
            return {"values": [], "last_updated": None}
        
        with open(self.historical_file, 'r') as f:
            return json.load(f)
    
    def save_historical_value(self, value: float, date: str = None):
        """Save today's portfolio value to history"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        history = self.load_historical_values()
        
        # Update or append today's value
        existing_idx = next(
            (i for i, v in enumerate(history['values']) if v['date'] == date), 
            None
        )
        
        entry = {'date': date, 'value': value}
        
        if existing_idx is not None:
            history['values'][existing_idx] = entry
        else:
            history['values'].append(entry)
            history['values'].sort(key=lambda x: x['date'])
        
        history['last_updated'] = datetime.now().isoformat()
        
        with open(self.historical_file, 'w') as f:
            json.dump(history, f, indent=2)
    
    async def fetch_all_prices(self, positions: pd.DataFrame) -> Dict[str, dict]:
        """Fetch current prices for all positions"""
        prices = {}
        
        # Separate by asset type
        stocks_etfs = positions[positions['type'].isin(['stock', 'etf'])]['ticker'].unique().tolist()
        cryptos = positions[positions['type'] == 'crypto']['ticker'].unique().tolist()
        
        # Fetch stock/ETF prices
        if stocks_etfs:
            stock_prices = await self.yahoo.get_prices(stocks_etfs)
            prices.update(stock_prices)
        
        # Fetch crypto prices
        if cryptos:
            crypto_prices = await self.coingecko.get_prices(cryptos)
            prices.update(crypto_prices)
        
        self._prices_cache = prices
        self._last_update = datetime.now()
        
        return prices
    
    async def calculate_portfolio(self) -> Dict:
        """Calculate complete portfolio with all metrics"""
        positions = self.load_positions()
        
        if positions.empty:
            return {
                'total_value': 0,
                'total_cost': 0,
                'total_gain_loss': 0,
                'total_gain_loss_pct': 0,
                'daily_change': 0,
                'daily_change_pct': 0,
                'positions': [],
                'by_type': {},
                'by_broker': {},
                'by_currency': {},
                'kpis': {},
                'last_updated': datetime.now().isoformat()
            }
        
        # Fetch all prices
        prices = await self.fetch_all_prices(positions)
        
        # Calculate position values
        position_data = []
        total_value = 0
        total_cost = 0
        daily_change = 0
        
        for _, pos in positions.iterrows():
            ticker = pos['ticker']
            quantity = pos['quantity']
            avg_price = pos['avg_price']
            asset_type = pos['type']
            currency = pos['currency']
            broker = pos['broker']
            
            price_data = prices.get(ticker, {})
            current_price = price_data.get('price', avg_price)
            prev_close = price_data.get('previous_close', current_price)
            
            # Calculate values
            cost_basis = quantity * avg_price
            market_value = quantity * current_price
            gain_loss = market_value - cost_basis
            gain_loss_pct = (gain_loss / cost_basis * 100) if cost_basis > 0 else 0
            
            day_change = (current_price - prev_close) * quantity
            day_change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close > 0 else 0
            
            # Convert to base currency
            fx_rate = await self.fx.get_rate(currency, self.base_currency)
            market_value_base = market_value * fx_rate
            cost_basis_base = cost_basis * fx_rate
            day_change_base = day_change * fx_rate
            
            position_info = {
                'ticker': ticker,
                'name': price_data.get('name', ticker),
                'quantity': quantity,
                'avg_price': avg_price,
                'current_price': current_price,
                'cost_basis': cost_basis,
                'market_value': market_value,
                'market_value_base': market_value_base,
                'gain_loss': gain_loss,
                'gain_loss_pct': round(gain_loss_pct, 2),
                'day_change': day_change,
                'day_change_pct': round(day_change_pct, 2),
                'type': asset_type,
                'currency': currency,
                'broker': broker,
                'weight': 0  # Will calculate after totals
            }
            
            position_data.append(position_info)
            total_value += market_value_base
            total_cost += cost_basis_base
            daily_change += day_change_base
        
        # Calculate weights
        for pos in position_data:
            pos['weight'] = round(pos['market_value_base'] / total_value * 100, 2) if total_value > 0 else 0
        
        # Sort by market value
        position_data.sort(key=lambda x: x['market_value_base'], reverse=True)
        
        # Aggregate by type
        by_type = {}
        for pos in position_data:
            t = pos['type']
            if t not in by_type:
                by_type[t] = {'value': 0, 'cost': 0, 'weight': 0}
            by_type[t]['value'] += pos['market_value_base']
            by_type[t]['cost'] += pos['cost_basis'] * (await self.fx.get_rate(pos['currency'], self.base_currency))
        
        for t in by_type:
            by_type[t]['weight'] = round(by_type[t]['value'] / total_value * 100, 2) if total_value > 0 else 0
            by_type[t]['gain_loss'] = by_type[t]['value'] - by_type[t]['cost']
            by_type[t]['gain_loss_pct'] = round(
                (by_type[t]['gain_loss'] / by_type[t]['cost'] * 100) if by_type[t]['cost'] > 0 else 0, 2
            )
        
        # Aggregate by broker
        by_broker = {}
        for pos in position_data:
            b = pos['broker']
            if b not in by_broker:
                by_broker[b] = {'value': 0, 'weight': 0, 'positions': 0}
            by_broker[b]['value'] += pos['market_value_base']
            by_broker[b]['positions'] += 1
        
        for b in by_broker:
            by_broker[b]['weight'] = round(by_broker[b]['value'] / total_value * 100, 2) if total_value > 0 else 0
        
        # Aggregate by currency
        by_currency = {}
        for pos in position_data:
            c = pos['currency']
            if c not in by_currency:
                by_currency[c] = {'value': 0, 'weight': 0}
            by_currency[c]['value'] += pos['market_value_base']
        
        for c in by_currency:
            by_currency[c]['weight'] = round(by_currency[c]['value'] / total_value * 100, 2) if total_value > 0 else 0
        
        # Calculate KPIs
        total_gain_loss = total_value - total_cost
        total_gain_loss_pct = (total_gain_loss / total_cost * 100) if total_cost > 0 else 0
        daily_change_pct = (daily_change / (total_value - daily_change) * 100) if (total_value - daily_change) > 0 else 0
        
        # Save today's value to history
        self.save_historical_value(total_value)
        
        # Calculate advanced KPIs from history
        kpis = await self._calculate_kpis(total_value, total_cost)
        
        return {
            'total_value': round(total_value, 2),
            'total_cost': round(total_cost, 2),
            'total_gain_loss': round(total_gain_loss, 2),
            'total_gain_loss_pct': round(total_gain_loss_pct, 2),
            'daily_change': round(daily_change, 2),
            'daily_change_pct': round(daily_change_pct, 2),
            'base_currency': self.base_currency,
            'positions': position_data,
            'by_type': by_type,
            'by_broker': by_broker,
            'by_currency': by_currency,
            'kpis': kpis,
            'last_updated': datetime.now().isoformat()
        }
    
    async def _calculate_kpis(self, current_value: float, total_cost: float) -> Dict:
        """Calculate advanced portfolio KPIs"""
        history = self.load_historical_values()
        values = history.get('values', [])
        
        kpis = {
            'cagr': 0,
            'max_drawdown': 0,
            'max_drawdown_date': None,
            'best_day': 0,
            'worst_day': 0,
            'volatility': 0,
            'sharpe_ratio': 0,
            'days_tracked': len(values)
        }
        
        if len(values) < 2:
            return kpis
        
        # Convert to numpy for calculations
        dates = [datetime.strptime(v['date'], '%Y-%m-%d') for v in values]
        vals = np.array([v['value'] for v in values])
        
        # Daily returns
        returns = np.diff(vals) / vals[:-1]
        
        if len(returns) > 0:
            # Best/worst day
            kpis['best_day'] = round(float(np.max(returns)) * 100, 2)
            kpis['worst_day'] = round(float(np.min(returns)) * 100, 2)
            
            # Volatility (annualized)
            kpis['volatility'] = round(float(np.std(returns) * np.sqrt(252)) * 100, 2)
            
            # Sharpe ratio (assuming 3% risk-free rate)
            risk_free = 0.03 / 252
            excess_returns = returns - risk_free
            if np.std(excess_returns) > 0:
                kpis['sharpe_ratio'] = round(
                    float(np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)), 2
                )
        
        # CAGR
        if len(dates) >= 2:
            years = (dates[-1] - dates[0]).days / 365.25
            if years > 0 and vals[0] > 0:
                kpis['cagr'] = round(
                    (pow(vals[-1] / vals[0], 1 / years) - 1) * 100, 2
                )
        
        # Maximum Drawdown
        peak = vals[0]
        max_dd = 0
        max_dd_date = dates[0]
        
        for i, (date, val) in enumerate(zip(dates, vals)):
            if val > peak:
                peak = val
            dd = (peak - val) / peak
            if dd > max_dd:
                max_dd = dd
                max_dd_date = date
        
        kpis['max_drawdown'] = round(max_dd * 100, 2)
        kpis['max_drawdown_date'] = max_dd_date.strftime('%Y-%m-%d') if max_dd > 0 else None
        
        return kpis
    
    async def get_portfolio_history(self, days: int = 365) -> List[Dict]:
        """Get portfolio value history"""
        history = self.load_historical_values()
        values = history.get('values', [])
        
        # Filter by days
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.strftime('%Y-%m-%d')
        
        return [v for v in values if v['date'] >= cutoff_str]
    
    async def get_asset_history(self, ticker: str, asset_type: str, days: int = 365) -> Optional[List[Dict]]:
        """Get historical prices for a specific asset"""
        if asset_type == 'crypto':
            return await self.coingecko.get_history(ticker, days)
        else:
            period = "1y" if days >= 365 else f"{days}d"
            return await self.yahoo.get_history(ticker, period)


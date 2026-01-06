"""
Data Models for the Portfolio API
Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


class AssetType(str, Enum):
    STOCK = "stock"
    ETF = "etf"
    CRYPTO = "crypto"


class Currency(str, Enum):
    EUR = "EUR"
    USD = "USD"
    GBP = "GBP"
    CHF = "CHF"


# Request Models
class PositionCreate(BaseModel):
    """Model for creating a new position"""
    ticker: str = Field(..., min_length=1, max_length=20, description="Asset ticker symbol")
    quantity: float = Field(..., gt=0, description="Number of units held")
    avg_price: float = Field(..., ge=0, description="Average purchase price")
    type: AssetType = Field(..., description="Type of asset")
    currency: str = Field(default="USD", description="Currency of the asset")
    broker: str = Field(..., min_length=1, description="Broker name")
    
    class Config:
        json_schema_extra = {
            "example": {
                "ticker": "AAPL",
                "quantity": 10,
                "avg_price": 150.00,
                "type": "stock",
                "currency": "USD",
                "broker": "TradeRepublic"
            }
        }


class PositionUpdate(BaseModel):
    """Model for updating an existing position"""
    quantity: Optional[float] = Field(None, gt=0)
    avg_price: Optional[float] = Field(None, ge=0)


# Response Models
class PriceData(BaseModel):
    """Current price data for an asset"""
    ticker: str
    price: float
    previous_close: float
    change: float
    change_percent: float
    currency: str
    name: Optional[str] = None
    market_cap: Optional[float] = None
    last_updated: datetime


class PositionDetail(BaseModel):
    """Detailed position information"""
    ticker: str
    name: str
    quantity: float
    avg_price: float
    current_price: float
    cost_basis: float
    market_value: float
    market_value_base: float
    gain_loss: float
    gain_loss_pct: float
    day_change: float
    day_change_pct: float
    type: str
    currency: str
    broker: str
    weight: float


class Distribution(BaseModel):
    """Distribution breakdown"""
    value: float
    weight: float
    cost: Optional[float] = None
    gain_loss: Optional[float] = None
    gain_loss_pct: Optional[float] = None
    positions: Optional[int] = None


class KPIs(BaseModel):
    """Portfolio KPIs"""
    cagr: float = 0
    max_drawdown: float = 0
    max_drawdown_date: Optional[str] = None
    best_day: float = 0
    worst_day: float = 0
    volatility: float = 0
    sharpe_ratio: float = 0
    days_tracked: int = 0


class PortfolioSummary(BaseModel):
    """Summary portfolio response"""
    total_value: float
    total_cost: float
    total_gain_loss: float
    total_gain_loss_pct: float
    daily_change: float
    daily_change_pct: float
    base_currency: str
    positions_count: int
    last_updated: datetime


class PortfolioFull(BaseModel):
    """Full portfolio response with all details"""
    total_value: float
    total_cost: float
    total_gain_loss: float
    total_gain_loss_pct: float
    daily_change: float
    daily_change_pct: float
    base_currency: str
    positions: List[PositionDetail]
    by_type: Dict[str, Distribution]
    by_broker: Dict[str, Distribution]
    by_currency: Dict[str, Distribution]
    kpis: KPIs
    last_updated: datetime


class HistoryPoint(BaseModel):
    """Single point in portfolio history"""
    date: str
    value: float


class PortfolioHistory(BaseModel):
    """Portfolio value history"""
    history: List[HistoryPoint]
    days: int


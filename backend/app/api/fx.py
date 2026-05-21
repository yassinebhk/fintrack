"""FX rates endpoint."""

from fastapi import APIRouter

from app.config import get_settings
from app.services.market import ExchangeRateService

router = APIRouter(prefix="/api", tags=["fx"])
_fx = ExchangeRateService(get_settings().base_currency)


@router.get("/fx/rates")
async def get_fx_rates() -> dict:
    rates = await _fx.fetch_rates()
    return {"base": get_settings().base_currency, "rates": rates}

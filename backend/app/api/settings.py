"""User-facing report/display preferences."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import report_prefs

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ExcludedIn(BaseModel):
    tickers: list[str]


@router.get("/report-excluded")
async def get_report_excluded() -> dict:
    return {"excluded": sorted(await report_prefs.get_excluded())}


@router.put("/report-excluded")
async def put_report_excluded(payload: ExcludedIn) -> dict:
    saved = await report_prefs.set_excluded(payload.tickers)
    return {"message": "actualizado", **saved}

"""User-facing report/display preferences."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import allocation, report_prefs

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ExcludedIn(BaseModel):
    tickers: list[str]


class TargetsIn(BaseModel):
    targets: dict[str, float]


@router.get("/report-excluded")
async def get_report_excluded() -> dict:
    return {"excluded": sorted(await report_prefs.get_excluded())}


@router.put("/report-excluded")
async def put_report_excluded(payload: ExcludedIn) -> dict:
    saved = await report_prefs.set_excluded(payload.tickers)
    return {"message": "actualizado", **saved}


@router.get("/allocation-targets")
async def get_allocation_targets() -> dict:
    return {"targets": await allocation.get_targets(), "blocks": allocation.BLOCKS}


@router.put("/allocation-targets")
async def put_allocation_targets(payload: TargetsIn) -> dict:
    saved = await allocation.set_targets(payload.targets)
    return {"message": "actualizado", "targets": saved}

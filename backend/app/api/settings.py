"""User-facing report/display preferences."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import get_current_user
from app.models.user import User
from app.services import allocation, report_prefs

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ExcludedIn(BaseModel):
    tickers: list[str]


class TargetsIn(BaseModel):
    targets: dict[str, float]


@router.get("/report-excluded")
async def get_report_excluded(current_user: User = Depends(get_current_user)) -> dict:
    return {"excluded": sorted(await report_prefs.get_excluded(current_user.id))}


@router.put("/report-excluded")
async def put_report_excluded(payload: ExcludedIn, current_user: User = Depends(get_current_user)) -> dict:
    # 2026-09-21 security fix: was a single global key — any logged-in user's
    # edit here used to silently overwrite the owner's real exclusions.
    saved = await report_prefs.set_excluded(payload.tickers, current_user.id)
    return {"message": "actualizado", **saved}


@router.get("/allocation-targets")
async def get_allocation_targets(current_user: User = Depends(get_current_user)) -> dict:
    return {"targets": await allocation.get_targets(current_user.id), "blocks": allocation.BLOCKS}


@router.put("/allocation-targets")
async def put_allocation_targets(payload: TargetsIn, current_user: User = Depends(get_current_user)) -> dict:
    # 2026-09-21 security fix: was a single global key — any logged-in user's
    # edit here used to silently overwrite the owner's real allocation targets.
    saved = await allocation.set_targets(payload.targets, current_user.id)
    return {"message": "actualizado", "targets": saved}

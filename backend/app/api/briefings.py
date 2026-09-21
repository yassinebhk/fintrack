"""Briefing endpoints."""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from app.auth import get_current_user, get_owner_user_id_cached
from app.models.user import User
from app.services.briefing import BriefingService

router = APIRouter(prefix="/api/briefings", tags=["briefings"])
_service = BriefingService()


# SECURITY (2026-09-21): the briefing is generated from the OWNER's portfolio
# (BriefingService uses get_owner_user_id_cached internally), so serving it to any
# logged-in user leaked the owner's portfolio. Owner-only until it's per-user.
async def _is_owner(user: User) -> bool:
    return user.id == (await get_owner_user_id_cached())


@router.get("/today")
async def get_today(current_user: User = Depends(get_current_user)) -> dict:
    if not await _is_owner(current_user):
        raise HTTPException(status_code=404, detail="No hay briefing para tu cuenta todavía.")
    today = date.today()
    existing = await _service.get_briefing(today)
    if existing:
        return existing
    raise HTTPException(status_code=404, detail="No briefing yet for today — call /generate")


@router.get("/{target_date}")
async def get_by_date(target_date: str, current_user: User = Depends(get_current_user)) -> dict:
    if not await _is_owner(current_user):
        raise HTTPException(status_code=404, detail="No hay briefing para tu cuenta todavía.")
    try:
        target = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date: {exc}") from exc
    existing = await _service.get_briefing(target)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"No briefing for {target_date}")
    return existing


@router.post("/generate")
async def generate(force: bool = False, current_user: User = Depends(get_current_user)) -> dict:
    if not await _is_owner(current_user):
        raise HTTPException(status_code=403, detail="No autorizado.")
    try:
        return await _service.generate_today(force=force)
    except Exception as exc:
        msg = str(exc)
        logger.exception("briefing generation failed")
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            raise HTTPException(
                status_code=503,
                detail="Cuota de Gemini (free tier) agotada por hoy. El briefing automático de las 08:00 se "
                       "regenerará con cuota fresca. Límite: ~20 generaciones/día.",
            ) from exc
        raise HTTPException(status_code=500, detail=msg) from exc

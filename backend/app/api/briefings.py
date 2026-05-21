"""Briefing endpoints."""

from datetime import date, datetime

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.services.briefing import BriefingService

router = APIRouter(prefix="/api/briefings", tags=["briefings"])
_service = BriefingService()


@router.get("/today")
async def get_today() -> dict:
    today = date.today()
    existing = await _service.get_briefing(today)
    if existing:
        return existing
    raise HTTPException(status_code=404, detail="No briefing yet for today — call /generate")


@router.get("/{target_date}")
async def get_by_date(target_date: str) -> dict:
    try:
        target = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date: {exc}") from exc
    existing = await _service.get_briefing(target)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"No briefing for {target_date}")
    return existing


@router.post("/generate")
async def generate(force: bool = False) -> dict:
    try:
        return await _service.generate_today(force=force)
    except Exception as exc:
        logger.exception("briefing generation failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

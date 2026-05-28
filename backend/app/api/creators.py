"""Latest AI summaries of finance creators we follow (YouTube)."""

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.services.creators import CreatorsService

router = APIRouter(prefix="/api/creators", tags=["creators"])


@router.get("/latest")
async def latest(limit: int = 20) -> list[dict]:
    return await CreatorsService().latest(limit=limit)


@router.post("/refresh")
async def refresh(deliver: bool = False) -> dict:
    """Manually trigger the creators pipeline (also runs on a daily cron)."""
    try:
        return await CreatorsService().check_and_process(deliver=deliver)
    except Exception as exc:
        logger.exception("creators refresh failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

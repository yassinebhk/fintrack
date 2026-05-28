"""Latest AI summaries of finance creators we follow (YouTube)."""

import os

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from app.services.creators import CreatorsService

router = APIRouter(prefix="/api/creators", tags=["creators"])

# Shared secret between this backend and the GitHub-Actions transcript worker.
# Set CREATORS_INGEST_SECRET in BOTH Render env vars and the repo's GitHub Secrets.
_INGEST_SECRET = os.getenv("CREATORS_INGEST_SECRET", "")


def _require_secret(secret: str) -> None:
    if not _INGEST_SECRET or secret != _INGEST_SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")


@router.get("/latest")
async def latest(limit: int = 20) -> list[dict]:
    return await CreatorsService().latest(limit=limit)


@router.get("/pending-transcripts")
async def pending_transcripts(secret: str = "") -> dict:
    """Called by the GH-Actions worker: list videos that still need a transcript."""
    _require_secret(secret)
    items = await CreatorsService().list_pending_transcripts()
    return {"pending": items, "count": len(items)}


class TranscriptIn(BaseModel):
    channel_id: str
    video_id: str
    transcript: str = Field(min_length=1)
    title: str = ""
    url: str = ""
    deliver: bool = True


@router.post("/ingest-transcript")
async def ingest_transcript(payload: TranscriptIn, secret: str = "") -> dict:
    """Receive a transcript from the worker, summarize + deliver."""
    _require_secret(secret)
    return await CreatorsService().ingest_transcript(
        channel_id=payload.channel_id, video_id=payload.video_id,
        transcript=payload.transcript, title=payload.title, url=payload.url,
        deliver=payload.deliver,
    )


@router.post("/refresh")
async def refresh(deliver: bool = False, reset: bool = False) -> dict:
    """Manually trigger the creators pipeline (also runs on a daily cron).
    `reset=true` clears the 'already seen' cache so the next run starts fresh."""
    try:
        svc = CreatorsService()
        if reset:
            await svc._save("creators_seen_ids", {})
        return await svc.check_and_process(deliver=deliver)
    except Exception as exc:
        logger.exception("creators refresh failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

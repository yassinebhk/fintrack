"""Opportunity discovery endpoints (AI market analyst)."""

import os

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from app.services.opportunities import get_opportunity_service

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])

# Reuse the same shared secret as the creators ingest worker.
_INGEST_SECRET = os.getenv("CREATORS_INGEST_SECRET", "")


@router.get("")
async def get_opportunities(force: bool = False) -> dict:
    """Today's opportunities. Non-blocking: returns the cached payload instantly, or
    {status:'generating'/'stale'} while a background scan runs (the frontend polls)."""
    try:
        return await get_opportunity_service().peek_or_start(force=force)
    except Exception as exc:
        msg = str(exc)
        logger.exception("opportunities generation failed")
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
            raise HTTPException(status_code=503, detail="Cuota LLM agotada; reintenta más tarde.") from exc
        raise HTTPException(status_code=500, detail=msg) from exc


class ScanIn(BaseModel):
    themes: list[dict]
    crypto: list[dict] = []
    deliver: bool = True   # the daily GH scan delivers to Telegram by default


@router.get("/llm-diag")
async def llm_diag(secret: str = "") -> dict:
    """List available models for the OpenAI-compatible providers (to fix model names)."""
    if not _INGEST_SECRET or secret != _INGEST_SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")
    import httpx

    from app.config import get_settings
    s = get_settings()
    out: dict = {}
    targets = [
        ("openrouter", "https://openrouter.ai/api/v1/models", s.openrouter_api_key),
        ("cerebras", "https://api.cerebras.ai/v1/models", s.cerebras_api_key),
    ]
    for name, url, key in targets:
        if not key:
            out[name] = "no key"
            continue
        try:
            async with httpx.AsyncClient(timeout=20.0) as c:
                r = await c.get(url, headers={"Authorization": f"Bearer {key}"})
            if r.status_code != 200:
                out[name] = f"HTTP {r.status_code}: {r.text[:120]}"
                continue
            data = r.json()
            ids = [m.get("id") for m in (data.get("data") or [])]
            out[name] = ids[:30]
        except Exception as exc:
            out[name] = f"error: {str(exc)[:120]}"
    return out


@router.post("/send-telegram")
async def send_telegram(secret: str = "") -> dict:
    """Push the current opportunities to the configured Telegram chat (server-side,
    uses the bot's rich delivery: summary + regime + trends + one chart per idea)."""
    if not _INGEST_SECRET or secret != _INGEST_SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")
    from app.services.telegram_bot import TelegramBotHandler
    await TelegramBotHandler()._send_opportunities()
    return {"status": "sent"}


@router.get("/scan-tickers")
async def scan_tickers(secret: str = "") -> dict:
    """Tickers the GitHub-Actions scan worker should ALWAYS score, on top of the
    curated universe + Yahoo screeners — the owner's own watchlist and open
    positions. Found 2026-09-25: Celestica (CLS) was a genuinely strong pick
    (real growth, cheap forward PE, unanimous analyst buy) that Yassine had to
    find by hand, because it was in neither the curated universe nor any
    screener category, so it never got scored and could never surface in
    Oportunidades. A ticker the user is already watching or holding is exactly
    the kind of thing that SHOULD compete for a slot, not silently miss out.

    Same shared secret as ingest-scan (the worker never touches user auth, and
    this only ever returns tickers/names — never quantities, prices or
    anything an outside party could act on)."""
    if not _INGEST_SECRET or secret != _INGEST_SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")
    from app.auth import get_owner_user_id_cached
    from app.db import session_scope
    from app.repositories import PositionRepository, WatchlistRepository

    owner_id = await get_owner_user_id_cached()
    if not owner_id:
        return {"tickers": {}}
    out: dict[str, dict] = {}
    async with session_scope() as s:
        for w in await WatchlistRepository(s, owner_id).list_all():
            tk = (w.ticker or "").upper()
            if tk:
                out[tk] = {"name": w.name or tk, "cat": "watchlist", "region": ""}
        for p in await PositionRepository(s, owner_id).list_all():
            if p.type == "crypto":
                continue  # scored separately by scan_crypto_basket(), needs a -EUR/-USD
                          # suffix scan_universe()'s stock-oriented fetch doesn't add —
                          # a bare "BTC" here would either fail to resolve or, worse,
                          # silently resolve to an unrelated stock of that symbol.
            tk = (p.ticker or "").upper()
            if tk:
                out.setdefault(tk, {"name": p.asset_name or tk, "cat": "cartera", "region": ""})
    return {"tickers": out}


@router.post("/ingest-scan")
async def ingest_scan(payload: ScanIn, secret: str = "") -> dict:
    """Receive a pre-computed (already scored) universe scan from the GitHub-Actions
    worker — the heavy part runs there (7GB runner) to avoid OOM on the free tier.
    The backend then does the light part: LLM analyst + enrichment + persist."""
    if not _INGEST_SECRET or secret != _INGEST_SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")
    if not payload.themes:
        raise HTTPException(status_code=400, detail="themes is empty")
    # Accept and finalize in the BACKGROUND — the LLM+enrichment can exceed Render's
    # ~100s gateway timeout (→ 502). Return immediately so the worker sees success.
    get_opportunity_service().start_finalize_from_scan(
        payload.themes, payload.crypto, deliver=payload.deliver)
    return {"status": "accepted", "themes_received": len(payload.themes),
            "crypto_received": len(payload.crypto), "will_deliver": payload.deliver}

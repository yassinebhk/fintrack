"""Broker sync endpoints."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models.broker_sync import BrokerSync
from app.services.brokers import KrakenService, PDFExtractionError, import_pdf
from app.services.brokers.kraken import KrakenAPIError, KrakenAuthError

router = APIRouter(prefix="/api/brokers", tags=["brokers"])

ALLOWED_PDF_BROKERS = {"MyInvestor", "TradeRepublic", "Generic"}
MAX_PDF_SIZE_MB = 10


@router.post("/kraken/sync")
async def kraken_sync(session: AsyncSession = Depends(get_session)) -> dict:
    settings = get_settings()
    if not settings.has_kraken:
        raise HTTPException(status_code=400, detail="Kraken API key/secret not configured")

    try:
        service = KrakenService()
    except KrakenAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = await service.sync_all(session)
    except KrakenAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("kraken sync failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"message": "Kraken sync completed", "result": result}


@router.get("/kraken/balance")
async def kraken_balance() -> dict:
    """Live balances from Kraken, without persisting. Useful for sanity checks."""
    settings = get_settings()
    if not settings.has_kraken:
        raise HTTPException(status_code=400, detail="Kraken not configured")
    try:
        service = KrakenService()
        balances = await service.get_balance()
    except KrakenAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KrakenAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"balances": balances}


@router.post("/pdf/import")
async def pdf_import(
    file: UploadFile = File(..., description="PDF de extracto (MyInvestor, TradeRepublic, etc.)"),
    broker: str = Form(default="Generic", description="MyInvestor | TradeRepublic | Generic"),
    replace_existing: bool = Form(default=True, description="Si true, borra las posiciones previas del broker antes de importar"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Import positions from a broker PDF statement via Gemini Flash-Lite."""
    settings = get_settings()
    if not settings.has_gemini and not settings.has_groq:
        raise HTTPException(status_code=400, detail="LLM not configured (need GEMINI_API_KEY or GROQ_API_KEY)")

    if broker not in ALLOWED_PDF_BROKERS:
        raise HTTPException(
            status_code=400,
            detail=f"broker must be one of {sorted(ALLOWED_PDF_BROKERS)}",
        )

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_PDF_SIZE_MB:
        raise HTTPException(status_code=413, detail=f"PDF demasiado grande ({size_mb:.1f} MB > {MAX_PDF_SIZE_MB} MB)")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="El archivo no parece un PDF válido")

    try:
        result = await import_pdf(
            pdf_bytes=content,
            broker=broker,
            session=session,
            replace_broker_positions=replace_existing,
        )
    except PDFExtractionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("pdf import failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"message": "PDF imported", **result}


@router.get("/syncs")
async def list_syncs(limit: int = 20, session: AsyncSession = Depends(get_session)) -> list[dict]:
    stmt = select(BrokerSync).order_by(BrokerSync.started_at.desc()).limit(limit)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    return [
        {
            "id": r.id,
            "broker": r.broker,
            "status": r.status,
            "positions_synced": r.positions_synced,
            "transactions_synced": r.transactions_synced,
            "error_message": r.error_message,
            "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in rows
    ]

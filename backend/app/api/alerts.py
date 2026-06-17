"""Alerts endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.alert import Alert
from app.services.alerts import AlertsEngine

router = APIRouter(prefix="/api/alerts", tags=["alerts"])
_engine = AlertsEngine()


class TrailingStopIn(BaseModel):
    ticker: str = Field(min_length=1)
    trailing_pct: float = Field(gt=0, le=90)
    label: str = ""
    peak: float | None = None
    currency: str = ""


@router.get("/trailing-stops")
async def list_trailing_stops() -> dict:
    from app.services import trailing_stops as ts
    return {"stops": await ts.get_all()}


@router.post("/trailing-stop")
async def set_trailing_stop(payload: TrailingStopIn) -> dict:
    from app.services import trailing_stops as ts
    stop = await ts.set_stop(payload.ticker, payload.trailing_pct,
                             payload.label, payload.peak, payload.currency)
    return {"message": "trailing stop armado", "stop": stop}


@router.get("")
async def list_alerts(
    status: str | None = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    stmt = select(Alert).order_by(Alert.triggered_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Alert.status == status)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "severity": r.severity,
            "title": r.title,
            "body": r.body,
            "payload": r.payload,
            "status": r.status,
            "delivered_telegram": r.delivered_telegram,
            "triggered_at": r.triggered_at.isoformat(),
            "acknowledged_at": r.acknowledged_at.isoformat() if r.acknowledged_at else None,
        }
        for r in rows
    ]


@router.post("/evaluate")
async def evaluate() -> dict:
    created = await _engine.evaluate()
    return {"created": created, "count": len(created)}


@router.post("/{alert_id}/ack")
async def ack(alert_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    row = await session.get(Alert, alert_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    row.status = "acknowledged"
    row.acknowledged_at = datetime.now(timezone.utc)
    return {"message": "ack", "id": alert_id}

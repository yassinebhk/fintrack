"""Investment-plan tracker endpoints."""

import os

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from app.services.plans import add_holding, evaluate_plans, register_plan

router = APIRouter(prefix="/api/plans", tags=["plans"])
_SECRET = os.getenv("CREATORS_INGEST_SECRET", "")


class Holding(BaseModel):
    ticker: str
    label: str = ""


class PlanIn(BaseModel):
    name: str
    horizon: str
    note: str = ""
    holdings: list[Holding]


class AddHoldingIn(BaseModel):
    name: str
    ticker: str
    label: str = ""


@router.get("")
async def get_plans() -> dict:
    try:
        return await evaluate_plans()
    except Exception as exc:
        logger.exception("plans eval failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("")
async def create_plan(payload: PlanIn, secret: str = "") -> dict:
    if not _SECRET or secret != _SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")
    return await register_plan(payload.name, payload.horizon,
                               [h.model_dump() for h in payload.holdings], payload.note)


@router.post("/holding")
async def append_holding(payload: AddHoldingIn, secret: str = "") -> dict:
    """Add a single asset to an existing plan without resetting the others' entries."""
    if not _SECRET or secret != _SECRET:
        raise HTTPException(status_code=401, detail="invalid secret")
    return await add_holding(payload.name, payload.ticker, payload.label)

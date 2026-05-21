"""CSV import endpoints — legacy multi-broker importer, now writing to DB."""

import io

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.repositories import PositionRepository

router = APIRouter(prefix="/api/import", tags=["import"])


def _process(df: pd.DataFrame, broker: str) -> pd.DataFrame:
    df.columns = df.columns.str.lower().str.strip()
    cols = set(df.columns)

    if {"ticker", "quantity", "avg_price", "type", "currency"}.issubset(cols):
        return df[["ticker", "quantity", "avg_price", "type", "currency"]].assign(broker=broker)

    if {"isin", "stück"}.issubset(cols) or {"isin", "anzahl"}.issubset(cols):
        result = []
        qty_col = "stück" if "stück" in cols else "anzahl"
        price_col = "kaufkurs" if "kaufkurs" in cols else "kurs"
        for _, row in df.iterrows():
            result.append({
                "ticker": row.get("isin", row.get("symbol", "")),
                "quantity": float(str(row.get(qty_col, 0)).replace(",", ".")),
                "avg_price": float(str(row.get(price_col, 0)).replace(",", ".").replace("€", "").strip()),
                "type": "stock",
                "currency": "EUR",
                "broker": broker,
            })
        return pd.DataFrame(result)

    if {"asset", "balance"}.issubset(cols):
        result = []
        for _, row in df.iterrows():
            asset = str(row.get("asset", "")).upper()
            if asset in {"EUR", "USD", "GBP"} or ".S" in asset:
                continue
            if asset.startswith(("X", "Z")):
                asset = asset[1:]
            balance = float(str(row.get("balance", 0)).replace(",", "."))
            if balance > 0:
                result.append({
                    "ticker": asset,
                    "quantity": balance,
                    "avg_price": 0,
                    "type": "crypto",
                    "currency": "USD",
                    "broker": broker,
                })
        return pd.DataFrame(result)

    # Generic
    ticker_col = next((c for c in ["ticker", "symbol", "isin", "name"] if c in cols), None)
    qty_col = next((c for c in ["quantity", "qty", "shares", "units", "amount", "anzahl"] if c in cols), None)
    price_col = next((c for c in ["avg_price", "price", "cost", "purchase_price", "kaufkurs"] if c in cols), None)
    type_col = next((c for c in ["type", "asset_type", "category"] if c in cols), None)
    currency_col = next((c for c in ["currency", "ccy"] if c in cols), None)

    if not (ticker_col and qty_col):
        return pd.DataFrame()

    result = []
    for _, row in df.iterrows():
        entry = {
            "ticker": str(row.get(ticker_col, "")).upper().strip(),
            "quantity": float(str(row.get(qty_col, 0)).replace(",", ".")),
            "avg_price": float(str(row.get(price_col, 0)).replace(",", ".").replace("€", "").replace("$", "").strip()) if price_col else 0,
            "type": str(row.get(type_col, "stock")).lower() if type_col else "stock",
            "currency": str(row.get(currency_col, "EUR")).upper() if currency_col else "EUR",
            "broker": broker,
        }
        if entry["ticker"] and entry["quantity"] > 0:
            result.append(entry)
    return pd.DataFrame(result)


def _detect_format(df: pd.DataFrame) -> dict:
    cols = set(df.columns.str.lower().str.strip())
    if {"ticker", "quantity", "avg_price"}.issubset(cols):
        return {"format": "fintrack", "confidence": "high"}
    if {"isin", "stück"}.issubset(cols) or {"isin", "anzahl"}.issubset(cols):
        return {"format": "trade_republic", "confidence": "high"}
    if {"asset", "balance"}.issubset(cols):
        return {"format": "kraken", "confidence": "high"}
    if "symbol" in cols or "ticker" in cols:
        return {"format": "generic", "confidence": "medium"}
    return {"format": "unknown", "confidence": "low"}


def _read_csv(content: bytes) -> pd.DataFrame:
    try:
        return pd.read_csv(io.StringIO(content.decode("utf-8")))
    except UnicodeDecodeError:
        return pd.read_csv(io.StringIO(content.decode("latin-1")))


@router.post("/preview")
async def preview_csv(file: UploadFile = File(...)) -> dict:
    content = await file.read()
    try:
        df = _read_csv(content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}") from exc
    return {
        "columns": list(df.columns),
        "rows": len(df),
        "preview": df.head(10).to_dict("records"),
        "detected_format": _detect_format(df),
    }


@router.post("/csv")
async def import_csv(
    file: UploadFile = File(...),
    broker: str = Form(default="Manual"),
    merge_existing: bool = Form(default=True),
    session: AsyncSession = Depends(get_session),
) -> dict:
    content = await file.read()
    try:
        df = _read_csv(content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}") from exc
    processed = _process(df, broker)
    if processed.empty:
        raise HTTPException(status_code=400, detail="No valid positions found in CSV")

    repo = PositionRepository(session)

    if not merge_existing:
        await repo.delete_by_broker(broker)

    rows = [
        {
            "ticker": r["ticker"],
            "quantity": float(r["quantity"]),
            "avg_price": float(r["avg_price"]),
            "type": str(r["type"]).lower(),
            "currency": str(r["currency"]).upper(),
            "broker": broker,
            "source": "csv_import",
        }
        for _, r in processed.iterrows()
    ]
    affected = await repo.bulk_upsert(rows)

    return {
        "message": f"Imported {len(rows)} positions",
        "positions_imported": len(rows),
        "affected": affected,
        "broker": broker,
    }

"""CSV import endpoints — multi-broker importer.

Two shapes are supported and auto-detected:
- a POSITIONS list (ticker/quantity/avg_price) → upserts current holdings, and
- a TRANSACTIONS ledger (dated buy/sell/dividend rows, e.g. a Revolut export) →
  writes each trade to the transactions table AND rebuilds the positions from
  them, so per-asset history and 'aportaciones' get populated.
"""

import hashlib
import io
import re

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models.user import User
from app.repositories import PositionRepository, TransactionRepository

router = APIRouter(prefix="/api/import", tags=["import"])


def _num(v) -> float:
    """Parse a number that may carry a currency symbol, thousands separators or
    parentheses for negatives: '$1,234.56', '1.234,56 €', '(12.30)' → float."""
    if v is None:
        return 0.0
    s = str(v).strip()
    if not s or s.lower() in {"nan", "none", "null", "-", "—", ""}:
        return 0.0
    neg = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[^\d,.\-]", "", s)  # drop currency symbols, spaces, letters
    if not s or s in {"-", ".", ","}:
        return 0.0
    if "," in s and "." in s:
        # the separator that appears LAST is the decimal one
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")   # 1.234,56 -> 1234.56
        else:
            s = s.replace(",", "")                       # 1,234.56 -> 1234.56
    elif "," in s:
        s = s.replace(",", ".") if len(s.split(",")[-1]) == 2 else s.replace(",", "")
    try:
        val = float(s)
    except ValueError:
        return 0.0
    return -val if neg else val


# Column-name variants for a transaction ledger (all lowercased).
_L_TICKER = ["ticker", "symbol", "instrument", "isin", "name", "asset"]
_L_QTY = ["quantity", "qty", "shares", "units", "no. of shares", "no of shares", "amount"]
_L_PRICE = ["price per share", "price / share", "price", "open rate", "rate", "unit price"]
_L_TOTAL = ["total amount", "total", "value", "consideration", "net amount", "gross amount"]
_L_DATE = ["date", "completed date", "started date", "time", "trade date", "date/time"]
_L_TYPE = ["type", "action", "side", "transaction type", "operation"]
_L_CCY = ["currency", "ccy", "currency (price)"]


def _pick(cols: set, opts: list) -> str | None:
    return next((c for c in opts if c in cols), None)


def _is_ledger(cols: set) -> bool:
    """A dated ledger with a per-row type is a transaction history, not a
    positions snapshot."""
    return bool(_pick(cols, _L_TYPE) and _pick(cols, _L_DATE) and _pick(cols, _L_TICKER)
                and (_pick(cols, _L_QTY) or _pick(cols, _L_TOTAL)))


def _map_type(raw: str) -> str | None:
    t = (raw or "").lower()
    if "buy" in t or "purchase" in t or t.strip() in {"b", "compra"}:
        return "buy"
    if "sell" in t or t.strip() in {"s", "venta"}:
        return "sell"
    if "div" in t:
        return "dividend"
    return None  # cash top-up / withdrawal / fee / interest / split → not a trade


def _parse_ledger(df: pd.DataFrame, broker: str) -> tuple[list[dict], int]:
    """Return (transactions, skipped_rows). Rows that aren't trades (top-ups,
    fees…) or can't be parsed are skipped, not fatal."""
    cols = set(df.columns)
    c_tk, c_qty, c_pr = _pick(cols, _L_TICKER), _pick(cols, _L_QTY), _pick(cols, _L_PRICE)
    c_tot, c_date, c_type, c_ccy = (_pick(cols, _L_TOTAL), _pick(cols, _L_DATE),
                                    _pick(cols, _L_TYPE), _pick(cols, _L_CCY))
    txs: list[dict] = []
    skipped = 0
    for _, row in df.iterrows():
        kind = _map_type(str(row.get(c_type, "")))
        if kind is None:
            skipped += 1
            continue
        tk = str(row.get(c_tk, "")).upper().strip()
        if not tk or tk in {"NAN", ""}:
            skipped += 1
            continue
        qty = _num(row.get(c_qty)) if c_qty else 0.0
        price = _num(row.get(c_pr)) if c_pr else 0.0
        total = _num(row.get(c_tot)) if c_tot else 0.0
        if price == 0 and qty and total:
            price = abs(total / qty)
        if kind in {"buy", "sell"} and (qty <= 0 or price <= 0):
            skipped += 1
            continue
        dt = pd.to_datetime(row.get(c_date), errors="coerce", utc=True)
        if pd.isna(dt):
            skipped += 1
            continue
        executed = dt.to_pydatetime()
        ccy = (str(row.get(c_ccy, "EUR")).upper().strip()[:8] or "EUR") if c_ccy else "EUR"
        raw_key = f"{broker}|{tk}|{kind}|{executed.isoformat()}|{qty}|{price}|{total}"
        ext = f"{broker[:8]}:{hashlib.md5(raw_key.encode()).hexdigest()[:24]}"
        txs.append({
            "type": kind, "ticker": tk, "quantity": abs(qty), "price": abs(price),
            "currency": ccy, "broker": broker, "executed_at": executed, "external_id": ext,
        })
    return txs, skipped


def _positions_from_txs(txs: list[dict], broker: str) -> list[dict]:
    """Net current holdings from a trade list: qty = Σbuys − Σsells, avg cost =
    Σ(buy_qty·price)/Σbuy_qty. Fully-sold tickers drop out."""
    agg: dict[str, dict] = {}
    for t in txs:
        a = agg.setdefault(t["ticker"], {"qty": 0.0, "buy_qty": 0.0, "buy_cost": 0.0, "ccy": t["currency"]})
        if t["type"] == "buy":
            a["qty"] += t["quantity"]
            a["buy_qty"] += t["quantity"]
            a["buy_cost"] += t["quantity"] * t["price"]
        elif t["type"] == "sell":
            a["qty"] -= t["quantity"]
    rows = []
    for tk, a in agg.items():
        if a["qty"] <= 1e-9:
            continue
        avg = a["buy_cost"] / a["buy_qty"] if a["buy_qty"] > 0 else 0.0
        rows.append({
            "ticker": tk, "quantity": round(a["qty"], 8), "avg_price": round(avg, 6),
            "type": "stock", "currency": a["ccy"], "broker": broker, "source": "csv_ledger",
        })
    return rows


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

    # Generic — also covers eToro ("Instrument"/"Units"/"Open Rate") and Revolut
    # ("Symbol"/"Quantity"/"Price per share") position/portfolio exports, which
    # don't match any of the specific formats above but use recognizable
    # column-name variants.
    ticker_col = next((c for c in ["ticker", "symbol", "isin", "instrument", "name"] if c in cols), None)
    qty_col = next((c for c in ["quantity", "qty", "shares", "units", "amount", "anzahl"] if c in cols), None)
    price_col = next(
        (c for c in [
            "avg_price", "price", "cost", "purchase_price", "kaufkurs",
            "open rate", "open price", "price per share", "average cost", "avg. open rate",
        ] if c in cols),
        None,
    )
    type_col = next((c for c in ["type", "asset_type", "category"] if c in cols), None)
    currency_col = next((c for c in ["currency", "ccy"] if c in cols), None)

    if not (ticker_col and qty_col):
        return pd.DataFrame()

    result = []
    for _, row in df.iterrows():
        entry = {
            "ticker": str(row.get(ticker_col, "")).upper().strip(),
            "quantity": float(str(row.get(qty_col, 0)).replace(",", ".")),
            "avg_price": float(
                str(row.get(price_col, 0)).replace(",", ".").replace("€", "").replace("$", "").replace("£", "").strip()
            ) if price_col else 0,
            "type": str(row.get(type_col, "stock")).lower() if type_col else "stock",
            "currency": str(row.get(currency_col, "EUR")).upper() if currency_col else "EUR",
            "broker": broker,
        }
        if entry["ticker"] and entry["quantity"] > 0:
            result.append(entry)
    return pd.DataFrame(result)


def _detect_format(df: pd.DataFrame) -> dict:
    cols = set(df.columns.str.lower().str.strip())
    if _is_ledger(cols):
        return {"format": "transactions_ledger", "confidence": "high"}
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
        text = content.decode("utf-8-sig")   # tolerate a BOM
    except UnicodeDecodeError:
        text = content.decode("latin-1")
    # Auto-detect the delimiter (Revolut/others may use ';' or tabs) and skip the
    # odd malformed line instead of failing the whole import.
    try:
        return pd.read_csv(io.StringIO(text), sep=None, engine="python", on_bad_lines="skip")
    except Exception:
        return pd.read_csv(io.StringIO(text), on_bad_lines="skip")


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
    current_user: User = Depends(get_current_user),
) -> dict:
    content = await file.read()
    try:
        df = _read_csv(content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No pude leer el CSV: {exc}") from exc
    df.columns = df.columns.str.lower().str.strip()
    cols = set(df.columns)

    # ── Transaction ledger (e.g. a Revolut 3-year export) ────────────────────
    if _is_ledger(cols):
        try:
            txs, skipped = _parse_ledger(df, broker)
        except Exception as exc:
            logger.exception("ledger parse failed")
            txs, skipped = [], 0
        # Only commit to the ledger path if we actually extracted trades; otherwise
        # fall through to the positions parser (the CSV may just have a date column).
        if txs:
            return await _import_ledger(txs, skipped, broker, merge_existing, session, current_user.id)

    return await _import_positions(df, broker, merge_existing, session, current_user.id)


async def _import_ledger(txs: list[dict], skipped: int, broker: str,
                         merge_existing: bool, session: AsyncSession, user_id: int) -> dict:
    tx_repo = TransactionRepository(session, user_id)
    existing = {t.external_id for t in await tx_repo.list_all() if t.external_id}
    added = 0
    for t in txs:
        if t["external_id"] in existing:
            continue
        await tx_repo.add(**t)
        existing.add(t["external_id"])
        added += 1
    pos_rows = _positions_from_txs(txs, broker)
    pos_repo = PositionRepository(session, user_id)
    if not merge_existing:
        await pos_repo.delete_by_broker(broker)
    if pos_rows:
        await pos_repo.bulk_upsert(pos_rows)
    from app.services.portfolio import invalidate_portfolio_cache
    invalidate_portfolio_cache(user_id)
    return {
        "message": f"Importadas {added} transacciones nuevas y reconstruidas {len(pos_rows)} posiciones "
                   f"({skipped} filas omitidas: ingresos/comisiones/no-operaciones).",
        "transactions_imported": added,
        "positions_updated": len(pos_rows),
        "skipped": skipped,
        "broker": broker,
    }


async def _import_positions(df: pd.DataFrame, broker: str, merge_existing: bool,
                            session: AsyncSession, user_id: int) -> dict:
    try:
        processed = _process(df, broker)
    except Exception as exc:
        logger.exception("positions parse failed")
        raise HTTPException(
            status_code=400,
            detail=f"No pude interpretar el CSV como lista de posiciones: {exc}. "
                   "Si es un histórico de movimientos, asegúrate de que incluye columnas de fecha y tipo de operación.",
        ) from exc
    if processed.empty:
        raise HTTPException(status_code=400, detail="No encontré posiciones válidas en el CSV.")

    repo = PositionRepository(session, user_id)
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
    from app.services.portfolio import invalidate_portfolio_cache
    invalidate_portfolio_cache(user_id)
    return {
        "message": f"Importadas {len(rows)} posiciones",
        "positions_imported": len(rows),
        "affected": affected,
        "broker": broker,
    }

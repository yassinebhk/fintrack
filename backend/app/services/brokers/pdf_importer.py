"""PDF statement importer (MyInvestor, Trade Republic, generic broker).

Strategy:
1. Extract raw text from the PDF with pdfplumber.
2. Send the text + a structured JSON schema to Gemini Flash-Lite for extraction.
3. Normalize the result to our Position model and upsert into the DB.

The LLM is responsible for handling format quirks (Spanish/English/German
language, decimal separator, currency symbols, line-wrap noise) so this
single pipeline works for any broker statement.
"""

from __future__ import annotations

import hashlib
import io
import re
from datetime import date, datetime, timezone
from typing import Any

import pdfplumber
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import LLMMessage, get_llm_client
from app.models.broker_sync import BrokerSync
from app.repositories import PositionRepository, TransactionRepository


# Schema we expect the LLM to fill
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "broker_detected": {
            "type": "string",
            "description": "Nombre del broker tal como aparece en el PDF",
        },
        "statement_date": {
            "type": "string",
            "description": "Fecha del extracto en formato YYYY-MM-DD si es legible, vacío si no",
        },
        "currency": {
            "type": "string",
            "description": "Divisa principal del extracto, p.ej. EUR",
        },
        "total_value": {
            "type": "number",
            "description": "Valor total de la cartera reportado en el PDF, 0 si no aparece",
        },
        "positions": {
            "type": "array",
            "description": "Líneas de posiciones extraídas",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "Ticker o ISIN del activo (preferir ISIN si está disponible)",
                    },
                    "name": {
                        "type": "string",
                        "description": "Nombre completo del activo",
                    },
                    "isin": {
                        "type": "string",
                        "description": "ISIN si aparece, vacío si no",
                    },
                    "quantity": {
                        "type": "number",
                        "description": "Número de participaciones / unidades",
                    },
                    "avg_price": {
                        "type": "number",
                        "description": "Precio medio de compra; 0 si no aparece en el extracto",
                    },
                    "current_price": {
                        "type": "number",
                        "description": "Valor liquidativo / cotización actual si aparece",
                    },
                    "currency": {
                        "type": "string",
                        "description": "Divisa de la posición (EUR si no especificada)",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["stock", "etf", "fund", "crypto", "bond"],
                        "description": "Tipo de activo inferido del nombre / ISIN",
                    },
                },
                "required": ["ticker", "quantity"],
            },
        },
    },
    "required": ["positions"],
}


SYSTEM_PROMPT = """Eres un extractor de datos de extractos bancarios y de brokers.

Recibes el TEXTO en bruto de un PDF (puede tener saltos de línea raros, números en formato español/europeo con coma decimal, encabezados repetidos, etc.).

Tu trabajo:
1. Identificar cada posición de inversión (acción, ETF, fondo, cripto, bono).
2. Extraer ticker/ISIN, nombre, cantidad, precio medio, divisa y tipo.
3. Ignorar filas que no son posiciones (efectivo, comisiones, totales agregados).
4. Devolver SIEMPRE un JSON válido siguiendo el schema dado.
5. Si un campo no aparece en el PDF, déjalo vacío (string) o 0 (número). NO inventes datos.
6. Cantidades y precios: convierte el formato europeo (1.234,56) al numérico estándar (1234.56).
7. ISINs siguen el patrón [A-Z]{2}[A-Z0-9]{9}[0-9] (12 caracteres).
"""


class PDFExtractionError(RuntimeError):
    pass


def extract_pdf_text(pdf_bytes: bytes, max_pages: int = 20) -> str:
    """Extract raw text from a PDF file (bytes)."""
    chunks: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            n = min(len(pdf.pages), max_pages)
            for i in range(n):
                page = pdf.pages[i]
                txt = page.extract_text() or ""
                if txt.strip():
                    chunks.append(f"--- Página {i + 1} ---\n{txt}")
    except Exception as exc:
        raise PDFExtractionError(f"No se pudo leer el PDF: {exc}") from exc
    if not chunks:
        raise PDFExtractionError("El PDF no contiene texto extraíble (¿es una imagen escaneada?)")
    return "\n\n".join(chunks)


async def extract_positions_from_text(
    text: str,
    broker_hint: str | None = None,
) -> dict[str, Any]:
    """Call the LLM to structure the PDF text into positions."""
    client = get_llm_client()
    user_prompt = (
        f"Broker indicado por el usuario: {broker_hint or 'desconocido'}\n\n"
        "Texto extraído del PDF:\n"
        "```\n"
        f"{text[:30000]}\n"  # cap to ~30k chars to stay within token budget
        "```\n\n"
        "Devuelve un JSON con `broker_detected`, `statement_date`, `currency`, "
        "`total_value` y `positions` siguiendo el schema."
    )

    from app.config import get_settings
    settings = get_settings()
    cheap_model = settings.gemini_model_cheap

    resp = await client.generate(
        [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_prompt),
        ],
        model=cheap_model,
        max_tokens=4096,
        temperature=0.1,
        json_schema=EXTRACTION_SCHEMA,
    )

    if resp.structured:
        return resp.structured
    # Fallback parser handled by the agent base, but call site shouldn't normally hit this
    import json
    try:
        return json.loads(resp.text)
    except json.JSONDecodeError as exc:
        raise PDFExtractionError(f"El LLM no devolvió JSON válido: {exc}") from exc


def _normalize_type(asset_type: str | None, ticker: str | None) -> str:
    t = (asset_type or "").lower().strip()
    if t in {"stock", "etf", "fund", "crypto", "bond"}:
        return t
    # Heuristics: ISIN starting with IE/LU/DE often → fund or etf
    if ticker and len(ticker) == 12:
        return "fund"
    return "stock"


# ── Deterministic parser for Revolut trading statements (no LLM → no quota) ──
# A Revolut statement is a fixed, machine-readable table, so we parse the trades
# ourselves instead of paying an LLM call (which was hitting Gemini's free-tier
# 429 quota). Validated against a real 3-year statement: the reconstructed net
# positions match the PDF's own "Portfolio breakdown" exactly.
_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
_DATE = (r"(?P<day>\d{1,2}) (?P<mon>[A-Z][a-z]{2}) (?P<yr>\d{4}) "
         r"(?P<h>\d{2}):(?P<mi>\d{2}):(?P<s>\d{2}) GMT")
# Buy/Sell across Market/Limit/Stop order types.
_TRADE_RE = re.compile(_DATE + r"\s+(?P<sym>[A-Z][A-Z0-9.]{0,9})\s+"
                       r"Trade - (?:Market|Limit|Stop)\s+(?P<qty>[\d.]+)\s+"
                       r"US\$(?P<price>[\d.,]+)\s+(?P<side>Buy|Sell)\b")
# A stock split adds shares at no cost.
_SPLIT_RE = re.compile(_DATE + r"\s+(?P<sym>[A-Z][A-Z0-9.]{0,9})\s+Stock split\s+(?P<qty>[\d.]+)")
# Portfolio-breakdown rows give clean names + ISINs for the held symbols.
_BREAKDOWN_RE = re.compile(
    r"^(?P<sym>[A-Z][A-Z0-9.]{0,9})\s+(?P<name>.+?)\s+(?P<isin>[A-Z]{2}[A-Z0-9]{9}\d)\s+[\d.]+\s+US\$",
    re.M)


def _num_usd(s) -> float:
    try:
        return float(str(s).replace(",", "").replace("US$", "").replace("$", "").strip())
    except ValueError:
        return 0.0


def _stmt_dt(m: re.Match) -> datetime:
    return datetime(int(m["yr"]), _MONTHS[m["mon"]], int(m["day"]),
                    int(m["h"]), int(m["mi"]), int(m["s"]), tzinfo=timezone.utc)


def looks_like_revolut(text: str) -> bool:
    return any(x in text for x in ("Trade - Market", "Trade - Limit", "Trade - Stop"))


def parse_statement_transactions(text: str, broker: str) -> tuple[list[dict], dict]:
    """Parse buy/sell/split rows deterministically. Returns (transactions, meta),
    meta = {symbol: {name, isin}} from the portfolio breakdown."""
    currency = "USD" if "US$" in text else "EUR"
    meta = {m["sym"]: {"name": m["name"].strip(), "isin": m["isin"]}
            for m in _BREAKDOWN_RE.finditer(text)}

    def _mk(sym, kind, dt, qty, price, note=None):
        raw = f"{broker}|{sym}|{kind}|{dt.isoformat()}|{qty}|{price}"
        row = {"type": kind if kind in ("buy", "sell") else "buy", "ticker": sym,
               "quantity": qty, "price": price, "currency": currency, "broker": broker,
               "executed_at": dt, "external_id": f"{broker[:8]}:{hashlib.md5(raw.encode()).hexdigest()[:24]}"}
        if note:
            row["notes"] = note
        return row

    txs: list[dict] = []
    for m in _TRADE_RE.finditer(text):
        qty, price = float(m["qty"]), _num_usd(m["price"])
        if qty <= 0 or price <= 0:
            continue
        txs.append(_mk(m["sym"], m["side"].lower(), _stmt_dt(m), qty, price))
    for m in _SPLIT_RE.finditer(text):
        qty = float(m["qty"])
        if qty > 0:
            txs.append(_mk(m["sym"], "split", _stmt_dt(m), qty, 0.0, note="Stock split"))
    return txs, meta


async def _import_transactions(txs: list[dict], meta: dict, broker: str,
                               session: AsyncSession, user_id: int,
                               replace_broker_positions: bool) -> tuple[int, list[dict]]:
    tx_repo = TransactionRepository(session, user_id)
    existing = {t.external_id for t in await tx_repo.list_all() if t.external_id}
    added = 0
    for t in txs:
        if t["external_id"] in existing:
            continue
        await tx_repo.add(**t)
        existing.add(t["external_id"])
        added += 1
    # Rebuild net positions: qty = Σbuys − Σsells, avg cost = Σ(buy_qty·price)/Σbuy_qty.
    agg: dict[str, dict] = {}
    for t in txs:
        a = agg.setdefault(t["ticker"], {"qty": 0.0, "bq": 0.0, "bc": 0.0, "ccy": t["currency"]})
        if t["type"] == "buy":
            a["qty"] += t["quantity"]
            a["bq"] += t["quantity"]
            a["bc"] += t["quantity"] * t["price"]
        elif t["type"] == "sell":
            a["qty"] -= t["quantity"]
    rows = []
    for tk, a in agg.items():
        if a["qty"] <= 1e-9:
            continue
        info = meta.get(tk, {})
        rows.append({
            "ticker": tk, "quantity": round(a["qty"], 8),
            "avg_price": round(a["bc"] / a["bq"] if a["bq"] > 0 else 0.0, 6),
            "type": "stock", "currency": a["ccy"], "broker": broker,
            "isin": info.get("isin"), "asset_name": info.get("name"), "source": "pdf_ledger",
        })
    pos_repo = PositionRepository(session, user_id)
    if replace_broker_positions:
        await pos_repo.delete_by_broker(broker)
    if rows:
        await pos_repo.bulk_upsert(rows)
    return added, rows


async def import_pdf(
    pdf_bytes: bytes,
    broker: str,
    session: AsyncSession,
    user_id: int,
    *,
    replace_broker_positions: bool = True,
) -> dict[str, Any]:
    """Full pipeline: PDF → text → (deterministic Revolut parse | LLM) → DB."""
    sync_row = BrokerSync(
        broker=broker,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    session.add(sync_row)
    await session.flush()

    try:
        text = extract_pdf_text(pdf_bytes, max_pages=60)
        logger.info("PDF text extracted: {} chars", len(text))

        # Deterministic path: a Revolut trading statement is parsed without the
        # LLM (no Gemini quota / 429), writing the full trade history AND the
        # rebuilt positions so per-asset history + 'aportaciones' get populated.
        if looks_like_revolut(text):
            txs, meta = parse_statement_transactions(text, broker)
            if txs:
                added, rows = await _import_transactions(
                    txs, meta, broker, session, user_id, replace_broker_positions)
                sync_row.status = "success"
                sync_row.positions_synced = len(rows)
                sync_row.finished_at = datetime.now(timezone.utc)
                logger.info("PDF (deterministic): {} txs, {} positions", added, len(rows))
                return {
                    "broker_detected": "Revolut",
                    "method": "deterministic",
                    "transactions_imported": added,
                    "positions_imported": len(rows),
                    "positions": rows,
                }

        extraction = await extract_positions_from_text(text, broker_hint=broker)
        positions = extraction.get("positions", []) or []
        logger.info("LLM extracted {} positions from PDF", len(positions))

        if not positions:
            sync_row.status = "error"
            sync_row.error_message = "El LLM no encontró posiciones en el PDF"
            sync_row.finished_at = datetime.now(timezone.utc)
            return {
                "broker_detected": extraction.get("broker_detected"),
                "positions_imported": 0,
                "positions": [],
                "warning": sync_row.error_message,
            }

        repo = PositionRepository(session, user_id)

        if replace_broker_positions:
            removed = await repo.delete_by_broker(broker)
            logger.info("removed {} prior positions for broker {}", removed, broker)

        rows = []
        for p in positions:
            ticker = (p.get("ticker") or p.get("isin") or "").strip()
            if not ticker or not p.get("quantity"):
                continue
            rows.append({
                "ticker": ticker.upper(),
                "quantity": float(p["quantity"]),
                "avg_price": float(p.get("avg_price") or p.get("current_price") or 0),
                "type": _normalize_type(p.get("type"), ticker),
                "currency": (p.get("currency") or extraction.get("currency") or "EUR").upper(),
                "broker": broker,
                "isin": (p.get("isin") or (ticker if len(ticker) == 12 else None)),
                "asset_name": p.get("name"),
                "source": "pdf_import",
            })

        affected = await repo.bulk_upsert(rows)

        sync_row.status = "success"
        sync_row.positions_synced = len(rows)
        sync_row.finished_at = datetime.now(timezone.utc)

        return {
            "broker_detected": extraction.get("broker_detected"),
            "statement_date": extraction.get("statement_date"),
            "total_value_reported": extraction.get("total_value"),
            "positions_imported": len(rows),
            "rows_affected": affected,
            "positions": rows,
        }
    except PDFExtractionError as exc:
        sync_row.status = "error"
        sync_row.error_message = str(exc)
        sync_row.finished_at = datetime.now(timezone.utc)
        raise
    except Exception as exc:
        sync_row.status = "error"
        sync_row.error_message = str(exc)
        sync_row.finished_at = datetime.now(timezone.utc)
        logger.exception("PDF import failed")
        raise

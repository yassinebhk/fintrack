"""Async Kraken read-only client + portfolio sync.

Signing: HMAC-SHA512 over POST URI + SHA256(nonce + post body), as per Kraken spec.
Reference: https://docs.kraken.com/rest/#section/Authentication
"""

import asyncio
import base64
import hashlib
import hmac
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import httpx
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.broker_sync import BrokerSync
from app.repositories import PositionRepository, TransactionRepository

KRAKEN_API_URL = "https://api.kraken.com"
KRAKEN_API_VERSION = "0"

# Kraken uses legacy X/Z prefixes for older assets — normalize to standard tickers.
KRAKEN_ASSET_MAP: dict[str, str] = {
    "XXBT": "BTC",
    "XBT": "BTC",
    "XETH": "ETH",
    "XLTC": "LTC",
    "XXMR": "XMR",
    "XXRP": "XRP",
    "XXLM": "XLM",
    "XXDG": "DOGE",
    "XDG": "DOGE",
    "XZEC": "ZEC",
    "ZEUR": "EUR",
    "ZUSD": "USD",
    "ZGBP": "GBP",
    "ZJPY": "JPY",
    "ZCAD": "CAD",
}

# Fiat tickers to skip when syncing crypto holdings
FIAT_TICKERS = {"EUR", "USD", "GBP", "JPY", "CAD", "CHF"}


def normalize_kraken_asset(asset: str) -> str:
    """Convert Kraken's internal code (e.g. XXBT) to the canonical ticker (BTC)."""
    upper = asset.upper()
    if upper in KRAKEN_ASSET_MAP:
        return KRAKEN_ASSET_MAP[upper]
    # Staking variants like ETH.S → ETH (treat staking as the same asset for now)
    if upper.endswith(".S"):
        base = upper[:-2]
        return KRAKEN_ASSET_MAP.get(base, base)
    # Strip legacy X/Z prefix if remaining looks like a 3-letter code
    if upper.startswith(("X", "Z")) and len(upper) == 4 and upper[1:].isalpha():
        return upper[1:]
    return upper


class KrakenAuthError(RuntimeError):
    pass


class KrakenAPIError(RuntimeError):
    pass


class KrakenService:
    def __init__(self, api_key: str | None = None, api_secret: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.kraken_api_key
        self.api_secret = api_secret or settings.kraken_api_secret
        if not self.api_key or not self.api_secret:
            raise KrakenAuthError("Kraken API key/secret not configured")
        try:
            self._decoded_secret = base64.b64decode(self.api_secret)
        except Exception as exc:
            raise KrakenAuthError(f"Invalid Kraken secret (not base64): {exc}") from exc

    # ------------------------------------------------------------------ low-level

    def _sign(self, uri_path: str, data: dict[str, Any]) -> str:
        post_body = urllib.parse.urlencode(data).encode()
        message = uri_path.encode() + hashlib.sha256(data["nonce"].encode() + post_body).digest()
        sig = hmac.new(self._decoded_secret, message, hashlib.sha512).digest()
        return base64.b64encode(sig).decode()

    async def _post_private(self, endpoint: str, data: dict[str, Any] | None = None) -> dict:
        data = dict(data or {})
        data["nonce"] = str(int(time.time() * 1000))
        uri_path = f"/{KRAKEN_API_VERSION}/private/{endpoint}"
        signature = self._sign(uri_path, data)
        headers = {
            "API-Key": self.api_key,
            "API-Sign": signature,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                KRAKEN_API_URL + uri_path,
                headers=headers,
                data=data,
            )
            resp.raise_for_status()
            payload = resp.json()
        if payload.get("error"):
            raise KrakenAPIError(f"{endpoint} -> {payload['error']}")
        return payload.get("result", {})

    # ------------------------------------------------------------------ public methods

    async def get_balance(self) -> dict[str, float]:
        result = await self._post_private("Balance")
        return {k: float(v) for k, v in result.items()}

    async def get_trades_history(self, start: float | None = None, ofs: int = 0) -> dict:
        data: dict[str, Any] = {"ofs": ofs}
        if start is not None:
            data["start"] = start
        return await self._post_private("TradesHistory", data)

    async def get_all_trades(self, since_unix: float | None = None) -> list[dict]:
        """Paginate through TradesHistory."""
        trades: list[dict] = []
        offset = 0
        while True:
            page = await self.get_trades_history(start=since_unix, ofs=offset)
            batch = list(page.get("trades", {}).items())
            if not batch:
                break
            for trade_id, t in batch:
                t["_trade_id"] = trade_id
                trades.append(t)
            count = int(page.get("count", 0))
            offset += len(batch)
            if offset >= count or not batch:
                break
            # Kraken caps at 50 per page; tiny pause to be polite
            await asyncio.sleep(0.5)
        return trades

    # ------------------------------------------------------------------ sync

    async def sync_balances(
        self,
        session: AsyncSession,
        broker_label: str = "Kraken",
    ) -> dict[str, Any]:
        """Refresh positions in DB from Kraken's live balance snapshot.

        avg_price stays untouched here (set/refined by sync_trades).
        """
        balances = await self.get_balance()
        pos_repo = PositionRepository(session)
        existing = await pos_repo.list_all()
        existing_by_ticker = {p.ticker: p for p in existing if p.broker == broker_label}

        canonical: dict[str, float] = {}
        for asset, bal in balances.items():
            if bal <= 0:
                continue
            ticker = normalize_kraken_asset(asset)
            if ticker in FIAT_TICKERS:
                continue
            canonical[ticker] = canonical.get(ticker, 0.0) + bal

        updated = 0
        for ticker, qty in canonical.items():
            prior = existing_by_ticker.get(ticker)
            prior_price = prior.avg_price if prior else 0.0
            await pos_repo.upsert(
                ticker=ticker,
                quantity=qty,
                avg_price=prior_price,
                type="crypto",
                currency="EUR",
                broker=broker_label,
                source="kraken_api",
            )
            updated += 1

        # Drop positions that no longer have a balance on Kraken
        removed = 0
        for ticker, pos in existing_by_ticker.items():
            if ticker not in canonical:
                await pos_repo.delete(ticker, broker_label)
                removed += 1

        return {"updated": updated, "removed": removed, "assets": list(canonical.keys())}

    async def sync_trades(
        self,
        session: AsyncSession,
        broker_label: str = "Kraken",
        since_unix: float | None = None,
    ) -> dict[str, Any]:
        """Pull trades history and (a) store transactions, (b) recompute weighted avg_price per ticker."""
        tx_repo = TransactionRepository(session)
        pos_repo = PositionRepository(session)

        trades = await self.get_all_trades(since_unix=since_unix)
        new_txs = 0
        seen_pairs: set[tuple[str, str]] = set()

        weighted: dict[str, dict[str, float]] = {}  # ticker -> {qty, cost}

        for t in trades:
            trade_id = t["_trade_id"]
            if await tx_repo.get_by_external_id(trade_id):
                continue
            pair = t.get("pair", "")  # e.g. XXBTZEUR
            kind = t.get("type", "buy")  # buy or sell
            price = float(t.get("price", 0))
            vol = float(t.get("vol", 0))
            fee = float(t.get("fee", 0))
            ts = float(t.get("time", 0))
            executed = datetime.fromtimestamp(ts, tz=timezone.utc)

            # Parse pair → base/quote (Kraken uses 6-8 char concatenated codes)
            base = quote = ""
            for cut in (4, 3):
                if len(pair) >= cut + 3:
                    candidate_base = pair[:cut]
                    candidate_quote = pair[cut:]
                    base = normalize_kraken_asset(candidate_base)
                    quote = normalize_kraken_asset(candidate_quote)
                    if quote in FIAT_TICKERS or quote in {"BTC", "ETH", "USDT", "USDC"}:
                        break
            if not base:
                logger.warning("kraken: could not parse pair {}", pair)
                continue

            await tx_repo.add(
                type=kind,
                ticker=base,
                quantity=vol,
                price=price,
                fee=fee,
                currency=quote if quote in FIAT_TICKERS else "EUR",
                broker=broker_label,
                executed_at=executed,
                external_id=trade_id,
                notes=f"kraken trade {pair}",
            )
            new_txs += 1
            seen_pairs.add((base, kind))

            agg = weighted.setdefault(base, {"qty": 0.0, "cost": 0.0})
            if kind == "buy":
                agg["qty"] += vol
                agg["cost"] += vol * price
            elif kind == "sell":
                # Reduce qty proportionally; keep cost basis on remaining
                remaining_qty = max(agg["qty"] - vol, 0.0)
                if agg["qty"] > 0:
                    remaining_cost = agg["cost"] * (remaining_qty / agg["qty"])
                else:
                    remaining_cost = 0.0
                agg["qty"] = remaining_qty
                agg["cost"] = remaining_cost

        # Update avg_price for tickers we have new trades on
        updated_prices = 0
        for ticker, agg in weighted.items():
            if agg["qty"] > 0:
                avg = agg["cost"] / agg["qty"]
                existing = await pos_repo.get(ticker, broker_label)
                if existing:
                    existing.avg_price = avg
                    updated_prices += 1

        return {"trades_imported": new_txs, "avg_prices_recomputed": updated_prices}

    async def sync_all(self, session: AsyncSession, broker_label: str = "Kraken") -> dict[str, Any]:
        """End-to-end sync: log a BrokerSync row, run balance + trades, return summary."""
        row = BrokerSync(broker=broker_label, status="running", started_at=datetime.now(timezone.utc))
        session.add(row)
        await session.flush()
        try:
            balance_result = await self.sync_balances(session, broker_label)
            trades_result = await self.sync_trades(session, broker_label)
            row.status = "success"
            row.positions_synced = balance_result["updated"]
            row.transactions_synced = trades_result["trades_imported"]
        except Exception as exc:
            row.status = "error"
            row.error_message = str(exc)
            logger.exception("kraken sync failed")
            raise
        finally:
            row.finished_at = datetime.now(timezone.utc)
        return {
            "balances": balance_result,
            "trades": trades_result,
        }

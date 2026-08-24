"""Portfolio service — DB-backed (positions/snapshots from SQLite).

Public API preserved for legacy callers:
- `load_positions()` returns a pandas DataFrame.
- `calculate_portfolio()` returns the same dict shape the frontend expects.
- `get_portfolio_history(days)` returns a list[{date, value}].
"""

import asyncio
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
from loguru import logger

from app.config import get_settings
from app.db import session_scope
from app.repositories import PositionRepository, SnapshotRepository
from app.services.market import CoinGeckoService, ExchangeRateService, YahooFinanceService


class PortfolioService:
    def __init__(self, base_currency: str | None = None) -> None:
        settings = get_settings()
        self.base_currency = (base_currency or settings.base_currency).upper()
        self.yahoo = YahooFinanceService()
        self.coingecko = CoinGeckoService()
        self.fx = ExchangeRateService(self.base_currency)
        self._prices_cache: dict[str, dict] = {}

    # ------------------------------------------------------------------ legacy compat

    async def load_positions(self) -> pd.DataFrame:
        async with session_scope() as session:
            repo = PositionRepository(session)
            rows = await repo.list_all()
        if not rows:
            return pd.DataFrame(columns=["ticker", "quantity", "avg_price", "type", "currency", "broker"])
        return pd.DataFrame([
            {
                "ticker": r.ticker,
                "quantity": float(r.quantity),
                "avg_price": float(r.avg_price),
                "type": r.type,
                "currency": r.currency,
                "broker": r.broker,
                "isin": r.isin,
                "asset_name": r.asset_name,
            }
            for r in rows
        ])

    # ------------------------------------------------------------------ pricing

    async def fetch_all_prices(self, positions: pd.DataFrame) -> dict[str, dict]:
        prices: dict[str, dict] = {}
        if positions.empty:
            return prices
        stocks_etfs = positions[positions["type"].isin(["stock", "etf", "fund"])]["ticker"].unique().tolist()
        cryptos = positions[positions["type"] == "crypto"]["ticker"].unique().tolist()

        if stocks_etfs:
            prices.update(await self.yahoo.get_prices(stocks_etfs))
        if cryptos:
            # Yahoo first, concurrently: no rate limit, and CoinGecko's free tier
            # 429s hard enough that get_prices()'s batch retry-sleep (up to 60s
            # across 3 attempts) was blocking the ENTIRE portfolio load behind it.
            # CoinGecko stays only as a fallback for whatever Yahoo has no market for.
            yahoo_results = await asyncio.gather(*(self._crypto_price_yahoo(t) for t in cryptos))
            yahoo_prices = {t: yp for t, yp in zip(cryptos, yahoo_results) if yp}
            prices.update(yahoo_prices)
            missing = [c for c in cryptos if c not in yahoo_prices]
            if missing:
                crypto_prices = await self.coingecko.get_prices(missing, vs_currency=self.base_currency.lower())
                prices.update(crypto_prices)
                for ticker, price in crypto_prices.items():
                    logger.info("crypto {} price via CoinGecko fallback: {}", ticker, price["price"])

        self._prices_cache = prices
        return prices

    async def _crypto_price_yahoo(self, ticker: str) -> dict | None:
        """Yahoo fallback for a crypto price in EUR. Tries -EUR, then -USD converted to EUR."""
        up = ticker.upper()
        yp = await self.yahoo.get_price(f"{up}-EUR")
        if yp and yp.get("price"):
            out = dict(yp)
            out["ticker"] = ticker
            out["currency"] = "EUR"
            return out
        # -USD with conversion
        yp = await self.yahoo.get_price(f"{up}-USD")
        if yp and yp.get("price"):
            rate = await self.fx.get_rate("USD", "EUR")
            out = dict(yp)
            out["ticker"] = ticker
            out["price"] = yp["price"] * rate
            out["previous_close"] = yp.get("previous_close", yp["price"]) * rate
            out["currency"] = "EUR"
            return out
        return None

    # ------------------------------------------------------------------ aggregation

    async def calculate_portfolio(self) -> dict:
        positions = await self.load_positions()
        if positions.empty:
            return self._empty_portfolio()

        prices = await self.fetch_all_prices(positions)
        logger.info("fetched prices for {} assets", len(prices))

        position_data: list[dict] = []
        total_value = total_cost = daily_change = 0.0

        for _, pos in positions.iterrows():
            ticker = pos["ticker"]
            quantity = float(pos["quantity"])
            avg_price = float(pos["avg_price"])
            asset_type = pos["type"]
            currency = pos["currency"]
            broker = pos["broker"]

            pdata = prices.get(ticker, {})
            current_price = pdata.get("price")
            if current_price is None:
                current_price = avg_price
                logger.warning("no live price for {}, using avg_price={}", ticker, avg_price)
            prev_close = pdata.get("previous_close", current_price)

            cost_basis = quantity * avg_price
            market_value = quantity * current_price
            gain_loss = market_value - cost_basis
            gain_loss_pct = (gain_loss / cost_basis * 100) if cost_basis > 0 else 0.0
            day_change = (current_price - prev_close) * quantity
            day_change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0.0

            fx_rate = await self.fx.get_rate(currency, self.base_currency)
            market_value_base = market_value * fx_rate
            cost_basis_base = cost_basis * fx_rate
            day_change_base = day_change * fx_rate

            position_data.append({
                "ticker": ticker,
                "name": pdata.get("name", pos.get("asset_name") or ticker),
                "quantity": quantity,
                "avg_price": avg_price,
                "current_price": current_price,
                "cost_basis": cost_basis,
                "market_value": market_value,
                "market_value_base": market_value_base,
                "gain_loss": gain_loss,
                "gain_loss_pct": round(gain_loss_pct, 2),
                "day_change": day_change,
                "day_change_pct": round(day_change_pct, 2),
                "type": asset_type,
                "currency": currency,
                "broker": broker,
                "weight": 0.0,
            })
            total_value += market_value_base
            total_cost += cost_basis_base
            daily_change += day_change_base

        for p in position_data:
            p["weight"] = round(p["market_value_base"] / total_value * 100, 2) if total_value > 0 else 0.0
        position_data.sort(key=lambda x: x["market_value_base"], reverse=True)

        by_type = await self._aggregate(position_data, "type", total_value, include_cost=True)
        by_broker = await self._aggregate(position_data, "broker", total_value, include_count=True)
        by_currency = await self._aggregate(position_data, "currency", total_value)

        total_gain_loss = total_value - total_cost
        total_gain_loss_pct = (total_gain_loss / total_cost * 100) if total_cost > 0 else 0.0
        daily_change_pct = (daily_change / (total_value - daily_change) * 100) if (total_value - daily_change) > 0 else 0.0

        await self._persist_snapshot(total_value, total_cost, total_gain_loss, daily_change)
        kpis = await self._kpis()

        return {
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_gain_loss": round(total_gain_loss, 2),
            "total_gain_loss_pct": round(total_gain_loss_pct, 2),
            "daily_change": round(daily_change, 2),
            "daily_change_pct": round(daily_change_pct, 2),
            "base_currency": self.base_currency,
            "positions": position_data,
            "by_type": by_type,
            "by_broker": by_broker,
            "by_currency": by_currency,
            "kpis": kpis,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    async def _aggregate(
        self,
        positions: list[dict],
        key: str,
        total_value: float,
        include_cost: bool = False,
        include_count: bool = False,
    ) -> dict:
        agg: dict[str, dict] = {}
        for p in positions:
            k = p[key]
            if k not in agg:
                agg[k] = {"value": 0.0, "weight": 0.0}
                if include_cost:
                    agg[k]["cost"] = 0.0
                if include_count:
                    agg[k]["positions"] = 0
            agg[k]["value"] += p["market_value_base"]
            if include_count:
                agg[k]["positions"] += 1
            if include_cost:
                fx_rate = await self.fx.get_rate(p["currency"], self.base_currency)
                agg[k]["cost"] += p["cost_basis"] * fx_rate
        for k in agg:
            agg[k]["weight"] = round(agg[k]["value"] / total_value * 100, 2) if total_value > 0 else 0.0
            if include_cost:
                cost = agg[k]["cost"]
                gl = agg[k]["value"] - cost
                agg[k]["gain_loss"] = gl
                agg[k]["gain_loss_pct"] = round((gl / cost * 100) if cost > 0 else 0.0, 2)
        return agg

    async def _persist_snapshot(
        self,
        total_value: float,
        total_cost: float,
        total_gain_loss: float,
        daily_change: float,
    ) -> None:
        async with session_scope() as session:
            await SnapshotRepository(session).upsert_today(
                snapshot_date=datetime.now().date(),
                total_value=total_value,
                total_cost=total_cost,
                total_gain_loss=total_gain_loss,
                daily_change=daily_change,
            )

    async def _kpis(self) -> dict:
        async with session_scope() as session:
            snaps = await SnapshotRepository(session).list_all()

        kpis = {
            "cagr": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_date": None,
            "best_day": 0.0,
            "worst_day": 0.0,
            "volatility": 0.0,
            "sharpe_ratio": 0.0,
            "days_tracked": len(snaps),
            "positive_days_pct": 0.0,
            "ytd_return": 0.0,
        }
        if len(snaps) < 2:
            return kpis

        dates = [s.snapshot_date for s in snaps]
        vals = np.array([s.total_value for s in snaps], dtype=float)
        if (vals <= 0).any():
            vals = np.where(vals <= 0, np.nan, vals)
            mask = ~np.isnan(vals)
            vals = vals[mask]
            dates = [d for d, m in zip(dates, mask) if m]
            if len(vals) < 2:
                return kpis

        raw_returns = np.diff(vals) / vals[:-1]
        # A deposit/withdrawal shows up as a same-day value jump that isn't a
        # market move — an early top-up can look like a +80% "return" and
        # wreck every stat below. Treat anything beyond this threshold as a
        # cash flow, not performance, and exclude it from the return series.
        FLOW_THRESHOLD = 0.20
        is_flow = np.abs(raw_returns) > FLOW_THRESHOLD
        returns = raw_returns[~is_flow]

        if len(returns) > 0:
            kpis["best_day"] = round(float(np.max(returns)) * 100, 2)
            kpis["worst_day"] = round(float(np.min(returns)) * 100, 2)
            kpis["volatility"] = round(float(np.std(returns) * np.sqrt(252)) * 100, 2)
            risk_free = 0.03 / 252
            excess = returns - risk_free
            if np.std(excess) > 0:
                kpis["sharpe_ratio"] = round(float(np.mean(excess) / np.std(excess) * np.sqrt(252)), 2)
            kpis["positive_days_pct"] = round(float(np.mean(returns > 0)) * 100, 1)

        # CAGR / YTD: compound the flow-excluded daily returns instead of the
        # raw start/end value ratio, so new contributions aren't counted as gains.
        clean_returns = np.where(is_flow, 0.0, raw_returns)
        cum = np.concatenate([[1.0], np.cumprod(1 + clean_returns)])

        year_start = date(dates[-1].year, 1, 1)
        ytd_idx = [i for i, d in enumerate(dates) if d >= year_start]
        if len(ytd_idx) >= 2:
            i0, i1 = ytd_idx[0], ytd_idx[-1]
            kpis["ytd_return"] = round((float(cum[i1]) / float(cum[i0]) - 1) * 100, 2)

        years = (dates[-1] - dates[0]).days / 365.25
        if years > 0 and cum[0] > 0:
            kpis["cagr"] = round((pow(float(cum[-1]) / float(cum[0]), 1 / years) - 1) * 100, 2)

        peak = vals[0]
        max_dd = 0.0
        max_dd_date = dates[0]
        for d, v in zip(dates, vals):
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
                max_dd_date = d
        kpis["max_drawdown"] = round(float(max_dd) * 100, 2)
        kpis["max_drawdown_date"] = max_dd_date.strftime("%Y-%m-%d") if max_dd > 0 else None
        return kpis

    async def get_portfolio_history(self, days: int = 365) -> list[dict]:
        async with session_scope() as session:
            rows = await SnapshotRepository(session).list_last_days(days=days)
        return [{"date": r.snapshot_date.strftime("%Y-%m-%d"), "value": float(r.total_value)} for r in rows]

    async def get_asset_history(self, ticker: str, asset_type: str, days: int = 365) -> list[dict] | None:
        if asset_type == "crypto":
            # Yahoo first (no rate limit) — see fetch_all_prices for why CoinGecko-first
            # is unsafe as the primary path (its 429 retry-sleep can block for a minute).
            up = ticker.upper()
            yperiod = "max" if days > 1825 else "5y" if days > 730 else "2y" if days > 365 else "1y" if days > 90 else "6mo" if days > 30 else "1mo"
            for yt in (f"{up}-EUR", f"{up}-USD"):
                hist = await self.yahoo.get_history(yt, period=yperiod)
                if hist:
                    return hist
            return await self.coingecko.get_history(ticker, days=days, vs_currency=self.base_currency.lower())
        period = "1y" if days >= 365 else f"{days}d"
        return await self.yahoo.get_history(ticker, period=period)

    async def risk_analysis(self) -> dict:
        """Real (not hardcoded) risk distribution by realized annualized volatility,
        and a pairwise return-correlation matrix, over both held positions."""
        cache = getattr(self, "_risk_cache", None)
        if cache and cache["expiry"] > datetime.now(timezone.utc):
            return cache["data"]

        portfolio = await self.calculate_portfolio()
        positions = portfolio.get("positions", [])
        empty = {"risk_distribution": {"low": 0.0, "medium": 0.0, "high": 0.0},
                 "risk_by_ticker": {}, "correlation": {"tickers": [], "matrix": []}}
        if not positions:
            return empty

        async def _hist(pos: dict) -> tuple[str, list[dict]]:
            ticker = pos["ticker"]
            try:
                # Yahoo directly for crypto too (not CoinGecko): firing 5+ concurrent
                # CoinGecko calls trips its free-tier rate limit instantly, and its
                # own retry-after-60s logic then makes this endpoint take minutes.
                if pos.get("type") == "crypto":
                    hist = await self.yahoo.get_history(f"{ticker.upper()}-EUR", period="3mo")
                else:
                    hist = await self.yahoo.get_history(ticker, period="3mo")
                return ticker, hist or []
            except Exception as exc:
                logger.debug("risk_analysis history fetch failed for {}: {}", ticker, exc)
                return ticker, []

        results = await asyncio.gather(*[_hist(p) for p in positions])
        closes: dict[str, dict[str, float]] = {}
        for ticker, hist in results:
            series = {h["date"]: (h.get("close") or h.get("price")) for h in hist if h.get("close") or h.get("price")}
            if len(series) >= 15:
                closes[ticker] = series

        weight_map = {p["ticker"]: p.get("weight") or 0.0 for p in positions}
        risk_weights = {"low": 0.0, "medium": 0.0, "high": 0.0}
        risk_by_ticker: dict[str, float] = {}
        for ticker, series in closes.items():
            vals = np.array([v for _, v in sorted(series.items())], dtype=float)
            if len(vals) < 10:
                continue
            rets = np.diff(vals) / vals[:-1]
            ann_vol = float(np.std(rets) * np.sqrt(252) * 100)
            risk_by_ticker[ticker] = round(ann_vol, 1)
            bucket = "low" if ann_vol < 20 else "medium" if ann_vol < 50 else "high"
            risk_weights[bucket] += weight_map.get(ticker, 0.0)

        total_w = sum(risk_weights.values())
        risk_distribution = (
            {k: round(v / total_w * 100, 1) for k, v in risk_weights.items()} if total_w > 0
            else {"low": 0.0, "medium": 0.0, "high": 0.0}
        )

        tickers = list(closes.keys())
        matrix: list[list[float]] = []
        if len(tickers) >= 2:
            common = set(closes[tickers[0]])
            for t in tickers[1:]:
                common &= set(closes[t])
            common_dates = sorted(common)
            if len(common_dates) >= 10:
                series_matrix = np.array([[closes[t][d] for d in common_dates] for t in tickers])
                rets_matrix = np.diff(series_matrix, axis=1) / series_matrix[:, :-1]
                with np.errstate(invalid="ignore"):
                    corr = np.corrcoef(rets_matrix)
                matrix = [[round(float(x), 2) if np.isfinite(x) else 0.0 for x in row] for row in corr]

        data = {
            "risk_distribution": risk_distribution,
            "risk_by_ticker": risk_by_ticker,
            "correlation": {"tickers": tickers, "matrix": matrix},
        }
        self._risk_cache = {"data": data, "expiry": datetime.now(timezone.utc) + timedelta(hours=1)}
        return data

    def _empty_portfolio(self) -> dict:
        return {
            "total_value": 0,
            "total_cost": 0,
            "total_gain_loss": 0,
            "total_gain_loss_pct": 0,
            "daily_change": 0,
            "daily_change_pct": 0,
            "base_currency": self.base_currency,
            "positions": [],
            "by_type": {},
            "by_broker": {},
            "by_currency": {},
            "kpis": {},
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

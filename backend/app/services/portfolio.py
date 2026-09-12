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
from app.repositories import PositionRepository, SnapshotRepository, TransactionRepository
from app.services.market import CoinGeckoService, ExchangeRateService, YahooFinanceService


class PortfolioService:
    def __init__(self, user_id: int, base_currency: str | None = None) -> None:
        settings = get_settings()
        self.user_id = user_id
        self.base_currency = (base_currency or settings.base_currency).upper()
        self.yahoo = YahooFinanceService()
        self.coingecko = CoinGeckoService()
        self.fx = ExchangeRateService(self.base_currency)
        self._prices_cache: dict[str, dict] = {}

    # ------------------------------------------------------------------ legacy compat

    async def load_positions(self) -> pd.DataFrame:
        async with session_scope() as session:
            repo = PositionRepository(session, self.user_id)
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
            await SnapshotRepository(session, self.user_id).upsert_today(
                snapshot_date=datetime.now().date(),
                total_value=total_value,
                total_cost=total_cost,
                total_gain_loss=total_gain_loss,
                daily_change=daily_change,
            )

    async def _kpis(self) -> dict:
        async with session_scope() as session:
            snaps = await SnapshotRepository(session, self.user_id).list_all()

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

    async def portfolio_risk_metrics(self, benchmark: str = "EUNL.DE") -> dict:
        """Book-LEVEL risk metrics — the same family we compute per asset, but for the
        WHOLE portfolio: annualized vol, Sortino, historical VaR/CVaR 95-99, max
        drawdown, Calmar, Sharpe, skew/kurtosis, and beta/alpha vs a benchmark
        (MSCI World). Computed from daily NAV snapshots, excluding contribution days
        (a deposit is a cash flow, not a return). Returns status 'insufficient' when
        there isn't enough history yet."""
        async with session_scope() as session:
            snaps = await SnapshotRepository(session, self.user_id).list_all()
        out = {"status": "insufficient", "days_tracked": len(snaps)}
        if len(snaps) < 20:
            return out
        dates = [s.snapshot_date for s in snaps]
        vals = np.array([s.total_value for s in snaps], dtype=float)
        mask = vals > 0
        vals, dates = vals[mask], [d for d, m in zip(dates, mask) if m]
        if len(vals) < 20:
            return out

        raw = np.diff(vals) / vals[:-1]
        FLOW = 0.20  # a >20% same-day jump is a deposit/withdrawal, not performance
        keep = np.abs(raw) <= FLOW
        r = raw[keep]
        if len(r) < 15:
            return out

        ann = np.sqrt(252)
        rf_daily = 0.03 / 252
        excess = r - rf_daily
        vol = float(np.std(r) * ann)
        downside = r[r < 0]
        dstd = float(np.std(downside)) if len(downside) else 0.0
        sortino = float(np.mean(excess) / dstd * ann) if dstd > 0 else 0.0
        sharpe = float(np.mean(excess) / np.std(excess) * ann) if np.std(excess) > 0 else 0.0
        var95, var99 = float(np.percentile(r, 5)), float(np.percentile(r, 1))
        cvar95 = float(r[r <= var95].mean()) if (r <= var95).any() else var95
        cvar99 = float(r[r <= var99].mean()) if (r <= var99).any() else var99

        peak, max_dd = vals[0], 0.0
        for v in vals:
            peak = max(peak, v)
            max_dd = max(max_dd, (peak - v) / peak)
        clean = np.where(keep, raw, 0.0)
        cum = np.cumprod(1 + clean)
        years = (dates[-1] - dates[0]).days / 365.25
        cagr = (float(cum[-1]) ** (1 / years) - 1) if years > 0 and cum[-1] > 0 else 0.0
        calmar = float(cagr / max_dd) if max_dd > 0 else 0.0

        from scipy.stats import kurtosis as _kurt, skew as _skew
        skewv = float(_skew(r)) if len(r) > 3 else 0.0
        kurtv = float(_kurt(r)) if len(r) > 3 else 0.0

        # Beta / alpha vs benchmark, aligned on the same snapshot dates.
        beta = alpha = None
        try:
            bh = await self.yahoo.get_history(benchmark, period="1y") or []
            bmap = {h["date"]: h.get("close") for h in bh if h.get("close")}
            closes_on = [bmap.get(d.isoformat()) for d in dates]
            braw = [((closes_on[i] - closes_on[i - 1]) / closes_on[i - 1])
                    if (closes_on[i] and closes_on[i - 1]) else None
                    for i in range(1, len(closes_on))]
            rp, rb = [], []
            for i, k in enumerate(keep):
                if k and braw[i] is not None:
                    rp.append(raw[i]); rb.append(braw[i])
            if len(rp) >= 15:
                rp, rb = np.array(rp), np.array(rb)
                varb = float(np.var(rb))
                if varb > 0:
                    beta = float(np.cov(rp, rb)[0, 1] / varb)
                    alpha = float((np.mean(rp) - beta * np.mean(rb)) * 252 * 100)
        except Exception as exc:
            logger.debug("portfolio beta/alpha failed: {}", exc)

        return {
            "status": "ready",
            "days_tracked": len(snaps),
            "n_returns": len(r),
            "volatility_pct": round(vol * 100, 1),
            "sortino": round(sortino, 2),
            "sharpe": round(sharpe, 2),
            "var_95_pct": round(var95 * 100, 2),
            "var_99_pct": round(var99 * 100, 2),
            "cvar_95_pct": round(cvar95 * 100, 2),
            "cvar_99_pct": round(cvar99 * 100, 2),
            "max_drawdown_pct": round(-max_dd * 100, 1),
            "calmar": round(calmar, 2),
            "skew": round(skewv, 2),
            "excess_kurtosis": round(kurtv, 2),
            "beta": round(beta, 2) if beta is not None else None,
            "alpha_annual_pct": round(alpha, 1) if alpha is not None else None,
            "benchmark": benchmark,
        }

    async def get_nav_returns(self, days: int = 180) -> dict:
        """Daily portfolio returns keyed by ISO date, excluding contribution days
        (>20% same-day jump = a cash flow, not performance). Used for correlation-
        aware position sizing of new ideas vs the current book."""
        hist = await self.get_portfolio_history(days)
        out: dict[str, float] = {}
        for i in range(1, len(hist)):
            v0, v1 = hist[i - 1].get("value"), hist[i].get("value")
            if v0 and v1 and v0 > 0:
                r = (v1 - v0) / v0
                if abs(r) <= 0.20:
                    out[hist[i]["date"]] = r
        return out

    async def get_holdings_catalysts(self) -> list[dict]:
        """Upcoming earnings / ex-dividend dates for the (non-crypto) assets you hold,
        soonest first — so a catalyst on something you own never blindsides you."""
        portfolio = await self.calculate_portfolio()
        positions = [p for p in portfolio.get("positions", [])
                     if p.get("type") != "crypto" and p.get("ticker")]

        async def one(p):
            try:
                return p, await self.yahoo.get_catalysts(p["ticker"])
            except Exception:
                return p, None

        results = await asyncio.gather(*[one(p) for p in positions]) if positions else []
        today = date.today().isoformat()
        events = []
        for p, c in results:
            if not c:
                continue
            nm = p.get("name") or p["ticker"]
            for kind, label in (("earnings", "Resultados"), ("ex_dividend", "Ex-dividendo")):
                d = c.get(kind)
                if d and d >= today:
                    events.append({"ticker": p["ticker"], "name": nm, "event": label, "date": d})
        events.sort(key=lambda e: e["date"])
        return events[:20]

    async def performance_attribution(self) -> dict:
        """What is actually driving your P/L: each holding's contribution to the total
        gain/loss (€ and % of the net total), plus a breakdown by asset type. Money-
        terms attribution from current unrealized P/L — the most honest view without
        per-lot return series. NOTE: a single winner can exceed 100% of the NET total
        when other positions are losing (the % is share of the net, not of a pie)."""
        portfolio = await self.calculate_portfolio()
        positions = portfolio.get("positions", []) or []
        total_gl = sum((p.get("gain_loss") or 0.0) for p in positions)

        by_position = sorted(
            [{
                "ticker": p.get("ticker"),
                "name": p.get("name") or p.get("ticker"),
                "type": p.get("type") or "otro",
                "gain_loss_eur": round(p.get("gain_loss") or 0.0, 2),
                "gain_loss_pct": round(p.get("gain_loss_pct") or 0.0, 2),
                "weight_pct": round(p.get("weight") or 0.0, 2),
                "contribution_pct": round((p.get("gain_loss") or 0.0) / total_gl * 100, 1) if total_gl else 0.0,
            } for p in positions],
            key=lambda c: c["gain_loss_eur"], reverse=True,
        )

        by_type_map: dict[str, float] = {}
        for p in positions:
            t = p.get("type") or "otro"
            by_type_map[t] = by_type_map.get(t, 0.0) + (p.get("gain_loss") or 0.0)
        by_type = sorted(
            [{"type": t, "gain_loss_eur": round(v, 2),
              "contribution_pct": round(v / total_gl * 100, 1) if total_gl else 0.0}
             for t, v in by_type_map.items()],
            key=lambda x: x["gain_loss_eur"], reverse=True,
        )
        return {"total_gain_loss_eur": round(total_gl, 2), "by_position": by_position, "by_type": by_type}

    async def stress_test(self) -> dict:
        """Illustrative what-if scenarios applied to the CURRENT holdings — the
        'how much could I lose' view a risk-aware trader wants. Flat class shocks are
        illustrative (labelled as such); the −2σ scenario is grounded in each asset's
        own realized volatility. Not predictions."""
        portfolio = await self.calculate_portfolio()
        positions = portfolio.get("positions", []) or []
        total = portfolio.get("total_value") or 0.0
        if not positions or total <= 0:
            return {"total_value": total, "scenarios": []}

        try:
            vol_by = (await self.risk_analysis()).get("risk_by_ticker") or {}
        except Exception:
            vol_by = {}

        def mv(p) -> float:
            return p.get("market_value_base") or 0.0

        is_crypto = lambda p: p.get("type") == "crypto"  # noqa: E731
        is_equity = lambda p: p.get("type") in ("stock", "etf", "fund")  # noqa: E731
        scenarios = []

        def add(name, desc, impact, note=None):
            s = {"name": name, "desc": desc, "impact_eur": round(impact, 2),
                 "impact_pct": round(impact / total * 100, 2), "new_value": round(total + impact, 2)}
            if note:
                s["note"] = note
            scenarios.append(s)

        def flat(name, desc, eq, cr):
            imp = sum(mv(p) * (cr if is_crypto(p) else eq if is_equity(p) else 0.0) for p in positions)
            add(name, desc, imp)

        flat("Corrección de mercado", "Bolsa −15%, cripto −25%", -0.15, -0.25)
        flat("Crash severo (tipo 2008)", "Bolsa −35%, cripto −55%", -0.35, -0.55)
        flat("Crash cripto", "Cripto −50%, bolsa −5%", -0.05, -0.50)

        top = max(positions, key=mv)
        add("Tu mayor posición cae 40%", f"{top.get('name') or top.get('ticker')} −40%", -0.40 * mv(top))

        if vol_by:
            imp = covered = 0.0
            for p in positions:
                v = vol_by.get(p.get("ticker"))
                if v is None:
                    continue
                daily = (v / 100.0) / (252 ** 0.5)
                imp += mv(p) * (-2 * daily)
                covered += mv(p)
            if covered > 0:
                add("Día malo histórico (−2σ)",
                    "Cada activo cae 2 desviaciones típicas diarias (según su propia volatilidad)",
                    imp, note=f"cubre {round(covered / total * 100)}% de la cartera con histórico")

        return {"total_value": round(total, 2), "scenarios": scenarios}

    async def money_weighted_return(self) -> dict:
        """Money-weighted return (annualized XIRR) — your TRUE personal return, which
        accounts for the timing and size of your contributions (unlike time-weighted
        CAGR). Cashflows are derived from net cost-basis changes in the daily NAV
        snapshots (money in when your invested cost rises), plus the current value as
        the final flow. Solved by bisection."""
        async with session_scope() as session:
            snaps = await SnapshotRepository(session, self.user_id).list_all()
        if len(snaps) < 2:
            return {"status": "insufficient", "days_tracked": len(snaps)}

        flows: list[tuple] = []  # (date, amount) — investor view: money IN is negative
        prev_cost = None
        for sN in snaps:
            c = float(sN.total_cost or 0.0)
            if prev_cost is None:
                if c > 0:
                    flows.append((sN.snapshot_date, -c))
            else:
                delta = c - prev_cost
                if abs(delta) > 1e-6:
                    flows.append((sN.snapshot_date, -delta))
            prev_cost = c
        last = snaps[-1]
        flows.append((last.snapshot_date, float(last.total_value or 0.0)))
        if len(flows) < 2 or not any(cf < 0 for _, cf in flows) or not any(cf > 0 for _, cf in flows):
            return {"status": "insufficient", "days_tracked": len(snaps)}

        t0 = flows[0][0]

        def npv(rate: float) -> float:
            return sum(cf / ((1 + rate) ** ((d - t0).days / 365.0)) for d, cf in flows)

        lo, hi = -0.9999, 10.0
        flo, fhi = npv(lo), npv(hi)
        if flo * fhi > 0:
            return {"status": "no_converge", "days_tracked": len(snaps)}
        for _ in range(200):
            mid = (lo + hi) / 2.0
            fm = npv(mid)
            if abs(fm) < 1e-6:
                lo = hi = mid
                break
            if flo * fm < 0:
                hi = mid
            else:
                lo, flo = mid, fm
        xirr = (lo + hi) / 2.0
        return {
            "status": "ready", "days_tracked": len(snaps),
            "xirr_pct": round(xirr * 100, 2),
            "net_invested_eur": round(sum(-cf for _, cf in flows[:-1] if cf < 0), 2),
            "current_value_eur": round(float(last.total_value or 0.0), 2),
        }

    @staticmethod
    def _irpf_savings(base: float) -> float:
        """Spanish savings-base IRPF on a positive net gain (2024/25 brackets):
        19% ≤6k, 21% 6k–50k, 23% 50k–200k, 27% 200k–300k, 28% >300k."""
        widths = [(6000.0, 0.19), (44000.0, 0.21), (150000.0, 0.23), (100000.0, 0.27), (float("inf"), 0.28)]
        tax, rem = 0.0, max(0.0, base)
        for width, rate in widths:
            if rem <= 0:
                break
            chunk = min(rem, width)
            tax += chunk * rate
            rem -= chunk
        return tax

    async def tax_report(self) -> dict:
        """FIFO realized gains/losses from the transaction history, this-year totals,
        an estimated Spanish IRPF (savings base) on the net gain, and tax-loss-
        harvesting candidates (current positions in the red). Reconstructed from
        transactions — no separate lot store. Assumes EUR (does not adjust FX)."""
        from collections import defaultdict, deque

        async with session_scope() as session:
            txs = await TransactionRepository(session, self.user_id).list_all()
        txs = sorted(txs, key=lambda t: t.executed_at)

        lots: dict[str, deque] = defaultdict(deque)   # ticker -> deque([qty, unit_cost])
        realized: list[dict] = []
        dividends_by_year: dict[int, float] = defaultdict(float)

        for t in txs:
            tk = (t.ticker or "").upper()
            typ = (t.type or "").lower()
            qty = float(t.quantity or 0.0)
            price = float(t.price or 0.0)
            fee = float(t.fee or 0.0)
            if typ in ("buy", "compra", "aportar") and qty > 0:
                unit = price + (fee / qty if qty else 0.0)
                lots[tk].append([qty, unit])
            elif typ in ("sell", "venta", "retirar") and qty > 0:
                proceeds = qty * price - fee
                cost, remaining = 0.0, qty
                while remaining > 1e-9 and lots[tk]:
                    lot = lots[tk][0]
                    take = min(remaining, lot[0])
                    cost += take * lot[1]
                    lot[0] -= take
                    remaining -= take
                    if lot[0] <= 1e-9:
                        lots[tk].popleft()
                realized.append({
                    "date": t.executed_at.date().isoformat(), "year": t.executed_at.year,
                    "ticker": tk, "qty": round(qty, 6),
                    "proceeds": round(proceeds, 2), "cost": round(cost, 2),
                    "gain": round(proceeds - cost, 2),
                })
            elif typ == "dividend":
                dividends_by_year[t.executed_at.year] += (qty * price) if price else qty

        year = date.today().year
        realized_ytd = sum(r["gain"] for r in realized if r["year"] == year)
        realized_total = sum(r["gain"] for r in realized)
        div_ytd = dividends_by_year.get(year, 0.0)
        taxable_ytd = realized_ytd + div_ytd

        by_ticker: dict[str, float] = defaultdict(float)
        for r in realized:
            if r["year"] == year:
                by_ticker[r["ticker"]] += r["gain"]

        portfolio = await self.calculate_portfolio()
        harvest = sorted(
            [{"ticker": p["ticker"], "name": p.get("name") or p["ticker"],
              "unrealized_loss_eur": round(p.get("gain_loss") or 0.0, 2)}
             for p in portfolio.get("positions", []) if (p.get("gain_loss") or 0.0) < 0],
            key=lambda x: x["unrealized_loss_eur"],
        )
        return {
            "year": year,
            "realized_ytd_eur": round(realized_ytd, 2),
            "dividends_ytd_eur": round(div_ytd, 2),
            "realized_total_eur": round(realized_total, 2),
            "taxable_ytd_eur": round(taxable_ytd, 2),
            "estimated_irpf_ytd_eur": round(self._irpf_savings(taxable_ytd), 2),
            "by_ticker_ytd": sorted(
                [{"ticker": k, "gain_eur": round(v, 2)} for k, v in by_ticker.items()],
                key=lambda x: x["gain_eur"]),
            "recent_sales": sorted(realized, key=lambda r: r["date"], reverse=True)[:15],
            "harvest_candidates": harvest[:10],
            "note": ("Estimación FIFO en EUR (no ajusta divisa). Base del ahorro. Las minusvalías "
                     "compensan plusvalías y el resto se arrastra 4 años. Ojo a la regla de recompra "
                     "(2 meses). No es asesoramiento fiscal."),
        }

    async def get_portfolio_history(self, days: int = 365) -> list[dict]:
        async with session_scope() as session:
            rows = await SnapshotRepository(session, self.user_id).list_last_days(days=days)
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

    async def get_position_history(self, ticker: str, days: int = 365) -> dict:
        """The user's OWN position over time for `ticker` — quantity held, market
        value (quantity * price), and cumulative cost basis (money actually put in)
        at each date. Distinct from get_asset_history(): that's the raw market
        price; this is worth 0 before the first purchase and jumps whenever the
        user actually buys/sells, since it's built by replaying their transactions
        against the price history, not the price series itself."""
        ticker_up = ticker.upper()
        async with session_scope() as session:
            txs = await TransactionRepository(session, self.user_id).list_for_ticker(ticker_up)
        txs = sorted(txs, key=lambda t: t.executed_at)

        positions = await self.load_positions()
        pos = positions[positions["ticker"].str.upper() == ticker_up]
        if not pos.empty:
            asset_type = pos.iloc[0]["type"]
        elif ticker_up in {"BTC", "ETH", "SOL", "DOGE", "PEPE", "XRP", "ADA"}:
            asset_type = "crypto"  # fully-exited crypto position: no row in Position anymore
        else:
            asset_type = "stock"

        if not txs:
            # No per-trade record exists (common for Kraken: its API only returns
            # actual buy/sell orders, not coins that arrived by deposit/transfer —
            # the live position is still real, just not reconstructable over time).
            live_qty = float(pos.iloc[0]["quantity"]) if not pos.empty else 0.0
            return {"ticker": ticker_up, "history": [], "current_quantity": live_qty, "has_transactions": False}

        first_date = txs[0].executed_at.date()
        span_days = max(days, (datetime.now(timezone.utc).date() - first_date).days + 1)
        price_hist = await self.get_asset_history(ticker_up, asset_type, days=span_days) or []

        # Replay buys/sells into (date, qty_delta, cost_delta) events. Dividends/fees
        # don't change quantity or cost basis here — they only appear in the raw
        # transaction list the frontend shows alongside this chart.
        events: list[tuple[date, float, float]] = []
        for t in txs:
            d = t.executed_at.date()
            if t.type == "buy":
                events.append((d, float(t.quantity), float(t.quantity) * float(t.price) + float(t.fee or 0)))
            elif t.type == "sell":
                events.append((d, -float(t.quantity), -float(t.quantity) * float(t.price)))
        events.sort(key=lambda e: e[0])

        history = []
        qty = cost_basis = 0.0
        ei = 0
        for h in sorted(price_hist, key=lambda h: h["date"]):
            h_date = datetime.strptime(h["date"], "%Y-%m-%d").date()
            while ei < len(events) and events[ei][0] <= h_date:
                qty += events[ei][1]
                cost_basis += events[ei][2]
                ei += 1
            if h_date < first_date:
                continue  # nothing held yet — skip rather than show a misleading 0 before day 1
            price = h.get("close") or h.get("price") or 0
            history.append({
                "date": h["date"],
                "quantity": round(qty, 8),
                "value": round(qty * price, 2),
                "cost_basis": round(max(cost_basis, 0.0), 2),
            })

        return {"ticker": ticker_up, "history": history, "current_quantity": round(qty, 8), "has_transactions": True}

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
        return_by_ticker: dict[str, float] = {}  # 3-month %, SAME window as the vol
        for ticker, series in closes.items():
            vals = np.array([v for _, v in sorted(series.items())], dtype=float)
            if len(vals) < 10:
                continue
            rets = np.diff(vals) / vals[:-1]
            ann_vol = float(np.std(rets) * np.sqrt(252) * 100)
            risk_by_ticker[ticker] = round(ann_vol, 1)
            return_by_ticker[ticker] = round(float((vals[-1] - vals[0]) / vals[0] * 100), 1) if vals[0] else 0.0
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
            "return_by_ticker": return_by_ticker,   # 3m %, for the risk/return scatter
            "weight_by_ticker": {t: round(weight_map.get(t, 0.0), 2) for t in risk_by_ticker},
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

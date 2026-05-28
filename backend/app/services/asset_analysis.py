"""Deep-dive analysis for a single asset — everything a professional would want.

Produces a JSON payload with:
- identity (ticker, name, category, region)
- extended risk metrics (CAGR, vol, Sharpe, Sortino, max DD + date, Calmar, beta/alpha vs benchmark)
- ensemble score breakdown (read from the cached opportunities)
- multiple chart URLs (price + SMA50/200, drawdown over time, daily-returns histogram,
  rolling volatility, cumulative vs benchmark)
- news_for_asset grouped by source + sentiment summary
- a broker-style narrative produced by the LLM

Same payload powers the web modal and the Telegram command.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
from loguru import logger

from app.llm.factory import get_llm_client
from app.llm.types import LLMMessage
from app.services.charts import area_chart, bar_chart, line_chart_multi
from app.services.discovery.market_scanner import MarketScanner
from app.services.discovery.quant_score import compute_factors
from app.services.discovery.technical import compute_signals
from app.services.news import NewsService
from app.services.opportunities import get_opportunity_service


# Benchmark per asset category/region. Auto-selected; falls back to SPY.
def _benchmark_for(ticker: str, category: str = "", region: str = "") -> tuple[str, str]:
    t = (ticker or "").upper()
    if t.endswith("-USD") or category == "cripto":
        return ("BTC-USD", "Bitcoin")
    if region in ("Europa", "España") or t.endswith(".L") or t.endswith(".DE") or t.endswith(".PA"):
        return ("SWDA.L", "MSCI World UCITS")
    return ("SPY", "S&P 500")


def _series_from_history(hist: list[dict]) -> pd.Series | None:
    if not hist:
        return None
    closes = [(h.get("date"), h.get("close")) for h in hist if h.get("close")]
    if len(closes) < 60:
        return None
    s = pd.Series([c for _, c in closes], index=pd.to_datetime([d for d, _ in closes]), dtype=float)
    return s


def _extended_metrics(s: pd.Series, bench: pd.Series | None) -> dict:
    rets = s.pct_change().dropna()
    last = float(s.iloc[-1])
    years = len(rets) / 252 if len(rets) else 0
    cagr = ((last / float(s.iloc[0])) ** (1 / years) - 1) * 100 if years > 0 and s.iloc[0] > 0 else 0.0
    vol = float(rets.std() * np.sqrt(252) * 100)
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else 0.0
    downside = rets[rets < 0]
    sortino = float(rets.mean() / downside.std() * np.sqrt(252)) if len(downside) > 1 and downside.std() > 0 else 0.0
    cum = (1 + rets).cumprod()
    dd = (cum - cum.cummax()) / cum.cummax()
    max_dd = float(dd.min() * 100)
    max_dd_date = str(dd.idxmin().date()) if not dd.empty else None
    calmar = abs(cagr / max_dd) if max_dd < 0 else 0.0

    # vs benchmark
    beta, alpha_pct, corr = None, None, None
    if bench is not None and len(bench) > 30:
        aligned = pd.concat([rets, bench.pct_change().dropna()], axis=1, join="inner").dropna()
        if len(aligned) > 30:
            a = aligned.iloc[:, 0].values
            b = aligned.iloc[:, 1].values
            var_b = float(np.var(b))
            beta = float(np.cov(a, b)[0, 1] / var_b) if var_b > 0 else None
            corr = float(np.corrcoef(a, b)[0, 1])
            alpha_daily = float(a.mean() - (beta or 0) * b.mean()) if beta is not None else 0.0
            alpha_pct = alpha_daily * 252 * 100

    return {
        "last_price": round(last, 4),
        "currency_hint": None,
        "n_days": int(len(rets)),
        "years_covered": round(years, 2),
        "cagr_pct": round(cagr, 2),
        "volatility_pct": round(vol, 2),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "max_drawdown_date": max_dd_date,
        "calmar": round(calmar, 2),
        "beta": round(beta, 2) if beta is not None else None,
        "alpha_annual_pct": round(alpha_pct, 2) if alpha_pct is not None else None,
        "correlation": round(corr, 2) if corr is not None else None,
    }


def _build_charts(s: pd.Series, bench: pd.Series | None, bench_name: str, name: str) -> dict:
    """Build the five chart URLs (QuickChart, rendered server-side as PNG)."""
    labels = [d.strftime("%Y-%m") for d in s.index]
    sma50 = s.rolling(50, min_periods=20).mean()
    sma200 = s.rolling(200, min_periods=60).mean()
    chart_price = line_chart_multi(
        f"{name} — precio · SMA50 · SMA200",
        labels,
        [
            {"name": "precio", "values": [round(x, 4) for x in s.values], "color": "#10b981", "width": 2},
            {"name": "SMA50", "values": [None if pd.isna(x) else round(x, 4) for x in sma50.values], "color": "#f59e0b", "dashed": True, "width": 1.5},
            {"name": "SMA200", "values": [None if pd.isna(x) else round(x, 4) for x in sma200.values], "color": "#ef4444", "dashed": True, "width": 1.5},
        ],
    )

    rets = s.pct_change().dropna()
    cum = (1 + rets).cumprod()
    dd = (cum - cum.cummax()) / cum.cummax() * 100
    chart_dd = area_chart(
        "Drawdown histórico (%)",
        [d.strftime("%Y-%m") for d in dd.index],
        [round(x, 2) for x in dd.values],
        color="#ef4444",
    )

    # Histogram of daily returns in 18 bins between -5% and +5% (cap outliers)
    capped = np.clip(rets.values * 100, -5, 5)
    bins = np.linspace(-5, 5, 19)
    hist_counts, edges = np.histogram(capped, bins=bins)
    hist_labels = [f"{edges[i]:+.1f}%" for i in range(len(edges) - 1)]
    chart_hist = bar_chart("Distribución de retornos diarios", hist_labels, hist_counts.tolist(), color="#6366f1")

    # Rolling 60d annualized volatility
    rv = rets.rolling(60).std() * np.sqrt(252) * 100
    rv = rv.dropna()
    chart_vol = area_chart(
        "Volatilidad rodante 60d (%, anualizada)",
        [d.strftime("%Y-%m") for d in rv.index],
        [round(x, 2) for x in rv.values],
        color="#f59e0b",
    )

    # Relative cumulative performance vs benchmark
    chart_rel = None
    if bench is not None and len(bench) > 30:
        aligned = pd.concat([s, bench], axis=1, join="inner").dropna()
        if len(aligned) > 30:
            aligned.columns = ["asset", "bench"]
            a_cum = aligned["asset"] / aligned["asset"].iloc[0]
            b_cum = aligned["bench"] / aligned["bench"].iloc[0]
            rl = (a_cum / b_cum - 1) * 100
            chart_rel = line_chart_multi(
                f"Rendimiento relativo vs {bench_name} (%)",
                [d.strftime("%Y-%m") for d in rl.index],
                [{"name": f"vs {bench_name}", "values": [round(x, 2) for x in rl.values], "color": "#00d4aa"}],
            )

    return {
        "price_with_smas": chart_price,
        "drawdown": chart_dd,
        "returns_histogram": chart_hist,
        "rolling_volatility": chart_vol,
        "relative_vs_benchmark": chart_rel,
    }


async def _llm_summary(name: str, ticker: str, metrics: dict, breakdown: dict | None,
                        news: list[dict], factors: dict, signals: dict) -> str:
    """Two-paragraph broker-style synthesis. Best-effort; degrades to '' on error."""
    bd_lines = []
    if breakdown:
        for k, v in list(breakdown.items())[:5]:
            bd_lines.append(f"{k}: {v:+.2f}")
    news_titles = "\n".join(f"- [{n.get('impact','neutral')}] {(n.get('title','') or '')[:140]}" for n in news[:8])
    system = (
        "Eres un analista financiero senior escribiendo una nota de análisis para un broker. "
        "Tono profesional, conciso, honesto. Distingues DATO (números) de OPINIÓN (tu lectura). "
        "Nunca recomiendas comprar/vender; ofreces lectura. Español, dos párrafos cortos."
    )
    user = (
        f"Activo: {name} ({ticker}).\n\n"
        f"Métricas:\n{metrics}\n\n"
        f"Factores cuantitativos:\n{factors}\n\n"
        f"Señales técnicas:\n{signals}\n\n"
        f"Desglose del ensemble (criterios que más pesan):\n{chr(10).join(bd_lines) or '(no disponible)'}\n\n"
        f"Titulares recientes (con sentimiento):\n{news_titles or '(no hay titulares específicos)'}\n\n"
        "Escribe la nota: párrafo 1 = lectura cuantitativa y técnica; párrafo 2 = contexto, "
        "riesgos y qué vigilar."
    )
    try:
        client = get_llm_client()
        resp = await client.generate(
            [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
            max_tokens=600, temperature=0.4,
        )
        return resp.text.strip()
    except Exception as exc:
        logger.warning("asset_analysis LLM summary failed: {}", exc)
        return ""


async def analyze_asset(ticker: str) -> dict:
    """Build the full deep-analysis payload for one ticker."""
    ticker = (ticker or "").strip()
    if not ticker:
        raise ValueError("ticker is required")

    scanner = MarketScanner()
    # Try to get up to 3 years of history (more data → better stats).
    hist = await scanner.yahoo.get_history(ticker, period="3y") or \
           await scanner.yahoo.get_history(ticker, period="1y")
    s = _series_from_history(hist or [])
    if s is None:
        raise ValueError(f"Sin histórico suficiente para {ticker}")

    # Identify the asset from cached opportunities (for name / category / breakdown).
    cached = (get_opportunity_service()._cache or
              await get_opportunity_service()._load_from_db()) or {}
    themes = cached.get("themes") or []
    match = next((t for t in themes if (t.get("ticker") or "").upper() == ticker.upper()), {}) or {}
    name = match.get("theme") or ticker
    category = match.get("category") or ""
    region = match.get("region") or ""

    factors = compute_factors([float(x) for x in s.values])
    signals = compute_signals([float(x) for x in s.values]) or {}

    bench_ticker, bench_name = _benchmark_for(ticker, category, region)
    bench_hist = await scanner.yahoo.get_history(bench_ticker, period="3y") or \
                 await scanner.yahoo.get_history(bench_ticker, period="1y")
    bench = _series_from_history(bench_hist or [])

    metrics = _extended_metrics(s, bench)
    charts = _build_charts(s, bench, bench_name, name)

    # Per-asset news from the news service (multiple sources, sentiment-classified).
    try:
        news = await NewsService().get_news_for_asset(ticker, limit=10)
    except Exception as exc:
        logger.warning("asset_analysis news failed: {}", exc)
        news = []
    sources = sorted({n.get("source", "") for n in news if n.get("source")})
    sentiment = {"bullish": 0, "bearish": 0, "neutral": 0}
    for n in news:
        sentiment[n.get("impact", "neutral")] = sentiment.get(n.get("impact", "neutral"), 0) + 1

    # Ensemble breakdown for whichever thesis this asset is stronger on.
    bd_full = match.get("breakdown") or {}
    which = "momentum" if (match.get("momentum_score") or 0) >= (match.get("value_score") or 0) else "value"
    breakdown = bd_full.get(which) or {}
    breakdown = dict(sorted(breakdown.items(), key=lambda kv: abs(kv[1]), reverse=True))

    narrative = await _llm_summary(name, ticker, metrics, breakdown, news, factors, signals)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "name": name,
        "category": category,
        "region": region,
        "benchmark": {"ticker": bench_ticker, "name": bench_name},
        "metrics": metrics,
        "factors": factors,
        "signals": signals,
        "scores": {
            "momentum_score": match.get("momentum_score"),
            "value_score": match.get("value_score"),
            "winner_affinity": match.get("winner_affinity"),
        },
        "score_breakdown": breakdown,
        "ensemble_thesis": which,
        "charts": charts,
        "news": news,
        "news_sources": sources,
        "news_sentiment": sentiment,
        "narrative": narrative,
    }

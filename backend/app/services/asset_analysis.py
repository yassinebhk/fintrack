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

import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from loguru import logger

from scipy import stats as _stats  # for chi² / t-distribution p-values

from app.llm import LLMMessage, get_llm_client
from app.services.charts import area_chart, bar_chart, line_chart_multi
from app.services.market.fred import FREDClient
from app.services.discovery.market_scanner import MarketScanner
from app.services.discovery.quant_score import compute_factors
from app.services.discovery.technical import compute_signals
from app.services.news import NewsService
from app.services.opportunities import get_opportunity_service


# Benchmark per asset category/region. Auto-selected; falls back to SPY.
def _benchmark_for(ticker: str, category: str = "", region: str = "") -> tuple[str, str]:
    t = (ticker or "").upper()
    # Bitcoin itself: compare to traditional equities (more informative than vs itself).
    if t == "BTC-USD":
        return ("SPY", "S&P 500")
    # Other crypto → compare to Bitcoin (the de-facto crypto benchmark).
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


async def _get_risk_free_pct() -> float:
    """Annualized risk-free rate (%, e.g. 4.5). 3M Treasury preferred, 2Y as
    fallback, 4.0 % static fallback so we never crash on a FRED outage."""
    fred = FREDClient()
    for sid in ("DGS3MO", "DGS2"):
        try:
            r = await fred.get_latest(sid)
            v = (r or {}).get("value")
            if v is not None:
                return float(v)
        except Exception:
            continue
    return 4.0


def _drawdown_durations(dd: pd.Series) -> tuple[int | None, float | None]:
    """From the underwater series (dd ≤ 0), return (max_run_days, avg_run_days).
    A "run" is a stretch of consecutive sessions strictly underwater."""
    if dd.empty:
        return (None, None)
    under = (dd.values < -1e-9)
    runs, cur = [], 0
    for u in under:
        if u:
            cur += 1
        else:
            if cur > 0:
                runs.append(cur)
            cur = 0
    if cur > 0:
        runs.append(cur)
    if not runs:
        return (0, 0.0)
    return (int(max(runs)), round(float(np.mean(runs)), 1))


def _capture_ratios(asset_rets: pd.Series, bench_rets: pd.Series) -> tuple[float | None, float | None]:
    """Standard up/down-capture ratios (%, monthly compounded) — needs ≥12 months."""
    df = pd.concat([asset_rets, bench_rets], axis=1, join="inner").dropna()
    if len(df) < 60:  # at least ~3 months daily ≈ 60 obs → roughly 3 months
        return (None, None)
    df.columns = ["asset", "bench"]
    monthly = (1 + df).resample("ME").prod() - 1 if hasattr(df.index, "to_period") else (1 + df).groupby(pd.Grouper(freq="ME")).prod() - 1
    monthly = monthly.dropna()
    if len(monthly) < 12:
        return (None, None)
    up, down = monthly[monthly["bench"] > 0], monthly[monthly["bench"] < 0]
    up_cap = (((1 + up["asset"]).prod() - 1) / ((1 + up["bench"]).prod() - 1) * 100) if len(up) and (((1 + up["bench"]).prod() - 1) != 0) else None
    dn_cap = (((1 + down["asset"]).prod() - 1) / ((1 + down["bench"]).prod() - 1) * 100) if len(down) and (((1 + down["bench"]).prod() - 1) != 0) else None
    return (round(up_cap, 1) if up_cap is not None else None,
            round(dn_cap, 1) if dn_cap is not None else None)


def _alpha_significance(asset_rets: pd.Series, bench_rets: pd.Series, beta: float, alpha_daily: float
                         ) -> tuple[float | None, float | None]:
    """Returns (t_alpha, p_alpha) from the OLS regression of asset on benchmark."""
    df = pd.concat([asset_rets, bench_rets], axis=1, join="inner").dropna()
    if len(df) < 30:
        return (None, None)
    a, b = df.iloc[:, 0].values, df.iloc[:, 1].values
    n = len(a)
    resid = a - (alpha_daily + beta * b)
    rss = float(np.sum(resid ** 2))
    sigma2 = rss / max(n - 2, 1)
    sx2 = float(np.sum((b - b.mean()) ** 2))
    if sx2 <= 0:
        return (None, None)
    se_alpha = float(np.sqrt(sigma2 * (1.0 / n + (b.mean() ** 2) / sx2)))
    if se_alpha == 0:
        return (None, None)
    t_alpha = alpha_daily / se_alpha
    p_alpha = float(2 * (1 - _stats.t.cdf(abs(t_alpha), df=max(n - 2, 1))))
    return (round(t_alpha, 2), round(p_alpha, 4))


def _probabilistic_sharpe(rets_excess: pd.Series, sharpe_daily: float) -> float | None:
    """López de Prado's PSR(0): prob. that the true Sharpe > 0 given observed skew
    and kurtosis (so a high Sharpe on a fat-tailed asset doesn't look as 'safe')."""
    n = len(rets_excess)
    if n < 30 or sharpe_daily == 0:
        return None
    skew = float(rets_excess.skew())
    ex_kurt = float(rets_excess.kurt())  # pandas .kurt() returns EXCESS kurtosis
    # LdP formula uses Pearson kurtosis: kurt_pearson = ex_kurt + 3 → (kurt_pearson - 1) = ex_kurt + 2
    denom_term = 1.0 - skew * sharpe_daily + ((ex_kurt + 2.0) / 4.0) * (sharpe_daily ** 2)
    if denom_term <= 0:
        return None
    z = sharpe_daily * np.sqrt(n - 1) / np.sqrt(denom_term)
    return round(float(_stats.norm.cdf(z)) * 100, 1)  # %


def _extended_metrics(s: pd.Series, bench: pd.Series | None, rf_annual_pct: float) -> dict:
    """Compute the broker-grade metric set. All metrics share the SAME aligned
    daily-returns series and the SAME risk-free rate, so the numbers are
    internally coherent (no apples-to-oranges across the table)."""
    rets = s.pct_change().dropna()
    if len(rets) < 30:
        return {}
    last = float(s.iloc[-1])
    years = len(rets) / 252
    cagr = ((last / float(s.iloc[0])) ** (1 / years) - 1) * 100 if years > 0 and s.iloc[0] > 0 else 0.0
    vol = float(rets.std() * np.sqrt(252) * 100)

    # --- Sharpe & Sortino, properly adjusted to the risk-free rate ---
    daily_rf = (rf_annual_pct / 100.0) / 252.0
    excess = rets - daily_rf
    sharpe = float(excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0.0
    downside = excess[excess < 0]
    sortino = float(excess.mean() / downside.std() * np.sqrt(252)) if len(downside) > 1 and downside.std() > 0 else 0.0
    sharpe_daily = float(excess.mean() / excess.std()) if excess.std() > 0 else 0.0

    # --- Drawdown: depth, date, duration ---
    cum = (1 + rets).cumprod()
    dd = (cum - cum.cummax()) / cum.cummax()
    max_dd = float(dd.min() * 100)
    max_dd_date = str(dd.idxmin().date()) if not dd.empty else None
    max_dd_days, avg_dd_days = _drawdown_durations(dd)
    calmar = abs(cagr / max_dd) if max_dd < 0 else 0.0

    # --- Tail risk (historical method — fat-tail-safe vs parametric) ---
    var95 = float(-np.quantile(rets.values, 0.05) * 100)
    var99 = float(-np.quantile(rets.values, 0.01) * 100)
    tail95 = rets[rets <= np.quantile(rets.values, 0.05)]
    tail99 = rets[rets <= np.quantile(rets.values, 0.01)]
    cvar95 = float(-tail95.mean() * 100) if len(tail95) else None
    cvar99 = float(-tail99.mean() * 100) if len(tail99) else None

    # --- Distribution shape (skew / excess kurtosis / Jarque-Bera) ---
    skew = float(rets.skew())
    ex_kurt = float(rets.kurt())
    n = len(rets)
    jb_stat = float(n / 6.0 * (skew ** 2 + (ex_kurt ** 2) / 4.0))
    jb_p = float(1.0 - _stats.chi2.cdf(jb_stat, df=2))

    # --- Probabilistic Sharpe Ratio (López de Prado) ---
    psr_pct = _probabilistic_sharpe(excess, sharpe_daily)

    # --- Benchmark-relative metrics on the aligned series ---
    beta = alpha_pct = corr = r2_pct = info_ratio = treynor = te_pct = None
    up_cap = down_cap = t_alpha = p_alpha = None
    if bench is not None and len(bench) > 30:
        bench_rets = bench.pct_change().dropna()
        aligned = pd.concat([rets, bench_rets], axis=1, join="inner").dropna()
        if len(aligned) > 30:
            a, b = aligned.iloc[:, 0].values, aligned.iloc[:, 1].values
            var_b = float(np.var(b))
            if var_b > 0:
                beta = float(np.cov(a, b)[0, 1] / var_b)
                corr = float(np.corrcoef(a, b)[0, 1])
                r2_pct = round(corr ** 2 * 100, 1)
                alpha_daily = float(a.mean() - beta * b.mean())
                alpha_pct = alpha_daily * 252 * 100
                # Information Ratio + Tracking Error
                diff = a - b
                if np.std(diff) > 0:
                    info_ratio = float(np.mean(diff) / np.std(diff) * np.sqrt(252))
                    te_pct = float(np.std(diff) * np.sqrt(252) * 100)
                # Treynor (annual excess return / beta) — only meaningful for |β| ≥ 0.1;
                # tiny |β| would make Treynor explode and mislead a reader.
                ann_excess = float(a.mean() * 252 - rf_annual_pct / 100.0)
                if beta is not None and abs(beta) >= 0.1:
                    treynor = ann_excess / beta * 100  # in %
                # Alpha significance (t-stat / p-value)
                t_alpha, p_alpha = _alpha_significance(
                    pd.Series(a, index=aligned.index), pd.Series(b, index=aligned.index),
                    beta, alpha_daily,
                )
                # Up / Down capture
                up_cap, down_cap = _capture_ratios(
                    pd.Series(a, index=aligned.index), pd.Series(b, index=aligned.index),
                )

    return {
        "last_price": round(last, 4),
        "n_days": int(n),
        "years_covered": round(years, 2),
        "rf_annual_pct": round(rf_annual_pct, 2),
        # core
        "cagr_pct": round(cagr, 2),
        "volatility_pct": round(vol, 2),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "max_drawdown_date": max_dd_date,
        "max_drawdown_days": max_dd_days,
        "avg_drawdown_days": avg_dd_days,
        "calmar": round(calmar, 2),
        # tail / distribution
        "var_95_pct": round(var95, 2),
        "var_99_pct": round(var99, 2),
        "cvar_95_pct": round(cvar95, 2) if cvar95 is not None else None,
        "cvar_99_pct": round(cvar99, 2) if cvar99 is not None else None,
        "skewness": round(skew, 2),
        "excess_kurtosis": round(ex_kurt, 2),
        "jarque_bera_stat": round(jb_stat, 2),
        "jarque_bera_p": round(jb_p, 4),
        "psr_pct": psr_pct,
        # vs benchmark
        "beta": round(beta, 2) if beta is not None else None,
        "alpha_annual_pct": round(alpha_pct, 2) if alpha_pct is not None else None,
        "alpha_t_stat": t_alpha,
        "alpha_p_value": p_alpha,
        "correlation": round(corr, 2) if corr is not None else None,
        "r_squared_pct": r2_pct,
        "information_ratio": round(info_ratio, 2) if info_ratio is not None else None,
        "tracking_error_pct": round(te_pct, 2) if te_pct is not None else None,
        "treynor_pct": round(treynor, 2) if treynor is not None else None,
        "up_capture_pct": up_cap,
        "down_capture_pct": down_cap,
    }


# QuickChart's free tier hard-caps at 250 data points per chart ("Maximum
# chart data exceeded" if you go over — confirmed empirically: even 255-256
# points was rejected). 3 years of daily data is ~750 points, well past
# that. Every series-based chart below must be downsampled first; only the
# fixed-bin histogram is naturally small enough to skip this. Stay safely
# under the real 250 cap rather than hugging it.
_MAX_CHART_POINTS = 200


def _downsample(labels: list, *value_lists: list, max_points: int = _MAX_CHART_POINTS) -> tuple:
    """Evenly stride-sample labels + any number of parallel value lists down to
    at most max_points, always keeping the most recent point. Preserves shape
    well enough for a quick visual read; the real stats are computed on the
    full-resolution series elsewhere, this only affects what gets *drawn*."""
    n = len(labels)
    if n <= max_points:
        return (labels, *value_lists)
    stride = math.ceil(n / max_points)
    idx = list(range(0, n, stride))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    ds_labels = [labels[i] for i in idx]
    ds_values = tuple([vl[i] for i in idx] for vl in value_lists)
    return (ds_labels, *ds_values)


def _build_charts(s: pd.Series, bench: pd.Series | None, bench_name: str, name: str,
                  rf_annual_pct: float = 0.0) -> dict:
    """Build the five chart URLs (QuickChart, rendered server-side as PNG)."""
    labels = [d.strftime("%Y-%m") for d in s.index]
    sma50 = s.rolling(50, min_periods=20).mean()
    sma200 = s.rolling(200, min_periods=60).mean()
    price_vals = [round(x, 4) for x in s.values]
    sma50_vals = [None if pd.isna(x) else round(x, 4) for x in sma50.values]
    sma200_vals = [None if pd.isna(x) else round(x, 4) for x in sma200.values]
    price_labels_ds, price_vals_ds, sma50_vals_ds, sma200_vals_ds = _downsample(
        labels, price_vals, sma50_vals, sma200_vals
    )
    chart_price = line_chart_multi(
        f"{name} — precio · SMA50 · SMA200",
        price_labels_ds,
        [
            {"name": "precio", "values": price_vals_ds, "color": "#10b981", "width": 2},
            {"name": "SMA50", "values": sma50_vals_ds, "color": "#f59e0b", "dashed": True, "width": 1.5},
            {"name": "SMA200", "values": sma200_vals_ds, "color": "#ef4444", "dashed": True, "width": 1.5},
        ],
    )

    rets = s.pct_change().dropna()
    cum = (1 + rets).cumprod()
    dd = (cum - cum.cummax()) / cum.cummax() * 100
    dd_labels_ds, dd_vals_ds = _downsample(
        [d.strftime("%Y-%m") for d in dd.index], [round(x, 2) for x in dd.values]
    )
    chart_dd = area_chart("Drawdown histórico (%)", dd_labels_ds, dd_vals_ds, color="#ef4444")

    # Histogram of daily returns in 18 bins between -5% and +5% (cap outliers)
    # — already just 18 bars regardless of history length, no downsampling needed.
    capped = np.clip(rets.values * 100, -5, 5)
    bins = np.linspace(-5, 5, 19)
    hist_counts, edges = np.histogram(capped, bins=bins)
    hist_labels = [f"{edges[i]:+.1f}%" for i in range(len(edges) - 1)]
    chart_hist = bar_chart("Distribución de retornos diarios", hist_labels, hist_counts.tolist(), color="#6366f1")

    # Rolling 60d annualized volatility
    rv = rets.rolling(60).std() * np.sqrt(252) * 100
    rv = rv.dropna()
    rv_labels_ds, rv_vals_ds = _downsample(
        [d.strftime("%Y-%m") for d in rv.index], [round(x, 2) for x in rv.values]
    )
    chart_vol = area_chart("Volatilidad rodante 60d (%, anualizada)", rv_labels_ds, rv_vals_ds, color="#f59e0b")

    # Rolling 60d Sharpe (excess returns), annualized — stability of risk-adjusted return.
    daily_rf = (rf_annual_pct / 100.0) / 252.0
    excess = rets - daily_rf
    rsh = (excess.rolling(60).mean() / excess.rolling(60).std()) * np.sqrt(252)
    rsh = rsh.dropna()
    chart_rolling_sharpe = None
    if len(rsh):
        rsh_labels_ds, rsh_vals_ds = _downsample(
            [d.strftime("%Y-%m") for d in rsh.index], [round(x, 2) for x in rsh.values]
        )
        chart_rolling_sharpe = area_chart(
            "Sharpe rodante 60d (Rf ajustada, anualizado)", rsh_labels_ds, rsh_vals_ds, color="#10b981"
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
            rl_labels_ds, rl_vals_ds = _downsample(
                [d.strftime("%Y-%m") for d in rl.index], [round(x, 2) for x in rl.values]
            )
            chart_rel = line_chart_multi(
                f"Rendimiento relativo vs {bench_name} (%)",
                rl_labels_ds,
                [{"name": f"vs {bench_name}", "values": rl_vals_ds, "color": "#00d4aa"}],
            )

    return {
        "price_with_smas": chart_price,
        "drawdown": chart_dd,
        "returns_histogram": chart_hist,
        "rolling_volatility": chart_vol,
        "rolling_sharpe": chart_rolling_sharpe,
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
        "Eres un analista cuantitativo senior escribiendo una nota de análisis para un broker. "
        "Tono profesional, conciso, honesto. REGLAS ESTRICTAS para evitar alucinaciones:\n"
        "1) USA ÚNICAMENTE los números que aparecen en los DATOS abajo. Cítalos textualmente.\n"
        "2) Si un valor es null / None / 'no disponible' en los DATOS, di 'no disponible' explícitamente. "
        "JAMÁS inventes una cifra que no esté en los DATOS.\n"
        "3) No menciones precios objetivos, no recomiendas comprar/vender, no estimas direcciones futuras.\n"
        "4) Si una métrica es bench-relativa pero el benchmark no se puso (beta/alpha/IR/etc. = null), "
        "no presumas correlaciones con el mercado.\n"
        "5) Distingue DATO (lo que el número dice) de LECTURA (tu interpretación)."
    )
    user = (
        f"Activo: {name} ({ticker}).\n\n"
        "MÉTRICAS (estos son los ÚNICOS números que puedes citar):\n"
        f"{metrics}\n\n"
        f"FACTORES CUANT.: {factors}\n\n"
        f"SEÑALES TÉCNICAS: {signals}\n\n"
        f"DESGLOSE DEL ENSEMBLE (criterios que más pesan):\n{chr(10).join(bd_lines) or '(no disponible)'}\n\n"
        f"TITULARES RECIENTES (con sentimiento):\n{news_titles or '(no hay titulares específicos)'}\n\n"
        "Escribe la nota (español, 2 párrafos cortos): "
        "párrafo 1 = lectura cuantitativa (Sharpe ajustado por Rf, drawdown, PSR si está, beta/IR si están); "
        "párrafo 2 = contexto, riesgos (tail risk via VaR/CVaR si están, distribución vía Jarque-Bera), qué vigilar."
    )
    try:
        client = get_llm_client()
        # Gemini 2.5 Flash spends part of max_tokens on internal "thinking" before
        # any visible text — 600 was too tight and truncated the narrative right
        # after the opening header (see analyst_agent.py for the same fix at a
        # larger scale).
        resp = await client.generate(
            [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)],
            max_tokens=2048, temperature=0.4,
        )
        return resp.text.strip()
    except Exception as exc:
        logger.warning("asset_analysis LLM summary failed: {}", exc)
        return ""


async def analyze_asset(ticker: str, name_override: str | None = None) -> dict:
    """Build the full deep-analysis payload for one ticker.

    name_override: the caller (frontend) usually already knows the real name —
    holdings outside the ~130-instrument opportunities scan universe (e.g. a
    MyInvestor-only fund identified by ISIN) have no match there and would
    otherwise fall back to the raw ticker/ISIN everywhere, including in the
    LLM narrative."""
    ticker = (ticker or "").strip()
    if not ticker:
        raise ValueError("ticker is required")

    scanner = MarketScanner()
    # Try to get up to 3 years of history (more data → better stats). Crypto
    # tickers (BTC, ETH...) aren't quotable as-is on Yahoo — same -EUR/-USD
    # suffix fallback used elsewhere (portfolio.py::get_asset_history).
    yahoo_candidates = [ticker]
    up = ticker.upper()
    if up in {"BTC", "ETH", "SOL", "DOGE", "PEPE", "XRP", "ADA"}:
        yahoo_candidates = [f"{up}-EUR", f"{up}-USD"]
    hist = None
    for yt in yahoo_candidates:
        hist = await scanner.yahoo.get_history(yt, period="3y") or await scanner.yahoo.get_history(yt, period="1y")
        if hist:
            break
    s = _series_from_history(hist or [])
    if s is None:
        raise ValueError(f"Sin histórico suficiente para {ticker}")

    # Identify the asset from cached opportunities (for name / category / breakdown).
    cached = (get_opportunity_service()._cache or
              await get_opportunity_service()._load_from_db()) or {}
    themes = cached.get("themes") or []
    match = next((t for t in themes if (t.get("ticker") or "").upper() == ticker.upper()), {}) or {}
    name = (name_override or "").strip() or match.get("theme") or ticker
    category = match.get("category") or ""
    region = match.get("region") or ""

    factors = compute_factors([float(x) for x in s.values])
    signals = compute_signals([float(x) for x in s.values]) or {}

    bench_ticker, bench_name = _benchmark_for(ticker, category, region)
    bench_hist = await scanner.yahoo.get_history(bench_ticker, period="3y") or \
                 await scanner.yahoo.get_history(bench_ticker, period="1y")
    bench = _series_from_history(bench_hist or [])

    rf_annual_pct = await _get_risk_free_pct()
    metrics = _extended_metrics(s, bench, rf_annual_pct)
    charts = _build_charts(s, bench, bench_name, name, rf_annual_pct=rf_annual_pct)

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

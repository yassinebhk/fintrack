"""Rules engine — evaluates portfolio + news and emits Alert rows + Telegram pushes."""

import re
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import select

from app.db import session_scope
from app.models.alert import Alert
from app.services.news import NewsService
from app.services.notifications.telegram import TelegramNotifier
from app.services.portfolio import PortfolioService


# Thresholds — overridable later by user preferences
PORTFOLIO_MOVE_DOWN_PCT = -3.0     # whole-book down day
PORTFOLIO_MOVE_UP_PCT = 4.0        # whole-book up day (higher bar → less noise)
PORTFOLIO_MOVE_BIG_PCT = 6.0       # |move| above this bumps severity

# Per-asset aggressive intraday move (BOTH directions), by asset class
EQUITY_MOVE_WARN_PCT = 5.0
EQUITY_MOVE_CRIT_PCT = 9.0
CRYPTO_MOVE_WARN_PCT = 9.0         # crypto swings a lot → higher bar to avoid spam
CRYPTO_MOVE_CRIT_PCT = 15.0

DRAWDOWN_THRESHOLD_PCT = -15.0
DEDUPE_WINDOW_HOURS = 24

# Search theme for thematic/sector ETFs whose own ticker never appears in news
# (nobody publishes headlines about "USPY.DE") — 2026-09-22, added after a
# Zscaler guidance miss dragged the whole cyber sector down and this engine
# had zero coverage for USPY.DE holders. Tried per-constituent-company search
# first (top holdings individually) — it mostly surfaced stale/generic stories
# (insider-sale filings, week-old rallies), not the actual event. A SECTOR-level
# query ("cybersecurity stocks fall today") reliably found the real, same-day
# story instead, so that's the approach here: one search per held sector ETF,
# not one per constituent.
SECTOR_ETF_THEME: dict[str, str] = {
    "USPY.DE": "cybersecurity stocks",
}

# Public app URL for deep-links in push alerts. The frontend hash router honors
# #asset/<ticker> (opens that asset's detail) and #<page> (e.g. #news).
APP_URL = "https://personalfintrack.duckdns.org"


def _asset_link(ticker: str) -> str:
    return f"{APP_URL}/#asset/{(ticker or '').upper()}"


def _friendly_label(ticker: str, name_by_tk: dict, fallback: str = "") -> str:
    """A label the user recognizes: 'Name (TICKER)', or just the ticker when we
    have no better name. Tickers like 'FGRIX' mean nothing to the user alone."""
    tk = (ticker or "").upper()
    nm = (name_by_tk.get(tk) or fallback or "").strip()
    if not nm or nm.upper() == tk:
        return tk
    nm = (nm[:28] + "…") if len(nm) > 29 else nm
    return f"{nm} ({tk})"


def _is_crypto(asset_type: str | None, ticker: str) -> bool:
    if (asset_type or "").lower() in ("crypto", "cryptocurrency", "coin"):
        return True
    t = (ticker or "").upper()
    return t.endswith("-USD") or t.endswith("-EUR") or t.endswith("-USDT")


class AlertsEngine:
    _scanner_singleton = None

    def __init__(self) -> None:
        # Owner-only until this loops over every user (Fase 2).
        self._portfolio_service: PortfolioService | None = None
        self.news_service = NewsService()
        self.telegram = TelegramNotifier()

    async def _get_portfolio_service(self) -> PortfolioService:
        if self._portfolio_service is None:
            from app.auth import get_owner_user_id_cached

            owner_id = await get_owner_user_id_cached()
            self._portfolio_service = PortfolioService(owner_id or 0)
        return self._portfolio_service

    async def evaluate(self) -> list[dict]:
        """Run all rules. Returns a list of alert payloads created."""
        portfolio = await (await self._get_portfolio_service()).calculate_portfolio()
        created: list[dict] = []
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # ticker → human name, so alerts can show 'Fidelity… (FGRIX)' not 'FGRIX'.
        self._name_by_tk = {(p.get("ticker") or "").upper(): (p.get("name") or p.get("ticker") or "")
                            for p in portfolio.get("positions", [])}

        from app.services.report_prefs import get_excluded
        excluded = await get_excluded()

        # Rule 1: whole-portfolio aggressive move (BOTH directions)
        daily_pct = portfolio.get("daily_change_pct", 0) or 0
        if daily_pct <= PORTFOLIO_MOVE_DOWN_PCT or daily_pct >= PORTFOLIO_MOVE_UP_PCT:
            up = daily_pct >= 0
            big = abs(daily_pct) >= PORTFOLIO_MOVE_BIG_PCT
            created.append(
                await self._maybe_create(
                    kind="portfolio_move",
                    severity=("warning" if big else "info") if up else ("critical" if big else "warning"),
                    title=f"{'📈' if up else '📉'} Cartera {'sube' if up else 'cae'} {daily_pct:+.2f}% hoy",
                    body=(
                        f"Tu cartera está en {portfolio.get('total_value', 0):.2f} "
                        f"{portfolio.get('base_currency', 'EUR')} ({daily_pct:+.2f}% hoy)."
                    ),
                    payload={"daily_change_pct": daily_pct, "total_value": portfolio.get("total_value"),
                             "direction": "up" if up else "down"},
                    dedupe_key=f"portfolio_move:{'up' if up else 'down'}:{today_str}",
                    link=f"{APP_URL}/#dashboard",
                    link_text="Ver tu cartera",
                )
            )

        # Rule 2: individual holding aggressive intraday move (BOTH directions)
        held_tickers: set[str] = set()
        for pos in portfolio.get("positions", []):
            if (pos.get("ticker") or "").upper() in excluded:
                continue  # dust position the user chose to hide from reports/alerts
            held_tickers.add(pos.get("ticker"))
            created.append(await self._eval_move(
                ticker=pos.get("ticker"),
                name=pos.get("ticker"),
                asset_type=pos.get("type"),
                broker=pos.get("broker"),
                pct=pos.get("day_change_pct", 0) or 0,
                price=pos.get("current_price") or 0,
                currency=portfolio.get("base_currency", "EUR"),
                weight=pos.get("weight"),
                source="portfolio",
            ))

        # Rule 2b: tickers tracked in plans/watchlist that AREN'T in the synced portfolio
        # (e.g. the tactical ETFs just bought in Trade Republic / MyInvestor, or a
        # scheduled-catalyst name like MIRM ahead of its FDA date). Price via Yahoo —
        # for a plain US ticker, try the extended-hours-aware quote FIRST (same fix
        # as _boost_extended_hours in portfolio.py, 2026-09-24: the plain get_price()
        # can show a stale/misleading previous_close outside the regular session,
        # exactly the kind of gap Yassine wants closed for a binary FDA-date name).
        for tk, label in (await self._watchlist_extra(held_tickers)).items():
            try:
                price = None
                if "." not in tk:
                    ext = await self._scanner().yahoo.get_extended_quote(tk)
                    if ext:
                        # get_extended_quote only ever returns non-None for a
                        # US-exchange ticker (that's what PRE/POST/POSTPOST
                        # means) — USD is always correct here.
                        price = {"price": ext["price"], "change_percent": ext["change_percent"],
                                 "currency": "USD", "name": label}
                if price is None:
                    price = await self._scanner().yahoo.get_price(tk)
            except Exception as exc:
                logger.debug("alerts watchlist price {} failed: {}", tk, exc)
                continue
            if not price:
                continue
            created.append(await self._eval_move(
                ticker=tk,
                name=label or price.get("name") or tk,
                asset_type="crypto" if _is_crypto(None, tk) else "etf",
                broker=None,
                pct=price.get("change_percent", 0) or 0,
                price=price.get("price") or 0,
                currency=price.get("currency"),
                weight=None,
                source="watchlist",
            ))

        # Rule 2c: trailing-stop sell signals (track peak, alert on drop from it)
        await self._check_trailing_stops(portfolio, created)

        # Rule 2d: entry-setup signals on watchlist tickers (oversold / pullback)
        await self._check_watchlist_setups(created)

        # Rule 3: drawdown from peak
        kpis = portfolio.get("kpis", {})
        max_dd = kpis.get("max_drawdown", 0)
        if max_dd >= abs(DRAWDOWN_THRESHOLD_PCT):
            created.append(
                await self._maybe_create(
                    kind="drawdown",
                    severity="warning",
                    title=f"Drawdown actual: -{max_dd:.2f}% desde el máximo",
                    body=(
                        f"Tu cartera ha caído un -{max_dd:.2f}% desde el máximo histórico "
                        f"(fecha: {kpis.get('max_drawdown_date')})."
                    ),
                    payload={"max_drawdown_pct": max_dd, "since": kpis.get("max_drawdown_date")},
                    dedupe_key="drawdown_threshold",
                    link=f"{APP_URL}/#analysis",
                    link_text="Ver análisis de riesgo",
                )
            )

        # Rule 4: high-impact bearish news on held tickers
        # Group bearish news by held asset → ONE digest alert per asset per day
        # (avoids spamming one alert per headline). Only fires if >= 2 bearish headlines.
        news = await self.news_service.get_news("all", limit=40)
        by_asset: dict[str, list[dict]] = {}
        for item in news:
            if item.get("impact") != "bearish":
                continue
            hits = set(item.get("impactedAssets", [])) & held_tickers
            for ticker in hits:
                by_asset.setdefault(ticker, []).append(item)

        for ticker, items in by_asset.items():
            if len(items) < 2:
                continue  # a single headline isn't a signal — skip the noise
            top = items[:4]
            lines = []
            for it in top:
                src = it.get("source", "")
                title = it.get("title", "")
                url = it.get("url", "")
                lines.append(f"• {src}: {title}" + (f"\n  {url}" if url else ""))
            label = _friendly_label(ticker, self._name_by_tk)
            body = (
                f"{len(items)} titulares bajistas sobre {label} hoy:\n\n" + "\n".join(lines)
            )
            created.append(
                await self._maybe_create(
                    kind="news_bearish",
                    severity="warning",
                    title=f"📰 {len(items)} noticias bajistas sobre {label}",
                    body=body,
                    payload={"ticker": ticker, "count": len(items),
                             "urls": [it.get("url") for it in top]},
                    dedupe_key=f"news_bearish:{ticker}:{today_str}",  # max 1/asset/day
                    link=_asset_link(ticker),
                    link_text="Ver el activo en detalle",
                )
            )

        # Rule 4b: sector-ETF proxy. A held ETF's own ticker never appears in
        # news (nobody publishes headlines about "USPY.DE"), and the generic
        # macro news feed (Rule 4, above) only tags big index/commodity moves,
        # never a single mid-cap company's earnings/guidance — so neither one
        # would have caught e.g. Zscaler's 2026-09-22 guidance miss dragging
        # the whole cyber sector down. One search per held sector ETF, themed
        # ("cybersecurity stocks fall today") rather than per constituent
        # company — tested both: per-company search mostly surfaced stale/
        # generic stories (insider-sale filings, week-old rallies) and missed
        # the actual event, while the sector-level query reliably found the
        # real, same-day story.
        #
        # A headline only counts as a hit if it states an explicit % move
        # ("Moved Down by 3.32%") — tried a bearish-keyword list first and real
        # headlines phrase a decline too indirectly ("narrow leadership",
        # "investors have deserted") for a fixed word list to catch reliably
        # OR to rule out false positives; an explicit number is unambiguous.
        # Requires >=2 DIFFERENT companies (by user's choice, 2026-09-22) —
        # one name's move might be company-specific, several at once reads as
        # a real sector day. NOTE: tested against the actual 2026-09-22 cyber
        # selloff and this free search only surfaced ONE such headline that
        # day (Cisco) even though ~6 sector names were down — the >=2 bar is a
        # deliberate noise/signal tradeoff, not a guarantee every real
        # sector-wide move gets caught.
        _PCT_DOWN_RE = re.compile(
            r"\b(down|falls?|drops?|declin\w*|sinks?|tumbles?|slides?|slumps?|plunges?)\b.{0,25}?"
            r"(\d{1,2}(?:\.\d+)?)\s*%|(\d{1,2}(?:\.\d+)?)\s*%.{0,25}?"
            r"\b(down|falls?|drops?|declin\w*|sinks?|tumbles?|slides?|slumps?|plunges?)\b",
            re.IGNORECASE,
        )
        from app.services import websearch as ws
        for etf_ticker, theme in SECTOR_ETF_THEME.items():
            if etf_ticker not in held_tickers or etf_ticker in excluded:
                continue
            try:
                results = await ws.search(f"{theme} fall today", max_results=8, days=1)
            except Exception as exc:
                logger.warning("sector news search failed for {}: {}", etf_ticker, exc)
                continue
            hits = [r for r in results if _PCT_DOWN_RE.search(r.get("title") or "")]
            if len(hits) < 2:
                continue
            top = hits[:4]
            lines = [f"• {h.get('title', '')}" + (f"\n  {h.get('url')}" if h.get("url") else "") for h in top]
            label = _friendly_label(etf_ticker, self._name_by_tk)
            body = (
                f"{len(hits)} titulares de hoy con caídas concretas en el sector que compone "
                f"{label}:\n\n" + "\n".join(lines)
            )
            created.append(
                await self._maybe_create(
                    kind="news_bearish_sector",
                    severity="warning",
                    title=f"📰 Movimiento bajista en el sector de {label}",
                    body=body,
                    payload={"ticker": etf_ticker, "urls": [h.get("url") for h in top]},
                    dedupe_key=f"news_bearish_sector:{etf_ticker}:{today_str}",
                    link=_asset_link(etf_ticker),
                    link_text="Ver el activo en detalle",
                )
            )

        # Rule 5: macro-shock radar (energy, chips, tariffs, rates, geopolitics,
        # credit). ONE consolidated deduped alert listing every active shock with
        # its headlines + second-order effects + which held names are exposed. The
        # sentiment classifier often reads these as 'neutral', so this flags them.
        try:
            from app.services import macro_shocks
            shocks = macro_shocks.active_shocks(news)
            if shocks:
                # NOTE: _deliver_batch HTML-escapes the body, so it must be PLAIN
                # text (no <b>/<i> tags) and the title must not repeat the severity
                # emoji (the delivery prepends ⚠️).
                positions = portfolio.get("positions", [])
                name_by_tk = {(p.get("ticker") or "").upper(): (p.get("name") or p.get("ticker") or "")
                              for p in positions}

                def _friendly(tk: str) -> str:
                    nm = name_by_tk.get((tk or "").upper()) or tk or ""
                    return (nm[:20] + "…") if len(nm) > 21 else nm

                blocks = []
                for s in shocks:
                    cp = s.get("chokepoint")
                    lines = [f"{s['emoji']} {s['name']}" + (f" — {cp}" if cp else "")]
                    for h in s["hits"][:2]:
                        lines.append(f"• {h.get('source','')}: {h.get('title','')}")
                    # s['note'] is the general who-wins/loses; label it so it's not
                    # confused with the reader's own holdings just below.
                    lines.append(f"En general: {s['note']}")
                    exp = macro_shocks.exposure(positions, s["key"])
                    ben = [f"👍 {_friendly(e['ticker'])}" for e in exp["beneficiado"]]
                    pres = [f"👎 {_friendly(e['ticker'])}" for e in exp["presionado"]]
                    if ben or pres:
                        lines.append("Tu cartera: " + " · ".join(ben + pres))
                    blocks.append("\n".join(lines))
                keys = "+".join(sorted(s["key"] for s in shocks))
                short = ", ".join(s["name"].split(" (")[0] for s in shocks)
                created.append(
                    await self._maybe_create(
                        kind="macro_shock",
                        severity="warning",
                        title=f"Contexto macro: {short}",
                        body="\n\n".join(blocks)
                             + "\n\n➡ Qué hacer: nada. Es solo contexto para que sepas cómo "
                               "te afecta el ruido de fondo — no es una recomendación ni cambia "
                               "tus recomendaciones ni el ranking.",
                        payload={"themes": [s["key"] for s in shocks]},
                        dedupe_key=f"macro_shock:{keys}:{today_str}",
                        link=f"{APP_URL}/#news",
                        link_text="Ver noticias en la app",
                    )
                )
        except Exception as exc:
            logger.debug("macro-shock rule failed: {}", exc)

        # Rule 6: position-review escalation. review_portfolio() already computes
        # a per-holding VIGILAR/REDUCIR/ROTAR signal with real reasons (technical
        # + a real catalyst-brief from actual news) — but it only lived on the
        # "¿Vender o mantener?" page, nobody was proactively told. Added
        # 2026-09-24 after Yassine found out about SNDK's -22% drawdown +
        # AI-slowdown risk himself instead of from the app, despite the signal
        # already existing there the day before. Distinguishes a routine
        # drawdown-only flag from real, stacked reasons (Yassine's explicit ask:
        # "es importante si es un simple vigilar o hay grandes indicios") — a
        # ROTAR, 2+ stacked reasons, or an unfavorable news verdict get the
        # stronger framing; a lone drawdown trigger with neutral/favorable news
        # stays low-key. Concentration-driven REDUCIR is framed separately (it's
        # a sizing flag, not "this will fall").
        try:
            from app.auth import get_owner_user_id_cached
            from app.services.position_review import review_portfolio
            owner_id = await get_owner_user_id_cached()
            review = await review_portfolio(owner_id, force=False)
            for r in review.get("reviews", []):
                signal = r.get("signal")
                if signal not in ("VIGILAR", "REDUCIR", "ROTAR"):
                    continue
                if r.get("immaterial") or r.get("materiality") != "alta":
                    continue
                ticker = r["ticker"]
                reasons = r.get("reasons") or []
                if not reasons:
                    continue
                brief = r.get("catalyst_brief") or {}
                verdict = brief.get("verdict")
                label = _friendly_label(ticker, self._name_by_tk, r.get("name", ""))
                concentration_only = (
                    signal == "REDUCIR" and len(reasons) == 1
                    and "Concentración alta" in reasons[0]
                )
                if concentration_only:
                    title = f"Demasiado peso en una sola posición: {label}"
                    body = (reasons[0] +
                            "\n\n➡ Qué hacer: no es que vaya a bajar, es un aviso de reparto de riesgo. "
                            "Valora si te incomoda tener tanto en un solo activo.")
                    severity = "info"
                else:
                    strong = signal == "ROTAR" or len(reasons) >= 2 or verdict == "desfavorable"
                    reason_lines = "\n".join(f"• {x}" for x in reasons)
                    if strong:
                        title = f"Motivos reales para {signal.lower()}: {label}"
                        news_line = ("\n• Los catalizadores/noticias recientes también apuntan a riesgo — "
                                     "revisa el detalle en la app."
                                     if verdict == "desfavorable" else "")
                        body = (f"No es solo que haya bajado de precio — hay varias señales apuntando en la "
                                f"misma dirección:\n{reason_lines}{news_line}\n\n"
                                "➡ Qué hacer: revísalo en la app antes de decidir; esto no es una orden "
                                "automática de vender.")
                        severity = "critical" if signal == "ROTAR" else "warning"
                    else:
                        title = f"Vigilancia rutinaria: {label}"
                        body = (f"{reason_lines}\n\n"
                                "De momento es solo el precio — no hay una tendencia rota ni noticias "
                                "negativas detrás. No hace falta actuar, solo tenerlo en el radar.")
                        severity = "info"
                created.append(
                    await self._maybe_create(
                        kind="position_review",
                        severity=severity,
                        title=title,
                        body=body,
                        payload={"ticker": ticker, "signal": signal, "materiality": r.get("materiality")},
                        dedupe_key=f"position_review:{ticker}:{signal}:{today_str}",
                        link=_asset_link(ticker),
                        link_text="Ver la posición en detalle",
                    )
                )
        except Exception as exc:
            logger.debug("position-review alert rule failed: {}", exc)

        return await self._deliver_batch([c for c in created if c is not None])

    async def _deliver_batch(self, alerts: list[dict]) -> list[dict]:
        """Send every alert created in this evaluate() run as ONE Telegram
        message instead of one push per rule (a volatile day could otherwise
        trigger 4-5 separate notifications within minutes of each other)."""
        if not alerts:
            return alerts
        from app.services.notifications.telegram import html_escape as esc
        severity_emoji = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}
        blocks = []
        for a in alerts:
            em = severity_emoji.get(a["severity"], "🔔")
            block = f"{em} <b>{esc(a['title'])}</b>\n{esc(a['body'])}"
            # Deep-link into the app (built after escaping so the <a> tag survives).
            link = a.get("link")
            if link:
                lt = a.get("link_text") or "Ver en la app"
                block += f'\n🔎 <a href="{esc(link)}">{esc(lt)} →</a>'
            blocks.append(block)
        header = "🔔 <b>Alertas</b>" if len(alerts) > 1 else ""
        html = "\n\n".join([header] + blocks) if header else blocks[0]
        delivered = await self.telegram.send_html(html)
        if delivered:
            ids = [a["id"] for a in alerts]
            async with session_scope() as session:
                rows = (await session.execute(select(Alert).where(Alert.id.in_(ids)))).scalars().all()
                for row in rows:
                    row.delivered_telegram = True
        for a in alerts:
            a["delivered_telegram"] = delivered
        return alerts

    # ---- helpers -----------------------------------------------------------

    def _scanner(self):
        if AlertsEngine._scanner_singleton is None:
            from app.services.discovery.market_scanner import MarketScanner
            AlertsEngine._scanner_singleton = MarketScanner()
        return AlertsEngine._scanner_singleton

    async def _check_trailing_stops(self, portfolio: dict, created: list) -> None:
        """Track each watched ticker's running peak; fire a CRITICAL sell signal when
        price drops `trailing_pct` below that peak. Needs no price history → works for
        brand-new listings (IPOs) where RSI/Sharpe/vol are meaningless."""
        try:
            from app.services import trailing_stops as ts
            stops = await ts.get_all()
        except Exception as exc:
            logger.debug("trailing stops load failed: {}", exc)
            return
        if not stops:
            return
        pos_price: dict[str, tuple] = {}
        for p in portfolio.get("positions", []):
            t = (p.get("ticker") or "").upper()
            if p.get("current_price"):
                pos_price[t] = (p["current_price"], p.get("currency") or "")
        changed = False
        for stop in stops:
            if not stop.get("active"):
                continue
            tk = (stop.get("ticker") or "").upper()
            price = None
            cur = stop.get("currency") or ""
            if tk in pos_price:
                price, cur = pos_price[tk][0], (pos_price[tk][1] or cur)
            else:
                try:
                    pr = await self._scanner().yahoo.get_price(tk)
                    if pr:
                        price, cur = pr.get("price"), (pr.get("currency") or cur)
                except Exception as exc:
                    logger.debug("trailing stop price {} failed: {}", tk, exc)
            if not price or price <= 0:
                continue
            peak = float(stop.get("peak") or 0)
            if price > peak:
                stop["peak"] = price
                peak = price
                changed = True
            # Optional upside target: alert ONCE when the price reaches it (informational
            # — the trailing stop is still the exit; a hard target only notifies).
            target = float(stop.get("target_price") or 0)
            if target > 0 and price >= target and not stop.get("target_hit"):
                label = _friendly_label(tk, getattr(self, "_name_by_tk", {}), fallback=stop.get("label") or "")
                res = await self._maybe_create(
                    kind="target_reached", severity="info",
                    title=f"🎯 Objetivo alcanzado: {label} en {price:.2f} {cur}",
                    body=(f"{label} ha llegado a tu objetivo de {target:.2f} {cur} (precio {price:.2f} {cur}). "
                          f"Valora tomar beneficios o dejar correr con el trailing stop. (Análisis, no recomendación.)"),
                    payload={"ticker": tk, "price": price, "target_price": target},
                    dedupe_key=f"target_reached:{tk}",
                    link=_asset_link(tk),
                    link_text="Ver el activo en detalle",
                )
                if res:
                    created.append(res)
                stop["target_hit"] = True
                changed = True
            pct = float(stop.get("trailing_pct") or 12)
            if peak > 0 and price <= peak * (1 - pct / 100.0):
                drop = (price - peak) / peak * 100
                label = _friendly_label(tk, getattr(self, "_name_by_tk", {}), fallback=stop.get("label") or "")
                res = await self._maybe_create(
                    kind="trailing_stop", severity="critical",
                    title=f"🔻 Señal de venta: {label} {drop:.1f}% desde máximo",
                    body=(f"{label}: precio {price:.2f} {cur}, ha caído {drop:.1f}% desde su máximo de "
                          f"{peak:.2f} {cur} (stop dinámico {pct:.0f}%). El movimiento se ha girado — "
                          f"valora vender. (Análisis, no recomendación.)"),
                    payload={"ticker": tk, "price": price, "peak": peak,
                             "trailing_pct": pct, "drop_from_peak_pct": round(drop, 2)},
                    dedupe_key=f"trailing_stop:{tk}",
                    link=_asset_link(tk),
                    link_text="Ver el activo en detalle",
                )
                if res:
                    created.append(res)
                stop["active"] = False  # fire once, then disarm (re-arm to reactivate)
                changed = True
        if changed:
            try:
                await ts.update_peaks_and_save(stops)
            except Exception as exc:
                logger.debug("trailing stops save failed: {}", exc)

    async def _check_watchlist_setups(self, created: list) -> None:
        """Entry-setup alerts on watchlist tickers: RSI oversold (<30) or a pullback
        in an uptrend (above the 200d SMA but RSI<42). Deduped once/day per condition.
        Signals, not recommendations."""
        try:
            from app.auth import get_owner_user_id_cached
            from app.repositories import WatchlistRepository
            owner = await get_owner_user_id_cached()
            if not owner:
                return
            async with session_scope() as s:
                entries = await WatchlistRepository(s, owner).list_all()
        except Exception as exc:
            logger.debug("watchlist setups load failed: {}", exc)
            return
        if not entries:
            return
        from app.services.discovery.technical import compute_signals
        for e in entries:
            tk = (e.ticker or "").upper()
            try:
                hist = await self._scanner().yahoo.get_history(tk, period="1y")
                rows = [h for h in (hist or []) if h.get("close")]
                if len(rows) < 30:
                    continue
                sig = compute_signals(
                    [h["close"] for h in rows], [h.get("high") for h in rows],
                    [h.get("low") for h in rows], [h.get("volume") for h in rows],
                ) or {}
            except Exception as exc:
                logger.debug("watchlist setup {} failed: {}", tk, exc)
                continue
            rsi, above = sig.get("rsi"), sig.get("above_sma200")
            name = e.name or tk
            # Lead with a name the user recognizes; only show the ticker in
            # parentheses (and skip it entirely when the name IS the ticker).
            label = name if name.upper() == tk else f"{name} ({tk})"
            cond = title = body = None
            if rsi is not None and rsi < 30:
                cond = "oversold"
                title = f"🟢 {label}: caída fuerte, posible rebote (técnico)"
                body = (f"{name} ha caído mucho (RSI {rsi:.0f} de 100 = muy sobrevendido). "
                        f"Cuando algo está así de castigado a veces rebota, pero también puede "
                        f"seguir bajando — no es garantía.\n"
                        f"➡ Qué hacer: nada obligatorio. Es solo un aviso de que, si pensabas "
                        f"entrar o añadir {name} (lo tienes en tu watchlist), ahora está "
                        f"técnicamente barato.")
            elif above and rsi is not None and rsi < 42:
                cond = "pullback"
                title = f"🟢 {label}: retroceso dentro de tendencia alcista (técnico)"
                body = (f"{name} sigue en tendencia alcista (por encima de su media de 200 días) "
                        f"pero ha hecho una pausa/retroceso (RSI {rsi:.0f}). Ese tipo de recorte "
                        f"a veces es un punto de entrada en tendencia, aunque no es garantía.\n"
                        f"➡ Qué hacer: nada obligatorio. Míralo solo si pensabas añadir {name} "
                        f"(lo tienes en tu watchlist).")
            if cond:
                res = await self._maybe_create(
                    kind="setup", severity="info", title=title, body=body,
                    payload={"ticker": tk, "rsi": rsi, "above_sma200": above, "setup": cond},
                    dedupe_key=f"setup:{tk}:{cond}",
                    link=f"{APP_URL}/#asset/{tk}",
                    link_text=f"Ver {name} en detalle",
                )
                if res:
                    created.append(res)

    async def _watchlist_extra(self, held: set[str]) -> dict[str, str]:
        """Plan/watchlist tickers not already in the portfolio. Returns {ticker: label}.

        Was "plans" only — the actual Watchlist table (added to via the app's
        watchlist feature, e.g. IONQ/AR/VIST added there 2026-09-23/24 after
        research sessions) was invisible to this rule: those tickers showed
        their live setup on the watchlist PAGE, but nobody was proactively
        alerted on a big move. Added 2026-09-24 after Yassine asked for an
        urgent push the moment a tracked catalyst (Mirum's FDA date) actually
        moves the price — same "signal existed, nobody was told" pattern as
        the position_review rule above."""
        out: dict[str, str] = {}
        try:
            from app.services import plans
            data = await plans._load()
            for p in data.get("plans", []):
                for h in p.get("holdings", []):
                    tk = (h.get("ticker") or "").strip()
                    if tk and tk not in held and tk not in out:
                        out[tk] = h.get("label") or tk
        except Exception as exc:
            logger.debug("alerts watchlist load failed: {}", exc)
        try:
            from app.auth import get_owner_user_id_cached
            from app.db import session_scope
            from app.repositories import WatchlistRepository
            owner_id = await get_owner_user_id_cached()
            async with session_scope() as s:
                entries = await WatchlistRepository(s, owner_id).list_all()
            for e in entries:
                tk = (e.ticker or "").strip().upper()
                if tk and tk not in held and tk not in out:
                    out[tk] = e.name or tk
        except Exception as exc:
            logger.debug("alerts watchlist-table load failed: {}", exc)
        return out

    async def _eval_move(self, *, ticker, name, asset_type, broker, pct, price,
                         currency, weight, source) -> dict | None:
        """Emit an alert if |pct| crosses the aggressive-move bar for this asset class."""
        if not ticker:
            return None
        crypto = _is_crypto(asset_type, ticker)
        # Backstop against residual data glitches (e.g. a corrupt previous_close):
        # a single-day move beyond these magnitudes is almost always bad data, not a
        # real move, so we refuse to alert on it rather than send a false positive.
        glitch_ceiling = 45.0 if crypto else 28.0
        if abs(pct) >= glitch_ceiling:
            logger.warning("alerts: skipping implausible {} move {:+.1f}% (likely data glitch, not alerting)", ticker, pct)
            return None
        warn = CRYPTO_MOVE_WARN_PCT if crypto else EQUITY_MOVE_WARN_PCT
        crit = CRYPTO_MOVE_CRIT_PCT if crypto else EQUITY_MOVE_CRIT_PCT
        if abs(pct) < warn:
            return None
        up = pct >= 0
        big = abs(pct) >= crit
        severity = ("warning" if big else "info") if up else ("critical" if big else "warning")
        bits = [str(b) for b in (asset_type, broker) if b]
        ctx = f" ({', '.join(bits)})" if bits else ""
        wtxt = f", peso {weight:.1f}%" if isinstance(weight, (int, float)) else ""
        try:
            ptxt = f"{float(price):.6g} {currency or ''}".strip()
        except Exception:
            ptxt = "-"
        label = _friendly_label(ticker, getattr(self, "_name_by_tk", {}), fallback=name)
        return await self._maybe_create(
            kind="asset_move",
            severity=severity,
            title=f"{'📈' if up else '📉'} {label} {'sube' if up else 'cae'} {pct:+.2f}% hoy",
            body=f"{name}{ctx}: {ptxt} ({pct:+.2f}% intradía{wtxt}).",
            payload={"ticker": ticker, "day_change_pct": round(pct, 2),
                     "direction": "up" if up else "down", "source": source},
            dedupe_key=f"asset_move:{ticker}:{'up' if up else 'down'}",
            link=_asset_link(ticker),
            link_text="Ver el activo en detalle",
        )

    async def _maybe_create(
        self,
        *,
        kind: str,
        severity: str,
        title: str,
        body: str,
        payload: dict,
        dedupe_key: str,
        link: str | None = None,
        link_text: str | None = None,
    ) -> dict | None:
        """Create an alert if no equivalent one exists within DEDUPE_WINDOW_HOURS."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=DEDUPE_WINDOW_HOURS)
        async with session_scope() as session:
            stmt = (
                select(Alert)
                .where(Alert.kind == kind)
                .where(Alert.triggered_at >= cutoff)
            )
            existing_rows = (await session.execute(stmt)).scalars().all()
            for row in existing_rows:
                if (row.payload or {}).get("__dedupe_key") == dedupe_key:
                    return None  # already alerted recently

            payload_with_key = {**payload, "__dedupe_key": dedupe_key}
            alert = Alert(
                kind=kind,
                severity=severity,
                title=title,
                body=body,
                payload=payload_with_key,
                triggered_at=datetime.now(timezone.utc),
            )
            session.add(alert)
            await session.flush()
            alert_id = alert.id

        # Telegram send happens once, batched, at the end of evaluate() — not
        # here — so a volatile day with several rules firing produces ONE
        # digest message instead of one push per rule.
        return {
            "id": alert_id,
            "kind": kind,
            "severity": severity,
            "title": title,
            "body": body,
            "link": link,
            "link_text": link_text,
        }

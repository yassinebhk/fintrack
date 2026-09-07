#!/usr/bin/env python3
"""FinTrack daily portfolio status — STANDALONE, format-identical to the server.

Reproduces app/services/portfolio_report.build_summary_html (header + HOY +
ACUMULADO + TENDENCIA + REPARTO) but fetches prices live from Yahoo/Coingecko
and sends to Telegram. Depends on NOTHING in the backend, Render, or Neon — so
it delivers the daily table even when the whole web service / DB is down (which
is exactly why it exists: both daily-summary.yml (needs Render) and
daily-summary-direct-stopgap.yml (needs Neon) go dark in an outage).

Positions come from the embedded snapshot below — update it when you buy/sell.
Secrets are read from env (GitHub Actions) or backend/.env (local runs).
Set DRY_RUN=1 to print the message without sending.
"""
import json
import os
import re
import urllib.request
import urllib.parse
import datetime
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0"}
TIMEOUT = 25
CUR = "EUR"
ENV = Path(__file__).resolve().parents[1] / "backend" / ".env"
EXCLUDED = {"DOGE", "SOL", "ETH"}  # report dust (per user preference)

# --- positions snapshot (from GET /api/portfolio, 2026-09-03) ---------------
# ticker, name, qty, cost_eur, kind, symbol, snap_eur
POS = [
    ("IE00BYX5NX33", "0P0001CLDK.F",                22.415958095113616, 301.37, "yh", "0P0001CLDK.F", 316.00),
    ("IE00B4ND3602", "iShares Physical Gold",       1.532456,           122.00, "yh", "PPFB.DE",      115.15),
    ("BTC",          "BTC",                          0.00154958,        140.61, "cg", "bitcoin",      108.54),
    ("BTEC.L",       "BTEC.L",                       12.408661949165698, 124.46, "yh", "BTEC.L",       107.29),
    ("LYX0F.DE",     "LYX0F.DE",                     0.982512,           97.00,  "yh", "UST.PA",       97.00),
    ("MU",           "Micron Technology Inc.",       0.06381010113901031, 60.00, "yh", "MU",           60.00),
    ("QDVF.DE",      "QDVF.DE",                      4.835589,           51.00,  "yh", "QDVF.DE",      57.13),
    ("COPX.L",       "COPX.L",                       0.81726,            59.39,  "yh", "COPX.L",       50.52),
    ("VVSM.DE",      "VVSM.DE",                      0.51261,            51.00,  "yh", "VVSM.DE",      44.99),
    ("ZPDU.DE",      "SSSPDR S+P US Ut..Sel.Se.UETF R", 0.8743169398907104, 40.00, "yh", "ZPDU.DE",   40.92),
    ("PLTR",         "Palantir Technologies Inc.",   0.177841,           24.30,  "yh", "PLTR",         27.98),
    ("NUKL.DE",      "NUKL.DE",                      0.382921,           21.00,  "yh", "NUKL.DE",      18.08),
    ("SPCX",         "Space Exploration",            0.137756,           30.13,  "yh", "SPCX",         17.78),
    ("USPY.DE",      "USPY.DE",                      0.385306,           16.00,  "yh", "USPY.DE",      16.00),
    ("IEAA.L",       "ISHARES III PLC ISH CORE EUR CO", 2.787068,        16.00,  "yh", "IEAA.L",       14.93),
    ("JEDI.DE",      "JEDI.DE",                      0.192012,           21.00,  "yh", "JEDI.DE",      13.05),
    ("PEPE",         "PEPE",                         1355888.11,         5.99,   "cg", "pepe",         4.38),
    ("ETH",          "ETH",                          0.0005662118,       1.72,   "cg", "ethereum",     1.22),
    ("SOL",          "SOL",                          0.0065541103,       0.87,   "cg", "solana",       0.59),
    ("DOGE",         "DOGE",                         1.251478,           0.21,   "cg", "dogecoin",     0.10),
]

_NICE = {
    "IE00B4ND3602": "Oro", "IE00BYX5NX33": "World", "LYX0F.DE": "Nasdaq",
    "VVSM.DE": "Semis", "QDVF.DE": "Energia", "NUKL.DE": "Uranio", "BTEC.L": "Biotech",
    "COPX.L": "Cobre", "JEDI.DE": "Espacio", "PLTR": "Palantir", "SPCX": "SpaceX",
    "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "DOGE": "Doge", "PEPE": "Pepe",
}
BLOCKS = ["nucleo", "oro", "tematico", "cripto", "estabilidad"]
BLOCK_LABEL = {"nucleo": "Núcleo", "oro": "Oro", "tematico": "Temático", "cripto": "Cripto", "estabilidad": "Estable"}
TARGETS = {"nucleo": 40, "oro": 10, "tematico": 20, "cripto": 15, "estabilidad": 15}
_BLOCK_BY_TICKER = {
    "IE00BYX5NX33": "nucleo", "LYX0F.DE": "nucleo", "IE00B4ND3602": "oro",
    "VVSM.DE": "tematico", "QDVF.DE": "tematico", "COPX.L": "tematico", "BTEC.L": "tematico",
    "PLTR": "tematico", "SPCX": "tematico", "NUKL.DE": "tematico", "JEDI.DE": "tematico",
    "USPY.DE": "tematico", "BTC": "cripto", "ETH": "cripto", "SOL": "cripto",
    "DOGE": "cripto", "PEPE": "cripto", "IEAA.L": "estabilidad",
}


def classify(t):
    return _BLOCK_BY_TICKER.get((t or "").upper(), "tematico")


def short(ticker, name):
    nm = _NICE.get(ticker.upper()) or name or ticker
    return nm.replace("&", "y")[:10]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=TIMEOUT) as r:
        return json.loads(r.read().decode())


def yahoo_full(symbol):
    """Return (price, currency, closes[]) or (None, None, []).

    price = live regularMarketPrice; closes = clean daily-close series (for both
    the 1-session day-change and the 1m/3m trend). We intentionally do NOT trust
    meta.previousClose/chartPreviousClose: on a 3mo range chartPreviousClose is
    the pre-range close (~3 months ago), which would turn the 'day change' into a
    quarter's move. The prior session is closes[-2] instead."""
    try:
        d = _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval=1d&range=3mo")
        res = d["chart"]["result"][0]
        meta = res["meta"]
        price = float(meta["regularMarketPrice"])
        closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
        return price, meta.get("currency", "EUR"), closes
    except Exception:
        return None, None, []


def cg_all(ids):
    try:
        return _get("https://api.coingecko.com/api/v3/simple/price?ids="
                    + ",".join(ids) + "&vs_currencies=eur&include_24hr_change=true")
    except Exception:
        return {}


def cg_chart(cid):
    try:
        d = _get(f"https://api.coingecko.com/api/v3/coins/{cid}/market_chart?vs_currency=eur&days=90&interval=daily")
        return [p[1] for p in d.get("prices", [])]
    except Exception:
        return []


def read_env(key):
    v = os.environ.get(key)
    if v:
        return v
    if ENV.exists():
        for line in ENV.read_text().splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def main():
    if datetime.date.today().weekday() >= 5:  # Sat/Sun: markets closed, Yahoo repeats Friday
        print("[skip] fin de semana — mercados cerrados, no envío.")
        return
    eurusd, _, _ = yahoo_full("EURUSD=X")
    eurgbp, _, _ = yahoo_full("EURGBP=X")
    eurusd, eurgbp = eurusd or 1.08, eurgbp or 0.85
    cg = cg_all([p[5] for p in POS if p[4] == "cg"])

    def fx(price, c):
        if c == "EUR":
            return price
        if c == "USD":
            return price / eurusd
        if c == "GBP":
            return price / eurgbp
        if c == "GBp":
            return (price / 100) / eurgbp
        return None

    enriched = []
    for ticker, name, qty, cost, kind, sym, snap in POS:
        mv, day_eur, dp, closes = None, 0.0, 0.0, []
        if kind == "cg":
            d = cg.get(sym) or {}
            p = d.get("eur")
            if p is not None:
                mv = qty * p
                dp = d.get("eur_24h_change") or 0.0
                prev_mv = mv / (1 + dp / 100) if (1 + dp / 100) else mv
                day_eur = mv - prev_mv
        else:
            price, c, cl = yahoo_full(sym)
            if price is not None and cl:
                last = cl[-1]
                # if today's close is already in the series, prior session is [-2];
                # otherwise the live price is today and [-1] is the prior session.
                if len(cl) >= 2 and abs(price - last) / (price or 1) < 0.005:
                    prev = cl[-2]
                else:
                    prev = last
                ep, epv = fx(price, c), fx(prev, c)
                if ep is not None:
                    cand = qty * ep
                    if snap > 0 and (cand > snap * 4 or cand < snap / 4):
                        mv = snap  # corrupt qty/price (known cost bug) → last known, flat
                    else:
                        mv, day_eur, dp = cand, qty * (ep - epv), (price / prev - 1) * 100
                        closes = [x for x in cl]
        if mv is None:
            mv = snap  # no live feed → last known, flat
        enriched.append({
            "ticker": ticker, "name": name, "kind": kind, "sym": sym,
            "mv": mv, "cost": cost, "day": day_eur, "dp": dp, "closes": closes,
            "glpct": (mv - cost) / cost * 100 if cost > 0 else 0.0,
        })

    non_excl = [x for x in enriched if x["ticker"].upper() not in EXCLUDED]
    total = sum(x["mv"] for x in non_excl)
    cost = sum(x["cost"] for x in non_excl)
    daily = sum(x["day"] for x in non_excl)
    pl = total - cost
    pl_pct = (pl / cost * 100) if cost > 0 else 0.0
    daily_pct = (daily / (total - daily) * 100) if (total - daily) > 0 else 0.0
    trend = "📈" if daily >= 0 else "📉"
    rows = sorted(non_excl, key=lambda x: x["mv"], reverse=True)[:14]

    def trend_of(x):
        cl = cg_chart(x["sym"]) if x["kind"] == "cg" else x["closes"]
        if len(cl) >= 25:
            m1 = (cl[-1] / cl[-22] - 1) * 100 if len(cl) > 22 else None
            m3 = (cl[-1] / cl[0] - 1) * 100
            return m1, m3
        return None, None

    Wd = 26
    hoy = [f"{'HOY':<10}{'€':>8}{'%':>8}", "─" * Wd]
    for x in rows:
        nm = short(x['ticker'], x['name'])[:10]
        de, dp = x["day"], x["dp"]
        hoy.append(f"{nm:<10}{f'{de:+.2f}€':>8}{f'{dp:+.1f}%':>8}")
    hoy.append("─" * Wd)
    hoy.append(f"{'TOTAL':<10}{f'{daily:+.2f}€':>8}{f'{daily_pct:+.1f}%':>8}")

    Wa = 33
    acum = [f"{'ACUMUL':<8}{'PUESTO':>6}{'AHORA':>6}{'P/L€':>7}{'P/L%':>6}", "─" * Wa]
    for x in rows:
        pv, nv, gl = x["cost"], x["mv"], x["glpct"]
        nm8 = short(x['ticker'], x['name'])[:8]
        acum.append(f"{nm8:<8}{f'{pv:.0f}€':>6}{f'{nv:.0f}€':>6}{f'{nv-pv:+.1f}€':>7}{f'{gl:+.0f}%':>6}")
    acum.append("─" * Wa)
    acum.append(f"{'TOTAL':<8}{f'{cost:.0f}€':>6}{f'{total:.0f}€':>6}{f'{pl:+.1f}€':>7}{f'{pl_pct:+.0f}%':>6}")

    head = (f"💼 <b>Tu cartera</b> · {total:.2f} {CUR}\n"
            f"{trend} Hoy {daily:+.2f} {CUR} ({daily_pct:+.2f}%)\n"
            f"💰 P/L {pl:+.2f} {CUR} ({pl_pct:+.2f}%)")
    msg = (head
           + "\n📈 <b>HOY</b> (variación del día)\n<pre>" + esc("\n".join(hoy)) + "</pre>"
           + "\n💰 <b>ACUMULADO</b> (desde la compra)\n<pre>" + esc("\n".join(acum)) + "</pre>")

    Wt = 24
    tend = [f"{'ACTIVO':<10}{'1m':>7}{'3m':>7}", "─" * Wt]
    any_t = False
    for x in rows:
        m1, m3 = trend_of(x)
        if m1 is None and m3 is None:
            continue
        s1 = f"{m1:+.1f}%" if m1 is not None else "–"
        s3 = f"{m3:+.1f}%" if m3 is not None else "–"
        tend.append(f"{short(x['ticker'], x['name'])[:10]:<10}{s1:>7}{s3:>7}")
        any_t = True
    if any_t:
        msg += "\n📉 <b>TENDENCIA</b> (precio del activo, no tu P/L)\n<pre>" + esc("\n".join(tend)) + "</pre>"

    agg = {b: 0.0 for b in BLOCKS}
    gtot = 0.0
    for x in enriched:
        agg[classify(x["ticker"])] += x["mv"]
        gtot += x["mv"]
    if gtot > 0:
        rep = [f"{'REPARTO':<9}{'Obj':>4}{'Real':>6}{'Desv':>6}", "─" * 25]
        diffs = {}
        for b in BLOCKS:
            tgt, real = TARGETS[b], agg[b] / gtot * 100
            diff = real - tgt
            diffs[b] = diff
            flag = "**" if abs(diff) >= 10 else ("*" if abs(diff) >= 5 else "")
            rep.append(f"{BLOCK_LABEL[b]:<9}{f'{tgt:.0f}%':>4}{f'{real:.0f}%':>6}{f'{diff:+.0f}':>6}  {flag}")
        under = sorted((b for b in BLOCKS if diffs[b] <= -5), key=lambda b: diffs[b])
        tail = "Ajusta con aportaciones nuevas, no vendiendo."
        hint = ("Aporta nuevo → " + ", ".join(f"{BLOCK_LABEL[b]} ({diffs[b]:+.0f}pp)" for b in under)) if under else ""
        msg += "\n⚖️ <b>REPARTO</b> (objetivo vs real)\n<pre>" + esc("\n".join(rep)) + "</pre>"
        msg += f"\n<i>{esc(hint + '. ' + tail if hint else tail)}</i>"

    msg += f"\n<i>excl.: {', '.join(sorted(EXCLUDED))}</i>"
    msg += "\n📌 <i>Resumen diario</i>"

    print(re.sub(r"<[^>]+>", "", msg))

    if os.environ.get("DRY_RUN"):
        print("\n[DRY_RUN] no envío.")
        return
    token, chat = read_env("TELEGRAM_BOT_TOKEN"), read_env("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("\n[!] Sin TELEGRAM_BOT_TOKEN/CHAT_ID — no envío.")
        raise SystemExit(1)
    data = urllib.parse.urlencode({"chat_id": chat, "text": msg, "parse_mode": "HTML"}).encode()
    with urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data), timeout=TIMEOUT) as r:
        print("\n[Telegram] enviado:", json.loads(r.read().decode()).get("ok"))


if __name__ == "__main__":
    main()

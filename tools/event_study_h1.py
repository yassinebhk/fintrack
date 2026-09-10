#!/usr/bin/env python3
"""H1 event study — "Semis rebound after a Nasdaq down-day" — STANDALONE.

Tests the hypothesis pre-registered in
backend/app/services/systematic/PREREGISTERED.md (2026-09-10, H1) against its
FROZEN success criteria. Fetches daily closes from Yahoo (only 2 symbols, so no
rate-limit worries), no backend/Neon/Render needed.

Signal (no look-ahead): a Nasdaq-100 (^NDX) session closing <= -0.5%. That is
known only at the US close, after Europe has closed — so we enter the European
semis ETF (VVSM.DE, the pre-registered proxy) at its FIRST close strictly AFTER
the signal date, and measure the forward return over 3/4/5 sessions.

Pre-registered criteria (ALL must hold — see the .md; do NOT edit them here):
  1. >= 60 qualifying events.
  2. Mean 3-5 session fwd return > 0 AND 95% CI lower bound > 0, after a
     0.15% per-trade cost/slippage haircut.
  3. Replicates out-of-sample: split events in half by time; sign holds in BOTH.
  4. Beats the unconditional baseline (same horizons, all days) — conditioning on
     a down-day must ADD something over plain equity drift.
"""
import statistics
import urllib.parse
import urllib.request
import json
import time

UA = {"User-Agent": "Mozilla/5.0"}
NDX = "^NDX"          # Nasdaq-100 index (signal)
SEMIS = "VVSM.DE"     # pre-registered proxy (VanEck Semiconductor UCITS, EUR)
DOWN = -0.005         # Nasdaq day <= -0.5%
HORIZONS = (3, 4, 5)  # "3-5 sessions"
HAIRCUT = 0.0015      # 0.15% per-trade round-trip cost/slippage
MIN_EVENTS = 60
Z = 1.96


def fetch(symbol, years=11):
    """Return [(date_str, close), ...] sorted ascending — DAILY closes.

    Fetch by period1/period2 (not range=): Yahoo silently downsamples range=max to
    WEEKLY bars for some tickers (e.g. VVSM.DE), which would turn a "3-5 session"
    study into a 3-5 WEEK one. Period-based requests stay daily. query2 first,
    query1 as fallback; both occasionally throw IncompleteRead on big payloads."""
    import datetime
    p2 = int(time.time())
    p1 = p2 - int(years * 365.25 * 86400)
    last = None
    for host in ("query2", "query1"):
        url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/"
               f"{urllib.parse.quote(symbol)}?period1={p1}&period2={p2}&interval=1d")
        for i in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                    d = json.loads(r.read().decode())
                res = d["chart"]["result"][0]
                ts = res["timestamp"]
                closes = res["indicators"]["quote"][0]["close"]
                out = [(datetime.datetime.fromtimestamp(t, datetime.UTC).date().isoformat(), float(c))
                       for t, c in zip(ts, closes) if c is not None]
                out.sort()
                # guard: refuse non-daily data (median gap must be ~1-4 days)
                gaps = sorted((datetime.date.fromisoformat(out[j][0]) - datetime.date.fromisoformat(out[j - 1][0])).days
                              for j in range(1, len(out)))
                med = gaps[len(gaps) // 2] if gaps else 99
                if med > 4:
                    raise ValueError(f"{symbol}: non-daily data (median gap {med}d)")
                return out
            except Exception as e:
                last = e
                time.sleep(1.5 * (i + 1))
    raise last


def mean_ci(xs):
    n = len(xs)
    m = sum(xs) / n
    sd = statistics.pstdev(xs) if n < 2 else statistics.stdev(xs)
    se = sd / (n ** 0.5) if n else 0.0
    return m, m - Z * se, m + Z * se


def fwd_returns(series, entry_dates):
    """For each entry date, average the {3,4,5}-session forward return from the
    entry close, minus the haircut. Skips events too close to the series end."""
    dates = [d for d, _ in series]
    px = {d: c for d, c in series}
    idx = {d: i for i, d in enumerate(dates)}
    out = []
    for d in entry_dates:
        i = idx.get(d)
        if i is None or i + max(HORIZONS) >= len(dates):
            continue
        rs = [px[dates[i + h]] / px[dates[i]] - 1 for h in HORIZONS]
        out.append(sum(rs) / len(rs) - HAIRCUT)
    return out


def main():
    print("H1 event study — semis rebound after a Nasdaq down-day\n" + "=" * 55)
    ndx = fetch(NDX, years=10)
    semis = fetch(SEMIS, years=11)   # capped at VVSM.DE inception (~Dec 2020) anyway
    print(f"^NDX closes: {len(ndx)} ({ndx[0][0]}..{ndx[-1][0]})")
    print(f"{SEMIS} closes: {len(semis)} ({semis[0][0]}..{semis[-1][0]})")

    # signal dates: Nasdaq day-over-day <= -0.5%
    ndx_ret = [(ndx[i][0], ndx[i][1] / ndx[i - 1][1] - 1) for i in range(1, len(ndx))]
    signal_dates = [d for d, r in ndx_ret if r <= DOWN]

    # entry = first semis close STRICTLY AFTER the signal date (no look-ahead)
    semis_dates = [d for d, _ in semis]
    entries = []
    for sd in signal_dates:
        nxt = next((d for d in semis_dates if d > sd), None)
        if nxt:
            entries.append(nxt)
    entries = sorted(set(entries))

    cond = fwd_returns(semis, entries)                       # conditional (post-down-day)
    uncond = fwd_returns(semis, semis_dates)                 # baseline (all days)

    n = len(cond)
    print(f"\nNasdaq down-days (<= {DOWN:+.1%}): {len(signal_dates)}")
    print(f"Usable events (with 5 fwd sessions): {n}")

    if n == 0:
        print("\nNO usable events — cannot evaluate. H1 UNPROVEN.")
        return

    m, lo, hi = mean_ci(cond)
    bm, blo, bhi = mean_ci(uncond)
    print(f"\nConditional  mean fwd (3-5d, net): {m:+.3%}  95% CI [{lo:+.3%}, {hi:+.3%}]  n={n}")
    print(f"Unconditional baseline (all days): {bm:+.3%}  n={len(uncond)}")

    # out-of-sample: split events in half by time
    half = n // 2
    h1m = sum(cond[:half]) / half if half else 0.0
    h2m = sum(cond[half:]) / (n - half) if (n - half) else 0.0
    print(f"OOS split — first half: {h1m:+.3%} | second half: {h2m:+.3%}")

    # --- evaluate the 4 pre-registered criteria ---
    c1 = n >= MIN_EVENTS
    c2 = (m > 0) and (lo > 0)
    c3 = (h1m > 0) and (h2m > 0)          # sign replicates in both halves
    c4 = m > bm                            # beats unconditional baseline
    print("\nPre-registered criteria:")
    print(f"  1) >= {MIN_EVENTS} events .................. {'PASS' if c1 else 'FAIL'} ({n})")
    print(f"  2) mean>0 & 95% CI lower>0 ......... {'PASS' if c2 else 'FAIL'}")
    print(f"  3) sign replicates OOS (both halves) {'PASS' if c3 else 'FAIL'}")
    print(f"  4) beats unconditional baseline .... {'PASS' if c4 else 'FAIL'}")

    verdict = all([c1, c2, c3, c4])
    print("\n" + "=" * 55)
    print("VERDICT: " + ("H1 SURVIVES — candidate for the engine (still paper-only, "
                         "size via the systematic pipeline)."
                         if verdict else
                         "H1 REJECTED — do NOT trade it. Per the kill rule, no "
                         "re-slicing horizon/threshold/proxy to force a pass."))


if __name__ == "__main__":
    main()

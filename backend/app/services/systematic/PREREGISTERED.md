# Pre-registered hypotheses & universe changes — systematic engine

> **Why this file exists.** Rigor means fixing the success bar *before* seeing the
> result, so we can't rationalise noise into signal after the fact. Git history is
> the immutable timestamp: an entry's criteria are frozen the moment it's committed.
> Same philosophy as the Polymarket Lab's pre-registered criteria.

---

## 2026-09-10 · Universe expansion (ETFs → + single stocks + bond curve)

**Change.** `buyable.py` went from ~18 (ETFs/funds + 1 bond + 2 crypto) to ~30 by
adding a new `equity_single` class (NVDA, AMD, ASML.AS, MU, PLTR, AAPL, NOVO-B.CO)
and a real bond curve (IB01 0-1y, IBTM 7-10y, IDTL 20y+, ITPS TIPS, LQDE IG, IHYU HY).

**Risk containment (pre-committed, not tuned to results).** Single-name
(idiosyncratic) risk is capped at a combined **40% sleeve** (`MAX_SINGLE_STOCK_SLEEVE`),
on top of the existing per-name 25%, crypto 20%, theme 60%. Sleeve caps are now
applied iteratively so they all hold simultaneously.

**Success bar = the *same* readiness gate, unchanged.** No new goalposts. The
expanded universe must still clear `_readiness()` in `paper.py` before ANY real money:
≥56 days & ≥30 marks out-of-sample, alpha>0 vs MSCI World, Sharpe>benchmark,
**PSR ≥ 0.75**, max drawdown > −25%. If the broader universe just adds noise, PSR
will *fall* — that's the test working, not a reason to widen the net further.

---

## 2026-09-10 · H1 — "Semis rebound after a Nasdaq down-day" (event study)

**Hypothesis.** After a session where the Nasdaq-100 closes ≤ −0.5%, the semiconductor
sleeve (proxy: VVSM.DE) has a *positive expected* forward return over the next 3–5
sessions, net of costs.

**Pre-registered success criteria (ALL must hold, set now, before running):**
1. Sample ≥ 60 qualifying events (Nasdaq ≤ −0.5% days) over the lookback.
2. Mean 3–5 session forward return **> 0** AND its 95% CI lower bound **> 0**
   after a per-trade cost/slippage haircut of 0.15%.
3. Effect survives out-of-sample: split the history in half; the sign and
   (roughly) the magnitude must replicate in BOTH halves.
4. Beats the naive baseline "always long VVSM for the same horizon" (i.e. the
   *conditioning on a down-day* has to add something, not just equity drift).

**Kill rule.** If H1 fails any criterion, it's dead — no re-slicing the horizon,
the threshold, or the proxy to make it pass. A new variant is a NEW entry here.

### Result — 2026-09-10 (evaluator: `tools/event_study_h1.py`)

**Data-quality bug caught first (and why it matters).** The first run fetched
VVSM.DE with `range=max`, which Yahoo silently returns as WEEKLY bars — so it
measured 3-5 *week* returns and (wrongly) REJECTED H1 on criterion 4. Fixed the
fetch to period1/period2 daily (1460 daily closes) + a guard that refuses any
series with a median gap > 4 days. Fixing corrupted input is not "re-slicing" —
the proxy, threshold and horizon are unchanged.

**Corrected result (daily, 415 usable events, 0.15% haircut):**
| criterion | value | verdict |
|---|---|---|
| 1 · ≥60 events | 415 | PASS |
| 2 · mean>0 & CI95 lower>0 | +0.704% [+0.326%, +1.081%] | PASS |
| 3 · sign replicates OOS | 1st half +0.427% / 2nd half +0.979% | PASS |
| 4 · beats unconditional | +0.704% vs +0.396% baseline | PASS |

**Verdict: H1 SURVIVES the pre-registered bar — but "survives" ≠ "trade it real."**
Open caveats that keep it PAPER-ONLY:
- **Overlapping windows.** Down-days cluster, so the 415 forward windows overlap
  heavily → autocorrelated observations → the 95% CI is too tight (effective n is
  far below 415). Re-test with NON-overlapping windows or a block bootstrap before
  trusting the significance.
- **One asset, one regime.** 2020-2026 was a historic semis bull market; the edge
  may be drift, not a real down-day reversal. Needs a bear-inclusive sample.
- **Small edge** (~0.31pp/event over baseline) — fragile to real costs beyond the
  haircut.

### Robustness re-test — 2026-09-10 (overlapping-window correction)

The naive n=415 CI assumes independent observations, but down-days cluster and the
3-5d windows overlap. Two corrections:

| test | result | reading |
|---|---|---|
| **Non-overlapping events** (≥5d apart, n=193, truly independent) | mean +0.537%, 95% CI **[−0.015%, +1.089%]**, baseline +0.466% | absolute return's CI **touches zero**; edge over baseline only ~0.07pp |
| **Moving-block bootstrap** on the edge (cond − baseline, block=20) | edge **+0.307%**, 95% CI [+0.026%, +0.599%], **P(edge≤0)=1.7%** | the *relative* edge is statistically real even with autocorrelation |

**Resolved status: UNPROVEN → SHELVED (paper-only, not wired live).** The two tests
tell a consistent, humbling story: conditioning on a Nasdaq down-day adds a small,
statistically detectable *relative* edge (~0.3pp vs always-in), **but the absolute
forward return is not reliably positive** once windows are independent, and the
whole effect lives in a single 2020-26 semis bull regime. ~0.3pp before real
frictions is not tradeable. The naive [+0.33%, +1.08%] CI was the false-positive
trap — overlap, not edge, did most of the work.

**Kept as the reference example** of why the block-bootstrap / non-overlap step is
mandatory before any hypothesis here graduates. To revive H1 it must clear a
bear-inclusive sample AND a materially larger edge — as a NEW dated entry.

---

## 2026-09-11 · H2 — H1 re-run on a BEAR-INCLUSIVE long-history proxy

**Why.** H1 died on a single-regime sample (VVSM.DE exists only since Dec-2020, a
pure semis bull). H2 keeps the *exact same hypothesis, threshold, horizon and
criteria* and changes ONLY the proxy to a long-history US semis ETF whose sample
spans real bears — **SMH** (~2000+, covers 2008/2018/2022) and **SOXX** (~2001+).
This is the "new dated entry" the H1 kill-rule requires, not a re-slice of H1.

**Hypothesis / signal / criteria: identical to H1** (≥60 events; mean>0 & 95% CI
lower>0 after 0.15% haircut; sign replicates OOS both halves; beats the
unconditional baseline) **PLUS the mandatory robustness gate** — must ALSO survive
non-overlapping windows AND the block-bootstrap edge CI. Frozen before running.
Evaluator: `python tools/event_study_h1.py SMH 25` (and `SOXX 25`).

**Kill rule.** Same as H1. If it fails on the bear-inclusive sample, the "semis
rebound after a Nasdaq down-day" family is dead — no more proxies fished for a pass.

### Result — 2026-09-11 (evaluator: `event_study_h1.py SMH 25` / `SOXX 25`)

Both independent long-history proxies, 2001-2026 (covers the 2008, 2018 and 2022
bear markets), 1715 events each:

| proxy | cond mean (3-5d, net) | non-overlap (n=789) 95% CI | block-boot edge · P(≤0) | verdict |
|---|---|---|---|---|
| **SMH**  | +0.422% (base +0.150%) | +0.322% **[+0.053%, +0.592%]** | +0.272% [+0.128%,+0.424%] · **0.0%** | SURVIVES |
| **SOXX** | +0.433% (base +0.145%) | +0.318% **[+0.040%, +0.596%]** | +0.288% [+0.136%,+0.443%] · **0.0%** | SURVIVES |

**Verdict: H2 SURVIVES pre-reg AND the overlap correction, on BOTH proxies.**
Unlike H1 (single 2020-26 bull, died on the correction), the bear-inclusive
25-year sample shows a ~0.27-0.29pp conditional edge that holds on independent
windows and replicates across two proxies. This is a real conditional tilt.

**But — honest caveats before anyone gets excited (still NO real money):**
1. **Small edge** (~0.28pp/event over baseline). Real after the haircut, but thin
   after Spanish CGT and timing; it's a tilt, not a money printer.
2. **Instrument mismatch.** The edge is *proven* on SMH/SOXX (long history). The
   thing Yassine actually buys is **VVSM.DE**, whose own short sample did NOT
   survive (H1). Same underlying semis index, so it should transfer — but the
   EUR-listed proxy's edge is inferred, not independently proven.
3. **One bet.** Single signal (Nasdaq), single sector (semis) — best implemented
   as a *conditional overlay/timing* on a semis sleeve, not a standalone system.

**Next step (graduation path, not a green light):** run it FORWARD, out-of-sample,
in the live paper engine and clear the `_readiness()` gate (≥56 days, ≥30 marks,
beat MSCI World in return & Sharpe, PSR≥0.75, no >25% DD) before ANY real pilot.
An in-sample survive is necessary, not sufficient.

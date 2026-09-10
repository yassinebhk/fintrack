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

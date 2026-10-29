# Pre-registration v2: Hedge or Not? (P6)
Frozen 2026-10-29. v1 pre-registration (hash 251c14117a04) and its results are unchanged.

## Evidence ranking
1. Forward paper tracking from 2026-11 (only unseen data). 2. Walk-forward / CPCV on 2001-2016.
3. 2017-2026: seen period (v1 reported it); descriptive only. Every table with dates after 2016 carries the label `seen period (v1 reported it)`.

Timing: signals are computed at the last business day of month m from data up to and including that day; the hedge applies from the next business day (v1 convention, unchanged).
Choices use data up to 2016-12 only. Evaluation window for H1-H2: **2006-01..2016-12** (estimation windows roll forward; no parameter is tuned on it except H2's target, chosen by walk-forward).
Returns: monthly USD returns of EFA + currency overlay (net of costs; stress-aware costs = v1 costs x3 on days after VIX closed above 30).
Industry reference: institutions use static ratios (bonds about 100% hedged, equities 0-50%); minimum-variance is the academic benchmark (research/evidence_v2.md). The v1 vote rule is a replication of one fund, not a claim of superiority.

## Primary hypotheses
- **H1 (min-variance benchmark).** The rolling 60-month minimum-variance hedge (OLS of EFA on the basket
  currencies' forward excess returns, coefficients / basket weights, clipped to [0, 1]) gives lower
  hedged-portfolio volatility than static 50% hedging. Stationary-bootstrap 95% CI of the volatility
  difference (mean block 6 months) excludes 0.
- **H2 (vol-capped hedge).** Hedge ratio = clip(1 - target / GJR-GARCH FX vol forecast, 0, 1), target
  chosen by walk-forward from {4, 6, 8, 10}% (anchored, 2-year test blocks from 2006), gives lower monthly
  CVaR(95%) than static 50%; bootstrap CI of the CVaR difference excludes 0.
- **H3 (overfitting audit of v1).** Family = every non-empty subset of the five v1 signals (31) +
  static 0/50/100 (34 configs), 2001-09..2016-12: PBO < 0.5 and the v1 `dynamic3` deflated Sharpe
  (n_trials = 34) > 0.90, on overlay net returns.

## Descriptive (no hypothesis)
- D1 cost sensitivity: v1 costs vs stress-aware (x3 when VIX > 30) vs 2x stress-aware.
- D2 regret: share of months each rule beats unhedged and fully hedged (v1 regret table, extended).
- D3 VaR backtest: Kupiec and Christoffersen on 99% one-month VaR of the hedged portfolio (GARCH-t).
- D4 benchmark set: static 0%, 50% and 100% are the industry-style benchmarks; the live fund and every
  rule are reported against all three (no ratio picked from a seen period).
- D5 Max-Carry baseline: hedge a currency when the US rate exceeds its rate, else 0%. The v1 vote must beat it
  on net Sharpe (with 95% CI) before any skill claim; reported as a baseline, not tested.
- D6 CIP-basis sensitivity: v1 uses 3-month OECD rates as a stand-in for 1-month forward rates. Roll cost is
  re-run with an added basis of 0, 10 and 25 bp per year on hedged notional (bound, not a measurement; free
  forward-point data are not available).
- D7 regimes: results split into USD-rising and USD-falling months (sign of the trailing 12-month USD basket
  return, known at month end). Seen-period months carry the label.
- D8 bond sleeve (synthetic): a synthetic bond sleeve built from free data (construction stated when run), hedged 0/50/100%,
  to check the industry rule "hedge bonds, not equities" on 2001-2016. Descriptive only.
- D9 roll volume: report average forward notional per month (share of portfolio) and monthly turnover per rule.

## Exploratory
- E1 conformal hedge: ACI interval (alpha 0.2) for next-month currency forward return; hedge 100% if the
  upper bound < 0, 0% if the lower bound > 0, else 50%. Coverage reported.
- E2 PySR hedge formula trained on 2001-09..2010-12, judged once on 2011-2016.

## Forward test
From 2026-11, monthly: static 50, v1 dynamic3, MV hedge, vol-capped hedge. First read 2027-11 (12 points:
explicitly too few for inference; reported as tracking only).

## What would change our conclusions
A bug found after freezing is fixed, logged in experiment_log_v2.md, and both numbers reported. v1 found static 100%
best in 2017-24 (USD carry regime); a "no" on H1-H3 is an acceptable result. Nothing is tuned on 2017-2026.

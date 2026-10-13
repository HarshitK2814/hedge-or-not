# Pre-registration: Hedge or Not? (P6)

Frozen before the test period (2017-01 to 2024-12, 96 months) is read. The code refuses to load test data until
`PREREG_HASH` equals the SHA-256 prefix of this file. Development (2001-09 to 2010-12) and validation (2011-2016)
informed every choice; see `experiment_log.md`.

## Question
A dynamic-currency-hedged ETF says its three-signal rule limits losses when foreign currencies fall while keeping
gains when they rise (497K, Q6). For a USD investor in developed ex-US equities, does the rule beat a static 50%
hedge out of sample, net of costs? Do two extra signals (volatility, cross-asset) help?

## Frozen system
`configs/hedge.yaml` as committed with this file. Nine currencies (EUR, JPY, GBP, CHF, AUD, SEK, DKK, NOK, NZD) with
MSCI EAFE weights. Votes computed on the last business day of month m; the hedge ratio (mean vote) applies from the
first business day of month m+1. Hedge P&L = -h x (spot return + (i_foreign - i_US) dt). Costs: spot + forward
spread on every change in hedge ratio, plus one FX-swap spread per month on the outstanding hedge (5-6 bp/yr in
total). The equity leg is EFA (total return, USD). Returns are monthly, in excess of the 3-month T-bill.

## Hypotheses (test period)
* **H1:** Sharpe(EFA + dynamic 3-signal hedge) - Sharpe(EFA + static 50% hedge) > 0. Paired stationary bootstrap
  (mean block 6 months, 5,000 draws), one-sided p < 0.05.
* **H2:** Sharpe(EFA + 5-signal hedge) - Sharpe(EFA + 3-signal hedge) > 0, same test. On development and
  validation the extension was slightly worse (-0.01, -0.04), so we expect H2 to fail.
* **H3:** For each disclosed signal used alone, the mean monthly overlay return minus the static-50% overlay is
  > 0 (HAC t, 6 lags, one-sided), Holm-adjusted across the three signals at 5%.

## Replication gate
Monthly correlation between our 3-signal overlay and the real fund's hedge effect (DDWM minus its unhedged sister
fund DWM, same equity index) over the test period must be >= 0.50. If it is lower, the test results describe our
rule, not the fund's, and are labelled "indicative of the disclosed design". Validation evidence that the overlay
mechanics are right: our 100% hedge vs the iShares hedged EAFE ETF (HEFA - EFA) has a monthly correlation of 0.978
and a 1.3% tracking error over 2014-2016.

## Reported without a hypothesis
Unhedged, static 100%, each of the five signals alone, average hedge ratio, cost drag, and **hedging regret**:
the Sharpe shortfall of each rule to the best static hedge (0%, 50% or 100%) chosen in hindsight for each calendar
year. The 2025+ period is reported separately and used for nothing.

Nothing in this file will be edited after the hash is set.

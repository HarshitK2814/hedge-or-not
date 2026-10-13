# Results: Hedge or Not? (P6)

Monthly returns of EFA (MSCI EAFE, USD, total return) plus each currency overlay, in excess of T-bills, net of
hedging costs (4-10 bp/yr). Signals use the last business day of month m; ratios apply over month m+1.
Pre-registration hash `251c14117a04`. Test = 2017-01 to 2024-12 (96 months).

## The reconstruction matches the real fund

| Check (test period, monthly) | Correlation | Tracking error |
|---|---|---|
| Our 100% hedge vs iShares hedged EAFE minus EFA | 0.990 | 1.0%/yr |
| Our 100% hedge vs Xtrackers hedged EAFE minus EFA | 0.989 | 1.1%/yr |
| **Our 3-signal rule vs the real fund minus its unhedged twin (DDWM - DWM)** | **0.919** | **1.6%/yr** |
| A static 50% hedge vs the same fund gap (benchmark) | 0.882 | 1.9%/yr |

The pre-registered gate (>= 0.50) is passed. Because any hedge correlates with currency moves, we also checked
(post hoc) the **time-varying part**: the fund's gap minus a 50% hedge, against ours minus a 50% hedge. That
correlation is 0.55 (0.67 in 2025-26), so the rule reproduces over half of the fund's month-to-month hedging
decisions from three public sentences. The fund's implied average hedge ratio was 53%; ours was 57%.

## Hypotheses

| | Claim | Test | Verdict |
|---|---|---|---|
| H1 | Dynamic 3-signal beats a static 50% hedge | Sharpe +0.008 [-0.04, 0.05], p = 0.36 | **Not supported** |
| H2 | Adding volatility + cross-asset signals helps | -0.005 [-0.04, 0.03], p = 0.60 | **Not supported** |
| H3 | A disclosed signal alone beats static 50% (Holm) | rate +1.1%/yr (p_holm 0.40), momentum -0.2%, value -0.9% | **Not supported** |
| sec. | Dynamic 3-signal vs unhedged | Sharpe +0.13 [-0.01, 0.28], p = 0.048 | better than unhedged |
| sec. | Dynamic 3-signal vs static 100% | -0.12 [-0.29, 0.02] | worse than fully hedged |

## Hedged-EAFE Sharpe (test 2017-24)

| Rule | Return/yr | Vol | Sharpe [Lo 95% CI] | Max DD | Avg hedge |
|---|---|---|---|---|---|
| Unhedged | 5.4% | 15.8% | 0.34 [-0.35, 1.03] | -28.4% | 0% |
| Static 50% | 6.3% | 13.8% | 0.46 [-0.24, 1.15] | -22.0% | 50% |
| Static 100% | 7.3% | 12.4% | 0.59 [-0.11, 1.28] | -20.8% | 100% |
| **Dynamic 3-signal** | 6.3% | 13.5% | 0.47 [-0.23, 1.16] | -21.8% | 57% |
| Dynamic 5-signal | 6.3% | 13.6% | 0.46 [-0.23, 1.16] | -22.1% | 52% |

The real ETFs agree. Over the same 96 months the fund's Sharpe was 0.44 against 0.28 for its unhedged twin
(+0.16; our model says +0.13 vs unhedged), and the iShares fully hedged EAFE ETF beat both (0.63).

## What we learned

1. **The disclosed rule is reproducible from the prospectus alone.** A 0.92 correlation and a 1.6% tracking error
   to a live fund with no access to its methodology document.
2. **Its signals did not beat a neutral 50% hedge out of sample.** The dynamic rule lands almost exactly on the
   static 50% line in every period. What it does deliver is risk reduction: 2.3 pp less volatility and 6.6 pp less
   drawdown than unhedged. It was worse than all three static hedges in 1 of the 8 test years
   (`results/tables/regret_test.csv`).
3. **2017-24 rewarded hedging everything,** because US rates were above every foreign rate, so hedging *earned*
   carry while the dollar rose. The rate signal alone (96% hedged on average) matched static 100%. A rule cannot
   beat the best static hedge in a period dominated by one carry regime.
4. **More signals did not help.** Volatility and cross-asset votes (our extension) added cost and nothing else.

## Recent period (2025-01 to 2026-10, 22 months; reported only)
The dollar fell, and unhedged won on returns (17.0%/yr vs 14.9% for static 100%), the regime the rule is designed
for. Too short to test anything.

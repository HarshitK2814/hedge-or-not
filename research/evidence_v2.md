# P6 evidence for v2: what industry does about currency hedging

Checked 2026-10-29. Every link below returned content when fetched (SEC needs a declared User-Agent header). Dropped as dead or blocked to bots: WisdomTree blog PDFs, Morningstar articles, and SSRN abstract 5047797 (403; Quantpedia's summary of it is used instead). Section 1 states the hedge-ratio benchmark.

## Benchmark answer: which hedge ratio does industry use?

Static ratios are the benchmark, split by asset class:

- **Bonds: about 100% hedged.** Campbell, Serfaty-de Medeiros and Viceira find the risk-minimising hedge for a global bond investor is close to a full hedge. Vanguard's rule of thumb is to hedge bond exposures.
- **Equities: unhedged, or a static partial hedge (0% to 50%).** Vanguard says to leave most foreign equities unhedged. The 50% hedge is a convention, not a derived optimum. We found no industry source that derives it.
- **Risk-based alternative: minimum-variance ratio.** This is the academic standard, and the dynamic min-variance strategy is a tested comparator in the Quantpedia-summarised paper below.
- **Regret-minimising: not found in any industry source.** It is an academic idea. Our v1 "static 50% vs fund" comparison is therefore a fair industry-style benchmark. v2 should add static 100%, static 0% and min-variance as peers.

## Sources

| Source | Type | One-line finding | Link |
|---|---|---|---|
| Campbell, Serfaty-de Medeiros, Viceira (2010), Global Currency Hedging, J. Finance | Academic | Min-variance hedge for bond investors is near full; little case for changing positions on rate differentials. | https://www.nber.org/papers/w13088 |
| Same paper, Harvard DASH copy | Academic | Equity investors do best with a long CAD/USD-type position as a hedge, not a blanket hedge. | https://dash.harvard.edu/server/api/core/bitstreams/7312037c-7829-6bd4-e053-0100007fdf3b/content |
| Du, Tepper, Verdelhan (2018), Deviations from CIP, J. Finance (NBER 23170) | Academic | CIP deviations persist after credit and transaction costs; widest at quarter-end. | https://www.nber.org/papers/w23170 |
| Du, Tepper, Verdelhan, MIT DSpace record | Academic | Same paper; links the deviation to bank balance-sheet regulation. | https://dspace.mit.edu/handle/1721.1/128481 |
| Vanguard, The FX dimension (multi-asset hedging) | Asset manager | Rule of thumb: hedge bonds, leave most foreign equities unhedged. The page gives no ratios or cost analysis. | https://www.vanguard.co.uk/professional/research/the-fx-dimension-evaluating-currency-hedging-for-global-multi-asset-portfolios |
| MSCI (Katiyar, Doole, Wei, April 2016), Currency Hedging: Adapting to Volatility | Index provider | Static hedges beat unhedged on risk-adjusted return; a Value/Momentum/Carry/Volatility dynamic hedge beat static in its sample. | http://www.msci.com/research-and-insights/paper/currency-hedging-adapting-to-volatility |
| Quantpedia summary of "The Best Strategies for FX Hedging" (Aug 2025) | Practitioner paper, secondary | Max-Carry rule beat full static hedging in nearly all developed markets (over 100 bp/yr in 9 of 14); the carry-based optimal hedge often had the top Sharpe; min-variance had the lowest volatility. The page does not discuss costs. | https://quantpedia.com/the-best-strategies-for-fx-hedging/ |
| WisdomTree Trust N-CSR, FY to 2026-03-31 (SEC) | Regulatory | Hedged funds hold rolling one-month forwards. Average month-end notional for International Hedged Quality Dividend Growth Fund was about $1.06bn (deliver USD) and $3.44bn (receive USD). | https://www.sec.gov/Archives/edgar/data/1350487/000121465926007194/dev33126ncsr.htm |
| WisdomTree DDWM 497K (already in `research/sources/`) | Regulatory | Hedge ratio 0 to 100% per currency, monthly reset, three equal-weight signals (rate differential, momentum, value). | `research/sources/ddwm_497k_2016.htm` (local) |
| Pictet Research Institute, Currency hedging: when one size doesn't fit all | Asset manager | Compares static full/no hedge with dynamic min-variance; the page text was not readable by our fetcher, so the claim rests on the search snippet only. Treat as unverified. | https://www.pictet.com/lu/en/about/pictet-research-institute/publications-and-press/currency-hedging-when-one-size-doesnt-fit-all |
| GitHub `ayondey47/fx-forward-pricing` (MIT) | Public code | CIP forward rate, forward points, annualised premium and implied rate; stdlib only, pytest on 3.10 to 3.12. | https://github.com/ayondey47/fx-forward-pricing |
| GitHub `BenyaminSuicmez/FX_Carry_Trade_Backtest` | Public code | G10 carry backtest; costs 1 bp per quarterly rebalance plus a 30 bp funding spread; Yahoo spot and OECD rates. Our P6 uses the same data class. | https://github.com/BenyaminSuicmez/FX_Carry_Trade_Backtest |

Forums: Reddit, Bogleheads and Quant StackExchange threads were searched. We found only a mirror of one Quant SE question, with no readable accepted answer, and no Bogleheads thread. The retail view is not evidenced here, so nothing is claimed from forums.

## What industry does that v1 does not

1. Treats bonds and equities differently. v1 hedges only an equity basket. (Vanguard; Campbell et al.)
2. Reports a min-variance hedge as the risk benchmark, next to static 0/50/100. v1 compares only static 50%.
3. Judges hedges on the forward premium. The "cost" of a hedge is the interest-rate differential, so a carry-based rule is the natural dynamic baseline. v1 uses carry only inside a vote.
4. Reports forward notional and roll volume (the N-CSR shows average notional in billions). v1 states "typical institutional spreads" as an assumption (L5) and does not measure roll volume.
5. Allows for the CIP basis. Observed forwards deviate from the OECD-rate theory, most at quarter-end (Du et al.). v1 uses 3-month OECD rates as a stand-in for 1-month forward rates (L1).

## v2 decisions

| Item | Tag | Reason |
|---|---|---|
| Add static 100%, static 0% and static 50% as the benchmark set, and report the fund against all three | **copy** | Matches how industry frames hedging (Vanguard, MSCI, Quantpedia paper). |
| Add a rolling min-variance hedge ratio (Campbell et al. style) as a risk benchmark | **copy** | Academic and practitioner standard. Needs a covariance window set before the test, with no look-ahead. |
| Add a Max-Carry rule (hedge when the US rate exceeds the foreign rate) as a simple dynamic baseline | **copy** | It beat full hedging in the cited paper. The dynamic vote must beat this to count as skill. |
| Keep the three-signal vote as the replication of the fund, not as a claim of superiority | **copy** | v1 captured only about half of the time-varying part (corr 0.55, L4). |
| Replace OECD 3-month rates with 1-month forward-implied rates where free data exists, otherwise bound the error with a stated CIP-basis sensitivity (0, 10, 25 bp) | **fix** | L1; Du et al. show the basis is not zero. |
| Report roll cost as forward points, per currency and month, plus an explicit bid-ask on each monthly roll | **fix** | Costs are the central argument for or against hedging. L5 is currently an assumption. |
| Split results into a USD-rising and a USD-falling regime, and label every period after 2017 `seen period (v1 reported it)` | **fix** | L6, and the roadmap rule. |
| Add a bond sleeve (even a synthetic one) to test the "hedge bonds, not equities" rule | **fix** | Only a bond sleeve tests the rule where industry says it matters. |
| Regret-minimising hedge ratio as a headline benchmark | **reject** | No industry source uses it; keep only as an optional appendix. |
| Claiming the dynamic fund beats static on vendor numbers (e.g. "100 to 150 bp") | **reject** | Vendor claim, not independently tested, and its page was blocked from our fetcher. |

## Rejected ideas

- **Copying the carry-trade repos' cost model.** The 1 bp per rebalance is too low for monthly forward rolls with spreads, so P6 keeps its own measured-spread approach.
- **Using Pictet's findings.** Its text could not be read, so it supports no claim here.
- **Using forum opinion as evidence.** None found; see above.

# Limitations

* **L1 Rates are a proxy.** OECD monthly 3-month interbank rates (lagged one month) stand in for the 1-month
  forward-implied rates the index uses. Fine for G10 carry; wrong by a few bp around rate moves and quarter-ends.
* **L2 PPP vintage.** World Bank PPP is today's vintage, not as first published; we only lag it two years. The
  euro fair value is a GDP-weighted composite of five members, because no aggregate is available for free.
* **L3 Equity leg.** EFA (cap-weighted EAFE) rather than the fund's dividend-weighted index; nine currencies
  (HKD, SGD and ILS, about 5% of the basket, are dropped).
* **L4 Vote rules are our reading** of three sentences. The index provider's full methodology may weight signals
  by conviction or differ in timing; the 0.55 correlation on the time-varying part says we capture about half.
* **L5 Costs** are typical institutional G10 spreads, not measured.
* **L6 One regime.** The test is dominated by a positive USD carry, which makes static 100% hard to beat; the
  result may not generalise to a falling-dollar decade.
* **L7 Post-hoc analysis** (the time-varying replication check, fund-level Sharpes) is labelled as such and was
  not part of the pre-registration. After the test, a mislabelled row in the replication table
  ("unhedged(=0)" was the static-50% book) was renamed; no numbers changed.

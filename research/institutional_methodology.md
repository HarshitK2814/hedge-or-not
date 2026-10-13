# What the fund discloses (Layer A)

Source: **Form 497K summary prospectus**, WisdomTree Dynamic Currency Hedged International Equity Fund (DDWM),
5 January 2016 (CIK 1350487, accession 0001193125-16-421050). Saved as `research/sources/ddwm_497k_2016.htm`.
Quotes are verbatim.

| # | Quote | What we take from it |
|---|---|---|
| Q1 | "The Index dynamically hedges currency fluctuations in the relative value of the applicable foreign currencies against the U.S. dollar, ranging from a 0% to 100% hedge." | The hedge ratio lies between 0% and 100%, set per currency. |
| Q2 | "The Index determines and adjusts the hedge ratios on such foreign currencies on a monthly basis using three equally-weighted, quantitative signals: interest rate differentials, momentum, and value." | Monthly reset; three signals, equal weights. |
| Q3 | "Interest rate differentials are determined by measuring the difference in interest rates, as implied in one month foreign exchange (FX) forwards, between each currency and the U.S. dollar." | Carry signal: hedge when the US rate is above the foreign rate (hedging then earns the forward premium). |
| Q4 | "Momentum is the relative price momentum of the foreign currency as determined by comparing two moving average signals on the historically observed U.S. dollar spot rates over 10 and 240 business day periods." | Momentum: 10-day vs 240-day moving average of the spot rate. |
| Q5 | "Value is the relative purchasing power of the foreign currency as determined with reference to the foreign currency spot rate over 20 business days as compared to the latest purchasing power parity (PPP) numbers as published by the Office of Economic Cooperation and Development (OECD)." | Value: 20-day average spot vs PPP fair value. |
| Q6 | "This approach is designed to limit losses related to foreign currencies as such currencies depreciate against the U.S. dollar while participating in gains related to foreign currencies when such currencies appreciate against the U.S. dollar" | The claim we test: better than a static hedge. |
| Q7 | "The Index applies an applicable published currency forward rate to such foreign currencies to hedge" | Hedges are one-month forwards, so the carry enters the P&L. |

## The three layers

* **A. Disclosed:** Q1-Q7. Signal inputs, windows, equal weights, monthly reset, 0-100% range.
* **B. Our reconstruction:** each signal is a 0/1 vote; the hedge ratio is the share of "hedge" votes (0, 1/3, 2/3,
  100%). OECD 3-month interbank rates stand in for forward-implied rates (covered interest parity; the 497K uses
  1-month forwards). PPP comes from the World Bank (it reproduces the OECD-Eurostat figures for these countries),
  lagged two years to respect publication dates. Currency weights are MSCI EAFE's (approx.) and the equity leg is
  the unhedged iShares MSCI EAFE ETF, because the fund's own dividend-weighted index is not free. Per-signal vote
  rules are our reading of Q3-Q5, not the index provider's methodology document.
* **C. Extensions (not disclosed):** a volatility signal (hedge when 21-day FX volatility exceeds its 1-year
  median) and a cross-asset signal (hedge risk-on currencies after a 3-month equity fall, safe havens after a rise),
  giving a 5-signal model.

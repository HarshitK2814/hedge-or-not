# Experiment log (append-only)

Development = 2001-09 to 2010-12; validation = 2011-2016. The test period was locked for all of these.

| ID | Date | Period | What | Why | Result |
|---|---|---|---|---|---|
| EXP-000 | 2026-10-13 | - | Data audit: FRED H.10 spot (9 ccys), OECD 3m rates (JPY backfilled with the call rate before 2002), World Bank PPP, Yahoo ETFs | - | World Bank has no euro-area PPP. |
| EXP-001 | 2026-10-13 | - | EUR PPP = fixed GDP-weighted geometric mean of DE/FR/IT/ES/NL | missing aggregate | Fair value ~1.5 USD/EUR in 2024, close to OECD's published EUR PPP. |
| EXP-002 | 2026-10-13 | dev+val | First full run: 3-signal and 5-signal rules, statics, single signals | baseline | Dynamic minus static-50 Sharpe +0.04 (dev), +0.05 (val). 5-signal -0.01 / -0.04 vs 3-signal. Momentum is the best single signal in both. |
| EXP-003 | 2026-10-13 | val | Mechanics check: static 100% vs HEFA - EFA | is the overlay arithmetic right? | corr 0.978, TE 1.3%/yr (35 months). DBEF - EFA corr 0.68 (Yahoo DBEF history is noisy; not used as a gate). |
| - | 2026-10-13 | - | **Frozen**; no parameter was tuned (all windows come from the 497K or were fixed a priori). | | |
| EXP-004 | 2026-10-13 | **test** | Locked test run (hash 251c14117a04) | pre-registered | H1, H2, H3 not supported; gate passed (0.919). See results.md. |
| EXP-005 | 2026-10-13 | test (post hoc) | Replication of the time-varying part (fund gap - 50% hedge vs ours - 50% hedge); fund-level Sharpes | a constant hedge already correlates 0.88 with the fund gap | 0.55 (test), 0.67 (recent). DDWM 0.44 vs DWM 0.28 Sharpe. Labelled post hoc. |
| EXP-006 | 2026-10-13 | - | Renamed mislabelled replication row ("unhedged(=0)" -> "static50") | cosmetic | no numbers changed |

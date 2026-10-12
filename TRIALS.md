
## Katz-improve family (target: reverse / petitioner wins) — see KATZ_PREREG.md
Declared K00-K09 on 2026-10-11 01:50 PT, none run yet. Prior trials counted: original rerun, score_hist, modern-only, clean, clean strict, stacked (6). N = 16.
| 2026-10-11 20:53 | K00-K09 | see katz/eval/run_meta_*.json | KATZ_PREREG population | selection 1990-2014 (Brier) | see katz/eval/selection_1990_2014.csv | | Selected K07; Holm p=0.0013 vs K00; PBO 0.00; K08 excluded (Oyez transcript coverage 88.1% < 90%), still counted. N=16. 2015-2025 = seen/informational. |
| 2026-10-11 22:00 | K10 (declared) | | K07 minus features unobservable for pending rows (Amendment 1) | | | | N=17 |
| 2026-10-12 10:40 | K10 | done | 1990-2014 Brier 0.2052 vs K07 0.2023 per-term mean; better 7/25, sign p=0.043 (K10 worse); K07 stays selected | | | | N=17 |
| 2026-10-12 11:10 | K11-K15 (declared, Amendment 2) | | K11 missingness-aware RF; K12 isotonic(K10); K13 K10+Masse-live log-odds; K14 model+Kalshi 50/50 (forward only); K15 hierarchical justice logistic (MPS) | | | | N=22 |
| 2026-10-12 15:21 | K11-K15 results | | 1990-2014 mean term Brier: K10 0.2052, K11 0.2063, K12 0.2069, K13 0.2049 (lowest; 15/25 terms, p_holm 0.85), K15 0.2125 (worse, p 0.015). PBO 0.257. No challenger passes -> K10 stays. Holdout (single read): K10 0.1889 vs always-rev 0.1993; Kalshi-36 K10 0.1929 vs Kalshi 0.0805 | | | | N=22 |

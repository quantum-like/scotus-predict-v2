
## Katz-improve family (target: reverse / petitioner wins) — see KATZ_PREREG.md
Declared K00-K09 on 2026-10-11 01:50 PT, none run yet. Prior trials counted: original rerun, score_hist, modern-only, clean, clean strict, stacked (6). N = 16.
| 2026-10-11 20:53 | K00-K09 | see katz/eval/run_meta_*.json | KATZ_PREREG population | selection 1990-2014 (Brier) | see katz/eval/selection_1990_2014.csv | | Selected K07; Holm p=0.0013 vs K00; PBO 0.00; K08 excluded (Oyez transcript coverage 88.1% < 90%), still counted. N=16. 2015-2025 = seen/informational. |
| 2026-10-11 22:00 | K10 (declared) | | K07 minus features unobservable for pending rows (Amendment 1) | | | | N=17 |
| 2026-10-12 10:40 | K10 | done | 1990-2014 Brier 0.2052 vs K07 0.2023 per-term mean; better 7/25, sign p=0.043 (K10 worse); K07 stays selected | | | | N=17 |
| 2026-10-12 11:10 | K11-K15 (declared, Amendment 2) | | K11 missingness-aware RF; K12 isotonic(K10); K13 K10+Masse-live log-odds; K14 model+Kalshi 50/50 (forward only); K15 hierarchical justice logistic (MPS) | | | | N=22 |

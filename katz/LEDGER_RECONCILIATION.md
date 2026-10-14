# Trial ledger reconciliation (draft, 2026-10-13 20:25 PT; corrected 21:50 PT, Claude on branch katz-claude-2). Paper only.
Three parties registered amendments in parallel on 2026-10-13, none on GitHub at this time: the box agent (its machine; state read from
~/scotus-predict-rerun/katz/STATUS_K16.md and ~/scotus-predict-rerun/katz-a6/STATUS_K24.md), a separate agent working on its own branch named
katz-claude (STATUS_K20.md), and Claude (this branch). Numbers collided (several "Amendment 5"s and "Amendment 6"s; K20/K21 and K25 meant
different models), so Claude's registration uses its own namespace (Amendment C1, trials KC1-KC4). This file lists every trial that counts
toward the deflated Sharpe, so that all families can use one N. **Total N = 37.** Proposal: keep one shared ledger (TRIALS.md on katz-improve) and give each agent a disjoint ID namespace.

| # | trial(s) | registered in | commit / branch | status (as of 21:50 PT) | results |
|---|---|---|---|---|---|
| 1-6 | prior runs: original rerun, score_hist, modern-only, clean, clean strict, stacked | KATZ_PREREG (counted) | katz-improve | done before the K-series | ~/scotus-predict-rerun (rerun, clean/, stacked/, ...) |
| 7-16 | K00-K09 (K03-K05 calibration/aggregation variants; K08 excluded by the 88.1% transcript coverage rule, counted) | KATZ_PREREG | 739c4c8, katz-improve | done; K07 selected on 1990-2014 | katz/eval/ |
| 17 | K10 (K07 minus pending-blank features) | Amendment 1 | f29092c | done; incumbent, live (v2 freeze) | katz/eval_k10/ |
| 18-22 | K11 missingness-aware, K12 isotonic, K13 Katz+Masse, K14 model+Kalshi blend (forward only), K15 hierarchical justice | Amendment 2 | d7acabf | done; K10 stays (PBO 0.257) | katz/eval_k11/ |
| 23-26 | K16 OA counts, K17 OA sentiment, K18 SG position, K19 post-argument | Amendment 3 | 59b4d24; results 02c7d81 | K18/K19 evaluated (K10 stays, PBO 0.629); K16/K17 excluded by the gate (87.1%), then run under the box's "Amendment 4 (waiver)". Latest box family (N = 32, eval_k2425): K16 0.1979 (p_holm 0.303, DSR 0.960), K17 0.1984 (0.146, 0.949), K18 0.2032, K19 0.2022 vs K10 0.2052 (all cases/reverse, 1990-2014) -> K10 stays | ~/scotus-predict-rerun/katz/eval_k16, eval_k1617; katz-a6/eval_k2425 |
| - | (no new trial) | "Amendment 4 (waiver)", box | 51f5557 (box) | waiver of the 90% transcript rule for K16/K17 | STATUS_K16.md |
| 27-30 | K20 advocates, K21 supremecourt.gov docket features, K22 argued/US-party fixes + issue-code drop, K23 pending hand-coding | "Amendment 5" by a separate agent (N = 30 there) | fe89cec, its own branch named katz-claude | dispatched 17:33; no results (a run was aborted; results/K21 holds only an input file) | ~/scotus-predict-rerun/katz/k20, k21, k22 (features) |
| - | (aborted, counted once as K24/K25) | box "Amendment 5" | b28a8b9 (box) | oral-argument K20/K21 started 19:24, aborted 19:28 over the ID clash, no results; re-registered as K24/K25 | STATUS_K16.md |
| 31-32 | K24, K25 (oral-argument features, companion coverage rule 97.5%; strict 88.1%) | box "Amendment 6" | bf8d3ab (box) | done; evaluated 20:35: K24 0.1972, K25 0.1983 (p_holm 0.146; DSR N32 0.926/0.941; PBO 0.186) -> K10 stays | ~/scotus-predict-rerun/katz-a6/eval_k2425 |
| 33-36 | KC1 strict base, KC2 + point-in-time ideal points, KC3 + circuit composition, KC4 both (argued cases, petitioner-wins label) | Amendment C1 (Claude) | 08431bd (as "Amendment 6", K25-K28) -> b821c1e (renamed before any run), branch katz-claude-2 | done: no challenger beats K10s; holdout read once (d574861); forward frozen (13dce9a) -> K10 stays | katz/results/claude/, katz/CLAUDE_REPORT.md |
| 37 | K10s (K10's forest through Amendment C1's stage 2; comparator, not selectable, counted to be conservative) | Amendment C1 | b821c1e | done (WF 0.2208, CPCV 0.2199) | katz/results/claude/ |

Notes
- Every trial counts in N whether or not it ran, passed a gate, or was excluded (user rule 2). Excluded-but-counted: K08; K16/K17 under
  Amendment 3 (later run under the waiver; counted once); the box's aborted b28a8b9 runs are the same trials as K24/K25 (counted once).
- K16/K17 (waiver) and K24/K25 (companion rule) stand only if coverage below the user's 90% per-docket transcript rule (strict count 88.1%) is accepted.
- The 2015-2025 holdout and the 36 settled Kalshi markets were read under Amendment 2 (K10); every later read is SEEN. Amendment C1 reads
  them once for KC1-KC4/K10s with a crash-safe lock.
- Branch names: the separate agent's branch is called katz-claude (fe89cec); Claude's is katz-claude-2 (pushed). None touches master or katz-improve.

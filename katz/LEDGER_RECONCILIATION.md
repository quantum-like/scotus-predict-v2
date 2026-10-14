# Trial ledger reconciliation (draft, 2026-10-13 20:25 PT, Claude on branch katz-claude-2). Paper only.
Two agents registered amendments in parallel on 2026-10-13: the "box" agent (commits made on its own machine, not on GitHub at this
time; state read from ~/scotus-predict-rerun/katz/STATUS_*.md and ~/scotus-predict-rerun/katz-a6/STATUS_K24.md) and Claude (this branch).
Numbers collided (two "Amendment 5"s, two "Amendment 6"s; K25 meant two different models), so Claude's registration moved to its own
namespace (Amendment C1, trials KC1-KC4). This file lists every trial that counts toward the deflated Sharpe, so that both families can
use one N. **Total N = 37.** Proposal: keep one shared ledger (TRIALS.md on katz-improve) and give each agent a disjoint ID namespace.

| # | trial(s) | registered in | commit / branch | status (as of 20:25 PT) | results |
|---|---|---|---|---|---|
| 1-6 | prior runs: original rerun, score_hist, modern-only, clean, clean strict, stacked | KATZ_PREREG (counted) | katz-improve | done before the K-series | ~/scotus-predict-rerun (rerun, clean/, stacked/, ...) |
| 7-16 | K00-K09 (K03-K05 calibration/aggregation variants; K08 excluded by the 88.1% transcript coverage rule, counted) | KATZ_PREREG | 739c4c8, katz-improve | done; K07 selected on 1990-2014 | katz/eval/ |
| 17 | K10 (K07 minus pending-blank features) | Amendment 1 | f29092c | done; incumbent, live (v2 freeze) | katz/eval_k10/ |
| 18-22 | K11 missingness-aware, K12 isotonic, K13 Katz+Masse, K14 model+Kalshi blend (forward only), K15 hierarchical justice | Amendment 2 | d7acabf | done; K10 stays (PBO 0.257) | katz/eval_k11/ |
| 23-26 | K16 OA counts, K17 OA sentiment, K18 SG position, K19 post-argument | Amendment 3 | 59b4d24; results 02c7d81 | K18/K19 evaluated (K10 stays, PBO 0.629); K16/K17 excluded by the gate (87.1%), then run under the box's "Amendment 4 (waiver)" and evaluated: K16 0.1979, K17 0.1984 vs K10 0.2052 (1990-2014), p_holm 0.13/0.06, PBO 0.0 -> K10 stays | ~/scotus-predict-rerun/katz/eval_k16, eval_k1617 |
| - | (no new trial) | "Amendment 4 (waiver)", box | 51f5557 (box) | waiver of the 90% transcript rule for K16/K17 | STATUS_K16.md |
| 27-30 | K20 advocates (Oyez), K21 supremecourt.gov docket features, K22 argued/US-party fixes + issue-code drop, K23 pending hand-coding | "Amendment 5", box (N = 30 there) | fe89cec (box), its own branch named katz-claude | dispatched 17:33; job_k2021.sh terminated; a results/K21 folder exists, no K20 | ~/scotus-predict-rerun/katz/results/K21 |
| 31-32 | K24, K25 (oral-argument features, companion coverage rule 97.5%) | "Amendment 6", box | bf8d3ab (box) | K24 done 20:02; K25 running | ~/scotus-predict-rerun/katz-a6/ |
| 33-36 | KC1 strict base, KC2 + point-in-time ideal points, KC3 + circuit composition, KC4 both (argued cases, petitioner-wins label) | Amendment C1 (Claude) | 08431bd (as "Amendment 6", K25-K28) -> b821c1e (renamed before any run), branch katz-claude-2 | KC1 forest queued behind the box's K25; ideal points done (70d024b) | katz/results/claude/ (after the evaluation) |
| 37 | K10s (K10's forest through Amendment C1's stage 2; comparator, not selectable, counted to be conservative) | Amendment C1 | b821c1e | runs with the KC evaluation | katz/results/claude/ |

Notes
- Every trial counts in N whether or not it ran, passed a gate, or was excluded (user rule 2). Excluded-but-counted: K08; K16/K17 under
  Amendment 3 (later run under the waiver; counted once).
- K16/K17 results stand only if the waiver of the user's rule 5 (>= 90% per-docket transcript coverage with each justice named) is accepted.
- The 2015-2025 holdout and the 36 settled Kalshi markets were read under Amendment 2 (K10); every later read is SEEN. Amendment C1 reads
  them once for KC1-KC4/K10s with a crash-safe lock.
- Branch names: the box's branch is also called katz-claude (fe89cec); Claude's is katz-claude-2. Neither touches main or katz-improve.

# REVIEW: scotus-predict-v2 (src/, notebooks) + our rerun.py and score_pending.py
Paper only. Branch katz-improve (from master e34e372). Severity: HIGH = changes results or Kalshi use materially; MED = biases or
breaks reproducibility; LOW = hygiene. Paths: src/ = this repo; rerun.py and pending_inputs/score_pending.py =
/workspace/recovered-repos/scotus-rerun/. The notebooks (src/model_growing_random_forest_1.ipynb, *_cv_5, baseline_*.ipynb) run the
same library calls; rerun.py is a line-by-line port of model_growing_random_forest_1, so findings on rerun.py apply to it too.

## Leakage
| # | Sev | Where | Finding | Fix |
|---|---|---|---|---|
| L1 | HIGH | src/legacy_model.py:179-189, 334-335, 379-380 | `decision_month_*` and `decision_delay` come from `dateDecision`: known only after the decision. Kept in the published model and in rerun.py:55 / score_pending.py:58 (only term_/natural_court are dropped). | Drop every dateDecision/dateRearg-derived feature (done in clean/ run: 2015-2025 case acc 0.7007 vs 0.7019, n.s.). |
| L2 | HIGH | src/legacy_model.py:131-143, 187-189; score_pending.py:57 | The -1 placeholder: missing dates map to month -1 and delay -1. In training, -1 marks rare odd rows (no date: DIGs, per curiams, legacy gaps); every pending case gets -1, so pending rows are out-of-distribution and land in the "odd case" leaves. Biases pending P(reverse). | Same as L1 (remove the features); never use -1 as a real category for something unknown at prediction time; add an explicit "missing" indicator only for pre-decision fields. |
| L3 | MED | src/legacy_model.py:210-213, 348-351 | `issue`, `issueArea`, `lawType`, `lawSupp` are coded by SCDB from the opinion. Partly post-decision; for pending cases they are hand-coded from the QP, a different process. | Pre-register a strict variant without them (clean strict: 0.6983 case acc 2015-2025, -0.2 pt, n.s.); for live use, code pending cases the same way or drop. |
| L4 | MED | src/legacy_model.py:170-172, 329-332; rerun.py:55 | `term_raw` and `natural_court_raw` stay as numeric features (only the one-hots are dropped). A forest cannot extrapolate a trend, so for a new term/court they act like "latest seen", and rebuild-on-court-change (rerun.py:86-88) makes court identity drive which forest is used. | Drop both raw columns in a trial; keep court change only as a rebuild trigger. |
| L5 | MED | score_pending.py:92 | Isotonic calibration fit on the 2015-2025 cases whose accuracy is then reported (in-sample), with clip 0.02-0.98; few steps -> quantized P (many pending cases at the same value, e.g. 0.463). Fine for 2026 predictions in time order, but the 2015-2025 calibration quality is overstated. | Calibrate on prior terms only (rolling, e.g. last 10 terms), report calibration out-of-sample; prefer Platt when < ~500 cases. |
| L6 | LOW | src/legacy_model.py:119-123, 192-213 | One-hot vocabularies built from the full dataset (incl. future terms and pending rows). No label leak, but column sets change when rows are added (noted in score_pending.py:8). | Fit encoders on training terms only, or fix the vocabulary from SCDB codebooks. |
| L7 | LOW | src/legacy_model.py:231-236, 260-263 | Lagged justice/court features use all of term t-1, including cases decided after term t opened (held over / reargued). Small. | Embargo: use only t-1 rows decided before Oct 1 of t (as in direction-improve). |

## Bugs
| # | Sev | Where | Finding | Fix |
|---|---|---|---|---|
| B1 | HIGH | rerun.py:82,92; score_pending.py:69,73 | `class_weight = training class frequencies` UP-weights the majority class (reverse) instead of balancing; the forest calls reverse for ~97-99% of cases, so the model is close to always-reverse. | Trial: class_weight=None and "balanced"; then calibrate. |
| B2 | MED | rerun.py:151; score_pending.py:90,94 | Case call = mean of predicted-reverse votes >= 0.5, so a 4-4 tie (recusal) is called reverse. A tie affirms by operation of law. | Use > 0.5, or P(majority) from per-justice probabilities (Poisson-binomial) with ties = affirm. |
| B3 | MED | rerun.py:147-152 | Cases with outcome -1 (DIG, dismissals, uncodable) are scored as "not reversed" and kept in case accuracy (842 vs 800 cases; score_hist drops them). | Report both; Kalshi resolution rules decide which is right per market. |
| B4 | MED | src/legacy_model.py:241-242, 267-269 | Mean of `direction` includes code 3 (unspecifiable), so "previous/cumulative direction" mixes in a non-ordinal code. | Use only direction in {1,2}. |
| B5 | LOW | src/legacy_model.py:88-94 | `get_outcome` rebuilds the outcome map on every row (`SCDB_OUTCOME_MAP` assigned as a local) and `if not outcome_map` raises if a DataFrame is passed. Slow (apply over ~270k rows), latent error. | Build the map once at module level; test `is None`. |
| B6 | LOW | src/legacy_model.py:50-51 | `.loc[1, codes]` with NaN `lcDisposition` raises KeyError on modern pandas (patched in our copy). | fillna(-1) with an explicit -1 column. |
| B7 | LOW | src/legacy_model.py:130-133, 140-143, 147-157 | Bare `except:` hides real errors (e.g. a dtype change makes every date None silently). | Catch specific exceptions; count failures. |
| B8 | LOW | src/legacy_model.py:224-304 | O(justices x terms) boolean masks over the full frame: the slowest part of preprocessing (~minutes). | groupby + shift. |
| B9 | LOW | src/legacy_model.py:421-424 | include_direction=False removes every column containing "direction", including the lower-court direction diffs. Intended? The published model uses True. | Name the drop list explicitly. |

## Reproducibility and dependencies
| # | Sev | Where | Finding | Fix |
|---|---|---|---|---|
| R1 | MED | rerun.py:62,91-94; score_pending.py:61,73 | Only `numpy.random.seed(0)`; the forest has no `random_state` and uses n_jobs, so results depend on global RNG state and call order (e.g. adding baseline fits changes trees). | random_state=0 on every estimator; log seeds. |
| R2 | MED | rerun.py:54; score_pending.py:57 | float16 features: ~3 significant digits, so rates like cumulative agreement collapse onto a coarse grid; ties change splits; float16 vs float32 changed direction-run accuracy (0.646 -> 0.675 together with seed/embargo). | float32 (memory ~2x, fine at n_jobs=-1 on 32 GB? check: peak ~8 GB at float16 -> ~12-14 GB). |
| R3 | MED | requirements.txt:1-50 | Pinned 2016 stack (pandas 0.18, sklearn 0.17.1, numpy/scipy dev builds) is not installable; we run Python 3.14 / sklearn 1.9 / pandas 3.0 with patches. statsmodels imported but unused (src/legacy_model.py:14). | New lock file; drop statsmodels; record versions in run_meta. |
| R4 | LOW | src/legacy_model.py:28-29 | Hard-coded SCDB release 2015_01 path. | CLI argument (as rerun.py does). |

## Kalshi-use biases
| # | Sev | Where | Finding | Fix |
|---|---|---|---|---|
| K1 | HIGH | score_pending.py:92-95 | Forecast P = isotonic(mean justice reverse score), while the call uses the fraction of predicted votes: two different aggregates. Kalshi needs P(petitioner wins) = P(majority reverses), not the mean score. | Poisson-binomial P(>= 5 of 9 reverse, ties affirm) from calibrated per-justice P, then case-level calibration on prior terms. |
| K2 | HIGH | L1/L2 above | Pending cases carry -1 date placeholders: their scores are systematically different from historical scoring. | Fix L1/L2 before any live use. |
| K3 | MED | market mapping (market_map.csv wording_match) | "Reverse" in SCDB includes vacate/remand and partial reversals; Kalshi YES may require the petitioner to "win" by its own rules; DIGs/dismissals resolve differently. | Per-market resolution map; drop or flag "partial/looser" matches. |
| K4 | MED | B1 | Near-always-reverse calls + coarse calibration give large apparent NO edges on most markets (clean table) that are artifacts. | B1 + K1 + calibrated Brier on prior terms before quoting edges; include fees ceil(0.07 C P(1-P)) in edge. |
| K5 | LOW | score_pending.py:73 | Recusals (n_j = 8, e.g. 25-170) handled implicitly; tie rule B2 matters there. | Explicit recusal handling. |

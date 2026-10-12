# AUDIT_ML4T: K07 (selected) and K10 (live variant) vs the ML4T skills (2026-10-12, paper only)
Skills read before acting: ml-trading-strategy-research/SKILL.md (standing rule, Steps 6/7/10, hardware, pitfalls, forecasting setups),
scotus/SKILL.md, and official ml4t-skills (commit f0ea01919e0c): lookahead-bias, point-in-time, data-leakage, purging-embargo, cpcv,
walk-forward-cv, feature-validation, feature-selection, information-coefficient, model-validation, backtest-overfitting,
deflated-sharpe, meta-labels, multi-agent-forecasting, monitoring-alerting, drift-detection, production-readiness.
There is NO official "conformal" or "calibration" skill in the 61 copies; calibration/conformal guidance taken from SKILL.md Step 7
and R2P 8.4 (named decision, not a skill).
Adaptation (book silent on classification of court cases, recorded as named decision): "returns" = per-term Brier skill vs the
prior-rate (always-reverse) forecast; "trial" = any spec change; holdout cut by term (decision dates fall inside the term+1 window).

| # | Skill | Finding (K07 / K10) | Gap? | Addressed by |
|---|---|---|---|---|
| G1 | point-in-time, lookahead-bias | Pending rows are coded from incomplete public records: 5 pre-decision fields blank (lcDisposition 92%, lcDisagreement 100%, certReason 100%, caseOrigin 66%, lawSupp 92%) vs <=5% in training. K07 scores live rows out-of-distribution (fixed in K10 by dropping, at a small skill cost). Historical rows carry values coded AFTER the decision by SCDB (certReason, lcDisagreement read from the opinion) - an availability-date leak for any feature "known" only from the opinion. | YES | K10 (drop), K11 (missingness-aware, live-like masking on all rows) |
| G2 | lookahead-bias / point-in-time | issue / issueArea / lawType are coded by SCDB from the opinion (REVIEW.md); kept in K07/K10. K01 (strict) tested removal: worse. Residual leak risk on history -> backtest optimistic vs live. | YES (documented, not removable without loss) | reported; live-like evaluation in K11 masks only the blank fields |
| G3 | data-leakage | Calibration (Platt/iso) fit on prior 10 terms only; no full-sample scaler (RF needs none; K09 MLP standardizes on train only). OK. | no | - |
| G4 | purging-embargo | Label horizon = case decision (within term t, decided by ~July t+1). Embargo drops term t-1 rows decided >= Oct 1 of t in model training. Calibration windows (roll_cal) do NOT apply the same embargo (a few t-1 cases decided after Oct 1 t can enter). | minor YES | K11+ apply the embargo in calibration/stacking too |
| G5 | cpcv, model-validation | Only one walk-forward path; no CPCV distribution (mean/std/worst fold). Refit-CPCV for the warm-start RF is infeasible (training after test breaks the Katz method), so CPCV is done on the walk-forward OOS term blocks (CSCV, 8 groups of 3 terms, 70 combos). | YES | K11+ selection reports CSCV distribution |
| G6 | walk-forward-cv | Expanding window only; rolling-window variant never compared. | YES (open) | not run (would be another trial); recorded |
| G7 | backtest-overfitting | PBO=0.0 reported in verdict.json was computed over K00-K09 (incl. obviously worse members) and with the 2-of-N style split, not CSCV complementary halves within the selection population. | YES | K11+ PBO by CSCV within the live-valid population |
| G8 | deflated-sharpe | No DSR computed (binding gate DSR > 0.95). | YES | K11+ DSR on per-term Brier skill, N=22 |
| G9 | backtest-overfitting | 2015-2025 "sealed" holdout was already seen several times (clean, direction, stacked, K-trials informational). Not a true holdout. | YES (cannot be undone) | K11+ touch it exactly once, labelled "seen" |
| G10 | feature-validation, information-coefficient | No per-feature IC/stability, null-share (<5%) or pairwise-correlation checks. 1,180-1,409 one-hot features, many >5% null-coded. | YES | IC/null audit of the free features in K11 run log (diagnostic) |
| G11 | feature-selection | Feature drops (strict, pendfix) were decided outside CV but were rule-based (availability), not target-based -> allowed. OK. | no | - |
| G12 | model-validation | No regularized linear baseline (book Ch 11) in the live-valid set; K06 logistic was on the full feature set only. | YES | K15 (hierarchical L2 logistic) doubles as the linear baseline |
| G13 | Step 7 calibration | Platt on per-justice then case; isotonic only tested on the mean score (K04). Probabilities still compressed for pending. No reliability/ECE/sharpness reported. | YES | K12 isotonic; ECE + reliability in K11+ report |
| G14 | Step 7 conformal | No uncertainty/abstention. Split conformal assumes exchangeability (violated); must monitor coverage by term. | YES | conformal sets reported as diagnostic (not a probability model -> not a trial) |
| G15 | meta-labels | Not applicable as a gate: model fires every case (no primary "signal" subset); n of Kalshi markets (37 settled) < 100-200 needed for a meta-model. | n/a | recorded |
| G16 | multi-agent-forecasting | Katz, Masse, Stefan+skills and Kalshi never combined; forecasts lack confidence/evidence fields; no diversity (rho) measured; only Kalshi markets resolved after the forecast timestamp may score a blend. | YES | K13 (Katz+Masse log-odds), K14 (model+Kalshi 50/50 logit, forward only); Stefan+skills combination left to the forecasting team (their OT2026 finals are not in this repo) |
| G17 | drift-detection | No PSI/KS check of live rows vs training (the exact failure Amendment 1 found by hand). | YES | PSI table pending vs 2015-2025 in K11+ report |
| G18 | monitoring-alerting | FORWARD_LOG has hashes but no staleness/drift alerts, no rule for when to re-freeze. | YES (paper) | documented re-freeze triggers in KATZ_PREREG Amendment 2 |
| G19 | production-readiness | Train/serve skew is the main issue (G1). Model hash registry exists (run_meta cfg_hash + preds sha). No kill switch needed: paper only, no orders. | partial | K11+ freeze records cfg_hash of model used |
| G20 | backtest-overfitting / scotus SKILL | Trial ledger in TRIALS.md had stale rows; total N must include K10 and every new arm. | fixed | N=22 after Amendment 2 |

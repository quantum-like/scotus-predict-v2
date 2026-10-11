# KATZ_PREREG: Katz pipeline fixes + pre-registered improvements (registered 2026-10-11 ~01:50 PT, before any fitting on this branch)
Target: case outcome reverse (petitioner wins) for Kalshi SCOTUS outcome markets. Paper only. Rules: ml-trading-strategy-research
skill (trial ledger with config hashes, declared candidate population, holdout discipline, multiple-testing correction, PBO by CSCV),
adapted to classification. Branch katz-improve, local only (no push).

## Windows and holdouts
- Rolling yearly retrain, training on terms <= t-1 with the embargo of REVIEW L7. Data: SCDB Legacy_07 + 2026_01 (combined, as rerun.py).
- SELECTION: 1990-2014 only (rolling predictions; per-term metrics).
- 2015-2025: ALREADY SEEN (clean, strict, stacked, direction runs). Reported as "seen, informational" only; never used to choose.
- Fresh holdout (a): settled Kalshi SCOTUS outcome markets. PARTLY SEEN: the clean Katz table compared model P with quotes for the
  25 markets open on 2026-10-08; any market among those that has since settled is flagged "seen", the rest are fresh.
- Fresh holdout (b), forward: OT2026 decisions as they come in. For each pending case, the selected model's P(petitioner wins) is
  frozen with timestamp + SHA256 of the prediction file in FORWARD_LOG.md BEFORE the decision, together with the Kalshi bid/ask at
  freeze time. Scored on resolution against always-reverse and the Kalshi mid, by Brier, log loss, accuracy, and fee-adjusted paper
  P&L (fee ceil(0.07*C*P*(1-P)*100)/100). No order is ever placed.

## T0 = fixes (K00), applied to all trials
L1/L2 drop decision_month_*, decision_delay and anything from dateDecision/dateRearg (no -1 date placeholder); L4 drop term_raw and
natural_court_raw; L7 embargo; B2 ties (4-4) = affirm; B3 report with and without outcome -1 cases (primary: without);
B4 direction mean over {1,2} only; B5-B7 code fixes; R1 random_state=0 everywhere; R2 float32; R3 versions logged.
Kept from the original method: growing forest (25 + 1 tree/term), rebuild on natural-court change, class_weight as original (B1 is a trial).

## Declared candidate population (immutable)
| id | change vs K00 |
|---|---|
| K00 | fixes only (reference) |
| K01 | strict: also drop issue_*, issue_area_*, law_type_*, law_supp_* (REVIEW L3) |
| K02 | class_weight=None (REVIEW B1) |
| K03 | K00 + Platt calibration of the case P on the 10 prior terms only |
| K04 | K00 + isotonic calibration of the case P on the 10 prior terms only |
| K05 | K00 + aggregation by P(majority reverses): Poisson-binomial over calibrated per-justice P (Platt per justice-pool, prior 10 terms), ties affirm, then K03-style case calibration |
| K06 | gradient boosting (HistGradientBoosting, fixed lr 0.05, 300 iters, 31 leaves; LightGBM GPU only if it runs, same params) + K05 aggregation |
| K07 | K05 + free features: US/SG side from SCDB party codes (27 = United States, federal agencies) and lower-court fields already in SCDB (lcDisagreement, lcDisposition, lcDispositionDirection, caseSource circuit + prior reversal rate, certReason conflict codes); Oyez advocates "for the United States, as amicus supporting petitioner/respondent" flag (free api.oyez.org, no key) |
| K08 | K07 + Oyez oral-argument transcript features: questions/words by justices per side (free api.oyez.org). Included ONLY if coverage >= 90% of argued cases 1990-2025; otherwise K08 is recorded as "not run (coverage)" and still counted |
| K09 | optional GPU trial: per-justice logistic/small MLP (PyTorch MPS; 2 hidden layers x 64, fixed epochs 20, weight decay 1e-4) on K07 features + K05 aggregation |
Prior trials on the same data and target (reverse), counted: original rerun, score_hist, modern-only, clean, clean strict, stacked = 6.
N_trials = 10 declared + 6 prior = 16 (direction-improve's 11 trials are a different target, listed in TRIALS.md, not added here).

Sources checked (2026-10-11): Oyez API answers without a key (cases list, case detail with `advocates`, `oral_argument_audio` ->
transcripts). Oyez `conclusion`, `decisions`, `written_opinion` are post-decision and must never be used. No free structured source
of amicus brief counts found -> not used. SCDB lower-court fields exist in 2026_01 (lcDisagreement, lcDisposition,
lcDispositionDirection, caseSource, caseOrigin, certReason).

## Metrics and inference
- Primary (selection): mean per-term Brier score of calibrated case P(reverse), 1990-2014 (Kalshi needs probabilities).
- Secondary: case accuracy (ties affirm), vote accuracy, log loss, calibration slope; baselines always-reverse and prior-term reverse rate.
- Tests vs K00 on 1990-2014: McNemar (accuracy) and paired per-term Brier difference (sign test); Holm across K01-K09 (family 0.05);
  Bonferroni at N=16 also reported.
- PBO by CSCV on the 1990-2014 per-term Brier matrix: 8 term groups, 4 IS / 4 OOS, 70 combinations; pass < 0.50.
- Decision: a trial replaces K00 only if Holm p < 0.05 on Brier AND PBO < 0.50; otherwise K00 is used for the forward set.
- 2015-2025 printed afterwards for all trials, labelled "seen, informational".

## Compute plan (Olga's Mac, one heavy job at a time, detached, caffeinate, nice)
- Random forests (K00-K05, K07, K08): CPU, n_jobs=-1 (sklearn has no GPU path).
- K06: HistGradientBoosting on CPU. LightGBM GPU needs OpenCL (deprecated on macOS); XGBoost has no MPS backend. We try LightGBM GPU
  once in a smoke test and record whether it works; if not, CPU. The method does not change for the GPU.
- K09: PyTorch MPS (record torch version and device); falls back to CPU only with the same code, logged.
- Calibration and aggregation (K03-K05): reuse saved K00/K02 per-justice probabilities, no refit (CPU, seconds).
- Each run's run_meta.json records which steps used MPS and which used CPU.

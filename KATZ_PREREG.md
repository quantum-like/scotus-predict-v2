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

## Amendment 1 (2026-10-11 ~22:00 PT, before rerunning): K10 pending-row fix. N_trials = 17.
Audit of pending_cases_scdb_rows.csv (26 dockets, 233 rows) vs SCDB 2026_01 terms 2015-2025 found pre-decision fields blank in the
pending rows that are almost never blank in training: lcDisposition 92% blank (hist 5%), lcDisagreement 100% (3%), certReason 100%
(1%), caseOrigin 66% (3%), lawSupp 92% (2%). The feature code turns blanks into a -1 category (lc_outcome_-1, lc_disagreement_-1,
cert_reason_-1, case_origin_-1, law_supp_-1; K07's cert_conflict = 0), which in training marks unusual cases, so every pending case
is scored as unusual. Oyez `oyez_found` is 0 for not-yet-argued pending cases but ~1 in training.
K10 = K07 method (features, K05 aggregation, Platt on prior 10 terms) with every feature that cannot be observed for the pending rows
removed for ALL rows (train and predict): lc_outcome_* (from lcDisposition), lc_disagreement_*, cert_reason_*, cert_conflict,
case_origin_*, law_supp_*, oyez_found. sg_amicus_* kept (0 = not known before argument; flagged). Values are NOT imputed.
Selection is unchanged (K07 stays selected on 1990-2014); K10 is the live-use variant of K07 for the forward set and is reported
on 1990-2014 vs K07 (Brier sign test) for transparency; 2015-2025 seen/informational. Refreeze as FORWARD_OT2026_frozen_v2.csv.

## Amendment 2 (2026-10-12 ~11:10 PT, before any K11+ run): K11-K15. N_trials = 22 (17 + 5).
Based on katz/AUDIT_ML4T.md. Skills followed: see audit header. Everything paper only; runs on Olga's Mac only.
**Live-valid population** (trials whose features exist for the pending rows): K10 (incumbent/reference), K11, K12, K13, K15.
K07 is excluded from live use (Amendment 1); it stays the 1990-2014 historical winner of the old population.
- **K11 missingness-aware (CPU, RF n_jobs=-1):** K07 feature set; for every row (train and test, all terms) each blank-prone group
  (lc_outcome_*, lc_disagreement_*, cert_reason_*+cert_conflict, case_origin_*, law_supp_*, oyez_found+sg_amicus_*) is masked to the
  missing code (-1 column = 1, others 0) with probability = that group's blank rate in the OT2026 pending rows, row-level Bernoulli,
  seed 0. Pending rows keep their real blanks. History is thus scored under live missingness.
- **K12 isotonic (CPU, seconds):** K10 per-justice preds, K05 aggregation, isotonic instead of Platt on the case P (prior 10 terms, embargoed).
- **K13 Katz+Masse ensemble (CPU):** Masse case-RF (author params 2000 trees, depth 12, seed 9) rerun rolling from 1956 on Masse
  features minus the pending-blank fields (lcDisagreement, certReason, lcDisposition, caseOrigin), with the term embargo, predicting
  OT2026 pending too. P(petitioner) = P(liberal) if lcDispositionDirection = conservative (1), 1-P(liberal) if liberal (2); missing ->
  K10 alone. Combined with K10 in log-odds by logistic regression on [logit K10, logit Masse] fit on the prior 10 terms.
- **K14 model+Kalshi blend (forward only):** inv_logit(0.5 logit(selected model) + 0.5 logit(Kalshi last price)) (fixed weights,
  Pilot-5 50/50 rule). Scored ONLY on OT2026 markets that resolve after the v3 freeze timestamp. No historical fit or selection.
- **K15 hierarchical justice model (PyTorch, device mps):** K10 features standardized on train only; logit p_ij = global w.x_i + b_j +
  u_j.x_i with L2 on u_j (partial pooling toward the court), trained per term from terms >= 1946 with the embargo, 4 epochs AdamW,
  float32, seed 0; then K05 aggregation (Poisson-binomial + Platt). GPU boosting: none possible on macOS MPS (LightGBM GPU = OpenCL,
  failed in K06; XGBoost/CatBoost have no MPS) - recorded, not a trial.
- **Conformal:** split-conformal 80% prediction sets on K10/winner case P using prior-10-term nonconformity; reported as a diagnostic
  with per-term coverage; not a probability model, so not a trial.
**Selection rule (1990-2014 only, fixed now):** winner = lowest mean per-term Brier among the live-valid population; it replaces
K10 only if (a) per-term Brier sign test vs K10 is significant after Holm across the 4 challengers (p_holm < 0.05), (b) Holm-corrected
McNemar on case accuracy vs K10 is not significantly worse, (c) PBO < 0.5 by CSCV on 1991-2014 (8 groups x 3 terms, 70 complementary
splits) within the population, and the CSCV distribution of its Brier (mean, std, worst) is reported. Otherwise K10 stays.
DSR (per-term Brier skill vs prior-rate, skew/kurtosis, N=22) is reported; DSR > 0.95 is the binding gate for any money use; failing
it means paper only (already the case).
**Holdout, touched once:** 2015-2025 is NOT fresh (seen in earlier runs - stated honestly). After selection, one script run scores the
winner, K10 and always-reverse on 2015-2025 and on the 37 settled Kalshi markets (terms 2023-2025, inside the holdout, also seen),
vs Kalshi d7 mid (fallback arg mid / last trade), Brier + log loss. Its sha256 is logged before running. No change after that read.
**Forward:** if the winner differs from K10, refreeze as FORWARD_OT2026_frozen_v3.csv (v1, v2 kept), log in FORWARD_LOG.md, plus
the K14 blend column. Re-freeze triggers (G18): new SCDB release, pending-row recoding, or a new trial selected.

## Amendment 3 (2026-10-12 ~15:35 PT, written and committed BEFORE any K16+ computation): K16-K19 + disagreement tracker. N_trials = 26 (22 + 4).
Approved by Amir via coordinator 2026-10-12 15:21 PT. Paper only; Olga's Mac only (one heavy job, >=30% RAM free). Skills: ml-trading-strategy-research, ml4t-skills.
**Honesty note:** the 2015-2025 holdout and the 36/37 settled Kalshi markets were ALREADY read once (Amendment 2 single read, 2026-10-12 ~15:15 PT).
Any 2015-2025 / Kalshi numbers produced under this amendment are PARTLY SEEN, informational only, never used for selection, and labelled so.
All trials below are K10 (incumbent, Brier 1990-2014 per-term mean 0.2052 as recorded in TRIALS.md) plus added features, same RF, same rolling
yearly retrain, same embargo, same K05 aggregation + Platt (prior 10 terms, embargoed). Only the feature set changes.
- **Coverage gate (binding, checked before K16/K17/K19 are fitted):** oral-argument transcript coverage = share of SCDB argued dockets
  (1990-2014) with a usable transcript (>= 2 advocate sections with speaker-attributed turns) from Oyez (cache in katz/oyez/raw) or, for
  dockets Oyez lacks, supremecourt.gov argument_transcripts PDFs (available OT2000+; 1 request/2 s). If coverage < 90%, K16, K17 and K19
  are NOT run and the shortfall is reported (they still count toward N=26). Cases without a transcript get oa_have=0 and zeros.
- **K16 oral-argument counts:** per row (justice x case): that justice's question/turn count to petitioner side and to respondent side,
  their difference, plus case totals (all justices) per side and difference; transcript speaker turns only (no audio, no outcome fields).
- **K17 oral-argument wording sentiment (MPS):** K16 + per justice x side mean sentiment (P(negative)) of that justice's turns, from a fixed
  pretrained transformer (distilbert-base-uncased-finetuned-sst-2-english, no fine-tuning, inference on torch device mps, batch 128,
  truncation 128 tokens), plus case-level side means and the resp-minus-pet differences. Model weights hash logged.
- **K18 Solicitor General position:** sg_side = +1 if the US/SG supports petitioner (as party: us_pet, or amicus: sg_amicus_pet),
  -1 if respondent, 0 none; sg_party and sg_amicus indicators; SG prior support win rate (smoothed, prior terms only). No transcript needed.
- **K19 post-argument re-forecast:** K17 + K18 features = information available right after the argument date. No leakage: features
  from the case's own argument only; training on terms < t with the embargo (no same-term outcomes). For OT2026, a case is re-scored only
  once its transcript is posted; unargued cases keep K10.
- **Selection (unchanged, 1990-2014 only):** population K10, K16, K17, K18, K19. Winner = lowest mean per-term Brier; replaces K10 only if
  per-term Brier sign test vs K10 p_holm < 0.05 (Holm over 4), Holm McNemar not significantly worse, PBO < 0.5 (CSCV 1991-2014, 8x3, 70).
  DSR (N=26) reported; DSR > 0.95 binding for any money use (paper only regardless).
- **Disagreement tracker (not a trial, no selection, no trading):** katz/DISAGREE_OT2026.csv lists OT2026 frozen markets with
  |P_model(v2 K10) - Kalshi at freeze| >= 0.25; katz/DISAGREE_LOG.md logs outcomes forward (who was closer, Brier each) as markets resolve.
- MPS use recorded per trial in run_meta.json (devices); RF parts are CPU (no sklearn GPU path).

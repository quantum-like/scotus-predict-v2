# PREREG: direction-improve (pre-registered 2026-10-09 21:15 PT, before any fitting)

Goal: improve out-of-sample prediction of decision direction (SCDB `direction`/`decisionDirection`, 1=conservative, 2=liberal; 3/NaN dropped)
over the reference direction model (scotus-predict-v2 retargeted, SCDB 2026_01, 2015-2025 case acc 0.6464 on 806 cases).
Rules follow the ml-trading-strategy-research skill (trial ledger, declared candidate population, sealed holdout, multiple-testing
correction, PBO by CSCV), adapted to classification.

## Data
- SCDB 2026_01 justice-centred (1946-2025). Martin-Quinn justices.csv (mqscores.wustl.edu, 2024 release, terms 1937-2024,
  SHA256 6f2eb2e9...aa3d54, in external/).

## Validation design
- Rolling yearly retrain: to predict term t, train only on terms <= t-1. Predictions from 1956.
- Embargo: training rows from term t-1 are kept only if decided before Oct 1 of term t (drop held-over / reargued cases);
  all lagged features use information dated before the first day of term t.
- Exploration / selection window: 1990-2014. Sealed holdout: 2015-2025, read ONCE for the whole declared population after the
  spec is frozen. Any change after reading it is a new trial and the holdout becomes validation.
- Post-decision features removed (decisionType, decision_month/delay, dateDecision-derived, vote counts, opinion writer,
  majority/minority, splitVote, term_/natural_court one-hots), as in the reference run.

## Features (candidates)
- F1 Martin-Quinn: justice prior-term post_mn (t-1), court median t-1, justice minus median, lower-court-direction x MQ.
  Term 2025 uses 2024 scores (latest available).
- F2 Justice issue-area history: expanding share of conservative votes by justice x issueArea over terms < t (and count).
  Note: SCDB codes issueArea from the opinion; T07 drops the current-case issueArea lookup (strict) as a leakage check.
- F3 US / SG as party: petitioner or respondent is the United States / federal agency (SCDB party codes), side indicator.
  (SG amicus position is not in SCDB; no free structured source identified -> not used.)
- F4 Circuit: caseSource mapped to circuit; circuit rolling reversal rate (terms < t); circuit-split = certReason in
  {conflict among courts of appeals / with state courts} codes.
- F5 Oral-argument question counts per side: only if a free source covers 2015-2025 (ConvoKit/Oyez checked separately).
  Not in the initial population; adding it later is a new declared trial.

## Models
- RF (reference hyperparameters, no tuning), HistGradientBoosting (fixed: lr 0.05, max_iter 300, max_leaf_nodes 31,
  l2 0.0) with isotonic calibration fit on the most recent 5 training terms only, L2 logistic regression (C=1, standardized)
  as the regularized linear baseline. No hyperparameter search.

## Declared candidate population (immutable)
| id  | model        | features                     |
|-----|--------------|------------------------------|
| T00 | RF           | reference (reproduction)     |
| T01 | RF           | ref + F1                     |
| T02 | RF           | ref + F1 + F2                |
| T03 | RF           | ref + F1 + F2 + F3           |
| T04 | RF           | ref + F1-F4                  |
| T05 | HGB+isotonic | ref + F1-F4                  |
| T06 | L2 logistic  | ref + F1-F4                  |
| T07 | HGB+isotonic | ref + F1-F4, strict (no current issueArea) |
Prior trials on the same data and target, counted for deflation: reference direction run, Masse A, Masse B (3). N_trials = 11.

## Metrics
- Primary: case-level direction accuracy (majority of predicted justice votes) on 2015-2025.
- Secondary: vote accuracy, case log loss / Brier, per-term accuracy; baselines: prior-term majority direction (all prior,
  last 10), reference model.

## Inference
- McNemar (exact) of each trial vs T00 on 2015-2025 cases; Holm correction across the 7 comparisons (family-wise 0.05),
  Bonferroni with N=11 also reported.
- PBO by CSCV on 1990-2014 per-term accuracy matrix: 8 term groups, 4 IS / 4 OOS, 70 combinations. Pass: PBO < 0.50.
- Selection: highest 1990-2014 case accuracy; it counts as an improvement only if Holm-adjusted p < 0.05 on the holdout
  AND PBO < 0.50. Otherwise report NO-GO.

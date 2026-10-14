# Amendment C1 (Claude, branch katz-claude-2): KC1-KC4 (+ reference K10s). N_trials = 37
Pre-registration, committed BEFORE the KC1 random-forest run, the 1980-2026 IRT run, and any metric on a real new feature. Paper only,
never trade. Branch katz-claude-2 from katz-improve (59b4d24 Amendment 3; 02c7d81 its results). Never pushed to main or katz-improve.

**Numbering and the other agent's work (from ~/scotus-predict-rerun/katz/STATUS_K16.md, STATUS_K20.md; none of it is on GitHub):**
"Amendment 4 (waiver)", 51f5557 (2026-10-13 12:32 PT): K16/K17 run under a waiver of the transcript gate. "Amendment 5", fe89cec on a branch
also named katz-claude (17:33 PT): K20 advocates, K21 supremecourt.gov docket features, K22 argued/US-party fixes + issue-code drop, K23
pending hand-coding, N = 30. "Amendment 6" (box bf8d3ab, ~/scotus-predict-rerun/katz-a6/STATUS_K24.md): K24/K25 (oral-argument
features under a companion coverage rule; K24 started 19:29 PT 2026-10-13). Because numbers are being claimed concurrently, this amendment
uses its own namespace: **Amendment C1 (Claude)**, trial IDs **KC1-KC4**, branch katz-claude-2 (first committed as "Amendment 6", K25-K28,
08431bd; renamed in the next commit, before any run, when the box's Amendment 6 / K24-K25 appeared). To avoid duplicating
their K21, the cert-stage family built here (CVSG, cert amicus, relists, days to grant, IFP, QP split; code parse_dockets.py, parse_qp.py)
is NOT registered as a trial; its features stay in katz/claude/features/ as diagnostics only. Overlap kept and disclosed: their K22 also
drops issue codes; our KC1 additionally drops argument month and the Oyez SG flags and is the base of KC2-KC4.
**Trial count:** 26 (Amendments 1-3: K00-K19 incl. K16/K17, plus 6 prior runs) + 4 (the box's Amendment 5: K20-K23) + 2 (the box's Amendment 6:
K24, K25) + 4 (KC1-KC4) + 1 (K10s, a reference that cannot be selected, counted to be conservative) = 37.

**Honesty log (before this commit).** Downloads approved by Amir 2026-10-12: supremecourt.gov dockets (2,105 of 2,169) and QP PDFs (1,828),
FJC judges.csv; coverage counts only. Dry runs of the evaluator used K10's own predictions as a stand-in forest with RANDOM features (no real
feature, no KC1): they scored K10 and noise models on 1990-2014, on both the old metric (all cases, reverse) and the registered one (argued,
petitioner wins: K10 as recorded 0.2231, K10 through the registered stage 2 0.2208), and led to the stage-2 rules below. IRT smoke fits for
prediction terms 1960-1962 only (corr. with published MQ -0.99). Label-availability counts printed the 2015-2025 0/1 split (517 petitioner
wins of 772); nothing depends on it (the holdout reverse rate was already public from Amendment 2). Amendment 2's holdout read: ~15:16 PT
2026-10-12 (28bc92c); Amendment 3 committed 15:23 PT (59b4d24). Three adversarial review rounds (leakage, statistics, conformance, bugs)
ran before this commit; their fixes are in the text below.

## Rules (Amir's brief 2026-10-12; "do all of these improvements" 2026-10-13; option 1 "yes" 2026-10-13)
1. No leakage: no post-decision fields (issue, issueArea, lawType, lawSupp, outcomes, decision dates as features). "Not argued" is never a
   feature value. 2. Pre-registered here, committed before running; every trial counts (N = 37). 3. Purged, embargoed CPCV; DSR (gate > 0.95),
   PBO (< 0.5), Brier, calibration plot, Holm McNemar vs always-reverse. 4. Holdout (2015-2025; 36 settled Kalshi markets) touched once at the
   end; **already SEEN** (Amendment 2 and earlier), so every number from it is labelled SEEN. 5. No transcript/oral-argument feature (K16/K17
   cover it elsewhere). Not repeated: K11-K15. Not duplicated: K16-K19, the other Amendment 5's K20-K23.

## Primary population and label (Kalshi-aligned) - the selection metric
Primary: argued cases (SCDB dateArgument present), y = petitioner wins (SCDB partyWinning 1; 0 loses; 2/missing excluded); 1990-2014,
n = 2,250. Secondary (K-ledger comparability, never used to choose): all cases, y = reverse (case_outcome_disposition > 0, outcome -1
excluded), K10 recorded 0.2052. Summary dispositions are excluded from the primary metric and from all stage-2 training.

## Design
**Stage 1 (only new random forest).** KC1's forest = K10's per-justice Katz RF (katz_trial.py: growing forest 25 + 1 tree/term, rebuild on
natural-court change, class_weight "orig", random_state 0, float32, T0 fixes, term embargo, "free" + "pendfix"), trained on all cases, with
feature set **strict20** = K10 minus issue_* (incl. issue_area_*), law_type_*, argument_month_* (level -1 = summary disposition) and the Oyez
sg_amicus_*. Code katz/claude/claude_katz_trial.py (= katz_trial.py + SPEC KC1 + read-only input root $SCOTUS_ROOT + output
katz/claude/results_local/); it skips the Oyez block and asserts 862 features and no forbidden prefix (issue_, law_type_, law_supp_,
argument_month_, sg_amicus_, oyez_, decision, lc_outcome_, cert_reason_, lc_disagreement_, case_origin_). CPU; starts only when no other katz
job runs and >= 30% memory is free (job_claude.sh). Inherited unchanged: the court-change rebuild compares naturalCourt over all rows of a
term (differs from start-of-term information only in 2015, a holdout term).
**Stage 2 (katz/claude/stage2.py).** Per-justice logit p'_ij = LR([logit p_ij] + Zj); case Pmaj = Poisson-binomial P(> n/2 reverse votes), ties
affirm, n = every justice row (as K05/K10); case P = LR([logit Pmaj] + Zc) on the primary label. sklearn LogisticRegression(C=1.0, lbfgs,
max_iter=2000); logits clipped [1e-4, 1-1e-4]; every column standardized on its observed training values, clipped +-5, missing -> 0 (= mean).
No availability flag is ever a regressor. Activation: a sub-family enters a fit only if its availability column is 1 for >= 25% of the
training rows and >= 150 cases (>= 1,000 justice rows for theta); availability = theta_have (non-imputed theta), lc_have (court-of-appeals
source with >= 3 classified judges). s is always on.
**WF (primary series):** per-justice LR for each term >= 1981 on terms max(1980, t-10)..t-1; case LR for terms >= 1990 on terms
max(1981, t-10)..t-1 (so every case LR trains on out-of-sample per-justice P built like the test term's); both on argued cases only and minus
term t-1 cases decided on/after Oct 1 of t. 2015+ outcomes enter only as walk-forward training rows for later terms (as K10's own P were made).
Logged coefficients stop at test term 2015.
**K10s (reference comparator, not selectable):** K10's own per-justice P through this identical stage 2 with no Z (WF and CPCV), so that
re-targeting the label to the primary metric earns a challenger nothing. K10 as recorded (katz_eval.build + k11_eval.cal) is reported too.

## New information
**A. Point-in-time ideal points (KC2, KC4; pit_irt.py, torch mps).** Published Martin-Quinn scores are smoothed over all terms (they contain the
votes being predicted): used only as a correlation check. For each prediction term t = 1980..2026: SCDB 2026_01 justice votes of terms
1946..t-1 minus term t-1 dockets decided on/after Oct 1 of t; y = 1 if vote direction = 2 (liberal), 0 if = 1; unanimous dockets dropped.
P = sigmoid(a_i + b_i theta_{j,tau}); priors a ~ N(0,5^2), b ~ N(0,2.5^2), first theta ~ N(0,1), random-walk increments ~ N(0,0.1); MAP by
Adam (lr 0.05, 3,000 full-batch steps), float32, seed 0, warm start; sign per fit so corr(theta, liberal share) > 0; theta_j(t) at the
justice's last term <= t-1; no prior votes -> mean of sitting same-party appointees, imputed = 1.
Zj = [s_i theta_j(t), s_i theta_med_i(t), s_i], s_i = +1 if lcDispositionDirection = 1, -1 if = 2, else 0.
**lcDispositionDirection:** a pre-decision fact coded by SCDB relative to its issue code (hand-coded INFERRED for pending rows); K10 uses it.
Amir was asked and instructed "do all of these improvements"; it is used as in K10 and reported as a **residual rule-1 risk**.
**C. Lower-court ideology, circuit level (KC3, KC4; fjc_lc_ideology.py).** FJC judges.csv (sha256 99a17f0c970daa74d91f29cfe47a61287f58a103d4e62be6084d81f9f89ad48c).
For caseSource = a U.S. court of appeals (SCDB 21-31, 32 = D.C., 8 = Federal) at d = the docket page's lower-court decision date, else Oct 1
of (term - 1): dshare = share of active judges (commissioned <= d < senior status and termination) appointed by a Democratic president; FJC
"None (reassignment)" rows take the party of the judge's reassigned-from appointment. Other sources missing (panel level needs credentials).
Zc = [dshare - 0.5, s_i (dshare - 0.5)].

## Trials
| id | stage 1 | Zj | Zc |
|---|---|---|---|
| KC1 | strict20 RF (new) | - | - |
| KC2 | KC1's forest | A | - |
| KC3 | KC1's forest | - | C |
| KC4 | KC1's forest | A | C |
| K10s (reference) | K10's forest | - | - |
Not run: published MQ as a feature (leak); panel-level ideology; transcript features; cert-stage family (overlaps the other K21).

## Validation (katz/claude/claude_eval.py)
WF per-term Brier (primary), 1990-2014, for K10, K10s, KC1-KC4; 2015+ outcomes masked before every metric; populations asserted.
**CPCV (purged, embargoed):** 10 contiguous groups (1990-92, 93-95, 96-98, 99-01, 02-04, 05-06, 07-08, 09-10, 11-12, 13-14), 2 test groups ->
45 splits, 9 paths (path p of group g = the p-th lexicographic split containing g). Per split, stage 2 refit on ARGUED cases of 1980-2014 outside
the test groups, minus purge (term before a test group, decided on/after Oct 1 of its first term) and embargo (term after each test group).
Activation decided once on the full 1980-2014 pool. Case LR on the training cases' in-sample per-justice P (<= 4 parameters, ~30,000 rows).
Outputs: 9 x 25 per-path per-term Brier; CPCV per-term Brier = path mean; CPCV P = mean of 9 test predictions; path/split mean/std/worst;
pooled Brier and log loss. Limitations: stage-1 P are walk-forward (the growing forest cannot be refit on later terms), and theta and lag
features of post-test training rows embed the test block's votes; the 1-term embargo removes the most direct carry-over. CPCV trains on more
terms than WF, so it is optimistic for every model (hence the edge gate needs both).
**Selection.** Winner = lowest WF mean per-term Brier among KC1-KC4. It replaces K10 for forward use only if, against **K10s**: (a) one-sided
sign test (better in more terms than chance) p_holm < 0.05 over the 4 challengers AND lower WF mean Brier; (b) Holm McNemar on accuracy not
significantly worse; (c) PBO < 0.5 by CSCV on the WF matrix {K10s, KC1..KC4}, 1991-2014, 8 x 3 terms, 70 splits; (d) CPCV mean per-term Brier
below K10s'. Sign test and McNemar vs K10 as recorded are reported, not gated.
**Edge gate.** Additionally DSR > 0.95 (N = 37) on both the WF and CPCV per-term skill series (skill_t = Brier of the prior-10-term
petitioner-win rate minus model Brier; formula as k11_eval) and PBO < 0.5 on both WF and CPCV matrices. SR-variance pool (must load, else the
evaluator fails): K00, K01, K02, K06, K07, K09, K10, K11, K12, K13, K15, K16, K17, K18, K19 (as recorded, scored on the primary metric),
K10s, KC1-KC4. The box's K20-K25 count in N but are not in the pool (they may not exist at evaluation time).
**Reported:** WF/CPCV/pooled Brier, log loss, accuracy, ECE, sharpness, calibration plot (WF and CPCV), McNemar vs always-petitioner (Holm),
DSR, PBO, secondary metric. Diagnostics (never used): coverage, CPCV active families, coefficients (<= 2015, argued only), MQ check.
**Pinning.** INPUT_SHA256.json (committed with the verdict) holds sha256 of KC1's preds/run_meta/features, pit_theta, lc_ideology, cert_docket,
qp_split, P_wf_all (gzip files hashed on decompressed bytes), K10's preds, SCDB 2026_01
(212615bf92c77ee478e87d3f52a5a989b03c8ecca43bfeb0e21b38d53550c1f8), kalshi_settled_prices.csv
(e2c29cd948d0f1205c7aed33b793ac630dc30e8c4934cb3be4829a53df28a198) and market_map_hist.csv
(ab7c44c75e988ded1caa9f4435ae370d4f4c29d06288d15972d35ec588ee478f). Dry runs (any CLAUDE_* override) cannot write to katz/results/claude.

## Holdout (once, at the end) and Kalshi
After the verdict commit, holdout_once_claude.py (sha256 committed first): refuses if a lock or any HOLDOUT_* file exists; requires the
verdict, input hashes, this amendment and all katz/claude code committed and unmodified and every pinned input matching; takes an exclusive
lock (time, HEAD, script sha256) before loading any label; asserts n = 772 (primary), 800 (secondary) and 36 (Kalshi at d7) before printing.
Scores K10, K10s, KC1-KC4 and the prior-10-term base rate on 2015-2025 (primary and secondary), and the 36 settled Kalshi markets (YES mapped
by market_map_hist.csv) vs Kalshi at three fixed times: argument-day morning, 30 and 7 days before the decision (d30/d7 anchored on the decision
date for both sides). The model P is frozen before argument; only argument morning approximates its information set. An arg/d30 price counts
only if ask - bid <= 0.20; d7 = Amendment 2's d7_mid. Calibration plot for the primary holdout; Brier-by-time panel for Kalshi.
**Disagreement tracker (not a trial, never traded):** |P_model - P_Kalshi| >= 0.25 at d7 and d30 for K10, K10s, KC1-KC4: count, who was closer,
Brier of each on the flagged set, hypothetical paper P&L at bid/ask with the Kalshi fee. Forward: OT2026 markets of FORWARD_OT2026_frozen_v2.csv
vs the Kalshi last price at that freeze (2026-10-12 10:37 PT), frozen with sha256 in katz/claude/FORWARD_CLAUDE.md before any resolves
(forward_freeze_claude.py; separate from Amendment 3's tracker).

## Compute
KC1 RF: CPU, n_jobs=-1, nice 5, one heavy job at a time. IRT: torch mps. Stage 2, CPCV, evaluation: CPU, minutes.

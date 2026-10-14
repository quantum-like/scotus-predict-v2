# CLAUDE_REPORT: improving the Katz SCOTUS model beyond K10 (Amendment C1, branch katz-claude-2)
Paper only; nothing was traded. Written 2026-10-13. Pre-registration: katz/AMENDMENT_C1_CLAUDE.md. Results: katz/results/claude/.

## Bottom line
**No edge survives the gates, and K10 stays the forward model** (verdict.json: replaces_K10 = false, used_for_forward = K10).
None of the four new trials (KC1-KC4) beats K10; all four are worse than K10's own predictions put through the same calibration stage
(K10s). On the 36 settled Kalshi markets Kalshi stays far ahead at every point in time, including the morning of oral argument
(Brier 0.130 vs 0.206 for the best model, n = 18; at that point no model even beats the base rate, 0.205).
Elsewhere in the project, the oral-argument trials run by the box agent are the only ones that moved Brier materially (K24 0.1972,
K16 0.1979, K25 0.1983, K17 0.1984 vs K10 0.2052; old all-cases metric, not comparable with the primary numbers below). None passed
its Holm gate, and their transcript coverage is below the 90% per-docket rule as strictly counted (88.1%).

## What was tried (Amendment C1; N = 37 trials counted in the deflated Sharpe)
Selection metric, changed to match what Kalshi trades: **argued cases only, label = petitioner wins** (SCDB partyWinning), 1990-2014
(n = 2,250 argued dockets, 2,030 cases; 1 docket with partyWinning = 2 excluded). The old K-ledger metric (all cases, reverse) is secondary.
| trial | what it adds | why |
|---|---|---|
| KC1 | strict base: K10's forest without issue/issueArea/lawType (coded from the opinion), argument month (its "not argued" level marks summary dispositions) and the Oyez SG-amicus flags (Oyez covers argued cases only, so their presence encodes "argued") | rule 1: no post-decision fields; "not argued" never a feature |
| KC2 | KC1 + point-in-time ideal points (Martin-Quinn-style dynamic IRT re-estimated each term from SCDB votes up to t-1, on Apple MPS) x lower-court direction | published MQ scores are smoothed over all terms and leak the votes being predicted; the re-estimate tracks MQ at r = -0.95 (sign opposite by construction) |
| KC3 | KC1 + lower-court ideology: share of Democratic-appointed active judges on the circuit below (FJC data), main effect and x lower-court direction | panel-level ideology would need credentials for a court-opinion service (none created) |
| KC4 | KC1 + both | |
| K10s | K10's forest through the same stage 2 (comparator, not selectable) | so that re-targeting the label earns no credit |
Stage 2 (all): per-justice and case-level logistic recalibration with the new features, Poisson-binomial majority (ties affirm), trained
walk-forward on the prior 10 terms of argued cases with the Oct-1 embargo. Validation: purged, embargoed CPCV (10 term groups, 45 splits,
9 paths), DSR (N = 37), PBO (CSCV), Holm McNemar vs always-petitioner, calibration plots.
Built but not registered: a cert-stage family (CVSG invitations, cert-stage amicus counts, relists, days to grant, IFP, circuit-split
wording in the Questions Presented; 2,105 dockets and 1,828 QP PDFs from supremecourt.gov). It was left out to avoid duplicating the K21
planned by the other agent's Amendment 5, which overlaps it partly (CVSG, amicus counts, timing; no relists, IFP or QP wording) and never
produced results. Not done: transcript features (K16/K17/K24/K25 cover them elsewhere), published MQ as a feature (leak).

## Numbers
**Selection window 1990-2014 (primary: argued cases, petitioner wins; lower is better)**
| model | WF Brier | CPCV Brier | accuracy | ECE (WF) | beats K10s in | DSR WF / CPCV (N=37) | secondary (all cases, reverse) |
|---|---|---|---|---|---|---|---|
| K10 as recorded | 0.2231 | - | 65.6% | 0.061 | - | 0.42 / - | 0.2052 |
| K10s (comparator) | **0.2208** | **0.2199** | 65.3% | 0.024 | - | 0.84 / 0.955 | 0.2069 |
| KC1 strict base | 0.2272 | 0.2265 | 63.9% | 0.027 | 4/25 terms | 0.41 / 0.64 | 0.2135 |
| KC2 + ideal points | 0.2274 | 0.2261 | 63.5% | 0.025 | 5/25 | 0.38 / 0.74 | 0.2140 |
| KC3 + circuit ideology | 0.2275 | 0.2263 | 64.0% | 0.034 | 4/25 | 0.23 / 0.64 | 0.2137 |
| KC4 + both | 0.2277 | 0.2259 | 63.7% | 0.033 | 5/25 | 0.21 / 0.72 | 0.2140 |
| base rate (prior 10 terms) | 0.2306 | | 63.8% (always petitioner) | | | | |
Gates for the winner KC1 vs K10s: (a) one-sided sign test p_holm = 1.0 FAIL; (b) McNemar significantly worse (66 vs 98, p_holm 0.046)
FAIL; (c) PBO 0.0 pass, but vacuous: the non-selectable K10s is best in every split (PBO over the four challengers alone, a diagnostic:
0.40 WF, 0.59 CPCV); (d) CPCV 0.2265 vs 0.2199 FAIL. Edge gate: DSR 0.41 / 0.64 < 0.95 FAIL. K10s's CPCV DSR of 0.955 is just over 0.95,
but its WF DSR is 0.84 and it cannot be selected.
Holm McNemar vs always-petitioner (WF; model right & rule wrong / model wrong & rule right): K10 96/55 (p_holm 0.006), K10s 133/99 (0.15),
KC1 55/53, KC2 42/50, KC3 111/107, KC4 109/111 (all p_holm 1.0). In accuracy the KC trials are level with the trivial rule (63.8%).
Calibration (calibration_1990_2014.png): K10 as recorded is overconfident on this metric (ECE 0.061, mean P 0.69 vs a 0.638 win rate);
K10s and KC1-KC4 are well calibrated (ECE 0.024-0.034; CPCV 0.020-0.027) but flat (spread 0.09-0.10 for KC vs 0.13 for K10s), close to the base rate.
An independent recomputation matched every selection statistic to about 1e-16 (except a ddof convention in sharpness); the DSR pool was
checked for internal consistency (one common benchmark SR0 = 0.468), not rebuilt; a bug hunt on KC1 found no error
(katz/results/claude/selection_verification_2026-10-13.json).

**Holdout 2015-2025, read once (SEEN: already seen several times, in the clean/strict/stacked/direction runs, the K-series evaluation and
Amendment 2's read; C1's pre-registration also printed its 0/1 split, 517 of 772)**
| model | argued, petitioner wins (n = 772) | all cases, reverse (n = 800) |
|---|---|---|
| K10 as recorded | **0.2119** | **0.1889** (reproduces Amendment 2) |
| K10s | 0.2132 | 0.1940 |
| KC1 / KC2 / KC3 / KC4 | 0.2217 / 0.2221 / 0.2215 / 0.2218 | 0.2049 / 0.2051 / 0.2045 / 0.2047 |
| base rate | 0.2224 | 0.1993 |
Holdout calibration plot: katz/results/claude/HOLDOUT_calibration_claude.png.

**Kalshi, 36 settled markets (SEEN), at three fixed times** (model P is frozen before argument; an argument-day or d30 quote counts only
if ask - bid <= 0.20)
| time | n | Kalshi | best model | K10 | base rate |
|---|---|---|---|---|---|
| argument-day morning | 18 | **0.130** | 0.206 (KC2) | 0.222 | 0.205 |
| 30 days before decision | 29 | **0.094** | 0.199 (KC1) | 0.208 | 0.203 |
| 7 days before decision | 36 | **0.080** | 0.192 (K10s) | 0.193 (reproduces Amendment 2's 0.1929 vs 0.0805) | 0.203 |
The KC models are within about 0.005 of the base rate at every time point.
Disagreement tracker (|model - Kalshi| >= 0.25; scored, never traded): at d7 K10 disagreed on 14 markets and was closer on 4; KC1 on 12,
closer on 2. On the flagged markets the model's Brier was about 0.39 vs Kalshi's 0.11-0.13. Hypothetical paper P&L, 1 contract per flag at
bid/ask with fees: K10 +0.26 (d7) and +0.54 (d30); KC1 -0.58 and -0.88 (small n; never traded). The big misses are petitioner losses the
model never sees coming: affirmances in Skrmetti, Moore, Hemani (the marijuana-gun case), NPPC and the tariffs case, and Gonzalez v.
Google (vacated and remanded), where Kalshi had moved to 0.07-0.27.
**Forward (OT2026),** frozen 2026-10-13 21:21 PT with sha256 in katz/claude/FORWARD_CLAUDE.md, against the Kalshi last price at the v2
freeze (2026-10-12 10:37 PT); 25 markets, 24 with a price. Gap >= 0.25: K10 (the forward model) on 6 of 24 (Anderson v. Intel, Beaird,
Crowther, Jouppi, International Partners, DOL v. Sun Valley); KC1 on 7 of 24 (the same minus Beaird, plus Wassily and Grand). Score them
as they resolve.

## Does any edge survive? No.
- Against K10: every new trial is worse, walk-forward on 1990-2014 (0.2272-0.2277 vs 0.2231) and on the holdout (0.2215-0.2221 vs
  0.2119); on CPCV every new trial is worse than K10s (0.2259-0.2265 vs 0.2199). DSR is far below 0.95.
- Against Kalshi: the gap is not a timing artefact. At argument-day morning, the closest the model's information gets to the market's,
  Kalshi's Brier is 0.13 against 0.21, and no model beats the base rate.

## Why, in short
1. KC1 loses about 0.0064 Brier against K10s on argued cases. About 0.0034 of that is cases with an SG amicus: legitimate pre-argument
   information, lost only because the Oyez flags' presence encodes "argued" (an encoding constraint, not a post-decision field). It could
   be recovered with an argued-neutral source in a new registered trial. The remaining ~0.0031 is consistent with losing the issue/law codes
   (post-decision under rule 1) and argument month.
2. Ideal points: in an in-sample diagnostic fit the standardized coefficient on (lower-court direction x theta) is 0.27 (the forest's own
   logit falls from 0.62 to 0.47), yet case-level Brier does not move (KC2 vs KC1: +0.0003 WF, -0.0004 CPCV). That the forest's lagged
   voting-direction features already carry this is a hypothesis, not tested. Circuit composition adds nothing measurable.
3. The information that matters arrives at argument. The oral-argument trials elsewhere (K24 0.1972, K16 0.1979, K25 0.1983, K17 0.1984 vs
   K10 0.2052, all cases/reverse, 1990-2014) are the only material movers. In the box's latest family (N = 32): K24/K25/K17 p_holm 0.146,
   K16 0.303; DSR 0.926 / 0.941 / 0.949 / 0.960; PBO 0.186; K10 stays. K16/K17 ran under a waiver of the 90% per-docket transcript rule
   (strict coverage 87-88%); K24/K25 under a looser "companion" coverage rule (97.5%). At N = 37 their DSRs would be a little lower.

## Caveats you should know
- **lcDispositionDirection** (lower-court direction) orients KC2-KC4. SCDB codes it relative to its issue code: a residual rule-1 risk,
  used as in K10 after your "do all of these" instruction. It produced no gain, so the conclusion does not depend on it.
- **Holdout is not fresh** (see above); it was never used to choose anything here.
- **Parallel agents.** Three parties registered amendments on 2026-10-13, none of them on GitHub: the box agent ("Amendment 4" waiver
  51f5557 for K16/K17; an "Amendment 5" b28a8b9 for oral-argument K20/K21, aborted after 3 minutes over the ID clash, then re-registered as
  "Amendment 6" bf8d3ab, K24/K25); a separate agent working on its own branch named katz-claude ("Amendment 5" fe89cec, K20-K23, no results
  yet); and this work. Numbers collided twice, so this work uses its own namespace (Amendment C1, KC1-KC4) and counts every registered
  trial: N = 37 (the box's aborted runs are counted once, as K24/K25, as the box does). katz/LEDGER_RECONCILIATION.md lists them all.
- **Branch base.** katz-claude-2 starts at 59b4d24 (Amendment 3); 02c7d81 (Amendment 3's results) is on katz-improve only. The DSR pool
  reads the recorded K16-K19 predictions from ~/scotus-predict-rerun, not from git.
- **Post-registration code changes:** one bug fix (dry-run detection, ca81439) found when the guard refused the real evaluation; no
  registered rule changed. Before registration, three adversarial reviews fixed (i) leaks that would have re-encoded "argued vs summary
  disposition" (availability flags as regressors, the QP-presence flag, summary-disposition "grants") and (ii) post-grant and
  post-decision Clerk notes left in old QP PDFs.

## Commits (katz-claude-2, pushed; master and katz-improve untouched)
08431bd pre-registration; b821c1e re-registration as C1 (before any run); 70d024b ideal points; bcf61be ledger reconciliation; ca81439 bug
fix; 3d852d9 selection results; 5c053d0 verification + holdout script sha256; d574861 single holdout read; 13dce9a forward freeze; then
this report and the corrected ledger.

## What I would do next
1. Restore the SG-amicus signal without the "argued" encoding (e.g. SG amicus filings from the supremecourt.gov dockets, available
   for docket years 2000 on) as a new registered trial: it is about half of the gap KC1 lost.
2. Decide on the oral-argument trials (K16/K17/K24/K25): either accept that coverage is below the 90% per-docket rule and evaluate them on
   the Kalshi-aligned metric with the same-time Kalshi comparison, or recompute coverage per term and restrict them to terms that meet it.
3. Score the 24 priced OT2026 markets as they resolve (FORWARD_CLAUDE.md, DISAGREE_OT2026_claude.csv; Amendment 3's tracker for K10).
4. Treat beating Kalshi as out of reach for pre-argument models. The realistic question is whether post-argument signals ever add to the
   market price, which needs far more than 36 settled markets.

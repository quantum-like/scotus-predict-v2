# TRIALS ledger (direction-improve). One row per run; every adaptive choice is a trial.
| date (PT) | trial | config hash | spec | window | case acc | vote acc | decision |
|---|---|---|---|---|---|---|---|
| 2026-10-09 19:58 | P1 (prior) | n/a | reference direction RF, SCDB 2026_01 | 2015-2025 | 0.6464 | 0.6786 | reference |
| 2026-10-09 21:06 | P2 (prior) | n/a | Masse A, random 70/30, leaky | 2015-2025 subset (189) | 0.656 | n/a | not comparable |
| 2026-10-09 21:06 | P3 (prior) | n/a | Masse B, rolling | 2015-2025 (706) | 0.6785 | n/a | prior |
 Declared population T00-T07 (see PREREG.md).

| 2026-10-10 22:40 | T00 | 734bd0459a6d | rf ref | explore 1990-2014 / holdout 2015-2025 | 0.6325 / 0.6749 | n/a | holm p=ref |
| 2026-10-10 22:40 | T01 | 97f390bda38e | rf F1 | explore 1990-2014 / holdout 2015-2025 | 0.6321 / 0.6675 | n/a | holm p=1.0 |
| 2026-10-10 22:40 | T02 | cd423e709078 | rf F1+F2 | explore 1990-2014 / holdout 2015-2025 | 0.6410 / 0.6576 | n/a | holm p=0.6226258548559882 |
| 2026-10-10 22:40 | T03 | ff78cdb2f77a | rf F1+F2+F3 | explore 1990-2014 / holdout 2015-2025 | 0.6446 / 0.6737 | n/a | holm p=1.0 |
| 2026-10-10 22:40 | T04 | b86ac6fdbc6f | rf F1+F2+F3+F4 | explore 1990-2014 / holdout 2015-2025 | 0.6482 / 0.6638 | n/a | holm p=1.0 |
| 2026-10-10 22:40 | T05 | b52d974fd09f | hgb F1+F2+F3+F4 | explore 1990-2014 / holdout 2015-2025 | 0.6381 / 0.6390 | n/a | holm p=0.1648487820544136 |
| 2026-10-10 22:40 | T06 | 258d8ad443a9 | lr F1+F2+F3+F4 | explore 1990-2014 / holdout 2015-2025 | 0.6119 / 0.5794 | n/a | holm p=1.1437827706548394e-05 |
| 2026-10-10 22:40 | T07 | df1d41517974 | hgb F1+F2s+F3+F4+strict | explore 1990-2014 / holdout 2015-2025 | 0.6107 / 0.6390 | n/a | holm p=0.1564211256633701 |

Trial count: 3 prior + 8 declared = 11. Holdout read ONCE 2026-10-10 22:40 PT. Selected on 1990-2014: T04. PBO (CSCV 8 groups, 70 combos) = 0.10. Verdict: NO-GO. Any further change is a new trial; 2015-2025 is now validation, not holdout.

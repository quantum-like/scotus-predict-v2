# STATUS_K11 (Amendment 2, N=22). Paper only. Olga's Mac only.
- 10:52 PT smoke OK: K15 on MPS (torch 2.14.1), K11 missaug path.
- Queue (job_k11.sh, detached, caffeinate, nice 5, one at a time, waits for >=30% free memory):
  1. K15 hierarchical justice logistic  -> MPS (.venv-gpu)
  2. Masse-live case RF (K13 input)      -> CPU n_jobs=-1
  3. K11 missingness-aware RF            -> CPU n_jobs=-1
  4. k11_eval.py selection (1990-2014)   -> CPU, seconds
- 10:51 PT K15 started (MPS)
- holdout_once.py sha256 e9dde364... logged before run (commit f0349db)
- 10:55 PT K15 exit 0
- 10:55 PT Masse-live started (CPU)
- 10:57 PT Masse-live exit 0
- 10:57 PT K11 started (CPU RF n_jobs=-1)
- 11:42 PT K11 exit 0
- 11:42 PT eval started
- 11:42 PT eval exit 1
- 15:17 PT eval died (NaN in K13 stack: calibrated K10 P undefined <1990). Bug fix: stack on K10 pre-calibration P(majority). Rerun.
- 15:20 PT eval OK after 2 more bug fixes (format string; conformal NaN quantile). Selection: K13 lowest Brier, not significant -> K10 stays. Running holdout_once.py (single read).
- 15:21 PT holdout read once: K10 Brier 0.1889 vs always-rev 0.1993 (n=800); Kalshi 36: K10 0.1929, always-rev 0.2009, Kalshi 0.0805. No v3 (K10 stays). DONE.

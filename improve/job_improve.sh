#!/bin/bash
cd ~/scotus-predict-rerun
while pgrep -f "run_stacked.py|job_stacked.sh|masse_|run_direction.py|score_hist.py|mac_pipeline.sh|btc15_v2" >/dev/null; do echo "$(date) waiting for other heavy job"; sleep 120; done
for T in T04 T06 T07; do .venv/bin/python -u -W ignore direction_improve/run_trial.py --trial $T --max-term 1992 --out direction_improve/results/_smoke_$T > direction_improve/smoke_$T.log 2>&1 || { echo "SMOKE_FAIL $T"; exit 1; }; done; echo SMOKE_OK
for T in T00 T01 T02 T03 T04 T05 T06 T07; do
  [ -f direction_improve/results/$T/explore_result.json ] && { echo "skip $T (done)"; continue; }
  memory_pressure | tail -1; echo "=== $T $(date)"
  /usr/bin/time -l .venv/bin/python -u -W ignore direction_improve/run_trial.py --trial $T --n-jobs 4 > direction_improve/run_$T.log 2>&1; echo "EXIT_$T $?"
done
echo "=== ALLDONE $(date)"

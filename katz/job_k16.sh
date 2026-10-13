#!/bin/bash
cd ~/scotus-predict-rerun
st() { echo "- $(date +%H:%M) PT $*" >> katz/STATUS_K16.md; }
wait_room() { while pgrep -f "katz_trial.py|run_trial.py|score_hist.py|masse_|lotm_daily|k13_masse" >/dev/null; do sleep 60; done
  while [ $(memory_pressure | tail -1 | grep -o '[0-9]*') -lt 30 ]; do echo low memory; sleep 120; done; }
for T in K18 K19; do wait_room; st "$T started (CPU RF n_jobs=-1)"; caffeinate -i nice -n 5 .venv/bin/python -u -W ignore katz/katz_trial.py --trial $T --n-jobs -1 > katz/run_$T.log 2>&1; st "$T exit $?"; done
echo ALLDONE

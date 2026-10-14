#!/bin/bash
# Amendment 6 (Claude) queue (paper only). One heavy job at a time on this Mac: waits until job_k16.sh (K18, K19) and every other katz/masse job
# has exited and >= 30% memory is free, then runs the K25 stage-1 forest (CPU, n_jobs=-1, nice 5, caffeinate). Inputs read-only from
# ~/scotus-predict-rerun. Our runner's command line contains "katz_trial.py", so job_k16.sh's own wait_room also waits for it.
K="$(cd "$(dirname "$0")" && pwd)"; PY="$HOME/scotus-predict-rerun/.venv/bin/python"; mkdir -p "$K/results_local"
st() { echo "- $(date '+%Y-%m-%d %H:%M %Z') $*" >> "$K/STATUS_CLAUDE.md"; }
busy() { pgrep -f "bash ./job_k16.sh|katz_trial.py|run_trial.py|score_hist.py|masse_|lotm_daily|k13_masse" >/dev/null; }
wait_room() { while :; do mem=$(memory_pressure 2>/dev/null | tail -1 | grep -o '[0-9]*' | head -1)
  if ! busy && [ "${mem:-0}" -ge 30 ]; then sleep 30; busy || break; fi; sleep 60; done; }   # both conditions re-checked every pass
st "queue started; waiting for job_k16.sh (K18, K19) and other katz jobs"
wait_room; st "K25 started (CPU RF n_jobs=-1, nice 5)"
cd "$K" && caffeinate -i nice -n 5 "$PY" -B -u -W ignore claude_katz_trial.py --trial K25 --n-jobs -1 > "$K/results_local/run_K25.log" 2>&1; st "K25 exit $?"
echo ALLDONE

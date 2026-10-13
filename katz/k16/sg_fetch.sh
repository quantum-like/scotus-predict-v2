#!/bin/bash
# polite fetch, 1 req / 2 s, curl, cached; paper only
cd ~/scotus-predict-rerun/katz/k16
tail -n +2 missing_transcripts.csv | awk -F, '$1>=2000{print $1","$2}' | while IFS=, read t d; do
  f="scotusgov/${t}_${d}.pdf"; [ -s "$f" ] && { echo "$t $d cached"; continue; }
  for u in "https://www.supremecourt.gov/oral_arguments/argument_transcripts/$t/$d.pdf" "https://www.supremecourt.gov/oral_arguments/argument_transcripts/$d.pdf"; do
    sleep 2; code=$(curl -s -m 30 -A "scotus research (paper only), low rate" -o "$f.tmp" -w "%{http_code}" "$u")
    if [ "$code" = 200 ] && head -c4 "$f.tmp" | grep -q %PDF; then mv "$f.tmp" "$f"; break; fi; rm -f "$f.tmp"
  done; echo "$t $d $([ -s "$f" ] && echo ok || echo miss)"
done; echo FETCH_DONE

"""Fetch supremecourt.gov argument transcript PDFs for dockets Oyez lacks (OT2000+), 1 req / 2 s, cached. Paper only."""
import pandas as pd, os, time, urllib.request
m = pd.read_csv("missing_transcripts.csv", dtype={"docket": str}); m = m[m.term >= 2000]
rows = []
for t, d in zip(m.term, m.docket):
    p = f"scotusgov/{t}_{d}.pdf"; ok = os.path.exists(p) and os.path.getsize(p) > 5000
    if not ok:
        for u in (f"https://www.supremecourt.gov/oral_arguments/argument_transcripts/{t}/{d}.pdf", f"https://www.supremecourt.gov/oral_arguments/argument_transcripts/{d}.pdf"):
            time.sleep(2)
            try:
                b = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "scotus research (paper only), low rate"}), timeout=30).read()
                if b[:4] == b"%PDF": open(p, "wb").write(b); ok = True; break
            except Exception: pass
    rows.append((t, d, int(ok))); print(t, d, ok, flush=True)
pd.DataFrame(rows, columns=["term", "docket", "pdf"]).to_csv("scotusgov_fetch.csv", index=False)

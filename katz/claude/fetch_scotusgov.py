"""Polite fetch of supremecourt.gov docket pages + Questions Presented PDFs (approved by Amir 2026-10-12). Paper only.
Docket list: SCDB dockets of terms >= 2000 in YY-NNNN form + the 26 OT2026 pending dockets. Order: pending, 2015-2025, 2000-2014.
Cache: raw/dockets/{docket}.html, raw/qp/{docket}.pdf; misses recorded in raw/fetch_index.csv. Resumable. ~1 request / 1.2 s."""
import csv, os, re, subprocess, sys, time
import pandas as pd
ROOT = os.path.expanduser("~/scotus-predict-rerun"); HERE = os.path.dirname(os.path.abspath(__file__)); RAW = os.path.join(HERE, "raw")
UA = {"User-Agent": "scotus research (paper only, low rate)"}; GAP = 1.2; last = [0.0]
def get(url):   # curl uses the macOS trust store (python.org Python lacks a CA bundle); TLS verification stays ON
    w = GAP - (time.time() - last[0])
    if w > 0: time.sleep(w)
    for k in range(3):
        last[0] = time.time()
        r = subprocess.run(["curl", "-s", "-L", "-m", "40", "-A", UA["User-Agent"], "-w", "\n%{http_code}", url], capture_output=True)
        if r.returncode == 0:
            body, _, code = r.stdout.rpartition(b"\n"); return int(code or 0), body
        err = r.returncode; time.sleep(5 * (k + 1))
    print("FAIL", url, "curl exit", err, flush=True); return -1, b""
rd = lambda p, **k: pd.read_csv(p, encoding="ISO-8859-1", low_memory=False, **k)
m = rd(os.path.join(ROOT, "data", "SCDB_2026_01_justiceCentered_Docket.csv"), usecols=["term", "docket"]).drop_duplicates()
p = rd(os.path.join(ROOT, "pending_inputs", "pending_cases_scdb_rows.csv"), usecols=["term", "docket"]).drop_duplicates()
m = m[m.term >= 2000]; m["docket"] = m.docket.astype(str).str.strip(); p["docket"] = p.docket.astype(str).str.strip()
ok = lambda d: isinstance(d, str) and re.fullmatch(r"\d{2}-\d{1,5}", d) is not None
order = list(dict.fromkeys([d for d in p.docket if ok(d)] + [d for d in m[m.term >= 2015].sort_values("term").docket if ok(d)] + [d for d in m[m.term < 2015].sort_values("term", ascending=False).docket if ok(d)]))
print(f"{len(order)} dockets to fetch", flush=True)
idx_p = os.path.join(RAW, "fetch_index.csv"); done = {}
if os.path.exists(idx_p): done = {r["docket"]: r for r in csv.DictReader(open(idx_p))}
f = open(idx_p, "a", newline=""); w = csv.DictWriter(f, ["docket", "docket_status", "docket_url", "qp_status"]);
if not done: w.writeheader()
for i, d in enumerate(order):
    if d in done: continue
    yy = int(d[:2]); new = f"https://www.supremecourt.gov/search.aspx?filename=/docket/docketfiles/html/public/{d}.html"; old = f"https://www.supremecourt.gov/search.aspx?filename=/docketfiles/{d}.htm"
    st, url = "miss", ""
    for u in ([new, old] if (yy >= 13 and yy < 90) else [old, new]):
        s, b = get(u)
        if s == 200 and (f"Docket for {d}".encode() in b or f"No. {d}".encode() in b):
            open(os.path.join(RAW, "dockets", d + ".html"), "wb").write(b); st, url = "ok", u; break
    a, n = d.split("-"); s, b = get(f"https://www.supremecourt.gov/qp/{a}-{int(n):05d}qp.pdf")
    qs = "ok" if (s == 200 and b[:4] == b"%PDF") else f"miss{s}"
    if qs == "ok": open(os.path.join(RAW, "qp", d + ".pdf"), "wb").write(b)
    w.writerow({"docket": d, "docket_status": st, "docket_url": url, "qp_status": qs}); f.flush()
    if i % 50 == 0: print(f"[{time.strftime('%H:%M:%S')}] {i}/{len(order)} {d} docket={st} qp={qs}", flush=True)
print("DONE", flush=True)

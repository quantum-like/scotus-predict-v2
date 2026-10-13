"""Parse supremecourt.gov PDFs into speaker-attributed justice turns (pet/resp main arguments). Unattributed 'QUESTION:' transcripts = not usable."""
import subprocess, re, glob, os, csv, gzip
J = re.compile(r"^\s*(?:\d+\s+)?((?:CHIEF )?JUSTICE [A-Z'\-]+):\s*(.*)$"); ARG = re.compile(r"ORAL ARGUMENT OF .*", re.I)
S = re.compile(r"^\s*(?:\d+\s+)?([A-Z][A-Z .'\-]+):\s*(.*)$")
cov = []; w = csv.writer(gzip.open("sg_turns.csv.gz", "wt", newline="")); w.writerow(["term", "docket", "side", "speaker", "last", "text"]); rows = []
for p in sorted(glob.glob("scotusgov/[12]*.pdf")):
    t, d = os.path.basename(p)[:-4].split("_", 1); txt = subprocess.run(["pdftotext", p, "-"], capture_output=True, text=True).stdout.splitlines()
    secs = []; cur = None; sec = None
    for i, ln in enumerate(txt):
        if re.search(r"ORAL ARGUMENT OF|REBUTTAL ARGUMENT OF", ln) and i > 40:
            ctx = " ".join(txt[i:i + 8]).upper(); sec = {"resp" if "RESPONDENT" in ctx or "APPELLEE" in ctx else "pet" if ("PETITIONER" in ctx or "APPELLANT" in ctx) and "REBUTTAL" not in ln.upper() else "other": []}; secs.append(sec); cur = None; continue
        if sec is None: continue
        m = S.match(ln)
        if m: cur = [m.group(1).strip(), m.group(2)]; list(sec.values())[0].append(cur)
        elif cur and ln.strip() and not ln.strip().isdigit(): cur[1] += " " + ln.strip()
    side = {}
    for s in secs:
        k = list(s)[0]
        if k in ("pet", "resp") and k not in side and any(J.match(sp + ": x") for sp, _ in s[k]): side[k] = s[k]
    n = 0
    for k, turns in side.items():
        for sp, tx in turns:
            if J.match(sp + ": x"): last = sp.split()[-1].title(); w.writerow([int(t), d, k, sp, last, tx]); n += 1
    ok = int(len(side) == 2 and n > 0); cov.append((int(t), d, ok)); print(t, d, len(secs), n, ok)
with open("oa_scotusgov_coverage.csv", "w", newline="") as f: c = csv.writer(f); c.writerow(["term", "docket", "have"]); c.writerows(cov)

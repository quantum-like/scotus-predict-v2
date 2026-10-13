"""For missing OT2004-2014 dockets: fetch same-date supremecourt.gov transcripts (index pages) and check if the PDF caption names the docket."""
import re, pandas as pd, subprocess, os, time, datetime
m = pd.read_csv("missing_transcripts.csv", dtype={"docket": str}); m = m[(m.term >= 2004) & m.docket.notna()]
have = {f[:-4] for f in os.listdir("scotusgov")}
out = []
for t, g in m.groupby("term"):
    h = open(f"idx/{t}.html").read(); rows = []
    for r in re.finditer(r"<tr.*?</tr>", h, re.S):
        a = re.search(r"href='([^']+\.pdf)'", r.group(0)); dt = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2})", re.sub("<[^>]+>", " ", r.group(0)))
        if a and dt: rows.append((a.group(1), datetime.date(2000 + int(dt.group(3)), int(dt.group(1)), int(dt.group(2)))))
    for d, da in zip(g.docket, g.dateArgument):
        if f"{t}_{d}" in have: continue
        mo, dy, yr = map(int, da.split("/")); dd = datetime.date(yr, mo, dy); hit = ""
        for href, rd in rows:
            if rd != dd: continue
            lead = os.path.basename(href)[:-4]; p = f"scotusgov/lead_{t}_{lead}.pdf"
            if not os.path.exists(p):
                time.sleep(2); subprocess.run(["curl", "-s", "-m", "30", "-A", "Mozilla/5.0 scotus research (paper only)", "-o", p, "https://www.supremecourt.gov" + href])
            cap = subprocess.run(["pdftotext", "-l", "2", p, "-"], capture_output=True, text=True).stdout
            if re.search(r"(?<![\d-])" + re.escape(d.replace(" ORIG", "")) + r"(?![\d])", cap): hit = lead; break
        out.append((t, d, hit)); print(t, d, hit or "-", flush=True)
pd.DataFrame(out, columns=["term", "docket", "caption_lead"]).to_csv("caption_check.csv", index=False)

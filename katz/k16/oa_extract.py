"""Amendment 3: extract speaker-attributed justice turns from cached Oyez transcripts (no network unless --fetch). Paper only."""
import json, os, re, sys, gzip, csv
RAW = os.path.join(os.path.dirname(__file__), "..", "oyez", "raw")
def fn(url): return os.path.join(RAW, re.sub(r"[^A-Za-z0-9]+", "_", url.split("api.oyez.org/")[1])[:150] + ".json")
def load(url):
    p = fn(url); return json.load(open(p)) if os.path.exists(p) else None
out = gzip.open(os.path.join(os.path.dirname(__file__), "oa_turns.csv.gz"), "wt", newline=""); w = csv.writer(out)
w.writerow(["term", "docket", "side", "speaker", "last", "text"]); cov = []
for term in range(1990, 2027):
    L = load(f"https://api.oyez.org/cases?per_page=0&filter=term:{term}") or []
    for c in L:
        d = load(c["href"])
        if not d: cov.append((term, "", 0, "nocase")); continue
        dk = (d.get("docket_number") or "").strip(); oa = [x for x in (d.get("oral_argument_audio") or []) if not x.get("unavailable")]
        m = load(oa[0]["href"]) if oa else None; secs = ((m or {}).get("transcript") or {}).get("sections") or []
        if len(secs) < 2: cov.append((term, dk, 0, "notranscript" if not oa else "nosections")); continue
        n = 0
        for side, sec in (("pet", secs[0]), ("resp", secs[-2] if len(secs) >= 3 else secs[1])):
            for u in sec.get("turns", []):
                sp = u.get("speaker") or {}
                if any(r.get("type") == "scotus_justice" for r in (sp.get("roles") or [])):
                    t = " ".join(x.get("text", "") for x in (u.get("text_blocks") or [])); w.writerow([term, dk, side, sp.get("identifier"), sp.get("last_name"), t]); n += 1
        cov.append((term, dk, 1 if n else 0, "ok" if n else "noturns"))
out.close()
with open(os.path.join(os.path.dirname(__file__), "oa_oyez_coverage.csv"), "w", newline="") as f:
    cw = csv.writer(f); cw.writerow(["term", "docket", "have", "why"]); cw.writerows(cov)
print("cases", len(cov), "with turns", sum(c[2] for c in cov))

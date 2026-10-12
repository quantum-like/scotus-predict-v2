"""Polite Oyez fetch (free api.oyez.org, no key): 1 request/second, cached to raw/, resumable. Paper only.
Uses ONLY pre-decision fields: advocates (who argued, for whom) and oral-argument transcript turns.
Never reads conclusion / decisions / written_opinion. Output oyez_case_features.csv (term, docket, features)."""
import json, os, re, sys, time, urllib.request
UA = {"User-Agent": "scotus research (paper only), low rate"}; RAW = "raw"; os.makedirs(RAW, exist_ok=True)
def get(url):
    fn = os.path.join(RAW, re.sub(r"[^A-Za-z0-9]+", "_", url.split("api.oyez.org/")[1])[:150] + ".json")
    if os.path.exists(fn): return json.load(open(fn))
    for k in range(3):
        try:
            time.sleep(1.0); d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30)); json.dump(d, open(fn, "w")); return d
        except Exception as e: err = e; time.sleep(5 * (k + 1))
    print("FAIL", url, err, flush=True); return None
rows = []
for term in range(int(sys.argv[1]), int(sys.argv[2]) + 1):
    L = get(f"https://api.oyez.org/cases?per_page=0&filter=term:{term}") or []
    print(term, len(L), flush=True)
    for c in L:
        try:
            d = get(c["href"]);
            if not d: continue
            r = {"term": term, "docket": (d.get("docket_number") or "").strip(), "oyez_found": 1, "sg_amicus_pet": 0, "sg_amicus_resp": 0}
            for adv in (d.get("advocates") or []):
                if not isinstance(adv, dict): continue
                s = (adv.get("advocate_description") or "").lower()
                if "united states" in s and "amicus" in s:
                    if "petitioner" in s or "appellant" in s: r["sg_amicus_pet"] = 1
                    elif "respondent" in s or "appellee" in s: r["sg_amicus_resp"] = 1
            oa = [x for x in (d.get("oral_argument_audio") or []) if not x.get("unavailable")]
            if oa:
                m = get(oa[0]["href"]); secs = ((m or {}).get("transcript") or {}).get("sections") or []
                def jq(sec): return sum(1 for u in sec.get("turns", []) if any(rl.get("type") == "scotus_justice" for rl in ((u.get("speaker") or {}).get("roles") or [])))
                if len(secs) >= 2:
                    r["oa_q_pet"] = jq(secs[0]); r["oa_q_resp"] = jq(secs[-2] if len(secs) >= 3 else secs[1])
                    r["oa_q_diff"] = r["oa_q_resp"] - r["oa_q_pet"]; r["oa_have"] = 1
            rows.append(r)
        except Exception as e: print("SKIP case", term, (c or {}).get("href") if isinstance(c, dict) else c, type(e).__name__, e, flush=True)
    import csv
    keys = ["term", "docket", "oyez_found", "sg_amicus_pet", "sg_amicus_resp", "oa_q_pet", "oa_q_resp", "oa_q_diff", "oa_have"]
    with open("oyez_case_features.partial.csv", "w", newline="") as f:
        w = csv.DictWriter(f, keys); w.writeheader(); [w.writerow({k: r.get(k, "") for k in keys}) for r in rows]
os.replace("oyez_case_features.partial.csv", "oyez_case_features_full.csv"); print("DONE", len(rows), flush=True)

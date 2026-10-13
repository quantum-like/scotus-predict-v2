"""K19 non-transcript post-argument features from cached Oyez case files: advocates per side (pre-decision field only)."""
import json, os, re, csv
RAW = "../oyez/raw"
def load(url):
    p = os.path.join(RAW, re.sub(r"[^A-Za-z0-9]+", "_", url.split("api.oyez.org/")[1])[:150] + ".json"); return json.load(open(p)) if os.path.exists(p) else None
rows = []
for term in range(1990, 2027):
    for c in load(f"https://api.oyez.org/cases?per_page=0&filter=term:{term}") or []:
        d = load(c["href"])
        if not d: continue
        r = {"term": term, "docket": (d.get("docket_number") or "").strip(), "n_adv_pet": 0, "n_adv_resp": 0, "n_adv_amicus": 0}
        for a in d.get("advocates") or []:
            if not isinstance(a, dict): continue
            s = (a.get("advocate_description") or "").lower()
            if "amicus" in s: r["n_adv_amicus"] += 1
            elif "petitioner" in s or "appellant" in s: r["n_adv_pet"] += 1
            elif "respondent" in s or "appellee" in s: r["n_adv_resp"] += 1
        rows.append(r)
w = csv.DictWriter(open("postarg_case.csv", "w", newline=""), list(rows[0])); w.writeheader(); w.writerows(rows); print(len(rows))

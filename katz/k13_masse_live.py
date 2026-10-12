"""Amendment 2 K13 input: Masse case-RF (author params) rolling 1980-2026 on Masse features minus pending-blank fields, term embargo,
incl. OT2026 pending. Output masse_live/preds.csv (docketId, term, p_lib, p_pet). Paper only; reads ../data, ../pending_inputs, ~/scotus-masse-rerun."""
import os, time, json, numpy as np, pandas as pd
from sklearn.ensemble import RandomForestClassifier
H = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(H); OUT = os.path.join(H, "results", "masse_live"); os.makedirs(OUT, exist_ok=True)
T0 = time.time(); rd = lambda p: pd.read_csv(p, encoding="ISO-8859-1", low_memory=False)
F = ["naturalCourt", "chief", "jurisdiction", "adminAction", "threeJudgeFdc", "caseSource", "lcDispositionDirection", "issue", "lawType"]
d = rd(os.path.join(R, "data", "SCDB_2026_01_justiceCentered_Docket.csv")).drop_duplicates("docketId")
pe = rd(os.path.join(R, "pending_inputs", "pending_cases_scdb_rows.csv")).drop_duplicates("docketId")
A = pd.concat([d, pe], ignore_index=True); A["dd"] = pd.to_datetime(A.dateDecision, format="%m/%d/%Y", errors="coerce")
X = pd.get_dummies(A[F].fillna(999).astype("category")).astype(np.float32).values
y = np.where(A.decisionDirection == 2, 1, np.where(A.decisionDirection == 1, 0, -1)); term = A.term.values.astype(int)
p = np.full(len(A), np.nan)
for t in range(1980, 2027):
    te = term == t; emb = ~((term == t - 1) & (A.dd.values >= np.datetime64(f"{t}-10-01")))
    tr = (term < t) & (y >= 0) & emb
    rf = RandomForestClassifier(n_estimators=2000, max_depth=12, n_jobs=-1, random_state=9).fit(X[tr], y[tr]); p[te] = rf.predict_proba(X[te])[:, 1]
    print(f"term {t} train={tr.sum()} test={te.sum()} {time.time()-T0:.0f}s", flush=True)
lc = A.lcDispositionDirection.values
pet = np.where(lc == 1, p, np.where(lc == 2, 1 - p, np.nan))   # lower court conservative -> reversal is liberal
o = pd.DataFrame({"docketId": A.docketId, "term": term, "p_lib": p, "p_pet": pet})[term >= 1980]; o.to_csv(os.path.join(OUT, "preds.csv"), index=False)
json.dump({"features": F, "runtime_s": round(time.time() - T0), "device": "cpu", "n_jobs": -1}, open(os.path.join(OUT, "run_meta.json"), "w"))
print("DONE", time.time() - T0)

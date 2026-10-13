import pandas as pd, sys
s = pd.read_csv("../../data/SCDB_2026_01_justiceCentered_Docket.csv", encoding="ISO-8859-1", usecols=["docketId","term","docket","dateArgument"], low_memory=False).drop_duplicates("docketId")
s = s[s.term.between(1990, 2014) & s.dateArgument.notna()].copy(); s["docket"] = s.docket.astype(str).str.strip()
c = pd.read_csv("oa_oyez_coverage.csv", dtype={"docket": str}); c["docket"] = c.docket.fillna("").str.strip()
have = set(zip(c[c.have == 1].term, c[c.have == 1].docket))
s["oyez"] = [(t, d) in have for t, d in zip(s.term, s.docket)]
extra = set()
try:
    p = pd.read_csv("oa_scotusgov_coverage.csv", dtype={"docket": str}); extra = set(zip(p[p.have == 1].term, p[p.have == 1].docket))
except FileNotFoundError: pass
s["sg"] = [(t, d) in extra for t, d in zip(s.term, s.docket)]
s["any"] = s.oyez | s.sg
print("argued dockets 1990-2014:", len(s), "oyez %.1f%%" % (100*s.oyez.mean()), "combined %.1f%%" % (100*s["any"].mean()))
print(s.groupby("term")["any"].mean().round(3).to_dict())
s[~s["any"]][["term","docket","dateArgument"]].to_csv("missing_transcripts.csv", index=False); print("missing", (~s["any"]).sum(), "of which term>=2000:", ((~s["any"]) & (s.term >= 2000)).sum())

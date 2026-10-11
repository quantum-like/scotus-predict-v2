"""Katz-improve evaluation (KATZ_PREREG.md). Light; reads results/K*/preds.csv.gz. Usage: python katz_eval.py RESULTS OUT
Selection on 1990-2014 only (per-term Brier of case P(reverse)); 2015-2025 printed as SEEN/INFORMATIONAL; writes pending P for OT2026."""
import sys, os, json, itertools, numpy as np, pandas as pd
from scipy.stats import binomtest
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
RD, OUT = sys.argv[1], sys.argv[2]; os.makedirs(OUT, exist_ok=True); N_TRIALS = 16
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
def pbinom_major(ps):   # P(#reverse > n/2), ties affirm
    d = np.zeros(len(ps) + 1); d[0] = 1
    for q in ps: d[1:] = d[1:] * (1 - q) + d[:-1] * q; d[0] *= (1 - q)
    return d[len(ps) // 2 + 1:].sum()
def roll_cal(C, col, kind):   # calibrate case P on the 10 prior terms only
    out = pd.Series(np.nan, index=C.index)
    for t in sorted(C.term.unique()):
        if t < 1990: continue
        tr = C[(C.term < t) & (C.term >= t - 10) & C.y.notna()]; te = C.term == t
        if kind == "platt": m = LogisticRegression(C=1e6).fit(lg(tr[col]).to_frame(), tr.y); out[te] = m.predict_proba(lg(C.loc[te, col]).to_frame())[:, 1]
        else: m = IsotonicRegression(out_of_bounds="clip", y_min=.01, y_max=.99).fit(tr[col], tr.y); out[te] = m.predict(C.loc[te, col])
    return out
def build(trial, agg):
    d = pd.read_csv(f"{RD}/{trial}/preds.csv.gz").dropna(subset=["p_rev"])
    if agg == "pmaj":   # per-justice Platt (pooled) on prior 10 terms, Poisson-binomial, then case Platt
        d["pj"] = np.nan; J = d[d.justice_outcome_disposition >= 0]
        for t in sorted(d.term.unique()):
            if t < 1990: continue
            tr = J[(J.term < t) & (J.term >= t - 10)]; te = d.term == t
            m = LogisticRegression(C=1e6).fit(lg(tr.p_rev).to_frame(), (tr.justice_outcome_disposition > 0).astype(int))
            d.loc[te, "pj"] = m.predict_proba(lg(d.loc[te, "p_rev"]).to_frame())[:, 1]
        d["pj"] = d.pj.fillna(d.p_rev)
    C = d.groupby("docketId").agg(term=("term", "first"), docket=("docket", "first"), m=("p_rev", "mean"), cod=("case_outcome_disposition", "first"),
                                  **({"pm": ("pj", lambda s: pbinom_major(s.values))} if agg == "pmaj" else {}))
    C["y"] = np.where(C.cod > 0, 1.0, np.where(C.cod == 0, 0.0, np.nan))   # outcome -1 excluded (primary)
    C.loc[C.term >= 2026, "y"] = np.nan
    if agg == "raw": C["P"] = C.m
    elif agg in ("platt", "iso"): C["P"] = roll_cal(C, "m", agg)
    else: C["P"] = roll_cal(C, "pm", "platt")
    return C
POP = {"K00": ("K00", "raw"), "K01": ("K01", "raw"), "K02": ("K02", "raw"), "K03": ("K00", "platt"), "K04": ("K00", "iso"),
       "K05": ("K00", "pmaj"), "K06": ("K06", "pmaj"), "K07": ("K07", "pmaj"), "K08": ("K08", "pmaj"), "K09": ("K09", "pmaj")}
CS = {}; missing = []
for k, (src, agg) in POP.items():
    if os.path.exists(f"{RD}/{src}/preds.csv.gz"): CS[k] = build(src, agg)
    else: missing.append(k)
def per_term(C, lo, hi):
    c = C[(C.term >= lo) & (C.term <= hi) & C.y.notna() & C.P.notna()]
    return c.assign(b=(c.P - c.y) ** 2, ok=((c.P > .5) == (c.y == 1)).astype(int)).groupby("term").agg(brier=("b", "mean"), acc=("ok", "mean"), n=("y", "size"))
E = {k: per_term(C, 1990, 2014) for k, C in CS.items()}
B = pd.DataFrame({k: v.brier for k, v in E.items()}); A = pd.DataFrame({k: v.acc for k, v in E.items()})
base = CS["K00"]; ix = base[(base.term.between(1990, 2014)) & base.y.notna()].index
rows = []
for k, C in CS.items():
    c = C.loc[ix]; ok = ((c.P > .5) == (c.y == 1)).astype(int); r = {"trial": k, "mean_term_brier_1990_2014": B[k].mean(), "case_acc_1990_2014": ok.mean(),
        "logloss": float(-np.mean(c.y * np.log(c.P.clip(1e-4, 1 - 1e-4)) + (1 - c.y) * np.log(1 - c.P.clip(1e-4, 1 - 1e-4))))}
    if k != "K00":
        o0 = ((base.loc[ix].P > .5) == (base.loc[ix].y == 1)).astype(int); x = int(((o0 == 1) & (ok == 0)).sum()); yy = int(((o0 == 0) & (ok == 1)).sum())
        r["mcnemar_acc_vs_K00"] = (x, yy, binomtest(x, x + yy).pvalue if x + yy else 1.0)
        dlt = (B[k] - B["K00"]).dropna(); w = int((dlt < 0).sum()); r["brier_terms_better"] = f"{w}/{len(dlt)}"; r["p_brier_sign"] = binomtest(w, len(dlt)).pvalue
    rows.append(r)
R = pd.DataFrame(rows).set_index("trial")
p = R.p_brier_sign.dropna().sort_values(); holm = {}; run = 0
for i, (k, pv) in enumerate(p.items()): run = max(run, min(1, (len(p) - i) * pv)); holm[k] = run
R["p_holm"] = pd.Series(holm); R["p_bonf_N16"] = (R.p_brier_sign * N_TRIALS).clip(upper=1)
groups = np.array_split(B.index.values, 8); lo = []
for isg in itertools.combinations(range(8), 4):
    i_ = np.concatenate([groups[i] for i in isg]); o_ = np.concatenate([groups[i] for i in range(8) if i not in isg])
    best = B.loc[i_].mean().idxmin(); rk = (-B.loc[o_].mean()).rank(pct=True)[best]; rk = min(max(rk, 1e-6), 1 - 1e-6); lo.append(np.log(rk / (1 - rk)))
pbo = float(np.mean(np.array(lo) <= 0)); sel = R.mean_term_brier_1990_2014.idxmin()
use = sel if (sel != "K00" and R.loc[sel, "p_holm"] < .05 and R.loc[sel, "mean_term_brier_1990_2014"] < R.loc["K00", "mean_term_brier_1990_2014"] and pbo < .5) else "K00"
# SEEN / informational 2015-2025
S = []
for k, C in CS.items():
    c = C[C.term.between(2015, 2025) & C.y.notna() & C.P.notna()]
    S.append({"trial": k, "n": len(c), "brier": ((c.P - c.y) ** 2).mean(), "acc": ((c.P > .5) == (c.y == 1)).mean(), "always_reverse_acc": c.y.mean(), "always_reverse_brier": ((c.y.mean() * 0 + C[C.term.between(2005, 2014) & C.y.notna()].y.mean() - c.y) ** 2).mean()})
S = pd.DataFrame(S).set_index("trial")
R.to_csv(f"{OUT}/selection_1990_2014.csv"); S.to_csv(f"{OUT}/SEEN_informational_2015_2025.csv"); B.to_csv(f"{OUT}/per_term_brier_1990_2014.csv")
pend = CS[use][CS[use].term == 2026][["docket", "P"]].rename(columns={"P": "P_reverse"}); pend.to_csv(f"{OUT}/pending_OT2026_{use}.csv")
v = {"selected_on_1990_2014": sel, "used_for_forward": use, "pbo": pbo, "missing_trials": missing, "n_trials_counted": N_TRIALS}
json.dump(v, open(f"{OUT}/verdict.json", "w"), indent=1, default=str)
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
f, ax = plt.subplots(1, 2, figsize=(14, 5)); ax[0].bar(R.index, R.mean_term_brier_1990_2014, color=["C3" if k == sel else "C0" for k in R.index])
ax[0].set_ylim(R.mean_term_brier_1990_2014.min() - .01, R.mean_term_brier_1990_2014.max() + .01); ax[0].set_title(f"1990-2014 mean per-term Brier (selected {sel}); PBO {pbo:.2f}; forward uses {use}")
ax[1].bar(S.index, S.acc); ax[1].axhline(S.always_reverse_acc.iloc[0], c="k", ls="--", label="always reverse"); ax[1].set_ylim(.55, .8); ax[1].legend(); ax[1].set_title("2015-2025 case acc: SEEN, informational only")
f.tight_layout(); f.savefig(f"{OUT}/katz_improve.png", dpi=110)
pd.set_option("display.width", 250); print(R.round(4).to_string()); print("SEEN 2015-2025 (informational):"); print(S.round(4).to_string()); print(v)

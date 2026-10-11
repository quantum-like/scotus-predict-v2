"""Frozen evaluation (PREREG.md). Reads results/T0*/ explore + sealed holdout ONCE. Usage: python evaluate.py RESULTS_DIR OUT_DIR"""
import sys, os, json, itertools, numpy as np, pandas as pd
from scipy.stats import binomtest
RD, OUT = sys.argv[1], sys.argv[2]; os.makedirs(OUT, exist_ok=True)
TR = [f"T0{i}" for i in range(8)]; REF = 0.6464; N_TRIALS = 11
def cases(d):
    d = d.assign(pc=(d.p_cons >= .5).astype(int))
    c = d.groupby("docketId").agg(term=("term", "first"), fc=("pc", "mean"), pm=("p_cons", "mean"), dd=("decisionDirection", "first"),
                                  lcdd=("lcDispositionDirection", "first"), cod=("case_outcome_disposition", "first"))
    c["call"] = np.where(c.fc > .5, 1, np.where(c.fc < .5, 0, (c.pm >= .5).astype(int)))
    return c
def mcn(a, b):
    x = int(((a == 1) & (b == 0)).sum()); y = int(((a == 0) & (b == 1)).sum()); return x, y, (binomtest(x, x + y).pvalue if x + y else 1.0)
ex = {t: json.load(open(f"{RD}/{t}/explore_result.json")) for t in TR}
sel = max(TR, key=lambda t: ex[t]["explore_case_acc"])            # frozen before reading holdout
# PBO on exploration window
E = {t: cases(pd.read_csv(f"{RD}/{t}/explore_1990_2014.csv.gz")) for t in TR}
M = pd.DataFrame({t: E[t][E[t].dd.isin([1, 2])].assign(ok=lambda c: (c.call == (c.dd == 1)).astype(int)).groupby("term").ok.mean() for t in TR})
groups = np.array_split(M.index.values, 8); logits = []
for isg in itertools.combinations(range(8), 4):
    ist = np.concatenate([groups[i] for i in isg]); oos = np.concatenate([groups[i] for i in range(8) if i not in isg])
    b = M.loc[ist].mean().idxmax(); r = M.loc[oos].mean().rank(pct=True)[b]; r = min(max(r, 1e-6), 1 - 1e-6)
    logits.append(np.log(r / (1 - r)))
pbo = float(np.mean(np.array(logits) <= 0))
# ---- holdout, read once
H = {t: cases(pd.read_csv(f"{RD}/{t}/sealed_holdout.csv.gz")) for t in TR}
rows = []; base = H["T00"]; dmask = base.dd.isin([1, 2])
for t in TR:
    c = H[t].loc[base.index]; okd = (c.call == (c.dd == 1)).astype(int)[dmask]
    pet = np.where(c.lcdd == 2, c.pm, np.where(c.lcdd == 1, 1 - c.pm, np.nan)); m = ~np.isnan(pet)
    rev = (c.cod > 0).astype(int).values; okp = ((pet[m] >= .5).astype(int) == rev[m]).astype(int)
    r = {"trial": t, "model": ex[t]["model"], "features": "+".join(ex[t]["features"]) or "ref", "explore_case_acc": ex[t]["explore_case_acc"],
         "hold_case_acc_dir": okd.mean(), "n_dir": int(dmask.sum()), "hold_pet_acc": okp.mean(), "always_reverse": rev[m].mean(), "n_pet": int(m.sum())}
    r["mcn_pet_vs_always_rev"] = mcn(rev[m], okp)
    if t != "T00":
        b0 = (base.call == (base.dd == 1)).astype(int)[dmask]; r["mcn_dir_vs_T00"] = mcn(b0, okd)
    rows.append(r)
R = pd.DataFrame(rows).set_index("trial")
p = R.mcn_dir_vs_T00.dropna().map(lambda x: x[2]).sort_values(); k = len(p); holm = {}; run = 0
for i, (t, pv) in enumerate(p.items()): run = max(run, min(1, (k - i) * pv)); holm[t] = run
R["p_vs_T00"] = p; R["p_holm"] = pd.Series(holm); R["p_bonf_N11"] = (p * N_TRIALS).clip(upper=1)
R["better_than_T00"] = R.hold_case_acc_dir > R.loc["T00", "hold_case_acc_dir"]
verdict = "GO" if (sel != "T00" and R.loc[sel, "p_holm"] < .05 and R.loc[sel, "better_than_T00"] and pbo < .5) else "NO-GO"
R.to_csv(f"{OUT}/holdout_results.csv")
pt = pd.DataFrame({t: H[t][dmask].assign(ok=lambda c: (c.call == (c.dd == 1)).astype(int)).groupby("term").ok.mean() for t in ["T00", sel]})
pt.to_csv(f"{OUT}/holdout_per_term.csv"); M.to_csv(f"{OUT}/explore_per_term.csv")
summ = {"selected_on_1990_2014": sel, "pbo_cscv_8groups_70": pbo, "verdict": verdict, "reference_prior_run": REF, "n_trials_counted": N_TRIALS}
json.dump(summ, open(f"{OUT}/verdict.json", "w"), indent=1)
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
f, ax = plt.subplots(1, 2, figsize=(14, 5))
ax[0].bar(R.index, R.hold_case_acc_dir, color=["C3" if t == sel else "C0" for t in R.index]); ax[0].axhline(REF, ls="--", c="k", label="reference 0.646")
ax[0].set_ylim(.55, .75); ax[0].set_title(f"2015-2025 case direction accuracy (selected {sel} in red); PBO={pbo:.2f}; {verdict}"); ax[0].legend()
for t in pt: ax[1].plot(pt.index, pt[t], "-o", label=t)
ax[1].set_title("per-term case direction accuracy"); ax[1].legend(); ax[1].grid(alpha=.3)
f.tight_layout(); f.savefig(f"{OUT}/direction_improve_holdout.png", dpi=110)
pd.set_option("display.width", 250); print(R.round(4).to_string()); print(summ)

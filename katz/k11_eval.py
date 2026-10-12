"""Amendment 2 selection on 1990-2014 (live-valid population K10,K11,K12,K13,K15). Writes eval_k11/. Does NOT read 2015-2025 outcomes
for any decision (they are masked before scoring)."""
import sys; sys.argv = ['x', 'results', 'eval_k11']
exec(open('katz_eval.py').read().split('CS = {}')[0])
import itertools, json
from scipy.stats import binomtest, skew, kurtosis, norm
os.makedirs("eval_k11", exist_ok=True)
dk = pd.read_csv("../data/SCDB_2026_01_justiceCentered_Docket.csv", encoding="ISO-8859-1", usecols=["docketId", "dateDecision"]).drop_duplicates("docketId")
DD = pd.to_datetime(dk.set_index("docketId").dateDecision, format="%m/%d/%Y", errors="coerce")
def cal(C, cols, kind="platt"):   # prior 10 terms, embargo: drop term t-1 cases decided >= Oct 1 of t (G4)
    out = pd.Series(np.nan, index=C.index); dd = C.index.map(DD)
    for t in sorted(C.term.unique()):
        if t < 1990: continue
        tr = C[(C.term < t) & (C.term >= t - 10) & C.y.notna() & ~((C.term == t - 1) & (dd >= pd.Timestamp(f"{t}-10-01")))]; te = C.term == t
        if kind == "iso": m = IsotonicRegression(out_of_bounds="clip", y_min=.01, y_max=.99).fit(tr[cols[0]], tr.y); out[te] = m.predict(C.loc[te, cols[0]])
        else:
            Z = lambda D: pd.concat([lg(D[c]) for c in cols], axis=1)
            m = LogisticRegression(C=1e6).fit(Z(tr), tr.y); out[te] = m.predict_proba(Z(C.loc[te]))[:, 1]
    return out
def mk(trial):
    C = build(trial, "pmaj"); C["P"] = cal(C, ["pm"]); return C
C10 = mk("K10"); C11 = mk("K11"); C15 = mk("K15")
C12 = C10.copy(); C12["P"] = cal(C10, ["pm"], "iso")
ms = pd.read_csv("results/masse_live/preds.csv").set_index("docketId")
C13 = C10.copy(); C13["mp"] = C13.index.map(ms.p_pet); C13["kp"] = C10.pm   # bug fix: calibrated P is NaN before 1990; stack on K10 raw P(majority)
has = C13.mp.notna(); C13.loc[~has, "mp"] = C13.loc[~has, "kp"]
C13["P"] = cal(C13.assign(kp=C13.kp.clip(.01, .99), mp=C13.mp.clip(.01, .99)), ["kp", "mp"]); C13.loc[C13.term < 1990, "P"] = np.nan
POP = {"K10": C10, "K11": C11, "K12": C12, "K13": C13, "K15": C15}
for C in POP.values(): C.loc[C.term >= 2015, "y_hidden"] = C.loc[C.term >= 2015, "y"]; C.loc[C.term >= 2015, "y"] = np.nan  # holdout masked
def pt(C, lo=1990, hi=2014):
    c = C[C.term.between(lo, hi) & C.y.notna() & C.P.notna()].copy(); c["b"] = (c.P - c.y) ** 2; return c.groupby("term").b.mean()
B = pd.DataFrame({k: pt(C) for k, C in POP.items()})
prior = {}
for t in range(1990, 2015):
    c = C10[(C10.term < t) & (C10.term >= t - 10) & C10.y.notna()]; cc = C10[(C10.term == t) & C10.y.notna()]; prior[t] = ((c.y.mean() - cc.y) ** 2).mean()
B["prior_rate"] = pd.Series(prior)
rows = {}
for k, C in POP.items():
    c = C[C.term.between(1990, 2014) & C.y.notna() & C.P.notna()]
    ece = np.abs(c.groupby(pd.cut(c.P, np.linspace(0, 1, 11)), observed=True).apply(lambda g: len(g) * (g.P.mean() - g.y.mean()), include_groups=False)).sum() / len(c)
    r = {"n": len(c), "mean_term_brier": B[k].mean(), "pooled_brier": ((c.P - c.y) ** 2).mean(), "logloss": -np.mean(c.y * np.log(c.P.clip(1e-6)) + (1 - c.y) * np.log((1 - c.P).clip(1e-6))),
         "acc": ((c.P > .5) == (c.y == 1)).mean(), "ece10": ece, "sharpness_sd": c.P.std(), "mean_P": c.P.mean(), "reverse_rate": c.y.mean()}
    if k != "K10":
        dlt = (B[k] - B.K10).dropna(); w = int((dlt < 0).sum()); r["terms_better_vs_K10"] = f"{w}/{len(dlt)}"; r["p_sign"] = binomtest(w, len(dlt)).pvalue
        j = c.join(C10[["P"]].rename(columns={"P": "P10"}), how="inner"); a1 = (j.P > .5) == (j.y == 1); a0 = (j.P10 > .5) == (j.y == 1)
        x, yy = int((a1 & ~a0).sum()), int((~a1 & a0).sum()); r["mcnemar_win_loss_vs_K10"] = f"{x}/{yy}"; r["p_mcnemar"] = binomtest(x, x + yy).pvalue if x + yy else 1.0
    rows[k] = r
S = pd.DataFrame(rows).T
for col in ("p_sign", "p_mcnemar"):
    pv = S[col].dropna().astype(float).sort_values(); run = 0; h = {}
    for i, (k, v) in enumerate(pv.items()): run = max(run, min(1, (len(pv) - i) * v)); h[k] = run
    S[col + "_holm"] = pd.Series(h)
# CSCV PBO on 1991-2014 (8 groups x 3 terms, 70 complementary splits), within population
Bt = B.loc[1991:2014, list(POP)]; grp = np.repeat(np.arange(8), 3); lam = []; oos_best = []
for isg in itertools.combinations(range(8), 4):
    im = np.isin(grp, isg); ib = Bt[im].mean(); ob = Bt[~im].mean(); best = ib.idxmin()
    rank = (ob > ob[best]).sum() + 1; w_ = rank / (len(ob) + 1); lam.append(np.log(w_ / (1 - w_))); oos_best.append(ob[best])   # rank 1 = worst
pbo = float(np.mean(np.array(lam) <= 0))
dist = {k: {"mean": float(np.mean(v)), "std": float(np.std(v)), "worst": float(np.max(v))} for k, v in
        {k: [Bt[~np.isin(grp, isg)][k].mean() for isg in itertools.combinations(range(8), 4)] for k in POP}.items()}
# DSR on per-term Brier skill vs prior rate, N_eff = 22; SR variance from all available trials' skill series
sk = {k: (B.prior_rate - B[k]).dropna() for k in POP}
extra = {}
for k in ("K00", "K01", "K02", "K06", "K07", "K09"):
    try: Cx = build(k, "pmaj"); Cx["P"] = cal(Cx, ["pm"]); extra[k] = (B.prior_rate - pt(Cx)).dropna()
    except Exception as e: print("skip", k, e)
allsr = [s.mean() / s.std(ddof=1) for s in {**sk, **extra}.values()]
def dsr(s, srs, n=22):
    sr = s.mean() / s.std(ddof=1); T = len(s); e = .5772156649; v = np.var(srs, ddof=1)
    sr0 = np.sqrt(v) * ((1 - e) * norm.ppf(1 - 1 / n) + e * norm.ppf(1 - 1 / (n * np.e)))
    return float(norm.cdf((sr - sr0) * np.sqrt(T - 1) / np.sqrt(1 - skew(s) * sr + (kurtosis(s, fisher=False) - 1) / 4 * sr ** 2))), float(sr)
S["SR_skill"] = [dsr(sk[k], allsr)[1] for k in S.index]; S["DSR_N22"] = [dsr(sk[k], allsr)[0] for k in S.index]
S["cscv_mean"] = [dist[k]["mean"] for k in S.index]; S["cscv_std"] = [dist[k]["std"] for k in S.index]; S["cscv_worst"] = [dist[k]["worst"] for k in S.index]
win = S.mean_term_brier.astype(float).idxmin()
ok = win != "K10" and float(S.loc[win, "p_sign_holm"]) < .05 and not (float(S.loc[win, "p_mcnemar_holm"]) < .05 and S.loc[win, "acc"] < S.loc["K10", "acc"])
use = win if (ok and pbo < .5) else "K10"
pd.set_option("display.width", 250); print(S.round(4).to_string()); print(f"PBO(CSCV,70)={pbo:.3f}; lowest Brier={win}; used for forward={use}")
# conformal diagnostic (80%) for the used model, 1990-2014 coverage per term + pending sets
U = POP[use]; cov = {}
for t in range(1990, 2015):
    c = U[(U.term < t) & (U.term >= t - 10) & U.y.notna()]; s = 1 - np.where(c.y == 1, c.P, 1 - c.P); q = np.nanquantile(s, .8)
    e = U[(U.term == t) & U.y.notna()]; inc1 = (1 - e.P) <= q; inc0 = e.P <= q
    cov[t] = {"coverage": float(np.where(e.y == 1, inc1, inc0).mean()), "singleton_share": float((inc1 ^ inc0).mean())}
cv = pd.DataFrame(cov).T; print("conformal 80%%: mean coverage %.3f, min %.3f, singleton share %.3f" % (cv.coverage.mean(), cv.coverage.min(), cv.singleton_share.mean()))
c = U[(U.term >= 2005) & (U.term <= 2014) & U.y.notna()]   # pending conformal quantile from 2005-2014 (holdout not used)
s = 1 - np.where(c.y == 1, c.P, 1 - c.P); q = float(np.nanquantile(s, .8))
pend = {k: C[C.term == 2026][["docket", "P"]].rename(columns={"P": "P_" + k}) for k, C in POP.items()}
PD = pd.concat([v.set_index("docket") for v in pend.values()], axis=1); PD["conformal80_set_" + use] = [("{rev}" if (1 - p) <= q and p > q else "{aff}" if p <= q and (1 - p) > q else "{rev,aff}") for p in PD["P_" + use]]
PD.to_csv("eval_k11/pending_OT2026_K11pop.csv"); S.to_csv("eval_k11/selection_1990_2014.csv"); B.to_csv("eval_k11/per_term_brier.csv"); cv.to_csv("eval_k11/conformal_coverage.csv")
json.dump({"lowest_brier": win, "used_for_forward": use, "pbo_cscv70": pbo, "cscv_dist": dist, "n_trials": 22, "conformal_q80_2005_2014": q}, open("eval_k11/verdict.json", "w"), indent=1)
print(PD.round(3).to_string())

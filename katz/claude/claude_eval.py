"""Amendment C1 (Claude) selection and gates (katz/AMENDMENT_C1_CLAUDE.md). 1990-2014 only: outcomes of terms >= 2015 are masked before any metric.
Primary metric: argued cases, label petitioner wins (partyWinning). Challengers KC1-KC4 (stage 2 on the strict20 forest). Comparator for the
gates: K10s = K10's own per-justice P through the identical stage 2 (no new features), so re-targeting the label earns nothing; K10 as
recorded (k11_eval protocol) is reported alongside. WF and purged/embargoed CPCV series; one-sided sign test and McNemar vs K10s (Holm over 4),
McNemar vs always-petitioner (Holm over all reported models), PBO by CSCV (WF and CPCV), DSR with N = 37 (WF and CPCV), ECE, calibration plot.
Writes katz/results/claude/ and katz/claude/results_local/P_wf_all.csv.gz (P for all terms; 2015+ not scored here). Usage: python -B claude_eval.py"""
import gzip, hashlib, itertools, json, os, sys
import numpy as np, pandas as pd
from scipy.stats import binomtest, kurtosis, norm, skew
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import stage2 as S
REPO = os.path.dirname(os.path.dirname(HERE)); OUT0 = os.path.join(REPO, "katz", "results", "claude")
OVR = {k: v for k, v in os.environ.items() if k.startswith("CLAUDE_")}; DRY = bool(OVR)   # any override = dry run (synthetic features)
OUT = os.environ.get("CLAUDE_OUT", OUT0); LOC = os.environ.get("CLAUDE_LOC", os.path.join(HERE, "results_local"))
assert not (DRY and os.path.abspath(OUT) == os.path.abspath(OUT0)), "dry run must not write to katz/results/claude"
os.makedirs(OUT, exist_ok=True); os.makedirs(LOC, exist_ok=True)
N_TRIALS = 37; CH = ["KC1", "KC2", "KC3", "KC4"]; REF = "K10s"; GPOP = [REF] + CH; POP = ["K10"] + GPOP; RES = os.path.join(S.ROOT, "katz", "results")
N_HOLD_REG = {"primary_argued_partyWinning": 772, "secondary_all_reverse": 800}   # registered holdout sizes (counts only)

# --- K10 and earlier trials exactly as recorded (katz_eval.build + k11_eval.cal: Platt on prior 10 terms, embargoed) ---
ns = {}; sys.argv = ["x", RES, os.path.join(LOC, "_katz_eval_scratch")]
exec(open(os.path.join(REPO, "katz", "katz_eval.py")).read().split("CS = {}")[0], ns)
DD, ARG = S.scdb_dates()
def cal(C, cols, kind="platt"):   # = k11_eval.cal
    out = pd.Series(np.nan, index=C.index); dd = C.index.map(DD)
    for t in sorted(C.term.unique()):
        if t < 1990: continue
        tr = C[(C.term < t) & (C.term >= t - 10) & C.y.notna() & ~((C.term == t - 1) & (dd >= pd.Timestamp(f"{t}-10-01")))]; te = C.term == t
        if kind == "iso": m = IsotonicRegression(out_of_bounds="clip", y_min=.01, y_max=.99).fit(tr[cols[0]], tr.y); out[te] = m.predict(C.loc[te, cols[0]])
        else:
            Z = lambda D: pd.concat([ns["lg"](D[c]) for c in cols], axis=1)
            out[te] = LogisticRegression(C=1e6).fit(Z(tr), tr.y).predict_proba(Z(C.loc[te]))[:, 1]
    return out
def mk(trial):
    C = ns["build"](trial, "pmaj"); C["P"] = cal(C, ["pm"]); return C
C10 = mk("K10")

# --- completeness and input pinning ---
if not DRY:
    assert "DONE" in open(os.path.join(HERE, "raw", "fetch.log")).read(), "supremecourt.gov fetch not finished"
    th = pd.read_csv(os.path.join(S.FEAT, "pit_theta.csv")); assert set(range(1980, 2027)) <= set(th.term), "pit_theta does not cover 1980-2026"
    assert json.load(open(os.path.join(LOC, "KC1", "run_meta.json")))["n_features"] == 862, "KC1 stage 1 is not the 862-feature strict20 set"
def sha(p):   # .gz files are hashed on their decompressed bytes (the gzip header carries a timestamp)
    return hashlib.sha256(gzip.open(p).read() if p.endswith(".gz") else open(p, "rb").read()).hexdigest()
INPUTS = {f"katz/claude/results_local/KC1/{f}": os.path.join(LOC, "KC1", f) for f in ("preds.csv.gz", "run_meta.json", "features.json")}
INPUTS |= {f"katz/claude/features/{f}": os.path.join(S.FEAT, f) for f in ("pit_theta.csv", "lc_ideology.csv", "cert_docket.csv", "qp_split.csv")}
INPUTS |= {os.path.join(S.ROOT, p): os.path.join(S.ROOT, p) for p in ("data/SCDB_2026_01_justiceCentered_Docket.csv", "katz/results/K10/preds.csv.gz",
           "katz/kalshi_hist/kalshi_settled_prices.csv", "katz/kalshi_hist/market_map_hist.csv")}

# --- stage 2: KC1-KC4 on KC1's forest; K10s = K10's forest through the same stage 2 (no Z); WF and CPCV ---
J25, C25 = S.frames(os.path.join(LOC, "KC1", "preds.csv.gz"))
J10, C10s = S.frames(os.path.join(RES, "K10", "preds.csv.gz"), families=())
PRIM = C25[C25.term.between(1990, 2014) & C25.y.notna()].index   # primary population: argued cases with a petitioner-wins label
assert C10.P.reindex(PRIM).notna().all() and set(PRIM) <= set(C10s.index), "K10 lacks P for part of the primary population"
assert set(C25[C25.term.between(1990, 2014) & C25.y_rev.notna()].index) == set(C10[C10.term.between(1990, 2014) & C10.y.notna()].index), "secondary population differs from K10"
N_HOLD = {"primary_argued_partyWinning": int((C25.term.between(2015, 2025) & C25.y.notna()).sum()), "secondary_all_reverse": int((C25.term.between(2015, 2025) & C25.y_rev.notna()).sum())}
if not DRY: assert N_HOLD == N_HOLD_REG, N_HOLD
coefs = []; WF = {"K10": C10, REF: S.wf(J10, C10s, "KC1")}
for m in CH: WF[m] = S.wf(J25, C25, m, coefs=coefs if m == "KC4" else None)
Pall = pd.DataFrame({m: WF[m].P for m in POP}); Pall.insert(0, "term", C25.term.reindex(Pall.index).fillna(C10.term)); Pall.insert(1, "docket", C25.docket.reindex(Pall.index))
Pall.to_csv(os.path.join(LOC, "P_wf_all.csv.gz"), compression={"method": "gzip", "mtime": 0}); INPUTS["katz/claude/results_local/P_wf_all.csv.gz"] = os.path.join(LOC, "P_wf_all.csv.gz")
HASH = {k: sha(p) for k, p in INPUTS.items() if os.path.exists(p)}; json.dump(HASH, open(os.path.join(OUT, "INPUT_SHA256.json"), "w"), indent=1)
CP = {"K10": None, REF: S.cpcv(J10, C10s, "KC1")} | {m: S.cpcv(J25, C25, m) for m in CH}; CP.pop("K10")

# --- mask holdout: from here on only 1990-2014 outcomes exist ---
Y = C25.y.copy(); Y[C25.term >= 2015] = np.nan; T = C25.term                       # PRIMARY: argued, petitioner wins
Y2 = C25.y_rev.copy(); Y2[C25.term >= 2015] = np.nan                                 # secondary: all cases, reverse (K-ledger, K10 0.2052)
def per_term(P, lo=1990, hi=2014):
    c = pd.DataFrame({"P": P, "y": Y, "term": T}).dropna(); c = c[c.term.between(lo, hi)]; return ((c.P - c.y) ** 2).groupby(c.term).mean()
Bwf = pd.DataFrame({m: per_term(WF[m].P) for m in POP})
cpb = lambda m: CP[m].assign(y=CP[m].docketId.map(Y)).dropna(subset=["y"]).assign(b=lambda d: (d.P - d.y) ** 2)
cp_path = {m: cpb(m).groupby(["path", "term"]).b.mean().unstack("term") for m in GPOP}
cp_split = {m: cpb(m).groupby(["split", "term"]).b.mean().groupby("split").mean() for m in GPOP}
Bcp = pd.DataFrame({m: cp_path[m].mean() for m in GPOP})                         # CPCV per-term Brier = mean over 9 paths
Pcp = {m: CP[m].groupby("docketId").P.mean() for m in GPOP}                      # CPCV P per docket = mean over its 9 test predictions
prior = {}
for t in range(1990, 2015):
    h = Y[(T < t) & (T >= t - 10)].dropna(); cc = Y[(T == t)].dropna(); prior[t] = ((h.mean() - cc) ** 2).mean()
prior = pd.Series(prior)

def holm(p):
    p = pd.Series(p).dropna().astype(float).sort_values(); run = 0; h = {}
    for i, (k, v) in enumerate(p.items()): run = max(run, min(1, (len(p) - i) * v)); h[k] = run
    return pd.Series(h)
def pbo(B):   # = k11_eval CSCV: 1991-2014, 8 groups x 3 terms, 70 complementary splits
    Bt = B.loc[1991:2014]; grp = np.repeat(np.arange(8), 3); lam = []
    for isg in itertools.combinations(range(8), 4):
        im = np.isin(grp, isg); ib = Bt[im].mean(); ob = Bt[~im].mean(); best = ib.idxmin()
        rank = (ob > ob[best]).sum() + 1; w_ = rank / (len(ob) + 1); lam.append(np.log(w_ / (1 - w_)))
    return float(np.mean(np.array(lam) <= 0))
def dsr(s, srs, n=N_TRIALS):   # = k11_eval.dsr with n = 37
    sr = s.mean() / s.std(ddof=1); T_ = len(s); e = .5772156649; v = np.var(srs, ddof=1)
    sr0 = np.sqrt(v) * ((1 - e) * norm.ppf(1 - 1 / n) + e * norm.ppf(1 - 1 / (n * np.e)))
    return float(norm.cdf((sr - sr0) * np.sqrt(T_ - 1) / np.sqrt(1 - skew(s) * sr + (kurtosis(s, fisher=False) - 1) / 4 * sr ** 2))), float(sr)
def mcn(ok_a, ok_b):   # exact McNemar: a right & b wrong vs a wrong & b right
    x, y_ = int((ok_a & ~ok_b).sum()), int((~ok_a & ok_b).sum()); return x, y_, (binomtest(x, x + y_).pvalue if x + y_ else 1.0)
def ece(P, y):
    c = pd.DataFrame({"P": P, "y": y}).dropna(); return float(np.abs(c.groupby(pd.cut(c.P, np.linspace(0, 1, 11)), observed=True).apply(lambda g: len(g) * (g.P.mean() - g.y.mean()), include_groups=False)).sum() / len(c))

# SR-variance pool (registered): every listed trial must load (no silent skip); the other Amendment 5's K20-K23 count in N only
POOL = ["K00", "K01", "K02", "K06", "K07", "K09", "K11", "K15", "K16", "K17", "K18", "K19"]
extra = {}
for k in POOL:
    if DRY and not os.path.exists(os.path.join(RES, k, "preds.csv.gz")): print("dry run: skip", k); continue
    extra[k] = (prior - per_term(mk(k).P)).dropna()
C12 = C10.copy(); C12["P"] = cal(C10, ["pm"], "iso"); extra["K12"] = (prior - per_term(C12.P)).dropna()
ms = pd.read_csv(os.path.join(RES, "masse_live", "preds.csv")).set_index("docketId"); C13 = C10.copy(); C13["mp"] = C13.index.map(ms.p_pet); C13["kp"] = C10.pm
hs = C13.mp.notna(); C13.loc[~hs, "mp"] = C13.loc[~hs, "kp"]; C13["P"] = cal(C13.assign(kp=C13.kp.clip(.01, .99), mp=C13.mp.clip(.01, .99)), ["kp", "mp"]); C13.loc[C13.term < 1990, "P"] = np.nan
extra["K13"] = (prior - per_term(C13.P)).dropna()
sk_wf = {m: (prior - Bwf[m]).dropna() for m in POP}; sk_cp = {m: (prior - Bcp[m]).dropna() for m in GPOP}
allsr = [s.mean() / s.std(ddof=1) for s in {**extra, **sk_wf}.values()]

rows = {}; ix = Y[T.between(1990, 2014)].dropna().index; yv = Y.loc[ix] == 1
ok = {m: ((WF[m].P.reindex(ix) > .5) == yv) for m in POP}; okc = {m: ((Pcp[m].reindex(ix) > .5) == yv) for m in GPOP}; ar = yv.copy()
ll = lambda P, y: float(-np.mean(y * np.log(P.clip(1e-6)) + (1 - y) * np.log((1 - P).clip(1e-6))))
for m in POP:
    P = WF[m].P.reindex(ix); r = {"n": len(ix), "wf_mean_term_brier": Bwf[m].mean(), "wf_pooled_brier": float(((P - Y.loc[ix]) ** 2).mean()),
         "wf_logloss": ll(P, Y.loc[ix]), "wf_acc": float(ok[m].mean()), "wf_ece10": ece(P, Y.loc[ix]), "sharpness_sd": float(P.std()), "mean_P": float(P.mean())}
    if m in GPOP:
        Q = Pcp[m].reindex(ix)
        r |= {"cpcv_mean_term_brier": Bcp[m].mean(), "cpcv_path_mean": float(cp_path[m].mean(1).mean()), "cpcv_path_std": float(cp_path[m].mean(1).std(ddof=0)),
              "cpcv_path_worst": float(cp_path[m].mean(1).max()), "cpcv_split_mean": float(cp_split[m].mean()), "cpcv_split_std": float(cp_split[m].std(ddof=0)),
              "cpcv_split_worst": float(cp_split[m].max()), "cpcv_pooled_brier": float(((Q - Y.loc[ix]) ** 2).mean()), "cpcv_logloss": ll(Q, Y.loc[ix]),
              "cpcv_acc": float(okc[m].mean()), "cpcv_ece10": ece(Q, Y.loc[ix])}
        r["cpcv_mcnemar_vs_AR"] = "%d/%d" % mcn(okc[m], ar)[:2]; r["p_cpcv_mcnemar_vs_AR"] = mcn(okc[m], ar)[2]
        r["DSR_cpcv_N37"], r["SR_cpcv"] = dsr(sk_cp[m], allsr)
    c2 = pd.DataFrame({"P": WF[m].P, "y": Y2, "term": T}).dropna(); c2 = c2[c2.term.between(1990, 2014)]   # secondary (all cases, reverse label)
    r["sec_all_reverse_mean_term_brier"] = float(((c2.P - c2.y) ** 2).groupby(c2.term).mean().mean()); r["sec_all_reverse_acc"] = float(((c2.P > .5) == (c2.y == 1)).mean()); r["sec_n"] = len(c2)
    r["mcnemar_vs_AR"] = "%d/%d" % mcn(ok[m], ar)[:2]; r["p_mcnemar_vs_AR"] = mcn(ok[m], ar)[2]
    for ref, tag in ((REF, "K10s"), ("K10", "K10rec")):
        if m in (ref, "K10"): continue
        d = (Bwf[m] - Bwf[ref]).dropna(); w = int((d < 0).sum()); r[f"terms_better_vs_{tag}"] = f"{w}/{len(d)}"
        r[f"p_sign_vs_{tag}"] = binomtest(w, len(d), alternative="greater").pvalue   # one-sided: challenger better in more terms than chance
        x, y_, p = mcn(ok[m], ok[ref]); r[f"mcnemar_vs_{tag}"] = f"{x}/{y_}"; r[f"p_mcnemar_vs_{tag}"] = p
    if m in CH: dc = (Bcp[m] - Bcp[REF]).dropna(); r["cpcv_terms_better_vs_K10s"] = f"{int((dc < 0).sum())}/{len(dc)}"
    r["DSR_wf_N37"], r["SR_wf"] = dsr(sk_wf[m], allsr)
    rows[m] = r
SEL = pd.DataFrame(rows).T
SEL["p_sign_vs_K10s_holm"] = holm(SEL.loc[CH, "p_sign_vs_K10s"]); SEL["p_mcnemar_vs_K10s_holm"] = holm(SEL.loc[CH, "p_mcnemar_vs_K10s"])
SEL["p_mcnemar_vs_AR_holm"] = holm(SEL.p_mcnemar_vs_AR); SEL["p_cpcv_mcnemar_vs_AR_holm"] = holm(SEL.p_cpcv_mcnemar_vs_AR)
PBO_WF, PBO_CP = pbo(Bwf[GPOP]), pbo(Bcp[GPOP])
win = SEL.loc[CH, "wf_mean_term_brier"].astype(float).idxmin(); s = SEL.loc[win]
gates = {"a_sign_vs_K10s_holm_lt_0.05_and_lower_brier": bool(s.p_sign_vs_K10s_holm < .05 and s.wf_mean_term_brier < SEL.loc[REF, "wf_mean_term_brier"]),
         "b_not_sig_worse_mcnemar_vs_K10s": bool(not (s.p_mcnemar_vs_K10s_holm < .05 and s.wf_acc < SEL.loc[REF, "wf_acc"])),
         "c_pbo_wf_lt_0.5": PBO_WF < .5, "d_cpcv_brier_below_K10s": bool(s.cpcv_mean_term_brier < SEL.loc[REF, "cpcv_mean_term_brier"])}
replaces = all(gates.values())
edge = {"replaces_K10": replaces, "DSR_wf_gt_0.95": bool(s.DSR_wf_N37 > .95), "DSR_cpcv_gt_0.95": bool(s.DSR_cpcv_N37 > .95), "pbo_wf_lt_0.5": PBO_WF < .5, "pbo_cpcv_lt_0.5": PBO_CP < .5}
V = {"winner_lowest_wf_brier": win, "comparator": REF, "selection_gates": gates, "replaces_K10": replaces, "used_for_forward": win if replaces else "K10",
     "edge_gates": edge, "edge_survives": all(edge.values()), "pbo_wf": PBO_WF, "pbo_cpcv": PBO_CP, "n_trials": N_TRIALS,
     "dsr_sr_variance_from": sorted(list(extra) + POP), "cpcv_active_families": {m: CP[m].attrs.get("active") for m in GPOP},
     "input_sha256": HASH, "n_primary_1990_2014": len(PRIM), "n_holdout_expected": N_HOLD, "label_primary": "partyWinning (argued cases)",
     "dry_run": DRY, "overrides": OVR, "holdout": "not read by this script (2015+ outcomes masked)"}
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 80)
SEL.to_csv(os.path.join(OUT, "selection_1990_2014.csv")); Bwf.assign(prior_rate=prior).to_csv(os.path.join(OUT, "per_term_brier_WF.csv"))
Bcp.assign(prior_rate=prior).to_csv(os.path.join(OUT, "per_term_brier_CPCV.csv"))
pd.concat({m: cp_path[m].mean(1) for m in GPOP}, axis=1).to_csv(os.path.join(OUT, "cpcv_path_mean_brier.csv"))
pd.concat({m: cp_path[m] for m in GPOP}, names=["model"]).to_csv(os.path.join(OUT, "cpcv_path_term_brier.csv"))   # 9 paths x 25 terms per model
pd.concat({m: cp_split[m] for m in GPOP}, axis=1).to_csv(os.path.join(OUT, "cpcv_split_brier.csv"))
json.dump(V, open(os.path.join(OUT, "verdict.json"), "w"), indent=1, default=str)

# --- diagnostics (never used to choose): coverage, coefficients, MQ check ---
cov = pd.DataFrame({"dockets": C25[C25.term.between(1990, 2026)].groupby("term").size(), "argued_share": C25.groupby("term").argued.mean(),
                    "primary_n": C25.groupby("term").y.apply(lambda s: s.notna().sum()), "lc_have": C25.groupby("term").lc_have.mean(),
                    "theta_have_rows": J25.groupby("term").theta_have.mean(), "docket_era": C25.groupby("term").docket_era.mean(),
                    "cert_features_present": C25.groupby("term").cvsg.apply(lambda s: s.notna().mean()), "qp_present": C25.groupby("term").qp_split.apply(lambda s: s.notna().mean())}).loc[1990:2026]
cov.to_csv(os.path.join(OUT, "coverage_by_term.csv"))
if coefs: pd.DataFrame(coefs).to_csv(os.path.join(OUT, "coefs_wf_case_K28_to2015.csv"), index=False)
fc = []
for m in CH:
    zj, zc = S.zcols(m); tr = C25[C25.term.between(1980, 2014) & C25.argued].index
    jt = J25.docketId.isin(tr) & (J25.jod >= 0); cj = S.active(["lp"] + zj, J25.loc[jt], "justice"); A, _ = S._z(J25.loc[jt], J25.loc[jt], cj)
    fc.append({"model": m, "level": "justice", **dict(zip(cj, LogisticRegression(C=1.0, max_iter=2000).fit(A, (J25.jod[jt] > 0).astype(int)).coef_[0]))})
pd.DataFrame(fc).to_csv(os.path.join(OUT, "coefs_full_fit_justice_level_1980_2014_argued.csv"), index=False)
mq = os.path.join(S.FEAT, "pit_mq_check.csv")
if os.path.exists(mq): pd.read_csv(mq).to_csv(os.path.join(OUT, "pit_mq_check.csv"), index=False)

# --- calibration plot (WF and CPCV, pooled 1990-2014) ---
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
f, ax = plt.subplots(1, 3, figsize=(17, 5)); bins = np.linspace(0, 1, 11)
for k, (lab, PP, ms_) in enumerate([("walk-forward", {m: WF[m].P for m in POP}, POP), ("CPCV (mean of 9 test predictions)", Pcp, GPOP)]):
    for m in ms_:
        c = pd.DataFrame({"P": PP[m].reindex(ix), "y": Y.loc[ix]}).dropna(); g = c.groupby(pd.cut(c.P, bins), observed=True).agg(P=("P", "mean"), y=("y", "mean"))
        ax[k].plot(g.P, g.y, "o-", ms=3, lw=1.6 if m in ("K10", REF, win) else .8, label=f"{m} (ECE {ece(c.P, c.y):.3f})")
    ax[k].plot([0, 1], [0, 1], "k--", lw=.8); ax[k].set_xlabel("predicted P(petitioner wins)  [K10 as recorded: its P(reverse)]")
    ax[k].set_ylabel("observed petitioner-win rate (argued cases)"); ax[k].set_title(f"Calibration 1990-2014, {lab}"); ax[k].legend(fontsize=7)
for m in POP: ax[2].plot(Bwf.index, Bwf[m].rolling(3, center=True).mean(), lw=1.6 if m in ("K10", REF, win) else .8, label=m)
ax[2].plot(prior.index, prior.rolling(3, center=True).mean(), "k--", label="prior-10 rate"); ax[2].set_title("WF per-term Brier, primary metric (3-term mean)"); ax[2].legend(fontsize=7)
f.tight_layout(); f.savefig(os.path.join(OUT, "calibration_1990_2014.png"), dpi=110)
print(SEL.T.to_string()); print(json.dumps({k: v for k, v in V.items() if k != "input_sha256"}, indent=1, default=str)); print(cov.round(3).to_string())

"""Amendment C1 (Claude) stage 2 (katz/AMENDMENT_C1_CLAUDE.md): stacked logistic models on stage-1 per-justice P(reverse), fit walk-forward (WF,
prior 10 terms, Oct-1 embargo) or by purged/embargoed CPCV (10 term groups, 2 test groups, 45 splits, 9 paths). Library for
claude_eval.py and holdout_once_claude.py. Paper only. Reads stage-1 preds and katz/claude/features/*.csv; SCDB dates read-only from
$SCOTUS_ROOT. Outcomes of terms >= 2015 are used only as walk-forward training rows for later terms (as K10's own P); no metric on them here.
No availability ("have") flag is ever a regressor: availability is by era or by pre-decision source type and only switches families on/off;
a missing value is imputed at the training mean (0 after standardization), which a linear model cannot single out (review fix: qp_have and
grant-found flags encoded argued/summary status).
Primary population and label (Kalshi-aligned): ARGUED cases (SCDB dateArgument present) scored on y = petitioner wins (SCDB partyWinning 1/0;
2 = unclear excluded). Stage 2 is trained on argued cases only; P is produced for every docket. y_rev (case_outcome_disposition, all
cases, as K05/K10) is kept for the secondary, K-ledger-comparable table."""
import itertools, os
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = os.environ.get("SCOTUS_ROOT", os.path.expanduser("~/scotus-predict-rerun"))
HERE = os.path.dirname(os.path.abspath(__file__)); FEAT = os.environ.get("CLAUDE_FEAT", os.path.join(HERE, "features"))   # override = dry runs only
EPS = 1e-4
lg = lambda p: np.log(np.clip(p, EPS, 1 - EPS) / (1 - np.clip(p, EPS, 1 - EPS)))
FAM = {"A": ["sA_theta", "sA_med", "s_lc"],
       "B": ["cvsg", "amicus_cert", "relists_log", "log_days_to_grant", "ifp", "qp_split"],
       "C": ["lc_dc", "s_lc_dc"]}
MODELS = {"KC1": ([], []), "KC2": (["A"], []), "KC3": ([], ["C"]), "KC4": (["A"], ["C"])}   # family B (cert stage) built but NOT registered: overlaps the other Amendment 5's K21
GROUPS = [(1990, 1992), (1993, 1995), (1996, 1998), (1999, 2001), (2002, 2004), (2005, 2006), (2007, 2008), (2009, 2010), (2011, 2012), (2013, 2014)]
DOCKET_ERA, QP_ERA = 2000, 2002   # supremecourt.gov online dockets exist for docket years >= 2000 (00-xxxx), QP PDFs for >= 2002
# sub-family -> (regressor columns, availability column used only for activation); s_lc and ifp are always on
SUB = {"theta": (["sA_theta", "sA_med"], "theta_have"), "docket": (["cvsg", "amicus_cert", "relists_log", "log_days_to_grant"], "docket_era"),
       "qp": (["qp_split"], "qp_era"), "lc": (["lc_dc", "s_lc_dc"], "lc_have")}
ACT_RATE, ACT_N = 0.25, {"case": 150, "justice": 1000}

def scdb_meta():
    d = pd.read_csv(f"{ROOT}/data/SCDB_2026_01_justiceCentered_Docket.csv", encoding="ISO-8859-1", low_memory=False,
                    usecols=["docketId", "dateDecision", "dateArgument", "partyWinning"]).drop_duplicates("docketId").set_index("docketId")
    return pd.to_datetime(d.dateDecision, format="%m/%d/%Y", errors="coerce"), d.dateArgument.notna(), d.partyWinning
scdb_dates = lambda: scdb_meta()[:2]

def docket_year(s):
    yy = s.str.extract(r"^(\d{2})-\d{1,5}$")[0].astype(float); return pd.Series(np.where(yy >= 50, 1900 + yy, 2000 + yy), index=s.index)

def frames(pred_path, families=("A", "B", "C")):
    """J: one row per (docket, justice) with stage-1 p_rev and Zj; C: one row per docket with y, decision date and Zc."""
    d = pd.read_csv(pred_path).dropna(subset=["p_rev"])
    d["docket"] = d.docket.astype(object).where(d.docket.notna(), "").astype(str).str.strip()
    d["s"] = np.select([d.lcDispositionDirection == 1, d.lcDispositionDirection == 2], [1.0, -1.0], 0.0)
    J = d[["docketId", "term", "justice", "p_rev", "justice_outcome_disposition", "s"]].rename(columns={"justice_outcome_disposition": "jod"}).reset_index(drop=True)
    J["lp"] = lg(J.p_rev.values); n0 = len(J)
    C = d.groupby("docketId").agg(term=("term", "first"), docket=("docket", "first"), cod=("case_outcome_disposition", "first"), s=("s", "first"))
    C["y_rev"] = np.where(C.cod > 0, 1.0, np.where(C.cod == 0, 0.0, np.nan)); C.loc[C.term >= 2026, "y_rev"] = np.nan   # secondary (K-ledger): outcome -1 excluded
    DD, ARG, PW = scdb_meta(); C["dd"] = C.index.map(DD)
    C["argued"] = C.index.map(ARG).fillna(False).astype(bool); C.loc[C.term >= 2026, "argued"] = True   # pending OT2026 rows are all granted plenary review
    pw = C.index.map(PW).astype(float); C["y"] = np.where(C.argued & (pw == 1), 1.0, np.where(C.argued & (pw == 0), 0.0, np.nan))   # PRIMARY label
    C.loc[C.term >= 2026, "y"] = np.nan
    if "A" in families:
        th = pd.read_csv(f"{FEAT}/pit_theta.csv")[["term", "justice", "theta", "imputed"]]
        J = J.merge(th, on=["term", "justice"], how="left", validate="many_to_one"); assert len(J) == n0
        J["theta_have"] = (J.theta.notna() & (J.imputed == 0)).astype(float)
        J["theta_med"] = J.groupby("docketId").theta.transform("median")
        J["sA_theta"] = J.s * J.theta; J["sA_med"] = J.s * J.theta_med; J["s_lc"] = J.s
    if "B" in families:
        yr = docket_year(C.docket); C["docket_era"] = (yr >= DOCKET_ERA).astype(float); C["qp_era"] = (yr >= QP_ERA).astype(float)
        cd = pd.read_csv(f"{FEAT}/cert_docket.csv", dtype={"docket": str}); cd["docket"] = cd.docket.str.strip(); cd = cd.drop_duplicates("docket").set_index("docket")
        g = pd.to_datetime(C.docket.map(cd.grant_date), errors="coerce")
        dispo = C.docket.map(cd.parse_note).fillna("").astype(str).str.contains("summary_disposition")   # review: grant_text regex misfired on cert before judgment
        bad = g.isna() | dispo | (C.dd.notna() & (g >= C.dd))   # no grant entry, or the "grant" is the decision itself
        for c in ("cvsg", "amicus_cert", "relists_log", "log_days_to_grant"): C[c] = C.docket.map(cd[c]).where(~bad)
        qp = pd.read_csv(f"{FEAT}/qp_split.csv", dtype={"docket": str}); qp["docket"] = qp.docket.str.strip(); qp = qp.drop_duplicates("docket").set_index("docket")
        C["qp_split"] = C.docket.map(qp.qp_split)
        ser = C.docket.str.extract(r"^\d{2}-(\d{1,5})$")[0].astype(float); C["ifp"] = np.where(ser.notna(), (ser >= 5000).astype(float), np.nan)
        C["grant_is_decision"] = (g.notna() & bad).astype(float)   # diagnostics only
    if "C" in families:
        li = pd.read_csv(f"{FEAT}/lc_ideology.csv").drop_duplicates("docketId").set_index("docketId")
        C["lc_have"] = C.index.map(li.lc_have).fillna(0).astype(float)   # = court-of-appeals source (pre-decision), activation only
        C["dshare"] = C.index.map(li.dshare).where(C.lc_have == 1)
        C["lc_dc"] = C.dshare - 0.5; C["s_lc_dc"] = C.s * C.lc_dc
    return J, C

def pmaj(dk, q):
    """Vectorized Poisson-binomial P(# reverse > n/2), ties affirm, per docket (dk = docket codes 0..nd-1). n = every justice row of the
    docket (as K05/K10: SCDB non-participants with a missing vote keep a row and a stage-1 P; pending rows cannot show recusals)."""
    o = np.argsort(dk, kind="stable"); dk, q = dk[o], q[o]
    nd = int(dk.max()) + 1; n = np.bincount(dk, minlength=nd); start = np.r_[0, np.cumsum(n)[:-1]]; slot = np.arange(len(dk)) - start[dk]
    Q = np.full((nd, int(n.max())), np.nan); Q[dk, slot] = q
    D = np.zeros((nd, Q.shape[1] + 1)); D[:, 0] = 1
    for k in range(Q.shape[1]):
        qk = Q[:, k]; h = ~np.isnan(qk); qk = np.nan_to_num(qk)[:, None]
        N = np.empty_like(D); N[:, 0] = D[:, 0] * (1 - qk[:, 0]); N[:, 1:] = D[:, 1:] * (1 - qk) + D[:, :-1] * qk
        D = np.where(h[:, None], N, D)
    return np.where(np.arange(D.shape[1])[None, :] >= (n // 2 + 1)[:, None], D, 0).sum(1)

def active(cols, Dtr, level):
    """Family activation: a sub-family enters a fit only if its availability column is 1 for >= 25% of the training rows and for >= 150
    training cases (>= 1000 justice rows); otherwise it is left out of that fit."""
    drop = set()
    for fam, (fc, h) in SUB.items():
        if any(c in cols for c in fc) and not (Dtr[h].mean() >= ACT_RATE and Dtr[h].sum() >= ACT_N[level]): drop |= set(fc)
    return [c for c in cols if c not in drop]

def _z(Dtr, Dap, cols):
    """Standardize on the observed training values, clip to +-5, missing -> 0 (= training mean)."""
    Xtr, Xap = Dtr[cols].values.astype(float).copy(), Dap[cols].values.astype(float).copy()
    for k in range(len(cols)):
        ok = np.isfinite(Xtr[:, k]); mu = Xtr[ok, k].mean() if ok.any() else 0.0; sd = Xtr[ok, k].std() if ok.any() else 1.0
        sd = sd if sd > 0 else 1.0
        Xtr[:, k], Xap[:, k] = (np.clip(np.nan_to_num((X - mu) / sd, nan=0.0), -5, 5) for X in (Xtr[:, k], Xap[:, k]))
    return Xtr, Xap

def _lr(X, y, Xap):
    if len(np.unique(y)) < 2: return np.full(len(Xap), float(np.mean(y)))
    return LogisticRegression(C=1.0, max_iter=2000).fit(X, y).predict_proba(Xap)[:, 1]

def zcols(model):
    zj, zc = MODELS[model]; return [c for f in zj for c in FAM[f]], [c for f in zc for c in FAM[f]]

def embargo_ok(C, t):   # drop term t-1 cases decided on/after Oct 1 of t (Amendment 2 G4)
    return ~((C.term == t - 1) & (C.dd >= pd.Timestamp(f"{t}-10-01"))).values

def wf(J, C, model, tmin=1990, tmax=2026, coefs=None, coef_tmax=2015):
    """Walk-forward stage 2: per-justice LR for every term >= 1981 on terms max(1980, t-10)..t-1; case LR for terms >= tmin on terms
    max(1981, t-10)..t-1, so every case LR is trained on out-of-sample per-justice P built the same way as the test term's; both embargoed.
    Coefficients are logged only for terms <= coef_tmax (training windows ending by 2014): nothing about 2015+ outcomes leaves here."""
    zj, zc = zcols(model); J = J.copy(); C = C.copy(); J["pj"] = J.p_rev
    for t in range(1981, tmax + 1):
        te = (J.term == t).values
        if not te.any(): continue
        win = C[(C.term >= max(1980, t - 10)) & (C.term < t) & embargo_ok(C, t) & C.argued].index
        tr = J.docketId.isin(win).values & (J.jod >= 0).values; cj = active(["lp"] + zj, J.loc[tr], "justice")
        A, B = _z(J.loc[tr], J.loc[te], cj)
        J.loc[te, "pj"] = _lr(A, (J.jod[tr] > 0).astype(int).values, B)
    codes, uniq = pd.factorize(J.docketId); C["pm"] = pd.Series(pmaj(codes, J.pj.values), index=uniq).reindex(C.index)
    C["P"] = np.nan; C["lpm"] = lg(C.pm.values)
    for t in range(tmin, tmax + 1):
        te = (C.term == t).values
        if not te.any(): continue
        tr = ((C.term >= max(1981, t - 10)) & (C.term < t)).values & embargo_ok(C, t) & C.y.notna().values; cc = active(["lpm"] + zc, C.loc[tr], "case")
        A, B = _z(C.loc[tr], C.loc[te], cc)
        C.loc[te, "P"] = _lr(A, C.y[tr].astype(int).values, B)
        if coefs is not None and zc and t <= coef_tmax and tr.sum() > 50:
            m = LogisticRegression(C=1.0, max_iter=2000).fit(A, C.y[tr].astype(int).values); coefs.append({"term": t, "level": "case", **dict(zip(cc, m.coef_[0]))})
    return C

def cpcv_splits():
    return list(itertools.combinations(range(len(GROUPS)), 2))

def cpcv(J, C, model):
    """Purged + embargoed CPCV of stage 2 over 1990-2014. Returns P per (split, docket) for test dockets, and path assignment.
    Training = terms 1980-2014 outside the 2 test groups, minus purge (term before a test group, decided >= Oct 1 of its first term)
    and embargo (the term right after each test group). 2015+ never used. Family activation is decided ONCE on the full 1980-2014 pool
    (not per split) so that which groups are held out cannot switch families on or off."""
    zj, zc = zcols(model); out = []
    pool = C.term.between(1980, 2014)
    cj = active(["lp"] + zj, J[J.docketId.isin(C.index[pool & C.argued]) & (J.jod >= 0)], "justice"); cc = active(["lpm"] + zc, C[pool & C.y.notna()], "case")
    for si, gs in enumerate(cpcv_splits()):
        test_terms = set().union(*[range(GROUPS[g][0], GROUPS[g][1] + 1) for g in gs])
        emb_terms = {GROUPS[g][1] + 1 for g in gs} - test_terms
        trc = (pool & C.argued & ~C.term.isin(test_terms) & ~C.term.isin(emb_terms)).values
        for g in gs:
            f = GROUPS[g][0]; trc = trc & ~((C.term == f - 1) & (C.dd >= pd.Timestamp(f"{f}-10-01"))).values   # purge
        tec = C.term.isin(test_terms).values
        trd, ted = C.index[trc], C.index[tec]
        jtr = J.docketId.isin(trd).values & (J.jod >= 0).values; jap = J.docketId.isin(trd.union(ted)).values
        A, B = _z(J.loc[jtr], J.loc[jap], cj)
        Jap = J.loc[jap, ["docketId"]].copy(); Jap["pj"] = _lr(A, (J.jod[jtr] > 0).astype(int).values, B)
        codes, uniq = pd.factorize(Jap.docketId); pm = pd.Series(pmaj(codes, Jap.pj.values), index=uniq)
        Cs = C.loc[trd.union(ted)].copy(); Cs["lpm"] = lg(pm.reindex(Cs.index).values)
        ctr = Cs.index.isin(trd) & Cs.y.notna().values; cte = Cs.index.isin(ted)
        A, B = _z(Cs.loc[ctr], Cs.loc[cte], cc)
        out.append(pd.DataFrame({"split": si, "docketId": Cs.index[cte], "term": Cs.term[cte].values, "P": _lr(A, Cs.y[ctr].astype(int).values, B)}))
    R = pd.concat(out, ignore_index=True)
    path = {}   # the p-th split (lexicographic) that contains group g gives path p for g's terms
    for g in range(len(GROUPS)):
        for p, si in enumerate([si for si, gs in enumerate(cpcv_splits()) if g in gs]): path[(si, g)] = p
    gi = {t: g for g, (a, b) in enumerate(GROUPS) for t in range(a, b + 1)}
    R["group"] = R.term.map(gi); R["path"] = [path[(s, g)] for s, g in zip(R.split, R.group)]
    R.attrs["active"] = {"justice": cj, "case": cc}
    return R

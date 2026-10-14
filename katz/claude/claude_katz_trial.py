"""Amendment 6 (Claude) stage-1 runner = katz_trial.py (katz-improve) + K25 (strict20) + read-only input root. Paper only.
Inputs are read from $SCOTUS_ROOT (default ~/scotus-predict-rerun): data/, src/, pending_inputs/ (never written). Output default
katz/claude/results_local/<trial>. strict20 never loads Oyez and asserts 862 features with no forbidden prefix (AMENDMENT_6_CLAUDE.md).
Original docstring:
katz-improve trial runner (KATZ_PREREG.md). Paper only. Lives in ~/scotus-predict-rerun/katz/ on the Mac.
Reads ../data, ../src (patched copy), ../pending_inputs, ./oyez (optional); writes only to --out.
T0 fixes (all trials): no dateDecision/dateRearg-derived features (decision_month_*, decision_delay) and no -1 date placeholder;
term_raw/natural_court_raw and term_*/natural_court_* dropped; direction code 3 -> NaN before lag features (B4);
embargo: term t-1 rows decided >= Oct 1 of t excluded from training (L7); random_state=0; float32.
Outputs per-justice P(reverse) for terms >= 1980 (calibration window) incl. pending OT2026 rows (never trained on)."""
import argparse, datetime, gc, hashlib, json, os, platform, resource, sys, time
import numpy, pandas, sklearn
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.environ.get("SCOTUS_ROOT", os.path.expanduser("~/scotus-predict-rerun"))
sys.path.insert(0, os.path.join(ROOT, "src"))
from legacy_model import get_raw_scdb_data, preprocess_raw_data
from legacy_model_data import party_map_data
SPEC = {"K00": ("rf", "orig", []), "K01": ("rf", "orig", ["strict"]), "K02": ("rf", "none", []),
        "K06": ("gbm", None, []), "K07": ("rf", "orig", ["free"]), "K08": ("rf", "orig", ["free", "oa"]), "K09": ("mlp", None, ["free"]), "K10": ("rf", "orig", ["free", "pendfix"]),
        "K11": ("rf", "orig", ["free", "missaug"]), "K15": ("hier", None, ["free", "pendfix"]),
        "K25": ("rf", "orig", ["free", "pendfix", "strict20"])}   # Amendment 6 (Claude): stage 1 of K25-K28
ap = argparse.ArgumentParser(); ap.add_argument("--trial", required=True, choices=SPEC); ap.add_argument("--n-jobs", type=int, default=-1)
ap.add_argument("--max-term", type=int); ap.add_argument("--min-term", type=int, help="smoke only"); ap.add_argument("--out")
a = ap.parse_args(); MODEL, CW, FS = SPEC[a.trial]; OUT = a.out or os.path.join(HERE, "results_local", a.trial); os.makedirs(OUT, exist_ok=True)
T0 = time.time(); SAVE_FROM = 1980; DEV = {"rf": "cpu", "gbm": "cpu", "mlp": "cpu", "hier": "cpu"}
def log(m):
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss; r = r / 2**20 if platform.system() == "Darwin" else r / 1024
    print(f"[{datetime.datetime.now():%H:%M:%S}] [+{time.time()-T0:7.1f}s] [peakRSS {r:6.0f} MB] {a.trial} {m}", flush=True)
cfg = {"trial": a.trial, "model": MODEL, "class_weight": CW, "features": FS, "fixes": "T0", "seed": 0, "dtype": "float32"}
cfg_hash = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]; log(f"{cfg} {cfg_hash} sklearn {sklearn.__version__}")
rd = lambda p: pandas.read_csv(p, encoding="ISO-8859-1", low_memory=False)
legacy = rd(os.path.join(ROOT, "data", "SCDB_Legacy_07_justiceCentered_Citation.csv")); modern = rd(os.path.join(ROOT, "data", "SCDB_2026_01_justiceCentered_Docket.csv"))
pend = rd(os.path.join(ROOT, "pending_inputs", "pending_cases_scdb_rows.csv"))
assert list(legacy.columns) == list(modern.columns) == list(pend.columns) and pend.vote.isna().all()
M = pandas.concat([legacy, modern, pend], ignore_index=True); del legacy, modern, pend
if a.max_term: M = M[M.term <= a.max_term]
if a.min_term: M = M[M.term >= a.min_term]
M.loc[~M.direction.isin([1, 2]), "direction"] = numpy.nan          # B4
M.loc[~M.decisionDirection.isin([1, 2]), "decisionDirection"] = numpy.nan
mp = os.path.join(OUT, "_in.csv"); M.to_csv(mp, index=False, encoding="ISO-8859-1"); del M; gc.collect()
raw = get_raw_scdb_data(mp); os.remove(mp)
F = preprocess_raw_data(raw, include_direction=True).astype(numpy.float32)
drop = [f for f in F.columns if f.startswith(("term_", "natural_court", "decision_month_")) or f in ("decision_delay",)]
if "strict" in FS: drop += [f for f in F.columns if f.startswith(("issue_", "law_type_", "law_supp_"))]
if "strict20" in FS: drop += [f for f in F.columns if f.startswith(("issue_", "law_type_", "argument_month_"))]   # Amendment 6 (Claude): post-decision codes + argued status
F = F.drop(columns=drop); assert not any(c.startswith(("decision", "term", "natural_court")) for c in F.columns)
term = raw.term.values.astype(int); y = raw.justice_outcome_disposition.astype(int).values
if "free" in FS:
    us = {27} | {k for k, v in party_map_data.items() if v == 2}   # 27 United States; group 2 = federal government (party_map)
    F["us_pet"] = raw.petitioner.isin(us).astype("float32").values; F["us_resp"] = raw.respondent.isin(us).astype("float32").values
    c = raw.groupby("docketId").agg(t=("term", "first"), src=("caseSource", "first"), cod=("case_outcome_disposition", "first"))
    c["src"] = c.src.fillna(-1).astype(int); c["rev"] = (c.cod > 0).astype(int)
    g = c[c.cod >= 0].groupby(["src", "t"]).rev.agg(["sum", "count"]).reset_index().sort_values("t")
    g[["cs", "cn"]] = g.groupby("src")[["sum", "count"]].cumsum().values - g[["sum", "count"]].values
    x = pandas.DataFrame({"src": raw.caseSource.fillna(-1).astype(int).values, "t": term}).merge(g[["src", "t", "cs", "cn"]], on=["src", "t"], how="left")
    F["src_prior_rev_rate"] = ((x.cs.fillna(0) + 3) / (x.cn.fillna(0) + 4)).values.astype("float32")
    F["cert_conflict"] = raw.certReason.isin([2, 3, 4, 5, 6]).astype("float32").values
    op = os.path.join(HERE, "oyez", "oyez_case_features.csv")
    if os.path.exists(op) and "strict20" not in FS:   # Amendment 6 (Claude): strict20 never loads Oyez (argued-status encoding; K18's SG position)
        oy = pandas.read_csv(op, dtype={"docket": str}); oy["docket"] = oy.docket.str.strip()
        cols = ["sg_amicus_pet", "sg_amicus_resp", "oyez_found"] + ([k for k in oy.columns if k.startswith("oa_")] if "oa" in FS else [])
        k = raw[["term", "docket"]].astype({"docket": str}).assign(docket=lambda d: d.docket.str.strip()).merge(oy[["term", "docket"] + cols].drop_duplicates(["term", "docket"]), on=["term", "docket"], how="left")
        for col in cols: F[col] = k[col].fillna(0).values.astype("float32")
        log(f"oyez features {cols}; matched rows {int(k.oyez_found.fillna(0).sum())}")
    elif "oa" in FS: raise SystemExit("K08 needs oyez/oyez_case_features.csv with oa_* columns")
if "missaug" in FS:   # Amendment 2 K11: mask blank-prone groups at the pending blank rate, all non-pending rows, seed 0
    pend = term == 2026; rng = numpy.random.default_rng(0); MASK = {}
    grp = {g: [c for c in F.columns if c.startswith(g)] for g in ("lc_outcome_", "lc_disagreement_", "cert_reason_", "case_origin_", "law_supp_")}
    grp["cert_reason_"] += [c for c in ("cert_conflict",) if c in F.columns]; grp["oyez"] = [c for c in ("oyez_found", "sg_amicus_pet", "sg_amicus_resp") if c in F.columns]
    for g, cg in grp.items():
        if not cg: continue
        neg = g + "-1" if g + "-1" in F.columns else None
        rate = float(F.loc[pend, neg].mean()) if neg else float(1 - F.loc[pend, "oyez_found"].mean())
        m = (rng.random(len(F)) < rate) & ~pend; F.loc[m, cg] = 0.0
        if neg: F.loc[m, neg] = 1.0
        MASK[g] = (round(rate, 3), int(m.sum())); log(f"missaug {g}: pending blank rate {rate:.3f}, masked rows {int(m.sum())}")
if "pendfix" in FS:   # Amendment 1: drop features unobservable for pending rows, for all rows
    pf = [f for f in F.columns if f.startswith(("lc_outcome_", "lc_disagreement_", "cert_reason_", "case_origin_", "law_supp_"))] + [f for f in ("cert_conflict", "oyez_found") if f in F.columns]
    F = F.drop(columns=pf); drop += pf
if "strict20" in FS:   # Amendment 6 (Claude) guard: registered width and no forbidden prefix
    bad = [c for c in F.columns if c.startswith(("issue_", "law_type_", "law_supp_", "argument_month_", "sg_amicus_", "oyez_", "decision", "lc_outcome_", "cert_reason_", "lc_disagreement_", "case_origin_"))]
    assert not bad and F.shape[1] == 862, (F.shape, bad[:5])
log(f"features {F.shape}; dropped {len(drop)}")
dd = pandas.to_datetime(raw.dateDecision, format="%m/%d/%Y", errors="coerce").values
X = F.values; cols = list(F.columns); del F; gc.collect()
lgbm_used = False
if MODEL == "gbm":
    try:
        import lightgbm as lgb
        lgb.LGBMClassifier(device_type="gpu", n_estimators=5, verbose=-1).fit(X[:2000], (y[:2000] > 0).astype(int)); lgbm_used = True; DEV["gbm"] = "gpu(OpenCL)"
        log("LightGBM GPU works -> using LightGBM GPU")
    except Exception as e: log(f"LightGBM GPU not usable ({type(e).__name__}: {str(e)[:120]}) -> HistGradientBoosting CPU")
if MODEL in ("mlp", "hier"):
    import torch; dev = "mps" if torch.backends.mps.is_available() else "cpu"; DEV[MODEL] = dev; torch.manual_seed(0); log(f"torch {torch.__version__} device {dev}")
p = numpy.full(len(raw), numpy.nan); mdl = None; tc = 0; MTY = 25; t_first = int(term.min()) + MTY
for t in range(t_first, int(term.max()) + 1):
    tc += 1; te = term == t
    if not te.any(): continue
    emb = ~((term == t - 1) & (dd >= numpy.datetime64(f"{t}-10-01")))
    tr = (term < t) & emb & (term <= 2025)
    if MODEL == "rf":
        if set(raw.naturalCourt[term == t - 1]) != set(raw.naturalCourt[te]): mdl = None
        if mdl is None:
            w = pandas.Series(y[tr]).value_counts(normalize=True).to_dict() if CW == "orig" else None
            mdl = RandomForestClassifier(n_estimators=MTY + tc, class_weight=w, warm_start=True, n_jobs=a.n_jobs, random_state=0)
        else: mdl.set_params(n_estimators=MTY + tc)
        mdl.fit(X[tr], y[tr]); p[te] = mdl.predict_proba(X[te])[:, list(mdl.classes_).index(1)]
    elif t >= SAVE_FROM:
        if MODEL == "gbm":
            if lgbm_used:
                b = lgb.LGBMClassifier(device_type="gpu", learning_rate=0.05, n_estimators=300, num_leaves=31, random_state=0, verbose=-1).fit(X[tr], y[tr])
            else:
                b = HistGradientBoostingClassifier(learning_rate=0.05, max_iter=300, max_leaf_nodes=31, random_state=0).fit(X[tr], y[tr])
            p[te] = b.predict_proba(X[te])[:, list(b.classes_).index(1)]
        elif MODEL == "hier":   # Amendment 2 K15: global logistic + justice intercept + L2-pooled justice slopes, terms >= 1946
            import torch, torch.nn as nn
            if t == SAVE_FROM or "JID" not in globals(): JID = torch.tensor(pandas.factorize(raw.justice)[0], device=dev)
            trh = tr & (term >= 1946); mu = X[trh].mean(0); sd = X[trh].std(0) + 1e-6
            Z = lambda A: torch.tensor((A - mu) / sd, dtype=torch.float32, device=dev)
            Xt, yt, jt = Z(X[trh]), torch.tensor((y[trh] > 0).astype("float32"), device=dev), JID[torch.tensor(numpy.where(trh)[0], device=dev)]
            nJ, d = int(JID.max()) + 1, X.shape[1]; torch.manual_seed(0)
            W = nn.Linear(d, 1).to(dev); Bj = nn.Embedding(nJ, 1).to(dev); Uj = nn.Embedding(nJ, d).to(dev)
            nn.init.zeros_(Bj.weight); nn.init.zeros_(Uj.weight)
            opt = torch.optim.AdamW([*W.parameters(), *Bj.parameters()], lr=1e-3, weight_decay=1e-4); optU = torch.optim.Adam(Uj.parameters(), lr=1e-3)
            lf = nn.BCEWithLogitsLoss(); g = torch.Generator().manual_seed(0)
            f = lambda xb, jb: W(xb).squeeze(1) + Bj(jb).squeeze(1) + (xb * Uj(jb)).sum(1)
            for ep in range(4):
                for idx in torch.randperm(len(yt), generator=g).split(4096):
                    idx = idx.to(dev); opt.zero_grad(); optU.zero_grad(); ub = Uj(jt[idx])
                    loss = lf(f(Xt[idx], jt[idx]), yt[idx]) + 1e-3 * ub.pow(2).sum(1).mean(); loss.backward(); opt.step(); optU.step()
            with torch.no_grad(): p[te] = torch.sigmoid(f(Z(X[te]), JID[torch.tensor(numpy.where(te)[0], device=dev)])).cpu().numpy()
            del Xt, yt, jt
        else:
            import torch, torch.nn as nn
            mu = X[tr].mean(0); sd = X[tr].std(0) + 1e-6; Z = lambda A: torch.tensor((A - mu) / sd, dtype=torch.float32, device=dev)
            Xt, yt = Z(X[tr]), torch.tensor((y[tr] > 0).astype("float32"), device=dev)
            net = nn.Sequential(nn.Linear(X.shape[1], 64), nn.ReLU(), nn.Linear(64, 64), nn.ReLU(), nn.Linear(64, 1)).to(dev)
            opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-4); lf = nn.BCEWithLogitsLoss(); g = torch.Generator().manual_seed(0)
            for ep in range(20):
                for idx in torch.randperm(len(yt), generator=g).split(4096):
                    idx = idx.to(dev); opt.zero_grad(); lf(net(Xt[idx]).squeeze(1), yt[idx]).backward(); opt.step()
            with torch.no_grad(): p[te] = torch.sigmoid(net(Z(X[te])).squeeze(1)).cpu().numpy()
    if t >= SAVE_FROM and (t % 5 == 0 or t >= 2024): log(f"term {t} train={tr.sum()} emb_dropped={(~emb).sum()} test={te.sum()}")
keep = raw.term >= SAVE_FROM
R = raw.loc[keep, ["docketId", "docket", "term", "justice", "justice_outcome_disposition", "case_outcome_disposition", "lcDispositionDirection", "petitioner", "respondent"]].copy()
R["p_rev"] = p[keep.values]; R.to_csv(os.path.join(OUT, "preds.csv.gz"), index=False)
meta = {**cfg, "cfg_hash": cfg_hash, "n_features": len(cols), "devices": {"model": DEV[MODEL]}, "lightgbm_gpu": lgbm_used, "missaug": MASK if "missaug" in FS else None,
        "runtime_s": round(time.time() - T0, 1), "python": platform.python_version(), "sklearn": sklearn.__version__, "pandas": pandas.__version__}
json.dump(meta, open(os.path.join(OUT, "run_meta.json"), "w"), indent=1); json.dump(cols, open(os.path.join(OUT, "features.json"), "w"))
log(f"DONE {meta}")

"""direction-improve: one pre-registered trial per call (see ../PREREG.md). Paper only.
Runs inside ~/scotus-predict-rerun/direction_improve/ on the Mac; reads ../data, ../src, ./external; writes only to --out.
Rolling yearly retrain, train terms <= t-1, embargo: term t-1 rows decided on/after Oct 1 of term t are dropped from training.
Predictions saved 1990-2025; 2015-2025 goes to sealed_holdout.csv.gz and is NOT summarised here (read once by evaluate.py)."""
import argparse, datetime, gc, json, os, platform, resource, sys, time, hashlib
import numpy, pandas, sklearn
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
from legacy_model import get_raw_scdb_data, preprocess_raw_data
SPEC = {"T00": ("rf", []), "T01": ("rf", ["F1"]), "T02": ("rf", ["F1", "F2"]), "T03": ("rf", ["F1", "F2", "F3"]),
        "T04": ("rf", ["F1", "F2", "F3", "F4"]), "T05": ("hgb", ["F1", "F2", "F3", "F4"]), "T06": ("lr", ["F1", "F2", "F3", "F4"]),
        "T07": ("hgb", ["F1", "F2s", "F3", "F4", "strict"])}
ap = argparse.ArgumentParser(); ap.add_argument("--trial", required=True, choices=SPEC); ap.add_argument("--n-jobs", type=int, default=4)
ap.add_argument("--max-term", type=int, default=None); ap.add_argument("--out", default=None)
a = ap.parse_args(); MODEL, FS = SPEC[a.trial]; OUT = a.out or os.path.join(HERE, "results", a.trial); os.makedirs(OUT, exist_ok=True)
T0 = time.time()
def log(m):
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss; r = r / 2**20 if platform.system() == "Darwin" else r / 1024
    print(f"[{datetime.datetime.now():%H:%M:%S}] [+{time.time()-T0:7.1f}s] [peakRSS {r:6.0f} MB] {a.trial} {m}", flush=True)
cfg = {"trial": a.trial, "model": MODEL, "features": FS, "embargo": "drop t-1 rows decided >= Oct 1 of t", "pred_from": 1990}
cfg_hash = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]; log(f"cfg {cfg} hash {cfg_hash}")

m = pandas.read_csv(os.path.join(ROOT, "data", "SCDB_2026_01_justiceCentered_Docket.csv"), encoding="ISO-8859-1", low_memory=False)
if a.max_term: m = m[m.term <= a.max_term]
mp = os.path.join(OUT, "_in.csv"); m.to_csv(mp, index=False, encoding="ISO-8859-1"); del m; gc.collect()
raw = get_raw_scdb_data(mp); os.remove(mp)
F = preprocess_raw_data(raw, include_direction=True).astype(numpy.float32)
drop = [f for f in F.columns if f.startswith(("term_", "natural_court", "decision_month_")) or f == "decision_delay"]
if "strict" in FS: drop += [f for f in F.columns if f.startswith(("issue_", "law_type_", "law_supp_"))]
F = F.drop(columns=drop); assert not any(c.startswith("decision") for c in F.columns)
term = raw.term.values.astype(int); dirn = raw["direction"]; ok = dirn.isin([1, 2]).values; ycons = (dirn == 1).astype(int).values
lcs = numpy.where(raw.lcDispositionDirection == 1, 1.0, numpy.where(raw.lcDispositionDirection == 2, -1.0, 0.0))

if "F1" in FS:   # Martin-Quinn, prior term only
    mq = pandas.read_csv(os.path.join(HERE, "external", "mq_justices_2024.csv"))
    mqd = {(int(r.justice), int(r.term)): r.post_mn for r in mq.itertuples()}; med = mq.groupby("term").post_mn.median().to_dict()
    lastmq = int(mq.term.max())
    tl = numpy.minimum(term - 1, lastmq)
    s = numpy.array([mqd.get((int(j), int(t)), numpy.nan) for j, t in zip(raw.justice.values, tl)])
    F["mq_prev"] = numpy.nan_to_num(s, nan=0.0); F["mq_missing"] = numpy.isnan(s).astype(float)
    F["mq_court_median_prev"] = [med.get(int(t), 0.0) for t in tl]; F["mq_minus_median"] = F.mq_prev - F.mq_court_median_prev
    F["mq_x_lc"] = F.mq_prev * lcs; F["mqmm_x_lc"] = F.mq_minus_median * lcs
def expanding_share(keys, name):   # smoothed conservative-vote share of the key group over terms < t
    d = pandas.DataFrame({k: raw[k].values for k in keys}); d["term"] = term; d["c"] = (ycons * ok); d["n"] = ok.astype(int)
    g = d.groupby(keys + ["term"])[["c", "n"]].sum().reset_index().sort_values("term")
    g[["cc", "nn"]] = g.groupby(keys)[["c", "n"]].cumsum().values; g[["cc", "nn"]] = g[["cc", "nn"]].values - g[["c", "n"]].values
    x = d.merge(g[keys + ["term", "cc", "nn"]], on=keys + ["term"], how="left")
    F[name] = ((x.cc + 1) / (x.nn + 2)).values; F[name + "_n"] = numpy.log1p(x.nn.values)
if "F2" in FS: expanding_share(["justice", "issueArea"], "j_issue_cons")
if "F2s" in FS: expanding_share(["justice"], "j_all_cons")
if "F3" in FS:   # United States as party (SCDB party code 27)
    F["us_pet"] = (raw.petitioner == 27).astype(float); F["us_resp"] = (raw.respondent == 27).astype(float)
if "F4" in FS:   # circuit, its prior reversal rate, circuit split (certReason conflict codes)
    cs = raw.caseSource.fillna(-1).astype(int); circ = cs.where(cs.between(21, 32), 0)
    F["circuit"] = circ.values.astype(float)
    c = raw.groupby("docketId").agg(t=("term", "first"), src=("caseSource", "first"), cod=("case_outcome_disposition", "first"))
    c["src"] = c.src.fillna(-1).astype(int); c["rev"] = (c.cod > 0).astype(int)
    g = c.groupby(["src", "t"]).rev.agg(["sum", "count"]).reset_index().sort_values("t")
    g[["cs", "cn"]] = g.groupby("src")[["sum", "count"]].cumsum().values - g[["sum", "count"]].values
    x = pandas.DataFrame({"src": cs.values, "t": term}).merge(g[["src", "t", "cs", "cn"]], on=["src", "t"], how="left")
    F["src_prior_rev_rate"] = ((x.cs + 3) / (x.cn + 4)).values
    F["circuit_split"] = raw.certReason.isin([2, 3, 4, 5, 6]).astype(float).values
log(f"features {F.shape}")
dd = pandas.to_datetime(raw.dateDecision, errors="coerce")
X = F.values; del F
if MODEL == 'lr': X = numpy.nan_to_num(X, nan=0.0)  # LR cannot take NaN (bug fix found in smoke test, not a spec change); gc.collect()
numpy.random.seed(0); PFROM = 1990; mdl = None; tc = 0; p = numpy.full(len(raw), numpy.nan)
for t in range(int(term.min()) + 10, int(term.max()) + 1):
    tc += 1; te = term == t
    if not te.any(): continue
    emb = ~((term == t - 1) & (dd >= pandas.Timestamp(t, 10, 1)).values)
    tr = (term < t) & ok & emb
    if MODEL == "rf":
        if set(raw.naturalCourt[term == t - 1]) != set(raw.naturalCourt[te]): mdl = None
        n = 10 + tc; w = pandas.Series(ycons[tr]).value_counts(normalize=True).to_dict()
        if mdl is None: mdl = RandomForestClassifier(n_estimators=n, class_weight=w, warm_start=True, n_jobs=a.n_jobs, random_state=0)
        else: mdl.set_params(n_estimators=n)
        mdl.fit(X[tr], ycons[tr]); p[te] = mdl.predict_proba(X[te])[:, list(mdl.classes_).index(1)]
    elif t >= PFROM:
        fit_ = tr & (term < t - 5); cal = tr & (term >= t - 5)
        if MODEL == "hgb":
            b = HistGradientBoostingClassifier(learning_rate=0.05, max_iter=300, max_leaf_nodes=31, l2_regularization=0.0, random_state=0).fit(X[fit_], ycons[fit_])
            pr = lambda M: b.predict_proba(M)[:, 1]
        else:
            sc = StandardScaler().fit(X[fit_]); b = LogisticRegression(C=1.0, max_iter=2000).fit(sc.transform(X[fit_]), ycons[fit_])
            pr = lambda M: b.predict_proba(sc.transform(M))[:, 1]
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.001, y_max=0.999).fit(pr(X[cal]), ycons[cal])
        p[te] = iso.predict(pr(X[te]))
    if t >= PFROM: log(f"term {t} train={tr.sum()} emb_dropped={(~emb).sum()} test={te.sum()}")
R = raw.loc[term >= PFROM, ["docketId", "term", "justice", "direction", "decisionDirection"]].copy(); R["p_cons"] = p[term >= PFROM]
R.loc[R.term <= 2014].to_csv(os.path.join(OUT, "explore_1990_2014.csv.gz"), index=False)
R.loc[(R.term >= 2015) & (R.term <= 2025)].to_csv(os.path.join(OUT, "sealed_holdout.csv.gz"), index=False)
E = R[(R.term <= 2014)]; v = E[E.direction.isin([1, 2])]
c = E.assign(pc=(E.p_cons >= .5).astype(int)).groupby("docketId").agg(fc=("pc", "mean"), pm=("p_cons", "mean"), dd=("decisionDirection", "first"))
c = c[c.dd.isin([1, 2])]; call = numpy.where(c.fc > .5, 1, numpy.where(c.fc < .5, 0, (c.pm >= .5).astype(int)))
res = {**cfg, "cfg_hash": cfg_hash, "explore_case_acc": float((call == (c.dd == 1)).mean()), "explore_n_cases": len(c),
       "explore_vote_acc": float(((v.p_cons >= .5).astype(int) == (v.direction == 1)).mean()), "runtime_s": round(time.time() - T0, 1)}
json.dump(res, open(os.path.join(OUT, "explore_result.json"), "w"), indent=1); log(f"DONE {res}")

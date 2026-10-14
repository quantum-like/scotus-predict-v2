"""Amendment 6 (Claude) section A (K21 input): point-in-time dynamic 1-D IRT ideal points, Martin-Quinn style. Paper only, never trade.
Spec: katz/AMENDMENT_6_CLAUDE.md section A. For each prediction term t in [--tmin, --tmax] one MAP fit uses ONLY rows of the SCDB 2026_01
justice-centered docket file of terms 1946..t-1, minus term t-1 dockets decided on/after Oct 1 of year t (Amendment 2 G4 embargo).
  y_ij = 1 if direction == 2 (liberal), 0 if direction == 1, any other value dropped; dockets whose kept votes all agree are dropped.
  P(y_ij = 1) = sigmoid(a_i + b_i * theta_{j,tau}); a_i ~ N(0, 5^2), b_i ~ N(0, 2.5^2), theta_{j,first term} ~ N(0, 1),
  theta_{j,tau} - theta_{j,tau-1} ~ N(0, 0.1) (variance). Loss = -(sum Bernoulli log-lik + sum log priors), constants dropped.
  Adam lr 0.05, 3000 full-batch steps, float32, torch.manual_seed(0), device "mps" if available else "cpu" (logged, and in column
  `device`), each fit warm-started from the previous t's fit. Orientation: flip theta and all b if corr(theta_last, liberal share) < 0.
  Feature theta_j(t) = theta at the justice's last term <= t-1 with votes; a sitting justice without votes before t gets the mean
  theta_j(t) of the sitting justices appointed by a president of the same party (PARTY below), imputed = 1.
Outputs: --out (default features/pit_theta.csv): term, justice, justiceName, theta, imputed, last_term, n_votes_window, device
(one row per sitting justice of t); --mq-out (default: --out with pit_theta -> pit_mq_check): per t, Pearson/Spearman of theta_j(t)
vs published MQ post_mn at t-1 (MQ is conservative-positive, so strongly NEGATIVE is expected; MQ is a CHECK ONLY, never a feature);
--cov (default features/irt_coverage.txt): per-fit runtime, device, votes/dockets, convergence, feature distribution, MQ check.
No outcome column (vote, majority, disposition, winner, decisionDirection) is ever read: only docketId, term, justice, justiceName,
direction, dateDecision (the last only for the embargo).
Run: PYTHONDONTWRITEBYTECODE=1 nice -n 10 ~/scotus-predict-rerun/katz/.venv-gpu/bin/python -I -B katz/claude/pit_irt.py [--tmin 1980 --tmax 2026]
Implementation choices (where the spec delegates to code):
 1. One row per (docketId, justice): drop_duplicates keeps the first (the 2026_01 file has none).
 2. Unanimous dockets (every kept vote equal, incl. a single kept vote) are dropped once globally; windows remove whole dockets,
    so this equals dropping them per window.
 3. theta grid: one theta per justice for EVERY term from the justice's first to last term with kept votes in the window; the
    random walk links consecutive grid terms, so a gap term (none occur in 1946-2025) would be bridged by the prior alone.
 4. Warm start: dockets and (justice, term) cells present in the previous t's fit start from its ORIENTED values (the posterior is
    sign-symmetric, so an oriented mode is still a mode); new cells start at a = 0, b = 1, theta = 0. Adam moments are reset each
    fit. The first fit of a run (t = --tmin) is a cold start (a = 0, b = 1, theta = 0).
 5. Orientation: Pearson corr over the window's justices between theta at each justice's last grid term and the justice's share
    of liberal votes among his/her kept (non-unanimous-docket) votes in the window; if < 0, all theta and all b are negated.
 6. Sitting justices of t: justices on any SCDB 2026_01 row of term t (whatever the direction); for t = 2026 the pending file's.
 7. Imputation: mean over the NON-imputed sitting justices of t with the same appointing-president party; if none exists, the mean
    over all non-imputed sitting justices (logged as a fallback). Imputed rows: last_term empty, n_votes_window 0.
    n_votes_window = the justice's kept votes (direction 1/2, non-unanimous dockets) in the fit window, all terms.
 8. PARTY covers every justice in the 2026_01 file (1946-2025, a superset of 1980-2026); a sitting justice of a requested term who
    is missing from it stops the run. It is the APPOINTING PRESIDENT's party (Burton: Truman D; Brennan: Eisenhower R).
 9. MQ check: sitting non-imputed justices of t joined by SCDB justice code to mq_justices_2024.csv at term t-1; Pearson and
    Spearman need n >= 3, else empty (t = 2026: MQ ends at 2024, so empty).
10. Optimizer: speed only, same algorithm. Parameters are packed in one float32 vector P = [a, b, theta grid]; the full-batch
    gradient of the loss is computed analytically (d/deta = sigmoid(eta) - y; da = r, db = r*theta, dtheta = r*b, plus prior
    terms) instead of by autograd, and Adam is written out exactly as torch.optim.Adam (betas 0.9/0.999, eps 1e-8, bias
    correction, lr 0.05). This needs ~3x fewer GPU dispatches per step (the step is dispatch-bound). `--selftest` checks the
    gradient against torch autograd and 200 steps against torch.optim.Adam on the window of t = --tmin (result -> --cov).
11. Convergence is logged per fit: loss per vote, relative loss change over the last 100 steps, max |gradient| at the end.
12. The gradient uses atomic scatter-adds (index_add_) on MPS, so float32 results may differ in the last digits between runs.
13. torch.set_num_threads(1): the Mac is shared with a CPU-heavy job; the GPU does the math. No multiprocessing.
14. --timing: one cold-start fit on the real window STRUCTURE of t = --tmax with SYNTHETIC y (Bernoulli(0.5), numpy seed 0); it
    times the 3000 steps only, writes no theta and only appends a TIMING block to --cov, so no evaluation-window vote is fitted.
15. Outputs are rewritten after every fit (a crash keeps the finished terms); --cov is rewritten by a normal run, while --selftest
    and --timing append to it."""
import argparse, datetime, os, time
import numpy as np, pandas as pd, torch
from scipy.stats import pearsonr, spearmanr
HERE = os.path.dirname(os.path.abspath(__file__))
LR, STEPS, VA, VB, V0, VRW = 0.05, 3000, 5.0 ** 2, 2.5 ** 2, 1.0, 0.1
PARTY = {"HLBlack": "D", "SFReed": "D", "FFrankfurter": "D", "WODouglas": "D", "FMurphy": "D", "RHJackson": "D", "WBRutledge": "D",   # FDR
         "HHBurton": "D", "FMVinson": "D", "TCClark": "D", "SMinton": "D",                                                             # Truman
         "EWarren": "R", "JHarlan2": "R", "WJBrennan": "R", "CEWhittaker": "R", "PStewart": "R",                                      # Eisenhower
         "BRWhite": "D", "AJGoldberg": "D", "AFortas": "D", "TMarshall": "D",                                                         # Kennedy, Johnson
         "WEBurger": "R", "HABlackmun": "R", "LFPowell": "R", "WHRehnquist": "R", "JPStevens": "R",                                   # Nixon, Ford
         "SDOConnor": "R", "AScalia": "R", "AMKennedy": "R", "DHSouter": "R", "CThomas": "R",                                         # Reagan, Bush 41
         "RBGinsburg": "D", "SGBreyer": "D", "JGRoberts": "R", "SAAlito": "R", "SSotomayor": "D", "EKagan": "D",                      # Clinton, Bush 43, Obama
         "NMGorsuch": "R", "BMKavanaugh": "R", "ACBarrett": "R", "KBJackson": "D"}                                                   # Trump, Biden
ap = argparse.ArgumentParser(); ap.add_argument("--tmin", type=int, default=1980); ap.add_argument("--tmax", type=int, default=2026)
ap.add_argument("--out", default=os.path.join(HERE, "features", "pit_theta.csv")); ap.add_argument("--mq-out"); ap.add_argument("--cov")
ap.add_argument("--root", default=os.path.expanduser("~/scotus-predict-rerun"), help="read-only input root")
ap.add_argument("--timing", action="store_true", help="one synthetic-y fit at --tmax, timing only")
ap.add_argument("--selftest", action="store_true", help="gradient / optimizer check on the window of --tmin")
a = ap.parse_args(); OUT = os.path.abspath(a.out); FD = os.path.dirname(OUT); os.makedirs(FD, exist_ok=True)
MQO = a.mq_out or os.path.join(FD, os.path.basename(OUT).replace("pit_theta", "pit_mq_check"))
if os.path.abspath(MQO) == OUT: MQO = OUT[:-4] + "_mq_check.csv"
COV = a.cov or os.path.join(FD, "irt_coverage.txt")
T0 = time.time()
def log(m): print(f"[{datetime.datetime.now():%H:%M:%S}] [+{time.time()-T0:7.1f}s] pit_irt {m}", flush=True)
torch.manual_seed(0); torch.set_num_threads(1)
DEV = "mps" if torch.backends.mps.is_available() else "cpu"
log(f"torch {torch.__version__} device {DEV}" + ("" if DEV == "mps" else " (MPS unavailable -> CPU fallback)"))
rd = lambda p, **k: pd.read_csv(p, encoding="ISO-8859-1", low_memory=False, **k)
SP = os.path.join(a.root, "data", "SCDB_2026_01_justiceCentered_Docket.csv"); PP = os.path.join(a.root, "pending_inputs", "pending_cases_scdb_rows.csv")
MP = os.path.join(a.root, "direction_improve", "external", "mq_justices_2024.csv")
S = rd(SP, usecols=["docketId", "term", "justice", "justiceName", "direction", "dateDecision"]); n_raw = len(S); S = S.drop_duplicates(["docketId", "justice"])
PD = rd(PP, usecols=["docketId", "term", "justice", "justiceName"])
SIT = pd.concat([S[["term", "justice", "justiceName"]], PD.loc[PD.term == 2026, ["term", "justice", "justiceName"]]]).drop_duplicates(["term", "justice"])
miss = sorted(set(SIT.loc[SIT.term.between(a.tmin, a.tmax), "justiceName"]) - set(PARTY)); assert not miss, f"PARTY lacks {miss}"
V = S[S.direction.isin([1, 2])].copy(); V["y"] = (V.direction == 2).astype("float32")
g = V.groupby("docketId").y.agg(["min", "max"]); keep = g.index[g["min"] < g["max"]]; n_unan = len(g) - len(keep)
V = V[V.docketId.isin(keep)].copy(); V["dd"] = pd.to_datetime(V.dateDecision, format="%m/%d/%Y", errors="coerce"); assert V.dd.notna().all()
HEAD = [f"pit_irt.py coverage ({datetime.datetime.now():%Y-%m-%d %H:%M}); torch {torch.__version__}; device {DEV}; args {vars(a)}",
        f"SCDB 2026_01 rows {n_raw} -> {len(S)} unique (docketId, justice); direction 1/2 rows {int(S.direction.isin([1, 2]).sum())}, other/missing "
        f"{int((~S.direction.isin([1, 2])).sum())} dropped; dockets with a kept vote {len(g)}, unanimous dropped {n_unan}, kept {len(keep)}; kept votes {len(V)}",
        f"model: lr {LR}, steps {STEPS}, priors a N(0,{VA}), b N(0,{VB}), theta_first N(0,{V0}), rw var {VRW}; float32; seed 0"]
def window(t):   # terms 1946..t-1 minus term t-1 dockets decided on/after Oct 1 of year t
    emb = (V.term == t - 1) & (V.dd >= pd.Timestamp(f"{t}-10-01")); return V[(V.term <= t - 1) & ~emb], int(V.loc[emb, "docketId"].nunique())
B1, B2, EPS = 0.9, 0.999, 1e-8   # torch.optim.Adam defaults
def prep(W, warm):   # index the window; parameters packed P = [a (nd), b (nd), theta grid (nj)]
    dk = pd.Index(W.docketId.unique()); gj = W.groupby("justice").term.agg(["min", "max"]); nd = len(dk)
    jt = pd.DataFrame({"justice": np.repeat(gj.index.values, (gj["max"] - gj["min"] + 1).values),
                       "term": np.concatenate([np.arange(lo, hi + 1) for lo, hi in zip(gj["min"], gj["max"])])}); JT = pd.MultiIndex.from_frame(jt)
    di = dk.get_indexer(W.docketId); ji = JT.get_indexer(pd.MultiIndex.from_frame(W[["justice", "term"]])); assert (di >= 0).all() and (ji >= 0).all()
    first = np.r_[True, jt.justice.values[1:] != jt.justice.values[:-1]]; fi = np.where(first)[0]; last = np.r_[fi[1:] - 1, len(jt) - 1]
    if warm is None: a0, b0, t0 = np.zeros(nd), np.ones(nd), np.zeros(len(jt)); nw = (0, 0)
    else:
        a0, b0, t0 = warm["a"].reindex(dk), warm["b"].reindex(dk), warm["th"].reindex(JT); nw = (int(a0.notna().sum()), int(t0.notna().sum()))
        a0, b0, t0 = a0.fillna(0).values, b0.fillna(1).values, t0.fillna(0).values
    T = lambda x, dt=torch.float32: torch.tensor(np.asarray(x), dtype=dt, device=DEV)
    k = {"I": T(np.r_[di, nd + di, 2 * nd + ji], torch.long), "Y": T(W.y.values), "n2": 2 * nd,   # vote -> a, b, theta slots
         "W2": T(np.r_[np.full(nd, 1 / VA), np.full(nd, 1 / VB), np.where(first, 1 / V0, 0.)]),     # Gaussian prior precisions (rw apart)
         "RW": T((~first[1:]) / VRW)}                                                                # 1/VRW on within-justice increments
    return T(np.r_[a0, b0, t0]), k, (dk, gj, JT, last, nw)
def nlp(P, k):   # negative log posterior (constants dropped); differentiable, used for logging and --selftest
    G = P.index_select(0, k["I"]).view(3, -1); d = P[k["n2"] + 1:] - P[k["n2"]:-1]
    return (torch.nn.functional.binary_cross_entropy_with_logits(torch.addcmul(G[0], G[1], G[2]), k["Y"], reduction="sum")
            + 0.5 * (k["W2"] * P * P).sum() + 0.5 * (d * d * k["RW"]).sum())
def grad(P, k):  # analytic gradient of nlp: d/deta = sigmoid(eta) - y; da = r, db = r*theta, dtheta = r*b; + priors
    G = P.index_select(0, k["I"]).view(3, -1); r = torch.sigmoid(torch.addcmul(G[0], G[1], G[2])).sub_(k["Y"])
    g = (P * k["W2"]).index_add_(0, k["I"], torch.cat((r, r * G[2], r * G[1])))
    D = (P[k["n2"] + 1:] - P[k["n2"]:-1]).mul_(k["RW"]); g[k["n2"] + 1:].add_(D); g[k["n2"]:-1].sub_(D); return g
def run(P, k, steps):   # Adam exactly as torch.optim.Adam (lr, betas, eps, bias correction), on the analytic full-batch gradient
    m, v, L100 = torch.zeros_like(P), torch.zeros_like(P), None
    for s in range(1, steps + 1):
        g = grad(P, k)
        if s == steps - 99: L100 = nlp(P, k)
        m.lerp_(g, 1 - B1); v.mul_(B2).addcmul_(g, g, value=1 - B2)
        P.addcdiv_(m, (v.sqrt() / (1 - B2 ** s) ** 0.5).add_(EPS), value=-LR / (1 - B1 ** s))
    return P, L100
def fit(W, warm):
    P, k, (dk, gj, JT, last, nw) = prep(W, warm); nd = len(dk); P, L100 = run(P, k, STEPS)
    gmax, Lf, L100 = grad(P, k).abs().max().item(), nlp(P, k).item(), L100.item()
    p = P.cpu().numpy().astype("float64"); an, bn, thn = p[:nd], p[nd:2 * nd], p[2 * nd:]
    share = W.groupby("justice").y.mean().reindex(gj.index).values; r = float(np.corrcoef(thn[last], share)[0, 1])
    if r < 0: thn, bn = -thn, -bn
    warm = {"a": pd.Series(an, dk), "b": pd.Series(bn, dk), "th": pd.Series(thn, JT)}
    J = pd.DataFrame({"theta": thn[last], "last_term": gj["max"].values, "n_votes_window": W.groupby("justice").size().reindex(gj.index).values}, index=gj.index)
    st = {"n_votes": len(W), "n_dockets": nd, "n_justices": len(gj), "n_jt": len(JT), "warm_dockets": nw[0], "warm_jt": nw[1],
          "loss_per_vote": Lf / len(W), "rel_dloss_last100": (L100 - Lf) / abs(Lf), "max_abs_grad": gmax, "orient_corr": abs(r), "flipped": int(r < 0)}
    return warm, J, st
if a.selftest:   # analytic gradient vs autograd; 200 steps of run() vs torch.optim.Adam + autograd; window of t = --tmin, cold start
    W, _ = window(a.tmin); P0, k, _ = prep(W, None); Pr = (P0 + 0.5 * torch.randn(P0.shape, device=DEV)).requires_grad_()
    ga = grad(Pr.detach(), k); nlp(Pr, k).backward(); e1 = ((ga - Pr.grad).abs().max() / Pr.grad.abs().max()).item()
    Pa = P0.clone().requires_grad_(); opt = torch.optim.Adam([Pa], lr=LR)
    for _ in range(200): opt.zero_grad(); nlp(Pa, k).backward(); opt.step()
    Pm, _ = run(P0.clone(), k, 200); e2 = (Pm - Pa.detach()).abs().max().item()
    msg = (f"SELFTEST ({datetime.datetime.now():%Y-%m-%d %H:%M}, device {DEV}, window of t={a.tmin}, {len(W)} votes): analytic vs autograd gradient "
           f"max|diff|/max|g| = {e1:.2e}; 200 steps of the written-out Adam vs torch.optim.Adam: max|param diff| = {e2:.2e} (param scale {Pa.detach().abs().max().item():.2f})")
    log(msg); open(COV, "a").write("\n" + msg + "\n"); raise SystemExit
if a.timing:
    W, nE = window(a.tmax); W = W.assign(y=np.random.default_rng(0).integers(0, 2, len(W)).astype("float32"))
    t1 = time.time(); _, _, st = fit(W, None); sec = time.time() - t1
    msg = (f"TIMING ({datetime.datetime.now():%Y-%m-%d %H:%M}, device {DEV}): one cold-start fit, window structure of t={a.tmax} (terms {int(W.term.min())}-"
           f"{int(W.term.max())}, {st['n_votes']} votes, {st['n_dockets']} dockets, {st['n_jt']} justice-terms) with SYNTHETIC y: {sec:.1f} s for {STEPS} "
           f"steps ({1000 * sec / STEPS:.2f} ms/step). Upper bound for 47 fits (1980-2026, each <= this size): {47 * sec / 60:.1f} min.")
    log(msg); open(COV, "a").write("\n" + msg + "\n"); raise SystemExit
MQ = pd.read_csv(MP); warm = None; rows, fits, mqr = [], [], []
for t in range(a.tmin, a.tmax + 1):
    W, nE = window(t); t1 = time.time(); warm, J, st = fit(W, warm); sec = time.time() - t1
    s = SIT[SIT.term == t][["justice", "justiceName"]].sort_values("justice").copy(); s.insert(0, "term", t)
    s = s.join(J, on="justice"); s["imputed"] = s.theta.isna().astype(int); s["party"] = s.justiceName.map(PARTY); fb = 0
    for i in s.index[s.imputed == 1]:
        ref = s[(s.imputed == 0) & (s.party == s.at[i, "party"])]
        if ref.empty: ref = s[s.imputed == 0]; fb += 1
        s.at[i, "theta"] = ref.theta.mean()
    s["n_votes_window"] = s.n_votes_window.fillna(0).astype(int); s["last_term"] = s.last_term.astype("Int64"); s["device"] = DEV
    rows.append(s[["term", "justice", "justiceName", "theta", "imputed", "last_term", "n_votes_window", "device"]])
    m = s[s.imputed == 0].merge(MQ.loc[MQ.term == t - 1, ["justice", "post_mn"]], on="justice"); n = len(m)
    mqr.append({"term": t, "mq_term": t - 1, "n": n, "pearson": pearsonr(m.theta, m.post_mn)[0] if n >= 3 else np.nan,
                "spearman": spearmanr(m.theta, m.post_mn)[0] if n >= 3 else np.nan})
    fits.append({"t": t, "terms": f"{int(W.term.min())}-{int(W.term.max())}", "embargo_dockets": nE, **st, "sec": round(sec, 1), "device": DEV,
                 "n_sitting": len(s), "n_imputed": int(s.imputed.sum()), "impute_fallback": fb,
                 "theta_min": s.theta.min(), "theta_med": s.theta.median(), "theta_max": s.theta.max()})
    log(f"t={t} votes {st['n_votes']} dockets {st['n_dockets']} jt {st['n_jt']} embargo {nE} {sec:.1f}s loss/vote {st['loss_per_vote']:.4f} "
        f"dL100 {st['rel_dloss_last100']:.2e} |g| {st['max_abs_grad']:.2e} flip {st['flipped']} sitting {len(s)} imputed {int(s.imputed.sum())} "
        f"MQ r {mqr[-1]['pearson']:.3f} rho {mqr[-1]['spearman']:.3f} (n {n})")
    R = pd.concat(rows, ignore_index=True); R.to_csv(OUT, index=False, float_format="%.6f")
    MQD = pd.DataFrame(mqr); MQD.to_csv(MQO, index=False, float_format="%.4f"); FT = pd.DataFrame(fits)
    with open(COV, "w") as f:
        f.write("\n".join(HEAD) + f"\noutputs: {OUT}\n         {MQO}\ntotal runtime {time.time() - T0:.1f} s; fits {len(FT)}; mean {FT.sec.mean():.1f} s/fit\n\n")
        f.write("PER FIT (votes/dockets in the window; convergence; orientation corr = |corr(theta_last, liberal share)| before any flip)\n")
        f.write(FT.to_string(index=False, float_format=lambda v: f"{v:.4g}") + "\n\n")
        f.write(f"FEATURE theta_j(t) (one row per sitting justice; imputed rows {int(R.imputed.sum())} of {len(R)}):\n{R.theta.describe().to_string()}\n\n")
        f.write("MQ CHECK (theta_j(t) vs published MQ post_mn at t-1; MQ conservative-positive, so NEGATIVE expected; check only, never a feature)\n")
        f.write(MQD.to_string(index=False, float_format=lambda v: f"{v:.4f}") + "\n")
        mm = R[R.imputed == 0].merge(MQ.rename(columns={"term": "mq_term"})[["mq_term", "justice", "post_mn"]].assign(term=lambda d: d.mq_term + 1), on=["term", "justice"])
        if len(mm) >= 3: f.write(f"pooled over terms: n {len(mm)}, pearson {pearsonr(mm.theta, mm.post_mn)[0]:.4f}, spearman {spearmanr(mm.theta, mm.post_mn)[0]:.4f}\n")
log(f"done: {OUT} ({len(R)} rows), {MQO}, {COV}")

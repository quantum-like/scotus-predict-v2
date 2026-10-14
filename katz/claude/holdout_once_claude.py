"""Amendment 6 (Claude): the ONE read of the 2015-2025 holdout (already SEEN under Amendment 2) and the 36 settled Kalshi markets.
Order: (1) refuse if a lock or any HOLDOUT_* output exists; (2) require the verdict, INPUT_SHA256.json, the amendment and every
katz/claude/*.py to be committed and unmodified, and every pinned input (incl. SCDB and the Kalshi files) to match its hash; (3) take an
exclusive lock (O_EXCL) recording time, git HEAD and this file's sha256 BEFORE any label is loaded; (4) assert every count (772 primary,
800 secondary, 36 at d7) before anything is printed; (5) score, write, plot. Nothing changes after; a crash leaves the lock (no re-read).
Scores K10 (as recorded), K10s, K25-K28 and the prior-10-term base rate on PRIMARY (argued cases, petitioner wins) and SECONDARY (all cases,
reverse); on the settled Kalshi markets vs Kalshi at three fixed times (argument-day morning, 30 and 7 days before the decision; d30/d7 are
anchored on the decision date, ex post, for both sides). Only argument morning approximates the model's information set (its P is frozen
before argument); d30/d7 give Kalshi the argument. A price at arg/d30 counts only if ask - bid <= 0.20 (d7 = Amendment 2's d7_mid, as
recorded). Disagreement tracker (|P_model - P_Kalshi| >= 0.25) at d7 and d30: scored, never traded (P&L = hypothetical paper numbers)."""
import datetime, gzip, hashlib, json, math, os, subprocess, sys
import numpy as np, pandas as pd
from sklearn.metrics import log_loss
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
REPO = os.path.dirname(os.path.dirname(HERE)); OUT = os.path.join(REPO, "katz", "results", "claude"); LOC = os.path.join(HERE, "results_local")
LOCK = os.path.join(OUT, "HOLDOUT_READ_LOCK_claude.json")
assert not os.path.exists(LOCK) and not [f for f in os.listdir(OUT) if f.startswith("HOLDOUT_")], "holdout already read (or a read started): refusing"
git = lambda *a: subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True)
PINNED = ["katz/results/claude/verdict.json", "katz/results/claude/INPUT_SHA256.json", "katz/AMENDMENT_6_CLAUDE.md", "katz/claude"]
assert not git("status", "--porcelain", "--", *PINNED).stdout.strip(), "verdict, input hashes, amendment and katz/claude code must be committed and unmodified"
assert git("ls-files", "--error-unmatch", "katz/results/claude/verdict.json", "katz/claude/holdout_once_claude.py", "katz/claude/stage2.py").returncode == 0
sha = lambda p: hashlib.sha256(gzip.open(p).read() if p.endswith(".gz") else open(p, "rb").read()).hexdigest()
for k, h_ in json.load(open(os.path.join(OUT, "INPUT_SHA256.json"))).items():   # the read scores exactly the inputs behind the committed verdict
    assert sha(os.path.join(REPO, k)) == h_, f"input changed since the verdict: {k}"
V = json.load(open(os.path.join(OUT, "verdict.json"))); assert not V.get("dry_run"), "verdict.json is from a dry run"
fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)   # (3) exclusive lock before any label is loaded
os.write(fd, json.dumps({"started": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "git_head": git("rev-parse", "HEAD").stdout.strip(),
                         "script_sha256": sha(os.path.abspath(__file__))}).encode()); os.close(fd)

import stage2 as S
MODELS = ["K10", "K10s", "K25", "K26", "K27", "K28"]; N_REG = {"primary_argued_partyWinning": 772, "secondary_all_reverse": 800}
P = pd.read_csv(os.path.join(LOC, "P_wf_all.csv.gz"), index_col=0)
_, C = S.frames(os.path.join(LOC, "K25", "preds.csv.gz"), families=())
T = C.term; H = {}
for lab, ycol in (("primary_argued_partyWinning", "y"), ("secondary_all_reverse", "y_rev")):
    y = C[ycol]; h = pd.DataFrame({"term": T, "y": y}).join(P[MODELS]); h = h[h.term.between(2015, 2025) & h.y.notna()].dropna(subset=MODELS)
    h["base_rate_prior10"] = h.term.map({t: y[(T < t) & (T >= t - 10)].dropna().mean() for t in range(2015, 2026)}); H[lab] = h
k = pd.read_csv(os.path.join(S.ROOT, "katz", "kalshi_hist", "kalshi_settled_prices.csv"))
m = pd.read_csv(os.path.join(S.ROOT, "katz", "kalshi_hist", "market_map_hist.csv"))[["ticker", "yes_maps_to", "primary"]]
k = k.merge(m, on="ticker"); k = k[k.yes_maps_to.isin(["reverse", "affirm"])].copy(); k["y"] = (k.result == "yes").astype(int)
rev = k.yes_maps_to == "reverse"
for c in MODELS: pp = k.scdb_docketId.map(P[c]); k["m_" + c] = np.where(rev, pp, 1 - pp)
pp = k.term.map(lambda t: C.y[(T < t) & (T >= t - 10)].dropna().mean()); k["base_rate"] = np.where(rev, pp, 1 - pp)
mc = ["m_" + c for c in MODELS]; k = k.dropna(subset=mc + ["base_rate"]); KK = {}
for tau in ("arg", "d30", "d7"):
    q = k[f"{tau}_mid"].notna() & (((k[f"{tau}_ask"] - k[f"{tau}_bid"]) <= .20) if tau != "d7" else True)   # quote-quality rule (arg, d30)
    kk = k[q].copy(); kk["kalshi"] = kk[f"{tau}_mid"].clip(.01, .99); KK[tau] = kk
assert {lab: len(h) for lab, h in H.items()} == N_REG == V["n_holdout_expected"], ({lab: len(h) for lab, h in H.items()}, V["n_holdout_expected"])
assert len(KK["d7"]) == 36, len(KK["d7"])   # (4) every count checked before anything is printed

met = lambda p, yy: {"n": len(yy), "brier": float(((p - yy) ** 2).mean()), "logloss": float(log_loss(yy, p.clip(.01, .99), labels=[0, 1])),
                     "acc": float(((p > .5) == (yy == 1)).mean()), "mean_P": float(p.mean())}
cols = MODELS + ["base_rate_prior10"]
RES = {lab: pd.DataFrame({c: met(h[c], h.y) for c in cols}).T for lab, h in H.items()}
PTS = {lab: pd.DataFrame({c: h.assign(b=(h[c] - h.y) ** 2).groupby("term").b.mean() for c in cols}) for lab, h in H.items()}
KS = {}
for tau, kk in KK.items():
    if not len(kk): continue
    KS[tau] = pd.DataFrame({c: {**met(kk[c], kk.y), "brier_primary_wording": float(((kk[c] - kk.y)[kk.primary == 1] ** 2).mean()) if (kk.primary == 1).any() else np.nan,
                                "n_primary_wording": int(kk.primary.sum())} for c in ["kalshi", "base_rate"] + mc}).T
def fee(p): return math.ceil(0.07 * p * (1 - p) * 100) / 100
D = []
for tau in ("d7", "d30"):
    for c in MODELS:
        for _, r in KK[tau].iterrows():
            g = r["m_" + c] - r.kalshi
            if abs(g) < .25: continue
            side = "YES" if g > 0 else "NO"; ask, bid = r.get(f"{tau}_ask"), r.get(f"{tau}_bid")
            price = (ask if pd.notna(ask) else r.kalshi) if side == "YES" else (1 - bid if pd.notna(bid) else 1 - r.kalshi)
            win = r.y if side == "YES" else 1 - r.y
            D.append({"time": tau, "model": c, "ticker": r.ticker, "term": r.term, "y": r.y, "P_model": r["m_" + c], "kalshi_mid": r.kalshi, "gap": g,
                      "model_closer": abs(r["m_" + c] - r.y) < abs(r.kalshi - r.y), "hyp_side": side, "hyp_price": price, "hyp_paper_pnl_net_1c": win - price - fee(price)})
D = pd.DataFrame(D); DS = pd.DataFrame()
if len(D):
    DS = D.groupby(["time", "model"]).agg(n_flagged=("ticker", "size"), model_closer=("model_closer", "sum"), hyp_paper_pnl_net=("hyp_paper_pnl_net_1c", "sum"))
    DS["brier_model_flagged"] = D.groupby(["time", "model"])[["P_model", "y"]].apply(lambda g: float(((g.P_model - g.y) ** 2).mean()))
    DS["brier_kalshi_flagged"] = D.groupby(["time", "model"])[["kalshi_mid", "y"]].apply(lambda g: float(((g.kalshi_mid - g.y) ** 2).mean()))

for lab in RES: RES[lab].to_csv(os.path.join(OUT, f"HOLDOUT_{lab}_claude.csv")); PTS[lab].to_csv(os.path.join(OUT, f"HOLDOUT_per_term_brier_{lab}_claude.csv"))
pd.concat(KS, names=["time"]).to_csv(os.path.join(OUT, "HOLDOUT_kalshi_settled_claude.csv"))
k.to_csv(os.path.join(OUT, "HOLDOUT_kalshi_rows_claude.csv"), index=False)
D.to_csv(os.path.join(OUT, "HOLDOUT_DISAGREE_settled_claude.csv"), index=False); DS.to_csv(os.path.join(OUT, "HOLDOUT_DISAGREE_summary_claude.csv"))
pd.set_option("display.width", 250)
for lab in RES: print(f"HOLDOUT 2015-2025 {lab} (SEEN before: Amendment 2's read; this is Amendment 6's single read)\n", RES[lab].round(4).to_string())
for tau in KS: print(f"SETTLED KALSHI at {tau} (markets with a valid {tau} price; inside the holdout, SEEN)\n", KS[tau].round(4).to_string())
print("DISAGREEMENT TRACKER (|gap| >= 0.25; scored, never traded)\n", DS.round(4).to_string() if len(DS) else "no flagged markets")
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    f, ax = plt.subplots(1, 2, figsize=(13, 5)); bins = np.linspace(0, 1, 11); HP = H["primary_argued_partyWinning"]
    for c in cols:
        g = HP.groupby(pd.cut(HP[c], bins), observed=True).agg(P=(c, "mean"), y=("y", "mean"))
        ax[0].plot(g.P, g.y, "o-", ms=3, lw=1.6 if c in ("K10", "K10s", V["winner_lowest_wf_brier"]) else .8, label=f"{c} (Brier {RES['primary_argued_partyWinning'].loc[c, 'brier']:.4f})")
    ax[0].plot([0, 1], [0, 1], "k--", lw=.8); ax[0].set_xlabel("predicted P(petitioner wins)"); ax[0].set_ylabel("observed rate"); ax[0].set_title("Holdout 2015-2025, argued cases (SEEN, single read)"); ax[0].legend(fontsize=7)
    taus = list(KS)
    for c in ["kalshi"] + mc: ax[1].plot(taus, [KS[t].loc[c, "brier"] for t in taus], "o-", lw=1.6 if c in ("kalshi", "m_K10") else .8, label=c)
    ax[1].set_title("Settled Kalshi markets: Brier at three fixed times (own market subsets)"); ax[1].legend(fontsize=7)
    f.tight_layout(); f.savefig(os.path.join(OUT, "HOLDOUT_calibration_claude.png"), dpi=110)
except Exception as e: print("plot failed (results already written):", type(e).__name__, e)

"""Amendment 2: the ONE read of the (already partly seen) 2015-2025 holdout + 36 settled Kalshi markets (terms 2021-2025).
Runs k11_eval.py first (selection is fixed by then), then scores used model, K10 and always-reverse. sha256 of this file logged before run."""
exec(open("k11_eval.py").read())
from sklearn.metrics import log_loss
out = {}
for k in dict.fromkeys([use, "K10"]):
    C = POP[k]; c = C[C.term.between(2015, 2025) & C.y_hidden.notna() & C.P.notna()]
    out[k] = {"n": len(c), "brier": float(((c.P - c.y_hidden) ** 2).mean()), "logloss": float(log_loss(c.y_hidden, c.P.clip(.01, .99))), "acc": float(((c.P > .5) == (c.y_hidden == 1)).mean()), "mean_P": float(c.P.mean())}
pr = []
for t in range(2015, 2026):
    h = C10[(C10.term < t) & (C10.term >= t - 10)]; yy = h.y.fillna(h.y_hidden); cc = C10[(C10.term == t) & C10.y_hidden.notna()]; pr += [(yy.mean(), v) for v in cc.y_hidden]
pr = np.array(pr); out["always_reverse(prior10 rate)"] = {"n": len(pr), "brier": float(((pr[:, 0] - pr[:, 1]) ** 2).mean()), "logloss": float(log_loss(pr[:, 1], pr[:, 0])), "acc": float(pr[:, 1].mean()), "mean_P": float(pr[:, 0].mean())}
H = pd.DataFrame(out).T; print("HOLDOUT 2015-2025 (seen before; single read)\n", H.round(4).to_string())
k = pd.read_csv("kalshi_hist/kalshi_settled_prices.csv"); m = pd.read_csv("kalshi_hist/market_map_hist.csv")[["ticker", "yes_maps_to", "primary"]]
k = k.merge(m, on="ticker"); k = k[k.yes_maps_to.isin(["reverse", "affirm"])].copy(); k["y"] = (k.result == "yes").astype(int)
k["kalshi"] = k.d7_mid.clip(.01, .99)
for nm in dict.fromkeys([use, "K10"]):
    pp = k.scdb_docketId.map(POP[nm].P); k["m_" + nm] = np.where(k.yes_maps_to == "reverse", pp, 1 - pp)
pp = k.term.map(lambda t: C10[(C10.term < t) & (C10.term >= t - 10)].y.fillna(C10.y_hidden).mean()); k["always_rev"] = np.where(k.yes_maps_to == "reverse", pp, 1 - pp)
cols = ["kalshi", "always_rev"] + ["m_" + n for n in dict.fromkeys([use, "K10"])]; kk = k.dropna(subset=cols)
KS = pd.DataFrame({c: {"n": len(kk), "brier": ((kk[c] - kk.y) ** 2).mean(), "logloss": log_loss(kk.y, kk[c].clip(.01, .99)), "acc": ((kk[c] > .5) == (kk.y == 1)).mean()} for c in cols}).T
KS2 = pd.DataFrame({c: {"n": int(kk.primary.sum()), "brier": ((kk[c] - kk.y)[kk.primary == 1] ** 2).mean()} for c in cols}).T
print("SETTLED KALSHI (terms 2021-2025, inside holdout, seen)\n", KS.round(4).to_string(), "\nprimary-wording only\n", KS2.round(4).to_string())
H.to_csv("eval_k11/HOLDOUT_2015_2025_single_read.csv"); KS.to_csv("eval_k11/HOLDOUT_kalshi_settled.csv"); kk[["ticker", "term", "y", "primary"] + cols].to_csv("eval_k11/HOLDOUT_kalshi_rows.csv", index=False)

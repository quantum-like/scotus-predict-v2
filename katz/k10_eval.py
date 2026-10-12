"""Amendment 1: K10 vs K07 (1990-2014 Brier sign test), seen 2015-2025, pending P (v2). Reuses katz_eval.py functions unchanged."""
import sys; sys.argv = ['x', 'results', 'eval_k10']
exec(open('katz_eval.py').read().split('CS = {}')[0])
from scipy.stats import binomtest
C7, C10 = build("K07", "pmaj"), build("K10", "pmaj"); os.makedirs("eval_k10", exist_ok=True)
pt = lambda C: C[C.term.between(1990, 2014) & C.y.notna() & C.P.notna()].assign(b=lambda x: (x.P - x.y) ** 2).groupby("term").b.mean().to_frame("brier"); b7, b10 = pt(C7), pt(C10); d = (b10.brier - b7.brier).dropna(); w = int((d < 0).sum())
hist = {}
for lab, lo, hi in [("1990-2014", 1990, 2014), ("SEEN 2015-2025", 2015, 2025)]:
    for k, C in [("K07", C7), ("K10", C10)]:
        c = C[C.term.between(lo, hi) & C.y.notna() & C.P.notna()]
        hist[(lab, k)] = {"n": len(c), "brier": ((c.P - c.y) ** 2).mean(), "acc": ((c.P > .5) == (c.y == 1)).mean(), "mean_P": c.P.mean(), "reverse_rate": c.y.mean(), "share_P_gt_.5": (c.P > .5).mean()}
H = pd.DataFrame(hist).T; print(H.round(4).to_string())
print(f"K10 vs K07 per-term Brier 1990-2014: K10 better in {w}/{len(d)} terms, sign p={binomtest(w, len(d)).pvalue:.4g}; mean {b10.brier.mean():.4f} vs {b7.brier.mean():.4f}")
p = C10[C10.term == 2026][["docket", "P"]].rename(columns={"P": "P_reverse"}); p.to_csv("eval_k10/pending_OT2026_K10.csv")
print("pending K10 P: mean %.3f, share>0.5 %.2f, min %.3f max %.3f" % (p.P_reverse.mean(), (p.P_reverse > .5).mean(), p.P_reverse.min(), p.P_reverse.max()))
H.to_csv("eval_k10/k10_vs_k07.csv")

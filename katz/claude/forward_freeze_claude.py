"""Amendment 6 (Claude) forward freeze (paper only): pending OT2026 P(petitioner wins) for K25-K28 (and K10s) on the markets of
FORWARD_OT2026_frozen_v2.csv, and the forward disagreement tracker (|P_model - Kalshi last price at the v2 freeze| >= 0.25). YES = petitioner
wins, multi-docket markets = mean P over their dockets (v1/v2 rule). Requires the verdict, input hashes, amendment and katz/claude code to be
committed and unmodified and every pinned input to match; computes both files and their sha256 in memory, then writes them and the
katz/claude/FORWARD_CLAUDE.md log together. Refuses to overwrite. Amendment 3's K10 tracker (katz/DISAGREE_OT2026.csv) is not touched."""
import datetime, gzip, hashlib, json, os, subprocess
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(os.path.dirname(HERE)); LOC = os.path.join(HERE, "results_local")
OUTR = os.path.join(REPO, "katz", "results", "claude"); CH = ["K10s", "K25", "K26", "K27", "K28"]
F1, F2, LOG = (os.path.join(HERE, f) for f in ("FORWARD_OT2026_claude.csv", "DISAGREE_OT2026_claude.csv", "FORWARD_CLAUDE.md"))
assert not os.path.exists(F1) and not os.path.exists(F2), "already frozen; a re-freeze needs a registered trigger and a new file name"
git = lambda *a: subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True)
assert not git("status", "--porcelain", "--", "katz/results/claude/verdict.json", "katz/results/claude/INPUT_SHA256.json", "katz/AMENDMENT_6_CLAUDE.md", "katz/claude").stdout.strip(), \
    "verdict, input hashes, amendment and katz/claude code must be committed and unmodified"
sha = lambda p: hashlib.sha256(gzip.open(p).read() if p.endswith(".gz") else open(p, "rb").read()).hexdigest()
for k, h_ in json.load(open(os.path.join(OUTR, "INPUT_SHA256.json"))).items(): assert sha(os.path.join(REPO, k)) == h_, f"input changed since the verdict: {k}"
V = json.load(open(os.path.join(OUTR, "verdict.json"))); assert not V.get("dry_run"); best = V["winner_lowest_wf_brier"]
P = pd.read_csv(os.path.join(LOC, "P_wf_all.csv.gz"), index_col=0); P = P[P.term == 2026].copy(); P["docket"] = P.docket.astype(str).str.strip(); P = P.set_index("docket")
v2 = pd.read_csv(os.path.join(REPO, "katz", "FORWARD_OT2026_frozen_v2.csv"))
now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
F = v2[["ticker", "dockets", "wording_match", "kalshi_yes_last_at_freeze", "P_yes_model_K10"]].copy(); F.insert(0, "frozen_at", now)
for m in CH: F["P_yes_" + m] = [round(float(np.mean([P.loc[d, m] for d in str(ds).split("+")])), 4) for ds in F.dockets]
L = F.melt(id_vars=["frozen_at", "ticker", "dockets", "wording_match", "kalshi_yes_last_at_freeze"], value_vars=["P_yes_" + m for m in CH], var_name="model", value_name="P_yes")
L["model"] = L.model.str.replace("P_yes_", ""); L["gap"] = (L.P_yes - L.kalshi_yes_last_at_freeze).round(4)
L["flag_ge_0.25"] = L.gap.abs() >= .25; L["is_lowest_wf_brier_model"] = L.model == best
b1, b2 = F.to_csv(index=False).encode(), L.to_csv(index=False).encode()
rows = f"| {now} | katz/claude/FORWARD_OT2026_claude.csv | {hashlib.sha256(b1).hexdigest()} |\n| {now} | katz/claude/DISAGREE_OT2026_claude.csv | {hashlib.sha256(b2).hexdigest()} |\n"
log = rows if os.path.exists(LOG) else ("# FORWARD_CLAUDE: frozen OT2026 predictions, Amendment 6 (Claude; K25-K28, K10s). Paper only, no orders.\n"
       "Kalshi price = last YES price at the v2 freeze (2026-10-12T10:37:32-07:00, FORWARD_OT2026_frozen_v2.csv). Do not edit rows; append resolutions below.\n\n"
       "| frozen_at | file | sha256 |\n|---|---|---|\n" + rows + "\n## Resolutions\n| date | ticker | result | notes |\n|---|---|---|---|\n")
open(F1, "wb").write(b1); open(F2, "wb").write(b2); open(LOG, "a").write(log)
print(F.to_string()); print(L[L["flag_ge_0.25"]].to_string())

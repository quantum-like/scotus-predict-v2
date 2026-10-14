"""Amendment C1 (Claude), section B (docket part) + the lower-court decision date used by section C. Paper only, never trade.
Reads every raw/dockets/{docket}.html present (the fetcher may still be adding files: re-run any time), writes
features/cert_docket.csv (one row per file) and features/dockets_coverage.txt. Downloaded pages are UNTRUSTED: parsed as text only.
No outcome field is read anywhere in this module (it never opens SCDB); the coverage file holds only coverage counts, distributions
of the features themselves and spot checks against the raw text.

Parsing choices (the spec delegates these to code):
- Decoding: utf-8, else cp1252. <script>/<style>/comments removed; new-format <span class="documentlinks"> (PDF link labels such as
  "Petition", "Main Document") removed so link labels never enter entry text; tags stripped, html.unescape, nbsp -> space.
- Region: everything before "Docket for <no>" / id="docketinfo" (site navigation) is dropped. Header = from there to the
  proceedings header ("Proceedings and Orders"); proceedings = from that header to the first structural end marker of the
  attorneys block (~~Name~~, id="Contacts", class="ContactSubHeader", <B>Attorneys for Petitioner), never entry text.
- Entries: table rows split into cells. A row whose first cell is a date (Mon d[d] yyyy) starts an entry (text = the other
  cells); a row whose first cell is empty continues the current entry (OLD fixed-width layout: one <tr> per printed line);
  a row with any other first cell closes the current entry. Fallback when no row-entry is found: the region is turned into
  text lines; a line starting with an abbreviated, comma-less date ("Dec  4 2000") starts an entry, other lines continue it
  (so a wrapped "February 12, 2001, submitted ..." stays in its entry) (parse_note fmt=...+text).
- Layouts (parse_note fmt=): new (td class=ProceedingDate), mid (~2016-17, <table id="proceedings">), old (fixed-width or
  plain <td valign=top> rows). All three are read by the same row rule.
- Header: docketed_date = the visible "Docketed:" field (same row, or the first cell of the next row in the OLD 2000-2012
  layout); the <META name='Docketed'> tag only as fallback, since it can be stale (15-9260: META June 30, 2015 vs displayed
  May 11, 2016); disagreements are noted "meta_docketed_differs". lower_court = first non-empty cell after "Lower Ct:".
  lc_decision_date = the "Decision Date:" field; if absent, a full date written inside the Lower Ct cell ("<court> <Month dd, yyyy> (<no>)") or in the cells after the
  docketed date of the OLD layout; else empty. All dates ISO yyyy-mm-dd.
- GRANT_RE; grant = earliest-dated matching entry (page order breaks ties). GRANTED must directly follow "petition(s)" [optionally
  "for (a|an|the) (writ(s) of) certiorari|mandamus|prohibition|habeas corpus (before judgment)", "treated as a petition for a writ
  of certiorari and", "is/are"], and "petition" must start the entry or a sentence ([.;:] before it) or follow "and" (the combined
  "Motion ... in forma pauperis and petition ... GRANTED" order). So motions/applications ("... amicus ... GRANTED", "dispense with
  printing ... GRANTED", "Motion to expedite consideration of the petition ... GRANTED", "Petition for rehearing GRANTED") never fire.
  Case: GRANTED is case-sensitive; a lower-case "granted" never fires (so e.g. "The petition for a writ of certiorari is granted."
  does not; such dockets get parse_note "lowercase_grant_only" and stay missing). REFINEMENT: the title-case typo "Petition Granted."
  (capital G, seen on 14-10008) is accepted, since only the petition prefix can precede it; flagged "grant_titlecase" in parse_note.
  Also a grant: "PROBABLE JURISDICTION NOTED" and "Further consideration of the question of jurisdiction ... postponed/deferred"
  (both case-insensitive: these phrases occur only in such orders).
- grant_text = grant entry text from its start to the end of the sentence holding the match; if that sentence has a
  judgment/adjudged/reversed/vacated/affirmed/remanded word after the match, only up to the end of the match; trailing
  punctuation dropped; max 200 chars. So "Petition GRANTED. Judgment VACATED ..." and a plenary "Petition GRANTED." both give
  "Petition GRANTED": the disposition is not carried into this file. Diagnostic column only, never a feature.
- SUMMARY DISPOSITIONS (review fix; Amendment rule 1). The grant entry is still detected (the spec requires GRANT_RE to fire on
  "Petition GRANTED. Judgment VACATED, and case REMANDED"), but when the grant is itself the decision there is no pre-decision
  grant phase: days_to_grant would be decision date - petition date, and relists/amicus/CVSG would be counted up to the decision
  (14-10008: "Petition Granted. Judgment REVERSED and case REMANDED. Opinion per curiam." with 11 distributions, 285 days). Such a
  docket keeps docket_have=1, grant_date and grant_text, but n_entries_pre_grant, cvsg, n_amicus_cert, n_distributed_pre, relists,
  days_to_grant and their logs are empty (missing), exactly like a docket with no grant entry, and parse_note says
  "summary_disposition". This also makes the upper-case GVR/summary-reversal pages consistent with the lower-case per curiam pages
  ("the petition ... is granted", 17-654), which never match GRANT_RE and were already missing. Detection (SUMD_RE, searched in the
  grant entry AFTER the GRANT match and in every other entry dated on the grant date): upper-case REVERSED/VACATED/AFFIRMED/
  REMANDED, or (any case) "opinion per curiam", "adjudged to be", "judgment(s) (is|are) reversed/vacated/affirmed", "case(s) (is|are)
  remanded". Not the bare word "judgment": plenary grants say "certiorari before judgment ... are granted" (18-587), "in support of
  the judgment below" (16-6855), QP text (21-846), and same-day stay orders say "the judgment of the District Court ... is stayed"
  (16-1161); none of these is flagged (re-checked on every run in the coverage file, SD_CHECKS). The disposition words themselves
  are never written to this file (parse_note says only "summary_disposition", not the direction). A grant followed by a per curiam
  on a LATER date (briefing, no argument) is a real pre-decision grant and keeps its features.
- Only entries dated strictly before grant_date count (an entry on the grant date does not).
  cvsg = 1 if any such entry matches CVSG_RE ("Solicitor General (is) invited to file a brief", case-insensitive), else 0
  (invitation only; the SG's brief or recommendation is never parsed).
  n_amicus_cert = such entries that FILE an amicus brief or a motion for leave to file one: entry starts with (the)
  (supplemental|corrected|amended)? brief(s)/motion(s)/amicus/amici, contains an amicus phrase (brief(s) (of) (the) (court-appointed)
  amicus/amici curiae, amicus/amici (curiae) brief(s), brief(s) as/for amicus/amici curiae, leave to file ... amicus/amici) and
  filed|submitted|lodged, and is not a ruling (no granted/denied). Each entry counts once (motion + brief in one entry = 1).
  "Consent to the filing of amicus briefs" entries do not count. CHOICE: amicus briefs filed BY the United States / Solicitor
  General ("amicus curiae of (the) United States" followed by end/","/"("/filed/in support/supporting/as amicus) are NOT counted:
  at cert stage they are the response to the CVSG or the SG's own position, which the amendment keeps out of K22 ("never reads
  the SG's brief"); their number is in parse_note ("us_amicus_excluded=k") and in the coverage file.
  n_distributed_pre = such entries starting with "(RE)DISTRIBUTED for (the) Conference" (case-insensitive); "Motion DISTRIBUTED
  for Conference" (a motion, not the petition) does not count.
- petition_date = earliest entry that starts with petition for (a) (writ of) certiorari/mandamus/prohibition/habeas corpus,
  jurisdictional statement, statement as to jurisdiction, or appeal, and says filed/docketed within 200 chars.
  days_to_grant = grant_date - (petition_date if found and <= grant_date, else docketed_date if <= grant_date), else missing.
- docket_have = 1 for every file. With no grant entry: grant_date, grant_text, n_entries_pre_grant, cvsg, n_amicus_cert,
  n_distributed_pre, relists, days_to_grant and the logs are empty (missing) and parse_note says so.
  LEAK WARNING for stage 2: dockets with no grant entry are those disposed of without an upper-case cert-grant/PJN entry
  (summary affirmances of appeals, e.g. 16-1023; per curiam dispositions written "the petition ... is granted", e.g. 17-654, or
  with no grant words, e.g. 20-391; as read on their pages), and summary_disposition rows have a grant_date but missing features,
  so neither grant_date.notna() nor feature missingness may be a regressor: both encode the disposition type. A have/availability
  flag must come from page existence (docket_have) or the docket era, and only switch the family on/off; parse_note and grant_text
  are diagnostics, never features. (stage2.py as of 2026-10-12 16:56 uses the docket-year era for activation and no have regressor.)
Derived: relists = max(0, n_distributed_pre - 1); amicus_cert = log1p(n_amicus_cert); relists_log = log1p(relists);
log_days_to_grant = log1p(days_to_grant).
Run (from anywhere): nice -n 10 ~/scotus-predict-rerun/.venv/bin/python -I -B katz/claude/parse_dockets.py"""
import glob, html, os, re, time
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); RAW = os.path.join(HERE, "raw", "dockets"); OUT = os.path.join(HERE, "features")
COLS = ["docket", "docket_have", "docketed_date", "lower_court", "lc_decision_date", "petition_date", "grant_date", "grant_text", "n_entries_pre_grant",
        "cvsg", "n_amicus_cert", "n_distributed_pre", "relists", "days_to_grant", "amicus_cert", "relists_log", "log_days_to_grant", "parse_note"]
MON = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
EDATE = re.compile(r"(?i)(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})")      # entry date cell
FDATE = re.compile(r"(?i)\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s+(\d{4})\b")
GRANT_RE = re.compile(r"(?i:(?:^|[.;:]\s*|\band\s+)(?:the\s+)?petitions?(?:\s+for\s+(?:an?\s+|the\s+)?(?:writs?\s+of\s+)?(?:certiorari|mandamus|prohibition|"
                      r"habeas\s+corpus)(?:\s+before\s+judgment)?)?(?:\s+treated\s+as\s+an?\s+petition\s+for\s+(?:an?\s+)?writ\s+of\s+certiorari\s+and)?"
                      r"\s+(?:is\s+|are\s+)?)G(?:RANTED|ranted)\b"
                      r"|(?i:probable\s+jurisdiction\s+(?:is\s+)?noted)"
                      r"|(?i:further\s+consideration\s+of\s+the\s+question\s+of\s+(?:the\s+)?jurisdiction\b[^.]{0,80}?\b(?:postponed|deferred))")
LOWER_GRANT = re.compile(r"(?i:petitions?\b[^.]{0,80}?\b(?:is|are)\s+)granted\b")                     # diagnostic only, never a grant
CVSG_RE = re.compile(r"(?i)\bsolicitor\s+general\s+(?:is\s+)?invited\s+to\s+file\s+(?:a\s+)?briefs?\b")
AM_START = re.compile(r"(?i)^(?:the\s+)?(?:(?:supplemental|corrected|amended)\s+)?(?:briefs?|motions?|amicus|amici)\b")
AM_RE = re.compile(r"(?i)\bbriefs?\s+(?:of\s+)?(?:the\s+)?(?:court-appointed\s+)?amic(?:us|i)\s+curiae\b|\bamic(?:us|i)\s+(?:curiae\s+)?briefs?\b"
                   r"|\bbriefs?\s+(?:as\s+|for\s+)?amic(?:us|i)\s+curiae\b|\bleave\s+to\s+file\b[^.]{0,80}?\bamic(?:us|i)\b")
FILED_RE = re.compile(r"(?i)\b(?:filed|submitted|lodged)\b"); RULING_RE = re.compile(r"(?i)\b(?:granted|denied)\b")
US_AM_RE = re.compile(r"(?i)\b(?:amic(?:us|i)\s+curiae\s+of|briefs?\s+(?:of|for))\s+(?:the\s+)?(?:acting\s+)?(?:united\s+states(?:\s+of\s+america)?|solicitor\s+general)"
                      r"(?=\s*(?:,|\(|\.|$|filed|submitted|lodged|as\s+amic|in\s+support|supporting))")
DIST_RE = re.compile(r"(?i)^(?:re)?distributed\s+for\s+(?:the\s+)?conference\b")
PET_RE = re.compile(r"(?i)^(?:the\s+)?(?:petition\s+for\s+(?:an?\s+)?(?:writ\s+of\s+)?(?:certiorari|mandamus|prohibition|habeas\s+corpus)|jurisdictional\s+statement"
                    r"|statement\s+as\s+to\s+jurisdiction|appeal)\b.{0,200}?\b(?:filed|docketed)\b")
OUTW = re.compile(r"(?i)\b(?:judgments?|adjudged|reversed|vacated|affirmed|remanded)\b"); SENT = re.compile(r"\.(?=\s+[A-Z(]|\s*$)")
SUMD_RE = re.compile(r"\b(?:REVERSED|VACATED|AFFIRMED|REMANDED)\b|(?i:\bopinion\s+per\s+curiam\b|\bper\s+curiam\s+opinion\b|\badjudged\s+to\s+be\b"
                     r"|\bjudgments?\s+(?:is\s+|are\s+)?(?:reversed|vacated|affirmed)\b|\bcases?\s+(?:is\s+|are\s+)?remanded\b)")   # grant entry = decision
SD_FEATS = ["n_entries_pre_grant", "cvsg", "n_amicus_cert", "n_distributed_pre", "relists", "days_to_grant"]
PROC_RE = re.compile(r"(?i)proceedings(?:\s|&nbsp;)+and(?:\s|&nbsp;)+orders"); END_RE = re.compile(r"(?i)~~name~~|id=[\"']contacts[\"']|class=[\"']contactsubheader[\"']|<b>\s*attorneys\s+for\s+petitioner")
# 10 random spot checks: DataFrame.sample(10, random_state=0) over the 308 files present 2026-10-12 16:35 PT; each value was read
# by hand from the raw page text (proceedings up to the grant entry). docket -> (grant_date, n_entries_pre_grant, cvsg,
# n_amicus_cert, n_distributed_pre, days_to_grant); None = no grant entry. coverage() re-checks them on every run.
VERIFIED = {"14-1505": ("2015-11-06", 10, 0, 0, 3, 140), "14-990": ("2015-06-08", 8, 0, 1, 3, 118), "15-1039": ("2017-01-13", 15, 1, 4, 3, 332),
            "15-105": ("2015-11-06", 24, 0, 15, 2, 106), "15-6092": ("2016-01-19", 6, 0, 0, 1, 126), "15-9260": ("2016-10-28", 8, 0, 0, 2, 177),
            "16-373": ("2017-01-13", 8, 0, 2, 2, 113), "17-530": ("2018-01-12", 6, 0, 1, 2, 98), "25-417": ("2026-06-22", 17, 0, 0, 4, 262),
            "25-581": ("2026-04-20", 34, 0, 20, 3, 158)}
VERIFIED_NOTES = {"15-1039": "1 US amicus brief (Dec 7 2016, after the CVSG) excluded", "15-9260": "displayed Docketed May 11, 2016 (META says June 30, 2015)",
                  "25-581": "USCCB brief counted; 'Brief amicus curiae of United States in support of the petitioners' (Jan 30 2026) excluded",
                  "15-105": "14 amicus briefs on Aug 24 2015 + 1 on Aug 21; consents to amicus filings not counted"}
# summary-disposition regression checks, read by hand from the grant-date entries (2026-10-12): True = the grant entry is the decision.
SD_CHECKS = {"14-10008": True,   # "Petition Granted. Judgment REVERSED and case REMANDED. Opinion per curiam."
             "15-723": True,     # "Petition GRANTED and Judgment REVERSED. Opinion per curiam."
             "18-272": True,     # "Petition GRANTED. The judgment is VACATED and the case is REMANDED ..."
             "18-483": True,     # "Petition GRANTED as to Question 1 and Judgment REVERSED as to Question 1 ... Opinion per curiam."
             "20-1539": True,    # "Petition GRANTED. Determination of ... Ninth Circuit that ... is not entitled to qualified immunity REVERSED."
             "16-6855": False,   # IFP + petition GRANTED; amicus "invited to brief and argue ... in support of the judgment below"
             "18-587": False,    # "... certiorari before judgment in No. 18-588 and No. 18-589 are granted. The cases are consolidated"
             "21-846": False,    # "Petition GRANTED limited to the following question: Whether ..." (QP text)
             "16-1161": False,   # jurisdiction postponed; same-day stay order "... the judgment of the United States District Court ... [stayed]"
             "26-426": False}    # cert before judgment granted; same-day stay order "The February 25, 2026 order and judgment ... [stayed]"

def ed(m): return f"{int(m.group(3)):04d}-{MON[m.group(1)[:3].lower()]:02d}-{int(m.group(2)):02d}"
def fd(s):
    m = FDATE.search(s or ""); return ed(m) if m else ""
def txt(h): return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]*>", " ", h)).replace("\xa0", " ")).strip()
def rows(h):
    out = []
    for tr in re.split(r"(?i)<tr\b[^>]*>", h)[1:]:
        tr = re.split(r"(?i)</tr\s*>", tr)[0]; out.append([txt(c) for c in re.split(r"(?i)<t[dh]\b[^>]*>", tr)[1:]])
    return out
def entries_rows(h):
    E, cur = [], None
    for c in rows(h):
        if not c: continue
        m = EDATE.fullmatch(c[0])
        if m: cur = [ed(m), " ".join(x for x in c[1:] if x)]; E.append(cur)
        elif c[0] == "" and cur is not None: cur[1] = (cur[1] + " " + " ".join(x for x in c[1:] if x)).strip()
        else: cur = None
    return E
def entries_text(h):
    t = re.sub(r"(?i)<br\s*/?>|</(?:p|div|tr|li|pre|table)\s*>", "\n", h)
    E, cur = [], None
    for l in html.unescape(re.sub(r"(?s)<[^>]*>", " ", t)).replace("\xa0", " ").splitlines():
        l = re.sub(r"\s+", " ", l).strip(" |")
        m = re.match(r"(?i)((?:jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec)\.?\s+\d{1,2}\s+\d{4})\b\s*\|?\s*(.*)", l)   # 'Mon dd yyyy' only:
        if m: cur = [ed(EDATE.fullmatch(m.group(1))), m.group(2)]; E.append(cur)                         # 'February 12, 2001,' continues
        elif l and cur is not None and not l.startswith("~~"): cur[1] = (cur[1] + " " + l).strip()
    return E
def header(h):
    d = lc = lcd = ""; R = rows(h)
    for i, c in enumerate(R):
        k = [j for j, x in enumerate(c) if re.fullmatch(r"(?i)docketed:?", x)]
        if k and not d:
            d = fd(" ".join(c[k[0] + 1:k[0] + 2]))
            if not d and i + 1 < len(R) and R[i + 1]:
                d = fd(R[i + 1][0]); lcd = lcd or fd(" ".join(R[i + 1][1:]))   # OLD layout: next row = docketed date, (date) lc no
        k = [j for j, x in enumerate(c) if re.fullmatch(r"(?i)lower\s+ct\.?:?", x)]
        if k and not lc:
            nx = [x for x in c[k[0] + 1:] if x]
            if nx: m = FDATE.search(nx[0]); lc = (nx[0][:m.start()] if m else nx[0]).split("(")[0].strip(" ,|"); lcd = lcd or (ed(m) if m else "")
        if c and re.fullmatch(r"(?i)decision\s+date:?", c[0]) and len(c) > 1: lcd = fd(c[1]) or lcd
    meta = fd((re.search(r"(?i)<meta\s+name=['\"]docketed['\"]\s+content=['\"]([^'\"]*)", h) or [None, ""])[1])
    return d or meta, lc, lcd, (d and meta and d != meta)
def load(path):   # -> (header html, proceedings entries, fmt)
    b = open(path, "rb").read()
    try: h = b.decode("utf-8")
    except UnicodeDecodeError: h = b.decode("cp1252", "replace")
    h = re.sub(r"(?is)<(script|style)\b.*?</\1\s*>|<!--.*?-->", " ", h); h = re.sub(r"(?is)<span\s+class=[\"']documentlinks[\"']>.*?</span>", " ", h)
    s = min([m.start() for m in [re.search(r"(?i)docket\s+for\s+\d|id=[\"']docketinfo[\"']", h)] if m] or [0]); h = h[s:]
    p = PROC_RE.search(h); hd, pr = (h[:p.start()], h[p.end():]) if p else (h, h)
    e = END_RE.search(pr); pr = pr[:e.start()] if e else pr
    fmt = "new" if "proceedingdate" in h.lower() else "mid" if re.search(r"(?i)<table\s+id=[\"']proceedings", h) else "old"; E = entries_rows(pr)
    if not E: E = entries_text(pr); fmt += "+text"
    return hd, E, fmt
def parse(path):
    hd, E, fmt = load(path); d, lc, lcd, mm = header(hd)
    r = dict(docket=os.path.basename(path)[:-5], docket_have=1, docketed_date=d, lower_court=lc, lc_decision_date=lcd); note = [f"fmt={fmt}", f"n_entries={len(E)}"]
    if not d: note.append("no_docketed_date")
    if mm: note.append("meta_docketed_differs")
    pe = sorted(x[0] for x in E if PET_RE.search(x[1])); r["petition_date"] = pe[0] if pe else ""
    if not pe: note.append("no_petition_entry")
    G = sorted([(x[0], i, x[1]) for i, x in enumerate(E) if GRANT_RE.search(x[1])])
    if not G:
        note.append("no_grant_entry: docket features missing")
        if any(LOWER_GRANT.search(x[1]) for x in E): note.append("lowercase_grant_only")
        r.update(grant_date="", grant_text=""); r["parse_note"] = "; ".join(note); return r
    gd, gi, gt = G[0]; m = GRANT_RE.search(gt)
    if "Granted" in m.group(0): note.append("grant_titlecase")
    sd = bool(SUMD_RE.search(gt, m.end())) or any(SUMD_RE.search(x[1]) for i, x in enumerate(E) if x[0] == gd and i != gi)
    e = SENT.search(gt, max(m.end() - 1, 0)); seg = gt[:e.end() if e else len(gt)]
    if OUTW.search(seg, m.end()): seg = gt[:m.end()]                                      # never carry disposition words
    gt = re.sub(r"[\s.,;:]+$", "", seg)[:200]
    if sd:                                                                                # grant = decision: no pre-decision phase
        note.append("summary_disposition: grant entry is the decision, docket features missing")
        r.update(grant_date=gd, grant_text=gt, parse_note="; ".join(note)); return r
    pre = [x[1] for x in E if x[0] < gd]
    am = [t for t in pre if AM_START.match(t) and AM_RE.search(t) and FILED_RE.search(t) and not RULING_RE.search(t)]; us = [t for t in am if US_AM_RE.search(t)]
    if us: note.append(f"us_amicus_excluded={len(us)}")
    nd = sum(bool(DIST_RE.match(t)) for t in pre)
    st = r["petition_date"] if r["petition_date"] and r["petition_date"] <= gd else (d if d and d <= gd else "")
    if st != r["petition_date"]: note.append("days_from_docketed" if st else "no_start_date")
    days = (pd.Timestamp(gd) - pd.Timestamp(st)).days if st else np.nan
    r.update(grant_date=gd, grant_text=gt, n_entries_pre_grant=len(pre), cvsg=int(any(CVSG_RE.search(t) for t in pre)), n_amicus_cert=len(am) - len(us),
             n_distributed_pre=nd, relists=max(0, nd - 1), days_to_grant=days, parse_note="; ".join(note))
    return r

def coverage(D):
    sdm = D.parse_note.str.contains("summary_disposition"); g = D[D.grant_date.ne("") & ~sdm]; S = D[sdm]
    L = [f"parse_dockets.py coverage, run {time.strftime('%Y-%m-%d %H:%M %Z')} (raw/ may still be growing; re-run to refresh)",
        "Only coverage counts, parse-success rates, distributions of the features themselves, and spot checks. No outcome is read.", ""]
    rt = lambda s: f"{int(s.sum())}/{len(s)} = {s.mean():.3f}" if len(s) else "0/0"
    fm = D.parse_note.str.extract(r"fmt=([^;]+);")[0].fillna("error")
    L += [f"files parsed: {len(D)}   formats: " + ", ".join(f"{k}={v}" for k, v in fm.value_counts().items()),
          f"entries found (>0): {rt(D.parse_note.str.extract(r'n_entries=(\d+)')[0].astype(float).fillna(0) > 0)}",
          f"docketed_date found: {rt(D.docketed_date.ne(''))}", f"lower_court found: {rt(D.lower_court.ne(''))}",
          f"lc_decision_date found: {rt(D.lc_decision_date.ne(''))}", f"petition_date found: {rt(D.petition_date.ne(''))}",
          f"grant found: {rt(D.grant_date.ne(''))}", f"  grant_titlecase ('Petition Granted'): {int(D.parse_note.str.contains('grant_titlecase').sum())}",
          f"  no grant but a lower-case 'petition ... is granted' entry (left missing per spec): {', '.join(D.docket[D.parse_note.str.contains('lowercase_grant_only')]) or '-'}",
          f"  no grant entry (all, first 60): {', '.join(D.docket[D.grant_date.eq('')][:60]) or '-'}",
          f"  summary_disposition (grant entry is the decision; grant_date kept, docket features missing): {rt(sdm)}",
          f"    all of {', '.join(SD_FEATS)} + logs missing on these rows: "
          f"{bool(S[SD_FEATS + ['amicus_cert', 'relists_log', 'log_days_to_grant']].isna().all().all()) if len(S) else '-'}",
          f"    dockets: {', '.join(S.docket) or '-'}",
          f"  pre-decision grant (features present): {rt(D.grant_date.ne('') & ~sdm)}",
          f"parse errors (file caught mid-write?): {', '.join(D.docket[D.parse_note.str.startswith('parse_error')]) or '-'}",
          "LEAK WARNING: no-grant dockets are those disposed of without a cert-grant/PJN order (summary affirmances of appeals,",
          "  lower-case per curiam dispositions) and summary_disposition rows have a grant_date but missing features, so neither",
          "  grant_date.notna() nor feature missingness may be a regressor (both encode disposition type). Availability = page",
          "  existence (docket_have) or docket era, used only to switch the family on/off; parse_note/grant_text are diagnostics.", "",
          f"Among the {len(g)} dockets with a pre-decision grant (pre-grant entries only; summary dispositions excluded):",
          f"  cvsg = 1: {rt(g.cvsg.astype(int) == 1)}", f"  n_amicus_cert > 0: {rt(g.n_amicus_cert.astype(int) > 0)}",
          f"  relists > 0 (n_distributed_pre >= 2): {rt(g.relists.astype(int) > 0)}", f"  n_distributed_pre = 0: {rt(g.n_distributed_pre.astype(int) == 0)}",
          f"  days_to_grant missing: {int(g.days_to_grant.isna().sum())}; measured from docketed date (no usable petition entry): {int(g.parse_note.str.contains('days_from_docketed').sum())}",
          f"  US/SG amicus entries excluded from n_amicus_cert: {int(g.parse_note.str.extract(r'us_amicus_excluded=(\d+)')[0].astype(float).sum())} entries in "
          f"{int(g.parse_note.str.contains('us_amicus_excluded').sum())} dockets", "", "Feature distributions (dockets with a pre-decision grant):"]
    q = [0, .1, .25, .5, .75, .9, 1]
    for c in ["n_entries_pre_grant", "n_amicus_cert", "n_distributed_pre", "relists", "days_to_grant", "amicus_cert", "relists_log", "log_days_to_grant"]:
        s = g[c].astype(float).dropna(); L.append(f"  {c:18s} n={len(s):4d} mean={s.mean():8.2f} " + " ".join(f"q{int(p*100)}={s.quantile(p):.2f}" for p in q))
    L += ["", "By docket year prefix (files, grant found, of which summary_disposition, cvsg=1 | pre-decision grant, amicus>0 | same,",
          "  relists>0 | same, lc_decision_date found):"]
    yy = D.docket.str[:2]
    for y, d in D.groupby(yy):
        sd = d.parse_note.str.contains("summary_disposition"); gg = d[d.grant_date.ne("") & ~sd]
        f = lambda s: f"{s.mean():.2f}" if len(s) else "  - "
        L.append(f"  {y}: files={len(d):4d} grant={int(d.grant_date.ne('').sum()):4d} ({d.grant_date.ne('').mean():.2f}) sd={int(sd.sum()):3d}  "
                 f"cvsg={f(gg.cvsg.astype(int) == 1)} amicus>0={f(gg.n_amicus_cert.astype(int) > 0)} "
                 f"relists>0={f(gg.relists.astype(int) > 0)}  lc_date={d.lc_decision_date.ne('').mean():.2f}")
    L += ["", "Lower courts (top 12):"] + [f"  {v:4d}  {k}" for k, v in D.lower_court.replace("", "(none)").value_counts().head(12).items()]
    L += ["", f"Spot checks: {len(VERIFIED)} dockets drawn at random (seed 0) and verified by reading the raw page text; VERIFIED in parse_dockets.py",
          "  holds (grant_date, n_entries_pre_grant, cvsg, n_amicus_cert, n_distributed_pre, days_to_grant) as read by hand; 'match' re-checks the current parse."]
    for k, v in VERIFIED.items():
        r = D[D.docket == k]
        if not len(r): L.append(f"  {k}: file not present"); continue
        iv = lambda x: None if pd.isna(x) else int(x)
        r = r.iloc[0]; got = None if r.grant_date == "" else (r.grant_date, iv(r.n_entries_pre_grant), iv(r.cvsg), iv(r.n_amicus_cert), iv(r.n_distributed_pre), iv(r.days_to_grant))
        L.append(f"  {k}: match={got == v} parsed={got} | grant_text={r.grant_text!r} | petition={r.petition_date} docketed={r.docketed_date} "
                 f"lc={r.lower_court!r} lc_date={r.lc_decision_date} | {r.parse_note}" + (f" | note: {VERIFIED_NOTES[k]}" if k in VERIFIED_NOTES else ""))
    L.append(f"  spot checks matching: {sum(1 for x in L if ': match=True' in x)}/{len(VERIFIED)}")
    L += ["", f"Summary-disposition checks (SD_CHECKS, read by hand from the grant-date entries): expected flag vs current parse"]
    for k, v in SD_CHECKS.items():
        r = D[D.docket == k]
        if not len(r): L.append(f"  {k}: file not present"); continue
        r = r.iloc[0]; got = "summary_disposition" in r.parse_note
        L.append(f"  {k}: ok={got == v} expected_summary={v} parsed_summary={got} grant_date={r.grant_date} grant_text={r.grant_text!r} "
                 f"days_to_grant={'' if pd.isna(r.days_to_grant) else int(r.days_to_grant)}")
    L.append(f"  summary-disposition checks ok: {sum(1 for x in L if ': ok=True' in x)}/{sum(1 for k in SD_CHECKS if (D.docket == k).any())} present")
    return "\n".join(L) + "\n"

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    def safe(f):   # a page caught mid-write by the running fetcher (or any surprise) must not stop the run
        try: return parse(f)
        except Exception as ex: return dict(docket=os.path.basename(f)[:-5], docket_have=1, grant_date="", parse_note=f"parse_error: {type(ex).__name__}")
    fs = sorted(glob.glob(os.path.join(RAW, "*.html"))); D = pd.DataFrame([safe(f) for f in fs], columns=COLS)
    for c in ["n_entries_pre_grant", "cvsg", "n_amicus_cert", "n_distributed_pre", "relists", "days_to_grant"]: D[c] = pd.to_numeric(D[c], errors="coerce").astype("Int64")
    D["amicus_cert"] = np.log1p(D.n_amicus_cert.astype(float)); D["relists_log"] = np.log1p(D.relists.astype(float)); D["log_days_to_grant"] = np.log1p(D.days_to_grant.astype(float))
    for c in ["docketed_date", "lower_court", "lc_decision_date", "petition_date", "grant_date", "grant_text", "parse_note"]: D[c] = D[c].fillna("")
    D.to_csv(os.path.join(OUT, "cert_docket.csv"), index=False)
    open(os.path.join(OUT, "dockets_coverage.txt"), "w").write(coverage(D))
    print(f"{len(D)} files -> features/cert_docket.csv, features/dockets_coverage.txt; grant found {D.grant_date.ne('').mean():.3f}", flush=True)

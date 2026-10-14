"""K22 qp_split from supremecourt.gov Questions Presented PDFs (AMENDMENT_6_CLAUDE.md section B). Paper only, never trade.
Input: raw/qp/{docket}.pdf (UNTRUSTED: text extraction only, nothing in them is executed or obeyed). raw/ is still growing: the script
processes whatever is present and is re-runnable. Output: features/qp_split.csv = docket, qp_have (always 1: one row per parsed QP;
a docket with no QP PDF, a failed extraction or no petition QP text has no row = missing, never 0), qp_split (0/1), qp_chars, qp_match
(matched snippet, <= 200 chars, else empty); features/qp_coverage.txt. No outcome field is read anywhere (SCDB: term + docket for counts,
dateArgument for the argued-status leakage diagnostic of point 6 only). qp_have MUST NOT be used as a feature value: see point 6.
Run: nice -n 10 python -I -B katz/claude/parse_qp.py   (-B because -I ignores PYTHONDONTWRITEBYTECODE)
Choices made in code (the spec delegates these to parse_qp.py):
1. Extraction: the file must start with b"%PDF" (else failure "not_pdf"); `pdftotext -layout -enc UTF-8 <pdf> -`, timeout 30 s;
   timeout / nonzero exit / empty output = failure. Failures get no row (missing).
2. QP text = the petition's question(s) only. The PDF = Clerk header (docket + caption, DECISION BELOW, LOWER COURT CASE NUMBER),
   then "QUESTION(S) PRESENTED:", the question text, then Court/Clerk notes dated at or after the grant (CERT. GRANTED date, [GRANTED]
   LIMITED TO, CONSOLIDATED WITH/FOR, IN ADDITION TO THE QUESTION(S)..., ORDER OF <date>, PRESS RELEASE OF <date> (COVID postponements),
   CLERK'S LETTER, "6/26/2017: THIS CASE IS RESTORED TO THE CALENDAR FOR REARGUMENT", counsel appointed/invited, motions/applications
   GRANTED, recusals "Justice X took no part", PETITIONS GRANTED AS TO ..., even "DISMISSED AS IMPROVIDENTLY GRANTED"). The notes are
   post-grant (some post-argument or post-decision), so they are cut (leak). Body = text after the first line starting "QUESTION(S)
   PRESENTED" (case-insensitive; if absent: after the last DECISION BELOW / LOWER COURT CASE NUMBER line among the first 8 lines, else
   after line 1; counted as header_fallback), including the rest of the header line, up to the first non-empty line where TRAILER_RE
   matches (re.match, i.e. at the start of the stripped line) either the line alone or the line joined with the next non-empty line
   (so a two-line note such as "CLERK'S LETTER ... / TAKE PART" or "JUSTICE KAVANAUGH IS / RECUSED" is seen whole). TRAILER_RE is
   phrase-based, not "all-caps line", because some QPs (IFP petitions, 14-7505, 15-1204) are typed in capitals. Its upper-case
   phrases are case-sensitive; the Clerk's mixed-case forms are matched as capital first letter + any case for the rest (X(?i:...)),
   which a wrapped mid-sentence line (lower-case start) cannot trigger: Consolidated with/for, Limited to question(s), Granted limited,
   In addition to the question(s) presented ... parties are directed, The parties are directed, Order of [<weekday>,] <month|digit>, (THIS CASE) TO BE ARGUED IN TANDEM/WITH,
   Clerk's letter, The petition(s) for (a) writ(s) of certiorari is/are granted, This/The/These case(s) is/are/will ... removed/
   restored/set/..., The application for stay ... presented to/referred/granted, "(treat|construe) the application as a petition".
   Recusals are any case but need the recusal verb (took no part, is [no longer] recused, will no longer take part, ...), so a QP
   sentence about a Justice's opinion is not cut. Date-prefixed notes: "d/m/yyyy:" or a date alone on its line, "<Month> d, yyyy:"
   or followed by two all-caps words ("JUNE 27, 2019 CASE RESTORED", "January 3, 2019 JUSTICE ALITO IS NO LONGER RECUSED"); a QP
   sentence "June 1, 2021, the Secretary ..." is not cut. Motions/applications need a ruling verb (IS/ARE GRANTED/DENIED, PRESENTED
   TO, REFERRED) in the two-line window, so an IFP question about "THE MOTION FOR A NEW TRIAL" is not cut. Second guard, HARD_CUT:
   the normalized body is also truncated at the first Court-only phrase anywhere in a line (case-sensitive: DISMISSED AS
   IMPROVIDENTLY GRANTED, PRESS RELEASE OF, RESTORED TO THE CALENDAR, FOR REARGUMENT, CERT. GRANTED <d>, JURISDICTION NOTED <d>,
   AFFIRMED BY AN EQUALLY DIVIDED, IS HEREBY STAYED, CLERK'S LETTER, JUSTICE X TOOK NO PART, CONSOLIDATED FOR/WITH ... HOUR(S)/ORAL
   ARGUMENT; any case: "<n> hour(s) [is allotted] for oral argument"); the lower-case forms of these phrases appear in genuine QPs
   (16-373 "cert. dismissed as improvidently granted", 18-587 "affirmed, by an equally divided Court") and are not cut. Third check,
   NOTE_AUDIT and CAPS_TAIL (coverage file only, never change the feature): every kept body containing case-insensitive note vocabulary,
   or ending in all-caps line(s) (>= 12 letters, > 85% upper case) after its last mixed-case line, is listed; bodies read and found
   to be the petition's own text are in AUDIT_OK; any other hit is printed as UNREVIEWED in the file header, so a
   new note format surfaces automatically as raw/ grows (re-read, then extend TRAILER_RE/HARD_CUT or AUDIT_OK). Body empty because the
   first non-empty line after the header is already a note = failure "court_text_only": the PDF holds only the Court's own text (e.g.
   questions framed by the Court at grant: 21-588, 22-58, 24-656, pending 26-426 "Order of September 29, 2026 The parties are directed
   ..."); no petition QP -> missing (no row), consistent with "petition's question(s) only". Other bodies < 25 characters after
   normalization = failure "short_body" (e.g. image-only PDF).
3. Normalization: Unicode NFKC (ligatures such as U+FB02 -> "fl", no-break spaces); soft hyphens (U+00AD) joined/removed; form feeds
   -> newlines; a line-end hyphen between two lower-case letters is dropped only when the joined word is a SPLIT_RE keyword
   ("con-\\nflict" -> "conflict"), otherwise the hyphen is kept and the line break removed ("well-\\nsettled" -> "well-settled",
   "circuit-\\nsplit" -> "circuit-split"); then every whitespace run -> one space. qp_chars = len(normalized body).
4. SPLIT_RE: a court word within 0..120 characters of a split word, either order, case-insensitive, word-bounded (\\b), first
   (leftmost) match, with no sentence end in the gap. The spec's "no '.' in between" is its same-sentence proxy; here a sentence end is
   '.', '?' or '!', and before matching, abbreviation periods are masked (replaced by U+2024, same length, so the snippet is cut from
   the unmasked body): '.' after a single letter (U.S., D.C., F.3d, e.g., initials), after a listed legal abbreviation (ABBR: v., Cir.,
   Ct., No., Inc., Fed., App., state names ...), or followed by optional space + lower-case letter/digit/,;:)] . The literal reading
   (only '.' blocks, nothing masked) is LITERAL_RE, reported as a diagnostic in the coverage file, never written as a feature.
   Court words = spec list + inflections/synonyms: circuit(s) (incl. inter-circuit/intercircuit), court(s) of appeal(s), appeals
   court(s), state (high|highest|supreme|appellate) court(s), (state) court(s) of last resort, federal/lower [appellate|federal|state|
   district] courts, appellate courts, district courts (these plural only, as in the spec: singular "lower court" / "court below" is
   this case's own court), the hyphenated adjective lower-court(s) ("a lower-court conflict"), courts below (plural only).
   Synonyms added after reading non-matched QPs (text only, no outcome): "appeals courts" and "federal district courts" (15-1439),
   "lower-court conflict" (25-246). Not added (definition kept): named state courts ("the North Carolina Supreme Court", 15-1262).
   Split words: split(s|ting), conflict(s|ing|ed), divide(s|d)/dividing, division only before "of authority|among|amongst|between"
   (bare "Division" is mostly a name: Appellate Division, Antitrust Division), disagree(s|d|ing|ment|ments), diverge(s|d|nt|nce|nces)
   /diverging.
   Known false-positive classes are NOT excluded (pre-registered definition, no tuning on anything): preemption "conflicts with
   federal law", "conflicts with this Court's decisions" near a court word, "a divided panel of the ... Circuit", intra-case
   "disagreed with the district court", state "circuit court" (a trial court). FP_HINTS counts them in the coverage file only.
5. Coverage file: header warnings (point 6 leakage counts; NOTE_AUDIT / CAPS_TAIL unreviewed hits), counts, failures by reason (with dockets),
   HARD_CUT truncations, qp_chars distribution, qp_split rate overall / by docket-year prefix / by SCDB term (+ fetch status from
   raw/fetch_index.csv, argued counts), LITERAL_RE disagreements, FP_HINTS counts, NOTE_AUDIT hits, 15 matched snippets and 10 non-matched
   QP openings in sha1(docket) order (stable), and a hand-review section kept verbatim across re-runs (text from the MANUAL marker on).
6. LEAKAGE (spec-level, not fixable here; for the amendment owner): QP PDFs exist only for cases granted plenary review. Among SCDB
   dockets of terms <= 2025 with a fetch_index row, NO non-argued docket has a QP except a few granted-then-vacated-without-argument
   cases (08-1234, 10-72); every SCDB docket with qp_status "miss404" is non-argued (live counts in the coverage file header, e.g. at
   the 1,206-file snapshot: argued 1178/1185 with a QP PDF, the rest downloads in flight; non-argued 2/105). So qp_have, and qp_split
   with missing filled as 0, encode argued status, which rule 1 of the amendment treats as missing information, never a feature value
   (summary dispositions - GVRs, summary reversals - have no QP). This module follows spec B (row only when a QP exists); the consumer
   (stage2.py: qp_have in Zc, missing -> 0) must change before the amendment commit: drop qp_have from Zc and do not encode missing
   qp_split as 0 (impute the observed training mean, or fit and score the QP family only on granted cases, others falling back to
   K20). docket_have (parse_dockets.py) needs the same check.
"""
import csv, glob, hashlib, os, re, subprocess, sys, time, unicodedata
sys.dont_write_bytecode = True
import pandas as pd
ROOT = os.path.expanduser("~/scotus-predict-rerun"); HERE = os.path.dirname(os.path.abspath(__file__)); RAW = os.path.join(HERE, "raw")
QP = os.path.join(RAW, "qp"); FEAT = os.path.join(HERE, "features"); PDFTOTEXT = "/opt/homebrew/bin/pdftotext"
OUT, COV = os.path.join(FEAT, "qp_split.csv"), os.path.join(FEAT, "qp_coverage.txt"); MANUAL = "=== MANUAL REVIEW"
COURT_W = (r"(?:inter-?)?circuits?|courts?\s+of\s+appeals?|appeals\s+courts?|state\s+(?:high|highest|supreme|appellate)\s+courts?"
           r"|(?:state\s+)?courts?\s+of\s+last\s+resort|(?:federal|lower)\s+(?:appellate\s+|federal\s+|state\s+|district\s+)?courts"
           r"|(?:appellate|district)\s+courts|lower-courts?|courts\s+below")
SPLIT_W = (r"split(?:s|ting)?|conflict(?:s|ing|ed)?|divid(?:e|es|ed|ing)|division(?=\s+(?:of\s+authority|among|amongst|between))"
           r"|disagree(?:s|d|ing|ments?)?|diverg(?:e|es|ed|ing|ent|ences?)")
def _pair(stop):
    g = rf"[^{stop}]{{0,120}}?"; return re.compile(rf"\b(?:{COURT_W})\b{g}\b(?:{SPLIT_W})\b|\b(?:{SPLIT_W})\b{g}\b(?:{COURT_W})\b", re.I)
SPLIT_RE = _pair(".?!")     # the feature: searched on the abbreviation-masked body (docstring 4)
LITERAL_RE = _pair(".")     # diagnostic only: literal "no '.' in between", unmasked body
KW_RE = re.compile(r"(?:inter)?circuits?|courts?|appeals?|appellate|districts?|split(?:s|ting)?|conflict(?:s|ing|ed)?|divid(?:e|es|ed|ing)|division"
                   r"|disagree(?:s|d|ing|ments?)?|diverg(?:e|es|ed|ing|ent|ences?)", re.I)
ABBR = (r"v|vs|cf|al|Cir|Ct|App|Supp|Fed|Stat|Reg|Inc|Co|Corp|Ltd|No|Nos|Dist|Div|Mr|Ms|Mrs|Dr|St|Jr|Sr|Art|Amend|Const|Pet|Sup|Super"
        r"|Cal|Ill|Pa|Tex|Fla|Mich|Mass|Wash|Ariz|Colo|Conn|Ga|Ind|Kan|Ky|La|Md|Minn|Miss|Mo|Mont|Neb|Nev|Okla|Tenn|Va|Wis|Ala|Ark|Del|Vt")
ABBR_DOT = re.compile(rf"(?<![A-Za-z])(?:[A-Za-z]|{ABBR})\.|\.(?=\s?[a-z0-9,;:)\]])")
mask = lambda s: ABBR_DOT.sub(lambda m: m[0][:-1] + "․", s)
HDR_RE = re.compile(r"^\s*QUESTIONS?\s+PRESENTED\b\s*:?", re.I); META_RE = re.compile(r"^\s*(?:DECISION\s+BELOW|LOWER\s+COURT\s+CASE\s+NUMBER)", re.I)
MON = "JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER"; Mon = "|".join(m.capitalize() for m in MON.split("|"))
DAY, JN = "monday|tuesday|wednesday|thursday|friday|saturday|sunday", r"[a-z’'.\-]+"
TRAILER_RE = re.compile("|".join([   # see docstring 2: re.match on a stripped line, alone and joined with the next non-empty line
    # grant, limitation, consolidation, added questions (X(?i:...) = capital first letter, rest any case)
    r"CERT(?:IORARI|\.)?\s*GRANTED", r"(?:PROBABLE\s+)?JURISDICTION\s+(?:NOTED|POSTPONED)", r"FURTHER\s+CONSIDERATION\s+OF\s+THE\s+QUESTION",
    r"(?:CERT\.?\s+)?G(?i:ranted\s+limited)", r"L(?i:imited\s+to\s+(?:the\s+(?:following\s+)?)?questions?)", r"C(?i:onsolidated\s+(?:with|for)\b)",
    r"(?:THE\s+)?PETITIONS?\s+FOR\s+(?:(?:A\s+)?WRITS?\s+OF\s+)?CERTIORARI\s+(?:BEFORE\s+JUDGMENT\s+)?(?:IS\b|ARE\b|IN\b|GRANTED)", r"PETITIONS?\s+(?:IS\s+|ARE\s+)?GRANTED",
    r"T(?i:he\s+petitions?\s+for\s+(?:(?:a\s+)?writs?\s+of\s+)?certiorari\s+(?:before\s+judgment\s+)?(?:is|are)\s+(?:hereby\s+)?granted)",
    r"IN\s+ADDITION\s+TO\s+(?:THE\s+)?QUESTION", r"I(?i:n\s+addition\s+to\s+(?:the\s+)?questions?\b.{0,80}?\bparties\s+are\s+directed)",
    r"T(?i:he\s+parties\s+(?:and\s+the\s+solicitor\s+general\s+)?are\s+(?:directed|limited|invited))", r"THE\s+SOLICITOR\s+GENERAL\s+IS\s+INVITED",
    # dated orders, press releases, Clerk letters, date-prefixed notes ("6/26/2017: ...", "JUNE 27, 2019 CASE RESTORED ...", a date alone)
    rf"O(?i:rder\s+of\s+(?:(?:{DAY}),?\s+)?(?:{MON}|\d))", r"ORDER\s+OF\s+(?:[A-Za-z]+,?\s+)?\d", r"PRESS\s+RELEASE", r"C(?i:lerk.s\s+letter)",
    r"\d{1,2}/\d{1,2}/\d{2,4}\s*(?::|$)", rf"(?:{MON}|{Mon})\s+\d{{1,2}},\s*\d{{4}}(?:\s*:|\s*$|\s+(?=[A-Z][A-Z’']+\s+[A-Z]))",
    # recusals, any case; the recusal verb is required, so a QP sentence about a Justice's opinion cannot trigger it
    rf"(?i:(?:(?:the\s+)?chief\s+justice(?:\s+{JN})?|justices?\s+{JN})(?:\s+\[[^\]]{{1,30}}\])?(?:,?\s+(?:and\s+)?(?:(?:the\s+)?chief\s+justice(?:\s+{JN})?|justice\s+{JN})(?:\s+\[[^\]]{{1,30}}\])?)*\s+(?:took\s+no\s+part|takes?\s+no\s+part"
    r"|(?:is|are|has|have)\s+(?:no\s+longer\s+)?recused|recused|will\s+not\s+(?:take|participate)|did\s+not\s+(?:take|participate)|will\s+no\s+longer|(?:is|are)\s+not\s+participating))",
    # calendar / argument / briefing notes
    r"T(?i:h(?:is|e|ese)\s+cases?\s+(?:is|are|will|has|have)\s+(?:be\s+|been\s+|no\s+longer\s+)?(?:removed|restored|set|scheduled|held|rescheduled|postponed|continued|consolidated|argued|transferred))",
    r"T(?i:h(?:is|e|ese)\s+cases?\s+(?:is\s+|are\s+)?to\s+be\s+(?:argued|set|heard|scheduled|consolidated))",
    r"TO\s+BE\s+ARGUED\s+(?:IN\s+TANDEM|WITH|TOGETHER)", r"ARGUMENT\s+TO\s+BE\s+(?:RE)?SCHEDULED", r"EXPEDITED\s+BRIEFING", r"IN\s+KEEPING\s+WITH\s+PUBLIC\s+HEALTH", r"RESCHEDULED\s+FOR\s+ORAL",
    r"UPON\s+CONSIDERATION\s+OF\s+THE\s+MOTION", r"CONSIDERATION\s+OF\s+THE\s+(?:APPLICATIONS?|MOTIONS?)\b", r"THE\s+CLERK\s+IS\s+DIRECTED", r"(?i:a\s+total\s+of\s+\S+\s+(?:hours?|minutes))",
    # motions, applications, counsel: need a ruling verb / ESQ., so an all-caps IFP question about "THE MOTION FOR ..." is not cut
    r"(?:THE\s+)?MOTIONS?\s+(?:OF|FOR|TO|BY)\b.{0,240}?\b(?:IS|ARE)\s+(?:GRANTED|DENIED|DEFERRED)", r"(?:THE\s+)?MOTION\s+OF\s+(?:THE\s+)?(?:PETITIONER|RESPONDENT|APPELLANT|APPELLEE|UNITED)",
    r"THE\s+APPLICATIONS?\b.{0,200}?\b(?:PRESENTED\s+TO|REFERRED|(?:IS|ARE)\s+(?:GRANTED|DENIED))", r"ENLARGEMENT\s+OF\s+TIME",
    r"(?:THE\s+)?APPLICATIONS?\s+(?:\(\S+\)\s+)?(?:FOR\s+(?:AN?\s+)?(?:STAY|INJUNCTION|VACAT\w*)\s+)?(?:IS\s+|ARE\s+)?(?:GRANTED|DENIED|TREATED)", r"[A-Z][A-Z .,'’\-]+,\s+ESQ",
    r"T(?i:he\s+applications?\s+(?:\(\S+\)\s+)?(?:for|to)\s+(?:an?\s+)?(?:stay|injunction|vacat\w*)\b.{0,120}?\b(?:presented\s+to|referred\s+to|(?:is|are)\s+(?:granted|denied)))",
    r"(?i:.{0,120}?\b(?:treat|construe)\w*\s+the\s+(?:stay\s+)?applications?\s+as\s+(?:an?\s+)?petition|.{0,120}?\bapplications?\s+(?:is|are)\s+(?:also\s+)?treated\s+as\s+(?:an?\s+)?petition)",
    # dispositions (post-decision)
    r"DISMISSED\s+(?:AS\s+IMPROVIDENTLY|PURSUANT\s+TO|UNDER\s+RULE)", r"(?:THE\s+)?(?:WRIT\s+OF\s+CERTIORARI|PETITION|CASE|APPEAL)\s+(?:IS\s+)?DISMISSED",
    r"VACATED\s+AND\s+REMANDED", r"(?:THE\s+)?JUDGMENT\s+(?:IS\s+)?(?:VACATED|REVERSED|AFFIRMED)", r"AFFIRMED\s+BY\s+AN\s+EQUALLY"]))
HARD_CUT = re.compile("|".join([   # docstring 2: second guard, searched anywhere in the normalized body; case-sensitive except the last
    r"DISMISSED AS IMPROVIDENTLY GRANTED", r"PRESS RELEASE OF", r"RESTORED TO THE CALENDAR", r"FOR REARGUMENT", r"CERT\. GRANTED \d", r"JURISDICTION NOTED \d",
    r"PROBABLE JURISDICTION NOTED", r"AFFIRMED BY AN EQUALLY DIVIDED", r"IS HEREBY STAYED", r"CLERK.S LETTER", r"(?:(?:THE )?CHIEF )?JUSTICE[^.]{0,40}? TOOK NO PART",
    r"TREATED AS (?:AN? )?(?:PETITION|JURISDICTIONAL STATEMENT)", r"ENLARGEMENT OF TIME", r"ARGUED IN TANDEM", r"PARTIES ARE DIRECTED TO (?:BRIEF|FILE)",
    r"CONSOLIDATED (?:FOR|WITH) [^.?]{0,80}?(?:HOURS?|ORAL ARGUMENT)", r"(?i:\b(?:one|two|three|\d+)\s+hours?\s+(?:is\s+allotted\s+)?(?:for\s+|of\s+)?oral\s+argument)",
    # 2026-10-13 (main agent, after the full fetch): in-line trailer stamps of the OT2001-07 QP layout, case-insensitive
    r"(?i:\bcert(?:iorari|\.)?\s+granted\s*:?\s*\d)", r"(?i:\bjurisdiction\s+noted\s*:?\s*\d)", r"ORDER OF \d", r"(?i:https?://www\.\S*court\.gov/\S*argument)",
    r"(?i:\b(?:argued|decided|reargued)\s*:\s*\d)", r"(?i:\bexpedited\s+briefing\s+schedule)", r"PETITIONS? FOR REHEARING (?:IS|ARE) GRANTED"]))
NOTE_AUDIT = re.compile("|".join([   # docstring 2: third check, coverage file only
    r"\b(?:is|are)\s+(?:hereby\s+)?granted", r"press\s+release", r"reargument", r"took\s+no\s+part", r"take\s+part", r"recused", r"consolidated\s+(?:with|for)",
    r"restored\s+to\s+the\s+(?:argument\s+)?calendar", r"set\s+for\s+(?:oral\s+)?argument", rf"order\s+of\s+(?:{MON}|\d)", r"\bstayed\b", r"equally\s+divided",
    r"improvidently", r"oral\s+argument", r"\besq(?:uire)?\b", r"postpon", r"reschedul", r"expedited", r"clerk", r"directed\s+to\s+(?:file|brief)", r"allotted",
    r"invited\s+to", r"appointed\s+to", r"cert(?:iorari|\.)?\s+granted", r"limited\s+to\s+question", r"supplemental\s+(?:letter\s+)?brief", r"amicus\s+curiae",
    r"argument\s+session"]), re.I)
AUDIT_OK = {   # kept bodies whose NOTE_AUDIT / CAPS_TAIL hits were read (2026-10-12) and are the petition's own text; listed in qp_coverage.txt
    "10-63": "a court clerk returned mail (case facts)", "10-930": "proceedings stayed pending competency (the QP)",
    "09-1498": "Speedy Trial Act: motion causes a postponement (the QP)", "10-1150": "case history: writ dismissed as improvidently granted (Lab. Corp.)", "11-10189": "case history: federal proceeding stayed",
    "13-975": "expedited judicial review (statute)", "13-1174": "the QP itself: action consolidated with other suits", "14-723": "cites a Brief for the United States as Amicus Curiae",
    "15-1262": "asks the Court to order oral argument", "16-373": "case history: cert. granted / DIG in IndyMac", "17-7505": "case history: execution stayed, expedited motion",
    "17-9572": "allotted strikes", "18-587": "this Court affirmed by an equally divided Court (2016)", "18-588": "same as 18-587", "18-589": "same as 18-587",
    "19-161": "expedited removal", "20-1531": "this Court stayed that rule (2016)", "21-376": "en banc CA5 equally divided", "21-377": "en banc CA5 equally divided",
    "21-401": "Servotronics removed from the argument calendar (petition's own account)", "21-432": "an equally divided Federal Circuit",
    "21-463": "clerks and judges of state courts", "21-518": "prior case dismissed before oral argument", "22-674": "postponement (statutory text)",
    "22-1219": "Loper Bright cert. granted (petition footnote)", "22-7386": "Transcript of Oral Argument citation", "23-719": "state supreme court stayed its decision",
    "24-110": "QP 5: unnecessarily expediting the proceedings", "24-275": "reopening is granted (statutory question)"}
FP_HINTS = {"preemption: conflict(s) with federal/state law": r"conflict\w*\s+with\s+(?:the\s+)?(?:federal|state)\s+(?:law|statute|regulation)|preempt",
            "conflict with this Court / a named case": r"conflict\w*\s+with\s+(?:\S+\s+){0,6}?(?:this|the\s+Supreme)\s+Court|conflict\w*\s+(?:with|between)\s+(?:\S+\s+){0,4}?v\.\s",
            "intra-court division (divided panel / en banc / opinion)": r"\b(?:a|the)\s+(?:sharply\s+|closely\s+)?divided\s+(?:\S+\s+){0,3}?(?:panel|en\s+banc|court\b|circuit\b|opinion|decision|vote)"
                r"|en\s+banc\s+(?:\S+\s+){0,3}?(?:circuit|court)\s+(?:was\s+|is\s+)?(?:sharply\s+|closely\s+)?divided|(?:panel|majority|dissent)\b[^.]{0,60}\bdisagree",
            "disagreed with district/trial court": r"disagree\w*\s+with\s+(?:the\s+)?(?:district|trial|bankruptcy|magistrate)",
            "state 'circuit court' (singular; trial court)": r"\bcircuit\s+court\b(?!s)",
            "conflict of interest/laws, armed conflict": r"conflicts?[\s-]+of[\s-]+(?:interest|laws?)|armed\s+conflict",
            "split decision/verdict/sentence": r"split\s+(?:decision|verdict|sentence)"}
DOCKET_RE = re.compile(r"\d{2}-\d{1,5}"); yr4 = lambda d: (1900 if int(d[:2]) >= 50 else 2000) + int(d[:2])
dkey = lambda d: (yr4(d), int(d.split("-")[1]))
def extract(p):
    with open(p, "rb") as f:
        if f.read(4) != b"%PDF": return None, "not_pdf"
    try: r = subprocess.run([PDFTOTEXT, "-layout", "-enc", "UTF-8", p, "-"], capture_output=True, timeout=30)
    except subprocess.TimeoutExpired: return None, "timeout"
    if r.returncode != 0: return None, f"pdftotext_exit{r.returncode}"
    t = unicodedata.normalize("NFKC", r.stdout.decode("utf-8", "replace"))
    t = re.sub(r"­[ \t]*\n[ \t]*", "", t).replace("­", "").replace("\f", "\n")
    return (t, "ok") if t.strip() else (None, "empty_text")
caps = lambda l: (lambda a: None if len(a) < 12 else sum(c.isupper() for c in a) / len(a) > 0.85)([c for c in l if c.isalpha()])   # None: < 12 letters
def body(t):
    L = t.splitlines(); h = next((i for i, l in enumerate(L) if HDR_RE.match(l)), None); fb = h is None
    if fb: h = max([i for i, l in enumerate(L[:8]) if META_RE.match(l)], default=0); first = ""
    else: first = HDR_RE.sub("", L[h], count=1)
    LL = [l.strip() for l in [first] + L[h + 1:]]; nz = [i for i, l in enumerate(LL) if l]
    nxt = {a: LL[b] for a, b in zip(nz, nz[1:])}
    e = next((i for i in nz if TRAILER_RE.match(LL[i]) or TRAILER_RE.match(LL[i] + " " + nxt.get(i, ""))), len(LL))
    raw = re.sub(r"(\w+)-[ \t]*\n[ \t]*(\w+)", lambda m: m[1] + m[2] if (m[1][-1].islower() and m[2][0].islower() and KW_RE.fullmatch(m[1] + m[2]))
                 else m[1] + "-" + m[2], "\n".join(LL[:e]))
    b = re.sub(r"\s+", " ", raw).strip(); k = HARD_CUT.search(b)
    B = [LL[i] for i in nz if i < e]; mx = [i for i, l in enumerate(B) if caps(l) is False]   # CAPS_TAIL: all-caps line(s) after the last mixed-case line
    ct = " | ".join(B[mx[-1] + 1:]) if mx and any(caps(l) for l in B[mx[-1] + 1:]) else ""
    return (b[:k.start()].strip() if k else b), fb, e < len(LL), k is not None, bool(nz) and e == nz[0], ct
T0 = time.time(); os.makedirs(FEAT, exist_ok=True)
files = sorted(glob.glob(os.path.join(QP, "*.pdf"))); rows, fail, ex = [], {}, {}
for p in files:
    d = os.path.basename(p)[:-4]
    if not DOCKET_RE.fullmatch(d): fail[d] = "bad_name"; continue
    t, st = extract(p)
    if t is None: fail[d] = st; continue
    b, fb, trl, hc, c0, ct = body(t)
    if len(b) < 25: fail[d] = "court_text_only" if c0 else "short_body"; continue
    m = SPLIT_RE.search(mask(b))
    rows.append({"docket": d, "qp_have": 1, "qp_split": int(m is not None), "qp_chars": len(b), "qp_match": b[m.start():m.end()][:200] if m else ""})
    ex[d] = {"b": b, "fb": fb, "trl": trl, "hc": hc, "ct": ct, "lit": LITERAL_RE.search(b) is not None, "s": m.start() if m else None, "e": m.end() if m else None}
F = pd.DataFrame(rows, columns=["docket", "qp_have", "qp_split", "qp_chars", "qp_match"])
F = F.iloc[sorted(range(len(F)), key=lambda i: dkey(F.docket.iloc[i]))].reset_index(drop=True); F.to_csv(OUT, index=False)
# ---- coverage (feature distribution and parse counts only; no outcome field is read)
rd = lambda p, **k: pd.read_csv(p, encoding="ISO-8859-1", low_memory=False, **k)
S = pd.concat([rd(os.path.join(ROOT, "data", "SCDB_2026_01_justiceCentered_Docket.csv"), usecols=["term", "docket", "dateArgument"]),
               rd(os.path.join(ROOT, "pending_inputs", "pending_cases_scdb_rows.csv"), usecols=["term", "docket", "dateArgument"])]).dropna(subset=["term", "docket"])
S["docket"] = S.docket.astype(str).str.strip(); S["argued"] = S.dateArgument.notna()   # argued status only (not an outcome): leakage diagnostic, docstring 6
S = S[(S.term >= 2000) & S.docket.str.fullmatch(r"\d{2}-\d{1,5}")].drop_duplicates(["term", "docket"])
fidx = {}
try:
    with open(os.path.join(RAW, "fetch_index.csv"), newline="") as f: fidx = {r["docket"]: r.get("qp_status") or "" for r in csv.DictReader(f) if r.get("docket")}
except Exception as err: print("fetch_index unreadable:", err)
FI = F.set_index("docket"); S["fetched"] = S.docket.isin(list(fidx)); S["qp_online"] = S.docket.map(lambda d: fidx.get(d) == "ok")
S["parsed"] = S.docket.isin(FI.index); S["split"] = S.docket.map(FI.qp_split)
q = lambda x: f"{x:.3f}" if pd.notna(x) else "  -  "
pdfs = {os.path.basename(p)[:-4] for p in files}; S["pdf"] = S.docket.isin(pdfs)
A = S[(S.term <= 2025) & S.fetched]; xt = lambda a, c: f"{int(A[A.argued == a][c].sum())}/{int((A.argued == a).sum())}"
AH = [(d, k) for d, v in ex.items() for k in NOTE_AUDIT.finditer(v["b"])]; CT = sorted((d for d, v in ex.items() if v["ct"]), key=dkey)
AU = sorted({d for d, _ in AH if d not in AUDIT_OK} | {d for d in CT if d not in AUDIT_OK}, key=dkey)
o = [f"qp_coverage (parse_qp.py) run {time.strftime('%Y-%m-%d %H:%M:%S')}  runtime {time.time()-T0:.0f}s  raw/qp snapshot (fetch still running)",
     "", "!!! LEAKAGE WARNING for the amendment owner (docstring 6; NOT fixable in this module, whose outputs follow spec B):",
     "    a QP PDF exists only for cases granted plenary review, so qp_have (and qp_split filled 0 when missing) encodes argued status",
     "    almost exactly (exceptions: granted, then decided without argument, e.g. 08-1234, 10-72), which rule 1 says is missing",
     "    information, never a feature value (summary dispositions have no QP). SCDB terms <= 2025, dockets",
     f"    with a fetch_index row (dateArgument read for this count only; no outcome field): argued -> QP PDF {xt(True, 'pdf')}, QP row {xt(True, 'parsed')};",
     f"    not argued -> QP PDF {xt(False, 'pdf')}, QP row {xt(False, 'parsed')}. Do not put qp_have in Zc; do not encode missing qp_split as 0",
     "    (impute the training mean, or fit/score the QP family on granted cases only). Same check is needed for docket_have (parse_dockets.py).",
     f"!!! NOTE_AUDIT: {len({d for d, _ in AH})} bodies contain Court/Clerk-note vocabulary, CAPS_TAIL: {len(CT)} bodies end in all-caps line(s) after"
     f" mixed-case text; UNREVIEWED (not in AUDIT_OK): {len(AU)}  {' '.join(AU)}",
     "", f"PDF files present: {len(files)}   parsed (rows in qp_split.csv): {len(F)}   extraction failures / no petition QP text: {len(fail)}",
     "failures by reason: " + (", ".join(f"{k}={v}" for k, v in pd.Series(fail).value_counts().items()) if fail else "none")
     + "".join(f"\n  {r}: " + " ".join(sorted((d for d in fail if fail[d] == r), key=dkey if r != "bad_name" else str)) for r in sorted(set(fail.values()))),
     "  (court_text_only = the first line after the QP header is a Court/Clerk note, i.e. the PDF holds only the Court's own text, e.g. questions",
     "   framed by the Court at grant: no petition QP -> missing, docstring 2)",
     f"fetch_index rows: {len(fidx)}   qp_status ok: {sum(v == 'ok' for v in fidx.values())}   other (no QP online): {sum(v != 'ok' for v in fidx.values())}",
     f"header_fallback (no 'QUESTION(S) PRESENTED' line): {sum(v['fb'] for v in ex.values())}   no annotation trailer found: {sum(not v['trl'] for v in ex.values())}"
     + "  " + " ".join(d for d, v in ex.items() if v["fb"] or not v["trl"]),
     f"HARD_CUT truncations (note phrase inside a line, after the line cut): {sum(v['hc'] for v in ex.values())}  " + " ".join(d for d, v in ex.items() if v["hc"]),
     "qp_chars: " + (" ".join(f"{k}={F.qp_chars.quantile(v):.0f}" for k, v in [("min", 0), ("p10", .1), ("median", .5), ("p90", .9), ("max", 1)]) if len(F) else "n/a"),
     f"qp_split overall: {F.qp_split.sum()}/{len(F)} = {q(F.qp_split.mean())}", "", "by docket-year prefix (filing year): prefix n_parsed n_split rate"]
for yy, g in F.groupby(F.docket.map(lambda d: yr4(d)), sort=True): o.append(f"  {str(yy)[2:]} ({yy})  {len(g):5d} {g.qp_split.sum():5d}  {q(g.qp_split.mean())}")
o += ["", "by SCDB term (dockets YY-NNNN, terms >= 2000 incl. pending 2026): term n_dockets n_fetched n_qp_online n_parsed n_split split_rate parsed/dockets | n_argued(dateArgument) n_argued_fetched n_parsed_not_argued"]
for tm, g in S.groupby("term"):
    o.append(f"  {int(tm)}  {len(g):5d} {g.fetched.sum():5d} {g.qp_online.sum():5d} {g.parsed.sum():5d} {int(g.split.sum()):5d}  {q(g.split.mean())}  {q(g.parsed.mean())} | {g.argued.sum():5d} {(g.argued & g.fetched).sum():5d} {(g.parsed & ~g.argued).sum():5d}")
o.append(f"  parsed dockets not in SCDB/pending (term >= 2000): {len(set(F.docket) - set(S.docket))}")
dis = [(d, int(FI.qp_split[d]), int(v["lit"])) for d, v in ex.items() if int(FI.qp_split[d]) != int(v["lit"])]
o += ["", f"LITERAL_RE diagnostic (only '.' blocks, no abbreviation masking): disagrees with SPLIT_RE on {len(dis)} dockets"]
o += [f"  {d}: SPLIT_RE={a} LITERAL_RE={b}" for d, a, b in dis]
M = F[F.qp_split == 1]; ctx = {d: ex[d]["b"][max(0, ex[d]["s"] - 60):ex[d]["e"] + 80] for d in M.docket}
o += ["", "FP_HINTS among matches (diagnostic regexes on snippet +-60/80 chars; NOT used in the feature): class n dockets"]
for k, r in FP_HINTS.items():
    hit = [d for d in M.docket if re.search(r, ctx[d], re.I)]; o.append(f"  {k}: {len(hit)}  {' '.join(hit)}")
hs = lambda d: hashlib.sha1(d.encode()).hexdigest()
o += ["", f"NOTE_AUDIT hits in kept bodies (case-insensitive Court/Clerk-note vocabulary; a hit outside AUDIT_OK may be a leaked note: extend TRAILER_RE/HARD_CUT): {len(AH)}"]
o += [f"  {d} [{'ok: ' + AUDIT_OK[d] if d in AUDIT_OK else 'UNREVIEWED'}]: ...{ex[d]['b'][max(0, k.start()-60):k.end()+50]}..." for d, k in sorted(AH, key=lambda x: dkey(x[0]))]
o += [f"  CAPS_TAIL {d} [{'ok: ' + AUDIT_OK[d] if d in AUDIT_OK else 'UNREVIEWED'}]: {ex[d]['ct'][:200]}" for d in CT]
o += [f"  AUDIT_OK dockets without a hit now (stale entries): {' '.join(sorted(set(AUDIT_OK) - {d for d, _ in AH} - set(CT))) or 'none'}"]
o += ["", "15 matched snippets (sha1(docket) order) [context: 60 chars before / 80 after, match in <<>>]"]
for d in sorted(M.docket, key=hs)[:15]:
    b, s, e = ex[d]["b"], ex[d]["s"], ex[d]["e"]
    fl = [k for k, r in FP_HINTS.items() if re.search(r, ctx[d], re.I)]
    o.append(f"  {d}: ...{b[max(0, s-60):s]}<<{b[s:e]}>>{b[e:e+80]}...  FP_HINT: {'; '.join(fl) if fl else '-'}")
o += ["", "10 non-matched QP openings (sha1(docket) order; first 300 chars of the body)"]
o += [f"  {d}: {ex[d]['b'][:300]}" for d in sorted(F[F.qp_split == 0].docket, key=hs)[:10]]
keep = ""
if os.path.exists(COV):
    old = open(COV, encoding="utf-8").read(); keep = old[old.index(MANUAL):] if MANUAL in old else ""
o += ["", keep.rstrip() if keep else f"{MANUAL} (hand-written; kept verbatim on re-run)\n  (none yet)"]
open(COV, "w", encoding="utf-8").write("\n".join(o) + "\n")
print(f"{len(files)} files, {len(F)} parsed, {len(fail)} failures, qp_split {F.qp_split.sum()}/{len(F)}; wrote {OUT} and {COV} in {time.time()-T0:.0f}s", flush=True)

#!/usr/bin/env python3
"""
greek_audit.py — mechanical Greek-quote verification for Reframing Reality.

Extracts every Greek-script run from a chapter markdown file and verifies it
against the local corpora — deterministic string comparison, no inference.
Built after Ch. 24's audit found a fabricated πρώτως (Acts 11:26) and two
critical-text readings where the Byzantine textform was required.

What it checks:
  * Greek quotes (3+ words) — tries EVERY scripture reference within the
    context window, nearest first. NT refs → greek_lookup.py verse-byz
    (ranges expanded verse by verse); LXX refs → substring search in the
    lxx_septuagint TEI-XML. First verbatim match wins (MATCH); no match
    against any nearby ref → MISMATCH with the closest ref's actual text.
  * Quotes with no reference nearby → NO-REF (Philo/classical? verify manually).
  * Single words and 2-word terms of art (ἡ ὁδός) → advisory LSJ lookup only.
    LSJ indexes lemmas; inflected forms miss legitimately — a miss is a
    prompt to check, never proof of error.

Exit code 1 if any MISMATCH/LOOKUP-FAIL/NO-CORPUS rows exist.

Usage:
    python3 greek_audit.py "/path/to/Chapter 24 - The Phantom Cell.md"
    python3 greek_audit.py chapter.md --context 300
"""

import re
import sys
import json
import argparse
import bisect
import subprocess
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOOKUP = HERE / "greek_lookup.py"
LXX_DIR = HERE / "lxx_septuagint"

GREEK_WORD = r"[Ͱ-Ͽἀ-῿̀-͢]+"
GREEK_RUN = re.compile(rf"{GREEK_WORD}(?:[\s··,.;·’᾽ʼ'’]+{GREEK_WORD})*")

NT_BOOKS = (
    "Matt|Matthew|Mark|Luke|John|Acts|Rom|Romans|1 ?Cor|2 ?Cor|Gal|Galatians|"
    "Eph|Ephesians|Phil|Philippians|Col|Colossians|1 ?Thess|2 ?Thess|1 ?Tim|"
    "2 ?Tim|Titus|Phlm|Philemon|Heb|Hebrews|Jas|James|1 ?Pet|2 ?Pet|1 ?John|"
    "2 ?John|3 ?John|Jude|Rev|Revelation"
)
LXX_BOOKS = (
    "Gen|Genesis|Exod|Exodus|Lev|Leviticus|Num|Numbers|Deut|Deuteronomy|"
    "Josh|Joshua|Judg|Judges|Ruth|Ezra|Neh|Esth|Job|Ps|Psalms?|Prov|Proverbs|"
    "Eccl|Ecclesiastes|Song|Isa|Isaiah|Jer|Jeremiah|Lam|Ezek|Ezekiel|Dan|"
    "Daniel|Hos|Hosea|Joel|Amos|Obad|Jonah|Mic|Micah|Nah|Nahum|Hab|Zeph|Hag|"
    "Zech|Zechariah|Mal|Malachi|Wis|Wisdom|Sir|Sirach|Tob|Tobit|Jdt|Judith|"
    "1 ?Macc|2 ?Macc"
)
REF_RE = re.compile(
    rf"\b((?:{NT_BOOKS}|{LXX_BOOKS}))\.?\s+(\d+)[:.](\d+)(?:[-–](\d+))?"
)
NT_SET = {b.replace(" ?", " ").lower() for b in NT_BOOKS.split("|")}

# English book → LXX manifest title (accent-stripped, lowercased prefix).
LXX_TITLE = {
    "gen": "γενεσις", "genesis": "γενεσις",
    "exod": "εξοδος", "exodus": "εξοδος",
    "lev": "λευιτικον", "leviticus": "λευιτικον",
    "num": "αριθμοι", "numbers": "αριθμοι",
    "deut": "δευτερονομιον", "deuteronomy": "δευτερονομιον",
    "josh": "ιησους", "joshua": "ιησους",
    "judg": "κριται", "judges": "κριται",
    "ruth": "ρουθ",
    "ps": "ψαλμοι", "psalm": "ψαλμοι", "psalms": "ψαλμοι",
    "prov": "παροιμιαι", "proverbs": "παροιμιαι",
    "eccl": "εκκλησιαστης", "ecclesiastes": "εκκλησιαστης",
    "song": "αισμα",
    "job": "ιωβ",
    "isa": "ησαιας", "isaiah": "ησαιας",
    "jer": "ιερεμιας", "jeremiah": "ιερεμιας",
    "lam": "θρηνοι",
    "ezek": "ιεζεκιηλ", "ezekiel": "ιεζεκιηλ",
    "dan": "δανιηλ", "daniel": "δανιηλ",
    "hos": "ωσηε", "hosea": "ωσηε",
    "joel": "ιωηλ", "amos": "αμως",
    "mic": "μιχαιας", "micah": "μιχαιας",
    "nah": "ναουμ", "hab": "αμβακουμ", "zeph": "σοφονιας",
    "hag": "αγγαιος", "zech": "ζαχαριας", "zechariah": "ζαχαριας",
    "mal": "μαλαχιας", "malachi": "μαλαχιας",
    "wis": "σοφια", "wisdom": "σοφια",
    "sir": "σειραχ", "sirach": "σειραχ",
    "tob": "τωβιτ", "tobit": "τωβιτ",
    "jdt": "ιουδιθ", "judith": "ιουδιθ",
}


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c)).lower()


def norm(s):
    """Comparison normal form: NFC (folds oxia→tonos), unify elision marks,
    strip punctuation, collapse whitespace. Diacritics are PRESERVED."""
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"[’᾽ʼ']", "’", s)
    s = re.sub(r"[···,.;··!?()\[\]«»\"“”—–¶-]", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def run_lookup(*args):
    r = subprocess.run([sys.executable, str(LOOKUP), *args],
                       capture_output=True, text=True, timeout=60)
    return r.stdout.strip()


_verse_cache = {}
def byz_verse(book, ch, v):
    key = f"{book} {ch}:{v}"
    if key not in _verse_cache:
        out = run_lookup("verse-byz", key)
        if not out or "not found" in out.lower():
            _verse_cache[key] = (None, "")
        else:
            lines = out.splitlines()
            text = re.sub(r"^\S+\s+\[Byz\]\s*", "", lines[0])
            div = "; ".join(l.strip(" -") for l in lines
                            if l.strip().startswith("-"))
            _verse_cache[key] = (text, div)
    return _verse_cache[key]


def check_nt(quote, book, ch, v1, v2):
    """Compare against the cited verse range, widened ±1 verse (citations are
    often off by one). Returns (True, note) MATCH, ("precision", note) for
    right-text-imprecise-citation, or (False, combined_text) MISMATCH."""
    lo, hi = max(1, int(v1) - 1), int(v2 or v1) + 1
    cited = set(range(int(v1), int(v2 or v1) + 1))
    texts, divs = {}, []
    for v in range(lo, hi + 1):
        text, div = byz_verse(book, ch, v)
        if text is not None:
            texts[v] = text
            if div and v in cited:
                divs.append(div)
    if not any(v in texts for v in cited):
        return None, f"lookup failed for {book} {ch}:{v1}"
    nq = norm(quote)
    # 1. Exact match within the cited range
    cited_text = " ".join(texts[v] for v in sorted(cited) if v in texts)
    if nq in norm(cited_text):
        note = f"Byz≠critical in range: {'; '.join(divs)}" if divs else ""
        return True, note
    # 2. Exact match within the widened range → citation precision, not misquote
    wide_text = " ".join(texts[v] for v in sorted(texts))
    if nq in norm(wide_text):
        hit = [v for v in sorted(texts) if nq in norm(texts[v]) or nq in norm(
            " ".join(texts[u] for u in sorted(texts) if abs(u - v) <= 1))]
        return "precision", (f"text is verbatim Byz but sits in {book} {ch}:"
                             f"{hit[0] if hit else '?'} — cited range is {v1}"
                             + (f"-{v2}" if v2 else ""))
    # 3. Fragment fallback: composite/elided quotes — every clause of the
    #    quote found (non-contiguously) within the widened range.
    frags = [f for f in re.split(r"[··;,]", quote) if len(norm(f)) >= 8]
    if len(frags) >= 2 and all(norm(f) in norm(wide_text) for f in frags):
        return "precision", ("all clauses verbatim in Byz "
                             f"{book} {ch}:{lo}-{hi} but non-contiguous "
                             "(composite or elided quote — check ellipsis marks)")
    return False, cited_text


_lxx_manifest = None
def lxx_file_for(book):
    global _lxx_manifest
    if _lxx_manifest is None:
        _lxx_manifest = json.loads((LXX_DIR / "manifest.json").read_text())
    want = LXX_TITLE.get(book.lower().rstrip("."))
    if not want:
        return None
    for w in _lxx_manifest.get("works", []):
        if strip_accents(w.get("title", "")).startswith(want):
            p = LXX_DIR / w["file"]
            if p.exists():
                return p
    return None


_lxx_text_cache = {}
def check_lxx(quote, book):
    f = lxx_file_for(book)
    if f is None:
        return None, f"no LXX file matched '{book}'"
    if f not in _lxx_text_cache:
        xml = f.read_text(encoding="utf-8", errors="replace")
        _lxx_text_cache[f] = norm(re.sub(r"<[^>]+>", " ", xml))
    if norm(quote) in _lxx_text_cache[f]:
        return True, f"found in {f.name}"
    return False, f"not verbatim in {f.name}"


def check_word(word):
    out = run_lookup("lsj", word)
    if out.startswith("No LSJ entry"):
        return "LSJ-MISS", "no lemma entry (inflected forms miss legitimately — advisory)"
    return "LSJ-OK", ""


def main():
    ap = argparse.ArgumentParser(description="Mechanical Greek-quote audit")
    ap.add_argument("chapter", help="Path to the chapter .md file")
    ap.add_argument("--context", type=int, default=250,
                    help="Chars around a quote to search for references")
    args = ap.parse_args()

    text = Path(args.chapter).read_text(encoding="utf-8")
    newlines = [m.start() for m in re.finditer(r"\n", text)]

    def line_of(pos):
        return bisect.bisect_right(newlines, pos) + 1

    rows = []
    for m in GREEK_RUN.finditer(text):
        quote = m.group(0)
        words = re.findall(GREEK_WORD, quote)
        loc = f"L{line_of(m.start())}"

        # 1-2 words: advisory term check, not a quote.
        if len(words) <= 2:
            statuses = [check_word(w) for w in words]
            if all(s == "LSJ-OK" for s, _ in statuses):
                rows.append((loc, quote, "LSJ-OK", ""))
            else:
                rows.append((loc, quote, "LSJ-MISS",
                             "no lemma entry (inflected forms miss legitimately — advisory)"))
            continue

        # Collect every ref in the window, nearest first.
        w_start = max(0, m.start() - args.context)
        window = text[w_start: m.end() + args.context]
        refs = []
        for rm in REF_RE.finditer(window):
            dist = abs((w_start + rm.start()) - m.start())
            refs.append((dist, rm.group(1), rm.group(2), rm.group(3), rm.group(4)))
        refs.sort(key=lambda r: r[0])

        if not refs:
            rows.append((loc, quote, "NO-REF",
                         "no scripture ref within window — verify manually (Philo/classical?)"))
            continue

        matched = False
        precision_row = None
        closest_note = ""
        tried = []
        for _, book, ch, v1, v2 in refs:
            ref_str = f"{book} {ch}:{v1}" + (f"-{v2}" if v2 else "")
            tried.append(ref_str)
            if book.replace(".", "").lower() in NT_SET:
                ok, note = check_nt(quote, book, ch, v1, v2)
            else:
                ok, note = check_lxx(quote, book)
            if ok is True:
                rows.append((loc, quote, "MATCH",
                             f"[{ref_str}] {note}".strip()))
                matched = True
                break
            if ok == "precision" and precision_row is None:
                precision_row = (loc, quote, "CITATION-PRECISION",
                                 f"[{ref_str}] {note}")
            if not closest_note and ok is False:
                closest_note = f"closest ref {ref_str} reads: {note[:220]}"
        if not matched:
            if precision_row:
                rows.append(precision_row)
            else:
                rows.append((loc, quote, "MISMATCH",
                             f"no verbatim match vs nearby refs ({', '.join(tried)}); {closest_note}"))

    problems = [r for r in rows if r[2] == "MISMATCH"]
    print(f"# Greek audit: {Path(args.chapter).name}")
    print(f"{len(rows)} Greek runs; "
          f"{sum(1 for r in rows if r[2] == 'MATCH')} MATCH, "
          f"{len(problems)} MISMATCH, "
          f"{sum(1 for r in rows if r[2] == 'CITATION-PRECISION')} citation-precision, "
          f"{sum(1 for r in rows if r[2] == 'NO-REF')} no-ref, "
          f"{sum(1 for r in rows if r[2] == 'LSJ-MISS')} advisory LSJ misses\n")
    print("| Line | Greek | Status | Note |")
    print("|---|---|---|---|")
    for loc, quote, status, note in rows:
        display = quote if len(quote) <= 60 else quote[:57] + "…"
        flag = "**" if status == "MISMATCH" else ""
        print(f"| {loc} | {display} | {flag}{status}{flag} | {note} |")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

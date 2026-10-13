#!/usr/bin/env python3
"""check-footnote-length.sh — report footnotes over the word cap, once each.

    tools/check-footnote-length.sh              # every chapter and appendix
    tools/check-footnote-length.sh 10 26        # named chapters
    tools/check-footnote-length.sh --all        # include notes already ruled on
    tools/check-footnote-length.sh --cap 300    # a different cap for this run

WHY THIS EXISTS
    The original author set a word cap on footnotes while reading two long
    chapters. Several notes exceeded it and no ruling was ever recorded, so the
    same notes would have been listed again at every close-out.

    THE CAP IS 150 WORDS. The author: "I want footnotes to be footnotes, not a
    monograph." The standard: a note holds who said it and where, the words the
    body relies on, and one clause where a reader following the citation would
    otherwise land in the wrong place or read the wrong words. Under it, one
    chapter's notes went from about 10,000 words to about 5,000.

    NAVIGATION, NOT EVALUATION. A note says WHERE the thing is. It never says
    how much to believe it, and it never asserts the source's authority or
    access: a badge is not evidence and enters the book nowhere. The author:
    "The question isn't whether or not something is true, verified, or from a
    so-called authoritative source; the question is: a) who said it and b)
    what meaning they are conveying."

    LENGTH IS THE WEAKEST SIGNAL IN THE SET, AND THIS SCRIPT ONLY MEASURES IT.
    Before trimming anything this script reports, say what job the NOTE'S
    PARAGRAPH does in the chapter's argument. If the source does not bear on
    that job, the fault is placement and no trim fixes it. In the original
    book, one long note had been answering a question the chapter never asks;
    it came out whole rather than shorter.

    This script and check-footnotes.sh both read the cap. They are not
    duplicates: check-footnotes.sh reports structural classes and knows nothing
    about rulings; this one reports length ALONE and suppresses notes the
    author has already ruled on, which is why it is the one a lock gate calls.
    Change the cap in ONE place, DEFAULT_CAP below, and let check-footnotes.sh
    take it from the FOOTNOTE_CAP environment variable.

    The author: "If it has been checked and I approved it, I don't want to get
    asked about it again, so you need to be logging these checks, and checking
    the logs." So this reports a long note ONCE. The ruling goes in
    Fact Check/Footnote Length Rulings.md and the note stops being raised.

THE CAP IS A TRIGGER, NOT A VERDICT
    The author: "a word-count pass is not a licence to cut evidence." Some long
    notes are long because they hold a source chain that defends a corrected
    claim. Length is a reason to LOOK, never a reason to cut. This script
    decides nothing. It hands over a note and a number, and the reading happens
    with the note open. The lock gate refuses a lock while a note is over the
    cap and unruled; a ruling (keep it) or a trim clears it.

WHEN A RULING STOPS APPLYING
    The fingerprint covers the note's whole text. Edit the note and the ruling
    lapses, deliberately: a note that grew by 200 words after approval is not
    the note that was approved. See rulings.py.

EXIT CODES
    0  always. The lock gate reads the report, not the exit code.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rulings  # noqa: E402

RULINGS_FILE = "Footnote Length Rulings.md"
DEFAULT_CAP = 150

FOOTNOTE_DEF = re.compile(r"^\[\^([^\]]+)\]:\s*(.*)$")
# The block-id comment `<!-- b:xxxxxx -->` renders to nothing, but a split()
# counted it as two words, so every note measured two words heavier than it
# is. In the original book five notes were "over the cap" only by that comment.
BID = re.compile(r"<!--\s*b:[a-z0-9]{6}\s*-->")


def over_cap(text, cap=DEFAULT_CAP, ruled=frozenset()):
    """([(line, slug, words, fingerprint)], suppressed) for notes over `cap`."""
    over, suppressed = [], 0
    for n, line in enumerate(text.split("\n"), 1):
        m = FOOTNOTE_DEF.match(line)
        if not m:
            continue
        # Count the note as a reader meets it: the citation text, without the
        # slug or the block id. Other comments and code spans inside a note are
        # still words on the page, so they are NOT stripped here.
        words = len(BID.sub("", m.group(2)).split())
        if words <= cap:
            continue
        fp = rulings.fingerprint(line)
        if fp in ruled:
            suppressed += 1
            continue
        over.append((n, m.group(1), words, fp))
    return over, suppressed


def main():
    argv = sys.argv[1:]
    show_ruled = "--all" in argv
    cap = DEFAULT_CAP
    if "--cap" in argv:
        i = argv.index("--cap")
        try:
            cap = int(argv[i + 1])
        except (IndexError, ValueError):
            sys.exit("--cap needs a number, e.g. --cap 300")
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]

    ruled = set() if show_ruled else rulings.load(RULINGS_FILE)
    files = rulings.chapter_files(args)
    if not files:
        sys.exit("No matching chapter or appendix files.")

    print(f"Footnote length — cap {cap} words")
    print("The cap is a trigger to read the note, not a verdict on it.\n")

    total = suppressed = 0
    for path in files:
        label = rulings.label_for(path)
        over, supp = over_cap(path.read_text(encoding="utf-8"), cap, ruled)
        suppressed += supp
        if not over:
            continue
        total += len(over)
        print(f"--- {label}: {len(over)} note(s) over {cap}")
        for n, slug, words, fp in sorted(over, key=lambda r: -r[2]):
            print(f"    {label}/L{n:<4} [^{slug}]".ljust(46)
                  + f"{words:>5} words   {fp}")
        print()

    tail = f" {suppressed} already ruled and hidden — pass --all to see them." if suppressed else ""
    print(f"{total} unruled note(s) over the cap across {len(files)} file(s).{tail}")
    print("An unruled note over the cap blocks the chapter's lock until trimmed or ruled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

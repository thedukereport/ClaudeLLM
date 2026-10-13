#!/usr/bin/env python3
"""check-epistemics.sh — flag borrowed authority, pre-emptive retreat and their kin, for reading.

    tools/check-epistemics.sh              # every chapter and appendix
    tools/check-epistemics.sh 10 25        # named chapters
    tools/check-epistemics.sh --counts     # one line per file
    tools/check-epistemics.sh --all        # include lines already ruled on

WHY THIS EXISTS
    In the system this kit comes from, a footnote draft was rejected twice in
    one turn. The author: "I am an epistemologist and, ONCE AGAIN, you are
    trying to establish veracity by associating it with some imaginary
    authority." And of the replacement's closing sentences: "a weak apologia
    that I emphatically reject."

    The draft had settled a question by naming scholars, then closed by
    telling the reader none of the evidence settled anything. A book that
    asks its readers to weigh evidence cannot settle questions by citing
    interpreters, and cannot flinch in its own footnotes.

    "ONCE AGAIN" is the operative phrase. The instinct recurs, so the check
    has to be mechanical rather than a resolution to do better.

THE LIST LIVES IN ONE PLACE
    Methodology/Word Lists.md, between the EPISTEMIC-TRIGGERS markers, read
    through tools/wordlists.py. The failure classes are described there. This
    script holds no list of its own.

WHAT IT CANNOT SEE
    Two of the failure classes leave no trace in the words. A sense
    substitution (a word glossed in its dictionary headword sense where the
    source defines another sense in the same sentence) and an unsourced hinge
    (a load-bearing claim with no note) both read as ordinary confident prose.
    No regex reaches them. They are caught by reading, and by opening the
    dictionary whenever a sentence turns on a foreign word.

    A check that appears to cover every class while covering most of them is
    worse than one that says so. It says so here, and in every report.

A HIT IS A COORDINATE
    "Sitting" is a chair, "of course" is often just idiom, and a named scholar
    is legitimate when the name locates an argument rather than substitutes
    for one. The test on a name: strip every proper noun from the passage and
    ask whether anything checkable remains.

RULED LINES ARE HIDDEN
    Rulings go in Fact Check/Epistemic Rulings.md, keyed by the fingerprint
    printed beside each hit (see tools/rulings.py). --all shows them again.

EXIT CODES
    0  always, unless the trigger list is unreadable. The lock gate reads the
       counts: an unruled hit blocks the chapter's lock until fixed or ruled.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402
import rulings          # noqa: E402
import wordlists        # noqa: E402

RULES = B.WORD_LISTS
RULINGS_FILE = "Epistemic Rulings.md"

FAILURES = {
    "1": "borrowed authority — strip the names; is anything checkable left?",
    "2": "pre-emptive retreat — does this discount our own evidence?",
    "4": "over-reach — does the source claim this broadly?",
    "5": "true-when-written — date it rather than tense it",
    "6": "draft history — the reader has no earlier drafts",
    "8": "invented person — name him, or cut the sentence",
    "9": "BANNED \"a man who\" — name a real person or state the property",
    "10": "telegraphing — the prose announces its own structure instead of doing the work",
}


def load_triggers():
    return wordlists.load_triggers(RULES)


def scan(raw, triggers, ruled=frozenset()):
    """(hits, suppressed). Each hit is (line, match, note, original line, column, fingerprint)."""
    lines = rulings.strip_noise(raw).split("\n")
    original = raw.split("\n")
    hits, suppressed = [], 0
    for n, line in enumerate(lines, 1):
        for rx, note in triggers:
            for m in rx.finditer(line):
                fp = rulings.context_fingerprint(original[n - 1], m.start(), m.group(0))
                if fp in ruled:
                    suppressed += 1
                    continue
                hits.append((n, m.group(0), note, original[n - 1], m.start(), fp))
    return hits, suppressed


def main():
    argv = sys.argv[1:]
    counts_only = "--counts" in argv
    show_ruled = "--all" in argv
    args = [a for a in argv if not a.startswith("--")]

    triggers = load_triggers()
    ruled = set() if show_ruled else rulings.load(RULINGS_FILE)
    files = rulings.chapter_files(args)
    if not files:
        sys.exit("No matching chapter or appendix files.")

    print(f"Epistemic sweep — {len(triggers)} triggers from {RULES.relative_to(B.VAULT)}")
    print("Sense substitution and unsourced hinges leave no trace in the words")
    print("and are caught only by reading.\n")

    grand = suppressed = 0
    for path in files:
        hits, supp = scan(path.read_text(encoding="utf-8"), triggers, ruled)
        suppressed += supp
        label = rulings.label_for(path)
        grand += len(hits)
        if counts_only:
            print(f"  {label:<12} {len(hits)}")
            continue
        if not hits:
            print(f"--- {label}: clean")
            continue
        print(f"--- {label}: {len(hits)} candidate(s)")
        for n, hit, note, text, i, fp in sorted(set(hits), key=lambda h: (h[0], h[4])):
            lo, hi = max(0, i - 70), min(len(text), i + len(hit) + 70)
            snippet = ("…" if lo else "") + text[lo:hi].strip() + ("…" if hi < len(text) else "")
            cls = note.split(" ", 1)[0]
            print(f"    {label}/L{n:<4} {fp}  {snippet}")
            print(f"    {'':<{len(label) + 6}} {FAILURES.get(cls, note)}")
        print()

    tail = f" {suppressed} already ruled and hidden — pass --all to see them." if suppressed else ""
    print(f"\n{grand} unruled candidate(s) across {len(files)} file(s).{tail}")
    print("A hit is a coordinate. An unruled hit blocks the chapter's lock until fixed or ruled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

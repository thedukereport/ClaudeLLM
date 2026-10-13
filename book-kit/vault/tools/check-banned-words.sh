#!/usr/bin/env python3
"""check-banned-words.sh — report banned-word hits in the chapters, for reading.

    tools/check-banned-words.sh              # every chapter and appendix
    tools/check-banned-words.sh 10 25        # named chapters
    tools/check-banned-words.sh --counts     # one line per file, no hits listed
    tools/check-banned-words.sh --all        # include hits the author has already ruled on

WHY THIS EXISTS
    In the system this kit comes from, the author caught a banned word in a
    chat reply. A sweep then found the same word 41 times across four
    chapters, 21 of them violations, in prose that had passed a lock. No check
    had ever looked, because the banned-word list lived in a table nothing
    read. A rule nothing enforces is a rule in name only.

THE LIST LIVES IN ONE PLACE
    Methodology/Word Lists.md, between the BANNED-WORDS-MACHINE-LIST markers,
    read through tools/wordlists.py. This script holds no list of its own. Two
    copies of a rule drift the moment they exist. `load_list()` is kept by
    that name because tools/check-card-words.py imports it from here.

WHAT IT DOES NOT DO
    It decides nothing. A hit is a coordinate. The lock gate,
    tools/check-lock-ready.sh, refuses a lock while the chapter has an
    unruled hit; fixing the line or ruling the hit clears it. Of the 41 hits in that first sweep, 13 were literal or quoted
    and correct. Deciding needs the line open, which is why the line is
    printed.

RULED HITS ARE HIDDEN
    Fact Check/Banned-Word Rulings.md records every hit the author has ruled
    on, through tools/rulings.py. Those are suppressed by default so a sweep
    never asks the same question twice; pass --all to see them. The author
    asked for this mid-review: "I hope you're logging all these changes
    somewhere, so future scans will skip them." They were not being logged;
    they were in chat only.

    A ruling is keyed to a fingerprint of the surrounding text, not to a line
    number. It survives renumbering and moved paragraphs, and breaks when the
    sentence is rewritten, which is correct: a rewritten sentence needs ruling
    again.

WHAT IT STRIPS FIRST
    HTML comments (lock stamps quote their own banned words) and backtick
    code spans. Both produced false reports in the original system.

EXIT CODES
    0  always, unless the list or the vault is unreadable. The lock gate reads
       the counts, not the exit code.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402
import rulings          # noqa: E402  shared with check-footnote-length.sh — one loader, one format
import wordlists        # noqa: E402  the one loader for Methodology/Word Lists.md

RULES = B.WORD_LISTS
RULINGS_FILE = "Banned-Word Rulings.md"


def load_list():
    """[(compiled, pattern, carve-out note, auto regex or None)] from the one list."""
    return wordlists.load_banned(RULES)


def strip_noise(text):
    """Remove what is not the author's prose, and keep line numbers intact."""
    return rulings.strip_noise(text)


def scan(raw, patterns, ruled=frozenset()):
    """Hits in one file's text: (hits, carved, suppressed).

    Each hit is (line, word, carve-out note, original line, column).
    """
    lines = strip_noise(raw).split("\n")
    original = raw.split("\n")
    hits, carved, suppressed = [], 0, 0
    for n, line in enumerate(lines, 1):
        for rx, pattern, carve, rx_auto in patterns:
            for m in rx.finditer(line):
                # The mechanical carve-out, applied to the words around the hit
                # rather than printed beneath it.
                if rx_auto is not None and rx_auto.search(
                        line[max(0, m.start() - 40):m.end() + 40]):
                    carved += 1
                    continue
                # Keep the match position. Re-finding the word later showed the
                # first occurrence for every hit on a line, so two hits on one
                # line printed the same snippet twice.
                fp = rulings.context_fingerprint(original[n - 1], m.start(), m.group(0))
                if fp in ruled:
                    suppressed += 1
                    continue
                hits.append((n, m.group(0), carve, original[n - 1], m.start()))
    return hits, carved, suppressed


def main():
    flags = {"--counts", "--all"}
    args = [a for a in sys.argv[1:] if a not in flags]
    counts_only = "--counts" in sys.argv[1:]
    show_ruled = "--all" in sys.argv[1:]
    patterns = load_list()
    ruled = set() if show_ruled else rulings.load(RULINGS_FILE)
    files = rulings.chapter_files(args)
    if not files:
        sys.exit("No matching chapter or appendix files.")

    print(f"Banned-word sweep — {len(patterns)} patterns from {RULES.relative_to(B.VAULT)}")
    print("A hit is a coordinate, not a verdict. Open the line before deciding.\n")

    grand = suppressed = carved_total = 0
    for path in files:
        hits, carved, supp = scan(path.read_text(encoding="utf-8"), patterns, ruled)
        suppressed += supp
        carved_total += carved
        grand += len(hits)
        label = rulings.label_for(path)
        if counts_only:
            print(f"  {label:<12} {len(hits)}")
            continue
        if not hits:
            print(f"--- {label}: clean")
            continue
        print(f"--- {label}: {len(hits)} hit(s)")
        for n, word, carve, text, i in sorted(set(hits), key=lambda h: (h[0], h[4])):
            lo, hi = max(0, i - 60), min(len(text), i + len(word) + 55)
            snippet = ("…" if lo else "") + text[lo:hi].strip() + ("…" if hi < len(text) else "")
            print(f"    {label}/L{n:<4} {word:<12} {snippet}")
            if carve:
                print(f"    {'':<{len(label) + 6}} carve-out: {carve}")
        print()

    tail = ""
    if carved_total:
        tail += f" {carved_total} carved by a carve-out pattern."
    if suppressed:
        tail += f" {suppressed} already ruled and hidden — pass --all to see them."
    print(f"\n{grand} unruled hit(s) across {len(files)} file(s).{tail}")
    print("An unruled hit blocks the chapter's lock until the line is fixed or the hit is ruled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

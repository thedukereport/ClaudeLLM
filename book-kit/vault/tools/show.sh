#!/usr/bin/env python3
"""show.sh — print a manuscript line inside its context, before proposing any change.

    ./show.sh 2 5          # Ch02/L5 with its section and neighbours
    ./show.sh 2 5 --wide   # more lines either side
    ./show.sh 1 3 5        # several lines from one chapter

WHY THIS EXISTS
    The author: "I'm asking the question because you're not giving me
    context, and it has to be the most repeated ask in my history of this
    entire LLM experience."

    The standing rule already said it: "Context means the sentence, not the
    fragment, and the lines either side where the change touches an
    argument." Claude kept showing a target line with a proposed replacement
    and nothing around it, and the author had to ask what section it was in,
    because the line had been lifted from a section whose subject was never
    shown.

    Judgment failed repeatedly. This makes retrieval mechanical: run it, paste
    the output, then propose the change underneath. Never propose a change to
    a line this has not printed.

WHAT IT PRINTS
    The section heading the line is under, the numbered lines either side,
    the target marked, the zone the line is in (prose that prints, footnote
    apparatus, or scaffolding between PUBLISH-SKIP markers), and any footnote
    definitions the target anchors, because a change to a sentence often
    moves its citation too.
"""
import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    span = 6 if "--wide" in sys.argv else 3
    if len(args) < 2:
        sys.exit("usage: ./show.sh NN L [L ...] [--wide]")
    nn = int(args[0])
    f = B.chapter_file(nn)
    if f is None:
        sys.exit(f"No chapter {nn:02d} in {B.CHAPTERS}.")
    L = f.read_text(encoding="utf-8").split("\n")

    for target in [int(a) for a in args[1:]]:
        if not 1 <= target <= len(L):
            print(f"\n  {B.coord(nn, target)} is outside the file ({len(L)} lines).")
            continue
        head, hn = None, None
        for i in range(target - 1, -1, -1):
            if L[i].startswith("## "):
                head, hn = L[i], i + 1
                break
        # Which zone is this line in? Scaffolding reads exactly like prose.
        skip = False
        for i in range(0, target):
            if L[i].startswith("<!-- PUBLISH-SKIP-START"):
                skip = True
            elif L[i].startswith("<!-- PUBLISH-SKIP-END"):
                skip = False
        zone = ("SCAFFOLDING — inside PUBLISH-SKIP, will not print" if skip
                else "FOOTNOTE APPARATUS" if L[target - 1].startswith("[^")
                else "LIVE PROSE — prints in the book")

        print(f"\n{'═' * 78}")
        print(f"  {B.coord(nn, target)}   [{zone}]")
        if head:
            print(f"  under  {B.coord(nn, hn)}  {head[3:]}")
        mt = datetime.datetime.fromtimestamp(f.stat().st_mtime)
        print(f"  file last written {mt:%Y-%m-%d %H:%M:%S} — re-run if you have been talking a while")
        print(f"{'═' * 78}\n")

        # Outline blocks call material "parked" or "cut"; the prose itself says
        # nothing about its own status. A line was once polished for three
        # exchanges without anyone seeing the outline line that had parked it.
        if head:
            words = re.findall(r"[A-Za-z']{5,}", head[3:])[:4]
            notes = [(i + 1, l) for i, l in enumerate(L)
                     if l.startswith(("####", "**", "*")) and words
                     and sum(w.lower() in l.lower() for w in words) >= 2]
            if notes:
                print("  ── outline notes naming this section ──\n")
                for i, l in notes[:4]:
                    print(f"   L{i:<4}| {l}\n")

        lo, hi = max(0, target - 1 - span * 2), min(len(L), target + span * 2)
        for i in range(lo, hi):
            line = L[i]
            if not line.strip():
                continue
            mark = ">>" if i == target - 1 else "  "
            print(f"{mark} L{i + 1:<4}| {line}\n")

        anchors = re.findall(r"\[\^([^\]]+)\]", L[target - 1])
        if anchors:
            print("  ── footnotes this line anchors ──\n")
            for a in dict.fromkeys(anchors):
                for i, l in enumerate(L, 1):
                    if l.startswith(f"[^{a}]:"):
                        print(f"   L{i:<4}| {l}\n")
    print("Paste this above any proposed change. Do not propose a change to a line")
    print("this has not printed. The standing rule: context is the sentence and the")
    print("lines either side, never the fragment alone.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

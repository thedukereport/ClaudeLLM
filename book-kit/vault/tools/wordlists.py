#!/usr/bin/env python3
"""wordlists.py — the one loader for the machine lists in Methodology/Word Lists.md.

    import wordlists
    wordlists.block("BANNED-WORDS-MACHINE-LIST")   the raw lines between the markers
    wordlists.load_banned()     [(compiled, pattern, carve-out note, auto regex or None)]
    wordlists.load_triggers()   [(compiled, note)]   the epistemic triggers

WHY ONE LOADER

    Each list lives in one place, Methodology/Word Lists.md, between a pair of
    markers. Every tool that reads a list reads it through this file, so there
    is one parser and one format. Two copies of a rule drift the moment they
    exist; in the system this kit comes from, that happened twice in one day,
    once to this very word list.

THE FORMAT

    One entry per line: `pattern ;; note ;; optional auto carve-out regex`.
    The separator is ';;' rather than '|', because the patterns are regular
    expressions and use '|' for alternation. Splitting on '|' silently cut every
    alternation short the first time the original ran. Blank lines, lines
    starting with '#', and code-fence lines are skipped. A pattern that does
    not compile is reported on stderr and skipped, never dropped in silence.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

RULES = B.WORD_LISTS


def block(name, path=None):
    """The non-comment lines between <!-- NAME:BEGIN --> and <!-- NAME:END -->.

    Stops with a message naming the file and the markers when either is
    missing: a check that runs on an empty list reports a clean book.
    """
    path = Path(path) if path else RULES
    begin, end = f"<!-- {name}:BEGIN -->", f"<!-- {name}:END -->"
    if not path.exists():
        sys.exit(f"ERROR: cannot find {path}")
    text = path.read_text(encoding="utf-8")
    # A marker counts only on a line of its own, so the file can mention a
    # marker in its own instructions without the loader starting there.
    m = re.search(rf"(?ms)^\s*{re.escape(begin)}\s*$(.*?)^\s*{re.escape(end)}\s*$", text)
    if not m:
        sys.exit(f"ERROR: the machine-readable list {name} is missing from\n"
                 f"  {path}\nExpected a block between {begin} and {end}, "
                 f"each marker on a line of its own.")
    out = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("```") or line.startswith("#"):
            continue
        out.append(line)
    return out


def _compile(pattern, flags=re.I):
    try:
        return re.compile(pattern, flags)
    except re.error as exc:
        print(f"  ! skipping unparseable pattern {pattern!r}: {exc}", file=sys.stderr)
        return None


def load_banned(path=None):
    """The banned-word list: [(compiled, pattern, carve-out note, auto regex or None)].

    A CARVE-OUT THAT ONLY PRINTS IS NOT A CARVE-OUT. In the original system
    every carve-out was prose: the checker printed it under the hit and raised
    the hit anyway, so a line the rule explicitly permits came back to the
    author every run. The author ruled the carve-out good and asked for a
    better way to apply it. A third ';;' field holds a regex; when it matches
    the words around the hit, the hit is carved and counted, not shown as work.
    """
    out = []
    for line in block("BANNED-WORDS-MACHINE-LIST", path):
        pattern, _, carve = line.partition(";;")
        carve, _, auto = carve.partition(";;")
        pattern, carve, auto = pattern.strip(), carve.strip(), auto.strip()
        if not pattern:
            continue
        rx = _compile(pattern)
        rx_auto = _compile(auto) if auto else None
        if rx is None or (auto and rx_auto is None):
            continue
        out.append((rx, pattern, carve, rx_auto))
    return out


def load_triggers(path=None):
    """The epistemic triggers: [(compiled, note)]. The note starts with the
    failure-class number."""
    out = []
    for line in block("EPISTEMIC-TRIGGERS-MACHINE-LIST", path):
        pattern, _, note = line.partition(";;")
        pattern, note = pattern.strip(), note.strip()
        if not pattern:
            continue
        rx = _compile(pattern)
        if rx is not None:
            out.append((rx, note))
    return out


if __name__ == "__main__":
    print(f"{len(load_banned())} banned-word patterns, "
          f"{len(load_triggers())} epistemic triggers, from {RULES}")

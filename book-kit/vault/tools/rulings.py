#!/usr/bin/env python3
"""rulings.py — one place where "the author already ruled on this" is decided.

    import rulings
    ruled = rulings.load(rulings.BANNED_WORD_RULINGS)     # set of fingerprints
    fp = rulings.context_fingerprint(line, m.start(), m.group(0))
    if fp in ruled: ...                                   # skip it, he ruled

    ./rulings.py "a sentence of the manuscript"           # print its fingerprint
    ./rulings.py --word "the line" carries                # fingerprint of one word in a line

WHY THIS EXISTS
    A check that re-asks a settled question is worse than no check. It costs
    the author the same minutes every run, and the third time it asks he stops
    reading the output, which is when the real hits start getting missed.

    The author, mid-review: "I hope you're logging all these changes
    somewhere, so future scans will skip them." Nothing was. The rulings lived
    in chat only. And later: "If it has been checked and I approved it, I
    don't want to get asked about it again, so you need to be logging these
    checks, and checking the logs."

    That is a general rule about every recurring check, not two special cases,
    so the mechanism lives here once and each check imports it.

THE KEY IS CONTENT, NOT POSITION
    A ruling is keyed to a fingerprint of the text it was made about. Line
    numbers move on every insertion, so a line-keyed ruling would go stale
    silently.

    The fingerprint deliberately BREAKS when the text is rewritten. A rewritten
    sentence is a new sentence, and a footnote that grew by 200 words is a new
    footnote. Both need ruling again. Silence on changed text would be the
    worse failure: it would let an unreviewed edit inherit an old approval,
    which is the same defect as a chapter edited while marked locked.

FILE FORMAT
    Each rulings file in Fact Check/ is a markdown table whose first column is
    a backticked ten-hex-character fingerprint. Everything else in the row is
    for humans. Rows whose first cell is not a fingerprint (an em-dash, for a
    hit that was changed rather than kept) are ignored here: a changed passage
    no longer matches anything, so it needs no suppression.

    Fact Check/Banned-Word Rulings.md   one word in its sentence
                                        (context_fingerprint)
    Fact Check/Attribution Rulings.md   a body sentence's attribution verb
                                        against its note's source language
                                        (fingerprint of the body sentence)
"""
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

VAULT = B.VAULT
RULINGS_DIR = B.FACT
BANNED_WORD_RULINGS = "Banned-Word Rulings.md"
ATTRIBUTION_RULINGS = "Attribution Rulings.md"

FINGERPRINT_ROW = re.compile(r"^\|\s*`([0-9a-f]{10})`\s*\|")


def table_cells(line: str, expected: int = 6):
    """Split one markdown table row into cells, tolerating pipes inside the text.

    WHY THIS EXISTS
        Queues and ledgers quote regexes at each other. Rows hold things like
        `\\bword(s|ed)?` and `widely (accepted|regarded|held)`, and every one of
        those pipes is content, not a column boundary. A parser that splits on
        every "|" reads six columns as ten and puts the status field in the
        wrong place.

        The damage that produced this function: a repair that escaped the
        stray pipes, followed by a revert that unescaped them, dropped the
        tail of the finding and the whole fix column from a dozen rows, nearly
        ten thousand characters, recovered only from an editor's file-recovery
        snapshot.

        **The fix belongs in the readers, not in the file.** Editing hundreds
        of the author's rows to suit three scripts is the wrong direction, and
        the attempt to do it is what caused the loss.

    THE RULE
        Real separators are written " | " with spaces. Regex pipes are written
        without them: `(s|d|nce)`, never `(s | d | nce)`. So split on " | "
        first, and fall back to a bare "|" split when the spaced one does not
        yield the expected column count.

    Returns (cells, how) where how is "spaced", "unspaced", or "malformed".
    A malformed row is a defect in the data: report it, do not silently drop
    it, which is what an earlier table reader did to a dozen rows for weeks.
    """
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    spaced = s.split(" | ")
    if len(spaced) == expected:
        return [c.strip() for c in spaced], "spaced"
    bare = s.split("|")
    if len(bare) == expected:
        return [c.strip() for c in bare], "unspaced"
    longer = spaced if len(spaced) >= len(bare) else bare
    return [c.strip() for c in longer], "malformed"


def fingerprint(text: str) -> str:
    """Stable key for a span of text, whitespace normalised.

    Ten hex characters of SHA-1. Short enough to read in a table, long enough
    that a collision across a few hundred rulings is not a live concern.
    """
    return hashlib.sha1(
        re.sub(r"\s+", " ", text).strip().encode("utf-8")
    ).hexdigest()[:10]


def context_fingerprint(line: str, start: int, word: str, span: int = 30) -> str:
    """Fingerprint for one word IN a line: `span` characters either side.

    Used by the banned-word sweep, where the ruling is about a word in its
    sentence rather than about the whole line. Survives the paragraph moving;
    breaks when the sentence around the word is rewritten.
    """
    lo = max(0, start - span)
    return fingerprint(line[lo:start + len(word) + span])


def load(filename: str) -> set:
    """Fingerprints already ruled on. A missing file is not an error: it
    means nothing has been ruled yet, which is a real state on day one."""
    path = RULINGS_DIR / filename
    if not path.exists():
        return set()
    return {
        m.group(1)
        for m in (FINGERPRINT_ROW.match(line)
                  for line in path.read_text(encoding="utf-8").splitlines())
        if m
    }


def strip_noise(text: str) -> str:
    """Remove what is not the author's prose, preserving line numbers.

    HTML comments (lock stamps quote the book's own banned words, and list
    footnote slugs that then read as unmatched anchors) and inline code spans.
    Both produced false reports: footnotes reported missing that were only
    mentioned inside a lock stamp.
    """
    def blank(match):
        return re.sub(r"[^\n]", " ", match.group(0))

    text = re.sub(r"<!--.*?-->", blank, text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", blank, text)
    return text


def chapter_files(args, vault=None):
    """Chapters and appendices, filtered by any numbers in `args`.

    `vault` is accepted for callers written against the original signature;
    the folders always come from bookconfig."""
    files = list(B.chapter_files())
    if B.APPENDICES.is_dir():
        files += sorted(p for p in B.APPENDICES.glob("Appendix *.md") if not B.is_backup(p))
    nums = {int(a) for a in args if str(a).isdigit()}
    if not nums:
        return files
    return [p for p in files if B.chapter_number(p) in nums]


def label_for(path) -> str:
    """Ch07 / Appendix F: the form used in every report and every ruling row."""
    n = B.chapter_number(path)
    if n is not None:
        return f"Ch{n:02d}"
    return re.sub(r"^(Appendix [A-Z0-9]+).*", r"\1", Path(path).name)


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__.split("WHY")[0])
        return
    if args[0] == "--word" and len(args) >= 3:
        line, word = args[1], args[2]
        i = line.find(word)
        if i < 0:
            sys.exit(f'"{word}" is not in that line.')
        print(context_fingerprint(line, i, word))
        return
    print(fingerprint(" ".join(args)))


if __name__ == "__main__":
    main()

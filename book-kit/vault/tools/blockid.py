#!/usr/bin/env python3
"""blockid.py — gives every block in a chapter a block id that survives editing.

    python3 tools/blockid.py --sample 2     # show what chapter 2 would look like
    python3 tools/blockid.py                # what would change, nothing written
    python3 tools/blockid.py --write        # do it, with both proofs enforced
    python3 tools/blockid.py --write --above   # ids on their own line (see below)

Needs pandoc on the PATH for the rendered-output proof. Without it nothing is
written.

WHY

    The author: "using Chapter/Line is wholy contingent in the number of lines
    not changing, which is bankrupt from the get-go."

    A `Ch##/L##` coordinate points at a position in a file that changes under
    it, and nothing tells it when it goes stale. Re-deriving coordinates by
    hand after every edit is a hope, not a mechanism.

WHAT A BLOCK ID IS, AND WHY NOT A CONTENT HASH

    A short opaque name, assigned once, written into the file, never reused:

        <!-- b:k7f3a2 -->

    A content hash cannot do this job. When the author rewrites a paragraph
    the hash changes, and nothing can then tell "paragraph rewritten" from
    "paragraph deleted, new one inserted". That difference is the point: in
    the original system a tool deleted a body paragraph and wrote a footnote
    definition in its place, and nothing could see it.

    An id survives editing. A hash survives movement. Both are kept: the id
    for identity, the hash for change detection (see blocks.py).

TWO PROOFS, AND THE FIRST ONE WAS NOT ENOUGH

    Proof one — the prose hash. Every chapter's text, with id comments
    removed, must hash identically before and after.

    Proof two — the rendered output. `pandoc -t plain` must be byte-identical
    before and after.

    The second proof exists because the first one passed on a migration that
    would have corrupted the book. Putting ids on their own line broke every
    markdown table in one chapter: a comment line between two table rows
    splits the table, and pandoc printed the rows as literal text. The prose
    hash was identical, because the characters were all still there. Only the
    rendering changed, and the first proof could not see rendering. No
    chapter is written until its rendered output matches.

PANDOC, CHECKED RATHER THAN ASSUMED

    `-t plain` and `-t latex` drop the comments. `-t html` passes them through
    as HTML comments, invisible to a reader. An inline id is appended with NO
    space before it: pandoc strips the comment but keeps the space, which left
    every heading with a trailing space and broke byte-identity.

PUBLIC FUNCTIONS

    is_block(line) -> bool
    strip_ids(text) -> str
    prose_hash(text) -> str
    render_hash(text) -> str        "" when pandoc did not run
    new_id(taken) -> str            mints an id not in `taken`, and adds it
    assign(text, taken, mode) -> (new_text, how_many)
    chapters() -> iterator of chapter files
    existing_ids() -> set
    IDRE
"""
import hashlib
import re
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

CHAPTERS = B.CHAPTERS

IDRE = re.compile(r"<!--\s*b:([a-z0-9]{6})\s*-->")
# A line that holds prose can be addressed. Blank lines and horizontal rules
# hold nothing and get no name.
SKIP = re.compile(r"^\s*(---|\*\*\*|___)\s*$")


def is_block(line: str) -> bool:
    """Does this line hold prose that can be addressed?

    A bare `>` is an empty blockquote line and holds nothing — the first run
    of this gave one an id. So does a line of only punctuation. A name for
    nothing is a name that will later point at nothing.
    """
    s = line.strip()
    if not s or SKIP.match(s) or IDRE.fullmatch(s):
        return False
    stripped = s.lstrip("> ").strip()
    return bool(stripped) and any(c.isalnum() for c in stripped)


def strip_ids(text: str) -> str:
    """The prose alone — what the hash proof compares."""
    out = []
    for line in text.splitlines():
        if IDRE.fullmatch(line.strip()):
            continue                       # an id on its own line
        out.append(IDRE.sub("", line).rstrip())
    return "\n".join(out).strip()


def prose_hash(text: str) -> str:
    return hashlib.sha256(strip_ids(text).encode("utf-8")).hexdigest()


def render_hash(text: str) -> str:
    """What pandoc makes of it. The proof the prose hash cannot give.

    Returns "" when pandoc is unavailable, and a caller that gets "" must
    refuse to write rather than treat an unrun check as a pass. A check that
    did not run is not a check that found nothing.
    """
    import subprocess
    try:
        r = subprocess.run(["pandoc", "-f", "markdown", "-t", "plain"],
                           input=text, capture_output=True, text=True, timeout=120)
        return hashlib.sha256(r.stdout.encode("utf-8")).hexdigest() if r.returncode == 0 else ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def new_id(taken: set) -> str:
    while True:
        i = secrets.token_hex(3)
        if i not in taken:
            taken.add(i)
            return i


def assign(text: str, taken: set, mode: str):
    """Return (new_text, how_many_assigned). Existing ids are never changed."""
    lines = text.splitlines()
    out, n = [], 0
    for line in lines:
        if IDRE.fullmatch(line.strip()):
            out.append(line)
            continue
        if not is_block(line):
            out.append(line)
            continue
        has_above = bool(out and IDRE.fullmatch(out[-1].strip()))
        has_inline = bool(IDRE.search(line))
        if has_above or has_inline:
            out.append(line)
            continue
        bid = new_id(taken)
        n += 1
        if mode == "above":
            out.append(f"<!-- b:{bid} -->")
            out.append(line)
        else:                                   # inline, at the end of the line
            # NO SPACE BEFORE THE COMMENT. Pandoc strips the comment and
            # leaves the space, so "# Head <!--id-->" renders as "Head " with
            # a trailing space and the output is no longer byte-identical.
            out.append(f"{line}<!-- b:{bid} -->")
    return "\n".join(out) + ("\n" if text.endswith("\n") else ""), n


def chapters():
    """The chapter files. Backups and archived copies are not the book; a
    glob that reads them invents work (bookconfig.is_backup)."""
    yield from B.chapter_files()


def existing_ids():
    taken = set()
    for f in chapters():
        taken |= set(IDRE.findall(f.read_text(encoding="utf-8", errors="replace")))
    return taken


def main():
    args = sys.argv[1:]
    # INLINE IS THE DEFAULT, AND ONE CONVENTION PER BOOK.
    #
    # Every reader of block ids expects `line<!-- b:xxxxxx -->`. A tool that
    # reads ids at the end of the line cannot see an id that is on the line
    # above, and would drop it silently when it rewrites the line. `--above`
    # is there only for a chapter where an inline comment would break a table.
    mode = "above" if "--above" in args else "inline"

    if "--sample" in args:
        try:
            want = int(args[args.index("--sample") + 1])
        except (IndexError, ValueError):
            sys.exit("  --sample needs a chapter number")
        f = B.chapter_file(want)
        if not f:
            sys.exit(f"  no chapter {want}")
        text = f.read_text(encoding="utf-8")
        for m in ("above", "inline"):
            new, n = assign(text, existing_ids(), m)
            print("=" * 74)
            print(f"  {m.upper()} — {n} ids would be assigned in {f.stem}")
            print("=" * 74)
            for l in new.splitlines()[:14]:
                print(l[:148] + ("…" if len(l) > 148 else ""))
            print()
        return

    write = "--write" in args
    taken = existing_ids()
    plan, failures = [], []
    for f in chapters():
        text = f.read_text(encoding="utf-8")
        new, n = assign(text, taken, mode)
        if prose_hash(text) != prose_hash(new):
            failures.append(f"{f.name}: the prose itself changed")
            plan.append((f, new, n))
            continue
        if n:
            rb, ra = render_hash(text), render_hash(new)
            if not rb or not ra:
                failures.append(f"{f.name}: pandoc did not run — the render proof "
                                f"could not be taken, so this is NOT a pass")
            elif rb != ra:
                failures.append(f"{f.name}: the RENDERED output changed — "
                                f"a table or list was most likely split")
        plan.append((f, new, n))

    total = sum(n for _, _, n in plan)
    print(f"\n  {len(plan)} chapter(s).  {total} block id(s) to assign, mode={mode}.")
    if failures:
        print(f"\n  ABORTED — a proof failed in {len(failures)} chapter(s):")
        for name in failures:
            print(f"    {name}")
        print("  NOTHING WAS WRITTEN. This is the proof doing its job.\n")
        sys.exit(2)
    print("  prose hash AND rendered output identical in every chapter that changes.\n")
    for f, _, n in plan:
        print(f"    {n:>5}  {f.stem}")
    if not write:
        print("\n  Nothing written. Add --write.\n")
        return
    if not total:
        print("\n  Every block already has an id. Nothing to write.\n")
        return

    import vaultlog
    vaultlog.IN_BLOCKID.append(True)
    try:
        for f, new, n in plan:
            if n:
                vaultlog.write_file(f, new, tool="blockid.py",
                                    why=f"assigned {n} block id(s), mode={mode}")
    finally:
        vaultlog.IN_BLOCKID.pop()
    vaultlog.append("block.assigned", actor="claude",
                    chapters=sum(1 for _, _, n in plan if n), ids=total, mode=mode,
                    proof="prose hash and pandoc plain render identical in every chapter")
    print("\n  written, and logged.\n")


if __name__ == "__main__":
    main()

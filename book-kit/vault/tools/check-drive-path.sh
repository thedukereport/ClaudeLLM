#!/usr/bin/env python3
"""check-drive-path.sh — every drive_path recorded in Claims opens, or the run fails.

    ./check-drive-path.sh           # every Claims file
    ./check-drive-path.sh 2         # one chapter
    ./check-drive-path.sh --list    # print every failure in full

    A drive_path may be absolute, or relative to the library root
    ("PDF/Thomas Paine - Common Sense (1776).txt"). A relative path survives
    the library moving to another disk or another machine; an absolute one
    does not.

WHY THIS EXISTS

    The rule: a title invites a second search, a path ends the question. The
    first time the field was tested in the system this kit comes from, about
    half its values were descriptions ("the library", "on the drive", "held
    in the PDF folder") and a further share were paths that did not exist. So
    the field that exists to end a search was, for most of the book's
    sources, an invitation to start one.

FOUR THINGS IT TESTS

    1. Is the value a path at all, or a URL?
    2. Does that path exist?
    3. Is it a path on the AUTHOR'S machine? A path under /sessions/ is a
       Claude sandbox mount. It resolves inside the sandbox and nowhere the
       author can reach, so it passes any test Claude runs from inside and
       fails the only test that counts. Hundreds of such paths once stayed in
       the records for a day after a tool reported them clean.
    4. Does the file the path opens belong to the record's author? (WRONG
       BOOK?, below.)

AND IT IGNORES BACKUP FILES, WHICH IS NOT A DETAIL

    A count of the same field once reported hundreds of sandbox paths that had
    been repaired the day before: the glob swept the .bak snapshots beside
    the live files. The same glob bug gave a chapter's verification report
    false failures. Twice is a pattern, so the exclusion lives in one place
    (bookconfig.is_backup).
"""
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402
import citedworks as W  # noqa: E402

LIB = B.library_root()
SANDBOX = re.compile(r"^/sessions/")


def claims_files(only=None):
    """LIVE Claims files only. A .bak is a snapshot, not the book's state."""
    for f in W.claims_files():
        if only:
            m = re.search(r"(\d+)", f.stem)
            if not m or int(m.group(1)) not in only:
                continue
        yield f


def resolve(p: str):
    """The file this value names: absolute as written, or relative to the
    library root. None when a relative value has no library to resolve
    against."""
    if p.startswith("/") or p.startswith("~"):
        return Path(os.path.expanduser(p))
    return (LIB / p) if LIB is not None else None


def _shelf_part(target: Path) -> str:
    """The part of the path below the library root, so the words of the
    folders above it (a home folder, a disk name) never count as an author."""
    try:
        return str(target.resolve().relative_to(LIB.resolve()))
    except (ValueError, AttributeError):
        return str(target)


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def wrong_book(p: str, author) -> bool:
    """The path opens, but does it open the book the record names?

    **A path that opens the wrong book is worse than no path at all**, because
    it looks answered. A reader follows it, finds a book that does not contain
    the passage, and has no way to tell whether the citation is wrong or he is.
    In the system this kit comes from, three records once pointed at books by
    other authors whose titles shared a word with the cited one.

    The test is the author's surname against the filename and its folder. It
    is a coordinate, not a verdict: an anonymous work, an editor named where
    the file gives the author, a Latin name against an English filename all
    trip it honestly. The ruling happens with both open.
    """
    if not author or str(author).lower() in ("none", "null"):
        return False
    if not p.lower().endswith((".pdf", ".epub", ".txt", ".mobi", ".azw3")):
        return False
    hay = set(_norm(os.path.basename(p)).split()) | set(_norm(os.path.dirname(p)).split())
    sur = set()
    for part in re.split(r"[;,]| and | & ", str(author)):
        w = [x for x in _norm(part).split() if len(x) > 2]
        if w:
            sur.add(w[-1])
    return bool(sur) and not (sur & hay)


def main():
    args = sys.argv[1:]
    show = "--list" in args
    only = {int(a) for a in args if a.isdigit()} or None

    ok = url = 0
    faults = {"NOT A PATH": [], "DOES NOT EXIST": [], "SANDBOX ONLY": [],
              "NO LIBRARY TO RESOLVE AGAINST": [], "WRONG BOOK?": []}
    for f in claims_files(only):
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            p = r.get("drive_path") if isinstance(r, dict) else None
            if not isinstance(p, str) or not p.strip():
                continue
            p = p.strip()
            where = f"{f.stem} L{n}  {str(r.get('title'))[:44]}"
            if p.startswith(("http://", "https://")):
                url += 1
                continue
            if SANDBOX.match(p):
                faults["SANDBOX ONLY"].append((where, p))
                continue
            # A description has no folder separator and no file extension:
            # "the library", "on the shelf". A relative path has at least one.
            if not p.startswith(("/", "~")) and "/" not in p and not Path(p).suffix:
                faults["NOT A PATH"].append((where, p))
                continue
            target = resolve(p)
            if target is None:
                faults["NO LIBRARY TO RESOLVE AGAINST"].append((where, p))
            elif not target.exists():
                faults["DOES NOT EXIST"].append((where, p))
            elif wrong_book(_shelf_part(target), r.get("author")):
                faults["WRONG BOOK?"].append((where, p))
            else:
                ok += 1

    bad = sum(len(v) for v in faults.values())
    print(f"\n  {ok} drive_path value(s) open on this machine.  {url} URL(s).")
    print(f"  {bad} that do not.\n")
    for kind, rows in faults.items():
        if not rows:
            continue
        print(f"    {kind}: {len(rows)}")
        for where, p in (rows if show else rows[:6]):
            print(f"      {where}\n         {p[:110]}")
        if not show and len(rows) > 6:
            print(f"      … {len(rows) - 6} more.  --list prints them all.")
        print()
    if faults["NO LIBRARY TO RESOLVE AGAINST"]:
        print("  No library root in book.toml exists here, so relative paths could not")
        print("  be opened. That is a fact about this machine, not about the records.\n")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()

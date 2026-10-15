#!/usr/bin/env python3
"""check-read.sh — every work the chapters cite, and whether anyone opened it.

    ./check-read.sh              # the works with no record of a reader
    ./check-read.sh --all        # every work, with its state
    ./check-read.sh 2            # one chapter
    ./check-read.sh --strict     # exit 1 if any cited work is unread

WHY THIS EXISTS

    The author: "There should not be one source in this book that you have
    not opened." And: "It's against the rules for you to cite anything that
    you have not read."

    That is the rule the whole apparatus serves, and for a long time nothing
    measured it. A footnote check asks whether a reader could FOLLOW a
    citation. This asks the prior question: did anyone here follow it first.

    The failure it catches has happened repeatedly. An agent finds a title
    through a search, writes a citation from the search result, and never
    opens the file. The note looks complete. The page number may even be
    right. Nobody has read the page. In the system this kit comes from, the
    author found each case himself: a note that said the copy read had no
    publisher's imprint, when the copy on the shelf prints one on its
    title-page verso; a "pamphlet" that was a two-page review by someone else;
    phrases put in an author's mouth that appear nowhere in his books.

THE THREE STATES

    READ            a record in Fact Check/Claims/ names a reader or a date
                    read for this work
    UNREAD          the work is in the library and no record says anyone
                    opened it
    NOT IN LIBRARY  cited, and not found in the library by name

    UNREAD is the actionable one: the book is there, and reading it costs
    minutes. NOT IN LIBRARY is a Sources Wanted entry, after the searches
    have.sh prints when it finds nothing.

WHAT IT CANNOT DO

    It matches titles, so a work cited under a short title and read under its
    full one may read as UNREAD. That is the safe direction to fail: it
    over-reports work to do rather than certifying a source nobody opened.
    Periodicals are listed separately, because a newspaper is not a work
    anyone reads cover to cover.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402
import citedworks as W  # noqa: E402

LABELS = ("NOT IN LIBRARY", "UNREAD", "READ")


def ledger_reads():
    """Every work a Claims record shows as opened, by normalised title."""
    out = {}
    for f, _n, o in W.claims_rows():
        t = (o.get("title") or "").strip()
        if not t:
            continue
        # A READER OR A DATE. NOT A PATH.
        #
        # `drive_path` was once part of this test. Then a backfill filled
        # empty path fields by filename match, and every one of those records
        # would have flipped to READ here. A path says which copy exists. Only
        # a reader says somebody opened it, and conflating the two would have
        # certified hundreds of unread books in a single afternoon, the
        # failure this file was built to catch.
        if o.get("date_read") or o.get("reader"):
            k = W.norm(t)
            if k and k not in out:
                out[k] = (o.get("author", "") or "", o.get("date_read", "") or "", f.stem)
    return out


def match_read(k: str, read: dict) -> bool:
    """Does any Claims title name this work? Containment either way, on a key
    long enough not to collide. A footnote cites a short title where the
    record holds the full one with its subtitle; measuring string format and
    calling it unread sends someone to re-read a book already read."""
    return W.match(k, read) is not None


def classify(chapters):
    """{state: [(title, Counter of chapters)]} plus whether the library was searched."""
    have = W.load_tool("have.sh")
    lib = have.LIB
    stems = [s for s, _f in have.files()] if lib else []
    read = ledger_reads()
    states = {"READ": [], "UNREAD": [], "NOT IN LIBRARY": [], "NOT SEARCHED": [],
              "periodical": []}
    for title, chs in W.cited_works(chapters).items():
        k = W.norm(title)
        if W.PERIODICAL.search(title):
            states["periodical"].append((title, chs))
        elif match_read(k, read):
            states["READ"].append((title, chs))
        elif lib is None:
            # No library on this machine: the honest state is "not searched",
            # never "not in the library".
            states["NOT SEARCHED"].append((title, chs))
        elif have.have(title) or (len(k) > 8 and any(k in d or d in k for d in stems)):
            states["UNREAD"].append((title, chs))
        else:
            states["NOT IN LIBRARY"].append((title, chs))
    return states, lib


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    chapters = [B.chapter_file(int(args[0]))] if args else B.chapter_files()
    chapters = [c for c in chapters if c]
    if not chapters:
        sys.exit(f"No chapter files{' for ' + args[0] if args else ''} in {B.CHAPTERS}.")
    states, lib = classify(chapters)

    if lib is None:
        print("\nNO LIBRARY FOUND. None of the roots in book.toml [library] roots exists")
        print("on this machine, so no work was tested against the shelf. Works with no")
        print("reader are listed as NOT SEARCHED, never as NOT IN LIBRARY.")

    show_all = "--all" in sys.argv
    for label in ("NOT SEARCHED",) + LABELS[:2] + (("READ",) if show_all else ()):
        rows = states[label]
        if not rows:
            continue
        print(f"\n{label} — {len(rows)}")
        for title, chs in sorted(rows, key=lambda r: (-sum(r[1].values()), r[0]))[:60]:
            where = ", ".join(f"Ch{c:02d}" for c in sorted(chs))
            print(f"   {sum(chs.values()):>3}x  {title[:62]:<64}{where[:34]}")
    if show_all and states["periodical"]:
        print(f"\nperiodical — {len(states['periodical'])}")
        for title, chs in sorted(states["periodical"]):
            print(f"         {title[:62]}")

    print(f"\n{'-' * 74}")
    print(f"  cited works           "
          f"{sum(len(v) for k, v in states.items() if k != 'periodical'):>5}")
    for k in ("READ", "UNREAD", "NOT IN LIBRARY") + (("NOT SEARCHED",) if lib is None else ()):
        print(f"  {k:<22}{len(states[k]):>5}")
    print(f"  periodicals, listed separately{len(states['periodical']):>5}")
    print("\nUNREAD means the work is in the library and no Claims record names a")
    print("reader. The author's rule: the point of scanning for unread citations is to")
    print("read them. This list feeds the Fact-checker's reading queue")
    print("(tools/dashboard-sync.py queue writes Fact Check/Reading Queue.md) and never")
    print("goes to the author. NOT IN LIBRARY is searched again there first.")
    if "--strict" in sys.argv and (states["UNREAD"] or states["NOT IN LIBRARY"]
                                   or states["NOT SEARCHED"]):
        sys.exit(1)


if __name__ == "__main__":
    main()

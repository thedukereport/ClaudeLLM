#!/usr/bin/env python3
"""have.sh — the one search that answers "is this work in the library?"

    ./have.sh "Common Sense"
    ./have.sh "The Federalist Papers"
    ./have.sh Paine               # a surname: the author segment of the filename
    ./have.sh --audit             # re-test every work the Claims files call absent
    ./have.sh --reindex           # rebuild the index after adding books

WHY THIS EXISTS

    In the system this kit comes from, the book reported works absent from a
    library that held them four times in one day, and each time the instance
    was fixed instead of the search. The author: "This problem has been
    addressed several times, just today."

    The misses had four shapes, and each one is a rule below:

      A short title matched a longer one character by character ("Part II"
      is a substring of "Part III"), so the wrong book came back.

      A colon in a citation is a dash in a filename, so a title straddled two
      segments of the name and opened neither.

      Works filed under catalogue codes (one file per work, the title only in
      a manifest.json beside them) were never found by name.

      A work cited as "not read directly" while several copies were on the
      shelf. The author had to say where it was.

    THE CAUSE WAS NONE OF THOSE BUGS. Six files each implemented their own
    idea of searching the library, and none covered every shelf. Fixing one
    left the other five wrong. So: one search, every shelf, and every tool
    calls it.

THE SHELVES

    The library root is `[library] roots` in book.toml (the first that exists
    here). Every folder directly under it is a shelf. The hand-checked shelf,
    `[library] checked_shelf`, is searched and ranked first; the other shelves
    follow in name order, then loose files at the root. A folder named
    `text_cache` holds extracted text under hash names and is left to
    find-source.sh.

WHAT IT REPORTS

    HAVE          one or more copies, ranked by SHELF first (the checked shelf
                  on top), then by file type, then largest first.
    NOT BY NAME   searched every shelf and every manifest and found nothing.

    NOT BY NAME is trustworthy only because the search is complete, and even
    then it is a fact about the search. It never says the work does not exist.
"""
import datetime
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

LIB = B.library_root()
CACHE = B.LIBRARY_INDEX
SKIP_SHELVES = {"text_cache"}
BOOKISH = {".pdf", ".epub", ".mobi", ".azw3", ".txt", ".xml"}
TIER = {".pdf": 1, ".epub": 2, ".mobi": 3, ".azw3": 3, ".xml": 4, ".txt": 5}


def shelves():
    """The checked shelf first, then every other folder under the root, then
    the root itself for loose files ("." in this list)."""
    if LIB is None:
        return []
    names = sorted(d.name for d in LIB.iterdir()
                   if d.is_dir() and d.name not in SKIP_SHELVES
                   and not d.name.startswith("."))
    first = [B.CHECKED_SHELF] if B.CHECKED_SHELF in names else []
    return first + [n for n in names if n != B.CHECKED_SHELF] + ["."]


SHELVES = shelves()


def shelf_rank(f) -> int:
    """WHICH COPY THIS TOOL NAMES FIRST. The shelf decides, not the file size.

    The author, on the shelf he had curated by hand for months: that is the
    directory to read. The sort key used to be (file type, size, path) and
    never looked at the shelf, while the docstring claimed "checked shelf
    first." So a book-manager export under a truncated auto-generated name was
    recommended over the curated copy, to every tool and every agent that asks
    this file where a book is.
    """
    try:
        rel = Path(f).relative_to(LIB).parts
    except Exception:
        return len(SHELVES)
    if len(rel) == 1:
        return SHELVES.index(".") if "." in SHELVES else len(SHELVES)
    return SHELVES.index(rel[0]) if rel and rel[0] in SHELVES else len(SHELVES)


def norm(s):
    s = re.sub(r"[^a-z0-9 ]+", " ", str(s).lower())
    s = re.sub(r"\b(the|a|an|of|and|in|on|to|for|its|his|her|their|de|la|le)\b",
               " ", s)
    return re.sub(r"\s+", " ", s).strip()


# WORKS FILED UNDER A CODE. A corpus may file each work as a code
# (`author/tlg0000.tlg000.xml`) with its title only inside a manifest, and in
# another language. An English title will never match such a file by any
# amount of string cleverness, so the bridge has to be written down: the
# English title the book uses, and the folder/code-prefix of the file under
# the library root, e.g.
#
#     "some english title": "Greek-texts/author-folder/tlg0000.tlg001",
#
# THIS LIST IS EMPTY UNTIL YOU FILL IT, and an English title that is not here
# reports NOT BY NAME even if the library holds it. Add a line whenever one
# turns up, and prefer adding a line to arguing with the matcher.
CODED = {}


# A BOOK SHELVED UNDER ITS OTHER NAME. The same work published under two
# titles (a translation's title against the original's, a series title against
# the volume's, a collection against the essay it reprints). No matcher can
# bridge them because the words do not overlap. Write both directions if the
# book may cite either, e.g.
#
#     "title the book cites": "title on the shelf",
#
# Add a line whenever one turns up. Prefer a line here to loosening the
# matcher: every time the matcher was loosened it started finding the wrong
# book.
ALSO_KNOWN_AS = {}

_FILES = None
_MANIFEST = None


def shelf_signature():
    """A fingerprint of the shelves that changes when a file is added.

    WALKS DIRECTORIES ONLY, NEVER FILES. Adding a file changes its parent
    directory's mtime, so the newest directory mtime plus the directory count
    is enough to notice, and walking directories is far cheaper than walking
    files.

    The author: "I cannot run a new index every time I add something" to the
    library. He should not have to. Nobody should have to remember a
    maintenance command for a tool whose whole job is to know what is on the
    shelf, and forgetting is invisible until it reports a book absent.
    """
    newest = 0.0
    count = 0
    for shelf in SHELVES:
        d = LIB / shelf
        if not d.is_dir():
            continue
        walker = os.walk(d) if shelf != "." else [(str(d), [], [])]
        for root, _dirs, _files in walker:
            count += 1
            try:
                m = os.stat(root).st_mtime
                newest = max(newest, m)
            except OSError:
                continue
    return {"root": str(LIB), "dirs": count, "newest": round(newest, 3)}


def _shelf_files(shelf):
    d = LIB / shelf
    if shelf == ".":
        return [f for f in d.iterdir() if f.is_file()]
    return d.rglob("*")


def files(rebuild=False):
    """Every bookish file on every shelf, with its normalised stem.

    Read from the index (`[library] index_file`) when one exists and the
    shelves have not changed. `./have.sh --reindex` rebuilds it by hand.

    THE INDEX IS CACHED because rebuilding it per query is why --audit once
    timed out: the whole library walked once per record. Rescanning the shelf
    for every question is not searching, it is thrashing.

    A STALE INDEX IS A TOOL THAT LIES ABOUT THE SHELF. The author added two
    books and this answered NOT BY NAME on both while the files sat on the
    shelf. So the index holds a signature of the shelves and throws itself
    away when a file is added, without anyone being asked to notice.
    """
    global _FILES
    # A REBUILD MUST ACTUALLY REBUILD. An in-memory guard once returned the
    # stale list even when the caller had just asked for a fresh one.
    if rebuild:
        _FILES = None
    if _FILES is not None:
        return _FILES
    if LIB is None:
        _FILES = []
        return _FILES
    sig = shelf_signature()
    if CACHE.exists() and not rebuild:
        try:
            raw = json.loads(CACHE.read_text(encoding="utf-8"))
            if raw.get("signature") == sig:
                _FILES = [(k, LIB / p) for k, p in raw["files"]]
                return _FILES
        except Exception:
            pass
    _FILES = []
    for shelf in SHELVES:
        if not (LIB / shelf).is_dir():
            continue
        for f in _shelf_files(shelf):
            try:
                if f.is_file() and f.suffix.lower() in BOOKISH:
                    _FILES.append((norm(f.stem), f))
            except OSError:
                continue
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(
            {"built": datetime.date.today().isoformat(),
             "shelves": SHELVES,
             "signature": sig,
             "files": [[k, str(f.relative_to(LIB))] for k, f in _FILES]}),
            encoding="utf-8")
    except OSError:
        pass
    return _FILES


def manifest_titles():
    """Every work named in a manifest.json anywhere in the library.

    These are the holdings no filename can reveal: the file is a catalogue
    code and the title exists only inside its folder's manifest.json. Works
    were reported absent from the shelf for want of reading them.
    """
    global _MANIFEST
    if _MANIFEST is None:
        _MANIFEST = []
        if LIB is None:
            return _MANIFEST
        for m in LIB.rglob("manifest.json"):
            try:
                data = json.loads(m.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            for title, path in _walk(data, m.parent):
                _MANIFEST.append((norm(title), title, path, m.parent.name))
    return _MANIFEST


def _walk(node, base):
    """Pull (title, path) pairs out of a manifest of unknown shape."""
    out = []
    if isinstance(node, dict):
        title = node.get("title") or node.get("name") or node.get("work")
        fp = node.get("file") or node.get("path") or node.get("filename")
        if title:
            out.append((str(title), str(base / fp) if fp else str(base)))
        for v in node.values():
            out += _walk(v, base)
    elif isinstance(node, list):
        for v in node:
            out += _walk(v, base)
    return out


SEG = r"\s+-\s+|\s*[—–]\s*|_"
YEAR = re.compile(r"\s*[(\[]\s*\d{3,4}[^)\]]*[)\]]")


def segments(stem):
    """The filename's segments as word lists. A year in brackets is dropped,
    because files are named "Author - Title (Year)" and a whole-segment test
    on a short title would otherwise never match a dated file."""
    return [norm(YEAR.sub(" ", s)).split() for s in re.split(SEG, stem)]


def title_matches(k, stem):
    """The cited title's words, in order, opening a segment of the filename.

    Word-first, never character-first: "part ii" is a substring of
    "part iii" and is not that book. And a title may straddle two segments,
    because a colon in a citation is a dash in a filename; the run must still
    BEGIN where a segment begins, so a title found in the middle of another
    book's title is not a match.
    """
    words = k.split()
    if not words:
        return False
    segs = segments(stem)
    if len(words) < 2:
        # A ONE-WORD TITLE MUST BE THE WHOLE SEGMENT, never merely its opening.
        # Letting one word open a segment was tried once, and the regression
        # test caught it handing back a different book whose second segment
        # began with the query's word. One word is not enough to name a book;
        # the way to reach a work shelved under another name is ALSO_KNOWN_AS,
        # where the other name is written down and can be read.
        return any(sw == words for sw in segs)
    if any(sw[:len(words)] == words for sw in segs):
        return True
    flat, starts, i = [], set(), 0
    for sw in segs:
        starts.add(i)
        flat += sw
        i += len(sw)
    return any(flat[j:j + len(words)] == words for j in starts)


def _size(f):
    try:
        return Path(f).stat().st_size
    except OSError:
        return 0


def have(title, _following_alias=False):
    """Every copy of this work on every shelf, best first: [(path, how), ...].

    `_following_alias` stops a reciprocal pair in ALSO_KNOWN_AS from calling
    back and forth forever. Both directions are worth keeping, because the
    book may cite either title, so the recursion is cut instead of the table.
    """
    k = norm(title)
    if len(k) < 4 or LIB is None:
        return []
    hits = []
    for eng, frag in CODED.items():
        if k == norm(eng) or title_matches(k, eng):
            folder, _, code = frag.rpartition("/")
            d = LIB / folder
            for f in (d.glob(f"{code}*") if d.is_dir() else []):
                hits.append((shelf_rank(f), 0, 0, f, f"coded file: {eng}"))
    for stem, f in files():
        if title_matches(k, f.stem) or k == stem:
            hits.append((shelf_rank(f), TIER.get(f.suffix.lower(), 9), -_size(f), f,
                         "filename"))
    for mk, mtitle, mpath, _slug in manifest_titles():
        # WORD-FIRST HERE TOO. Plain containment on manifest titles returned
        # hundreds of "copies" for every query, because a short manifest title
        # is a substring of almost anything.
        if mk == k or title_matches(k, mtitle):
            hits.append((len(SHELVES), 0, 0, Path(mpath), f"manifest: {mtitle}"))

    # AN AUTHOR'S SURNAME IS NOT A TITLE, AND HAS TO BE ASKED FOR SEPARATELY.
    # A one-word query must be the WHOLE of a filename segment, and a surname
    # is never the whole of a title segment. It is the whole, or the last
    # word, of the AUTHOR segment, which is a different place to look. Files
    # are named "Author - Title", so the author is the first segment, and the
    # segment has to look like a name: a file whose only segment is a title
    # has no author in it at all.
    if not hits and len(k.split()) <= 3:
        for stem, f in files():
            segs = re.split(r"\s+-\s+|\s*[—–]\s*", f.stem)
            if len(segs) < 2:
                continue
            first = norm(segs[0])
            fw = first.split()
            if first and (k == first or (len(k.split()) == 1 and fw and k == fw[-1])):
                hits.append((shelf_rank(f), TIER.get(f.suffix.lower(), 9), -_size(f), f,
                             f"AUTHOR MATCH — no title was checked: “{k}”"))

    # THE OTHER NAME FIRST, before any partial-title guessing. A second title
    # for the same work is an exact answer; a main title without its subtitle
    # is an approximate one, and the exact answer should not lose to it.
    if not hits and not _following_alias:
        for cited, other in ALSO_KNOWN_AS.items():
            if k == norm(cited):
                for f, _ in have(other, _following_alias=True):
                    hits.append((shelf_rank(f), TIER.get(f.suffix.lower(), 9), -_size(f), f,
                                 f"also published as “{other}”"))
                break

    # THE SUBTITLE GAP, BOTH SIDES OF THE COLON. A citation gives the
    # subtitle; a filename often does not, so the whole cited run never fits
    # inside a name that stops at the colon. And a shelf may file a book under
    # its running subtitle instead. Only when the full title finds nothing,
    # main title first (the likelier filename), and every hit is labelled so
    # a reader can see the rest of the title went unchecked.
    #
    # A one-word main title is allowed, and the safety is elsewhere: the match
    # must be the WHOLE filename segment. A first attempt set a three-word
    # floor and hid three of the five books it was written to find, because
    # norm() strips articles and a two-word title measures one word.
    parts = [p for p in re.split(r"[:;]|\s+—\s+|\s+-\s+", title) if norm(p)]
    for which, main in ([("main title", norm(parts[0])),
                         ("subtitle", norm(parts[-1]))] if len(parts) > 1 else []):
        if hits:
            break
        words = main.split()
        short = len(words) < 3
        # A SHORT SUBTITLE IS NOT A TITLE. A subtitle is often a stock phrase,
        # and a two-word subtitle once returned HAVE for a book the library did
        # not hold, led by an unrelated book whose whole title was that phrase.
        # A NOT BY NAME sends a reader to the next search. A wrong HAVE puts the
        # wrong book in a footnote. That is the right trade.
        if which == "subtitle" and short:
            continue
        for stem, f in (files() if main and main != k else []):
            segs = segments(f.stem)
            ok = (any(sw == words for sw in segs) if short
                  else (title_matches(main, f.stem) or main == stem))
            if not ok:
                continue
            hits.append((shelf_rank(f), TIER.get(f.suffix.lower(), 9), -_size(f), f,
                         f"{which.upper()} ONLY — the rest of the title was "
                         f"not checked: “{main}”"))

    hits.sort(key=lambda h: (h[0], h[1], h[2], str(h[3])))
    seen, out = set(), []
    for _, _, _, f, how in hits:
        if str(f) in seen:
            continue
        seen.add(str(f))
        out.append((f, how))
    return out


def rel(f):
    try:
        return Path(f).relative_to(LIB)
    except (ValueError, TypeError):
        return f


def no_library():
    roots = [str(r) for r in B.LIBRARY_ROOTS] or ["(none set)"]
    print("\n  NO LIBRARY FOUND. None of the roots in book.toml [library] roots")
    print("  exists on this machine:")
    for r in roots:
        print(f"      {r}")
    print("\n  This is a fact about the settings, never about the books. Nothing")
    print("  was searched, so nothing may be recorded as absent.")
    sys.exit(2)


def audit():
    """Every work a Claims file records as absent, re-tested against the shelf."""
    import citedworks as W
    wrong = []
    for jf, _n, o in W.claims_rows():
        t = (o.get("title") or "").strip()
        if not t or (o.get("drive_path") or "").strip() or o.get("not_a_work"):
            continue
        blob = " ".join(str(o.get(x) or "") for x in
                        ("states", "location", "path_unresolved"))
        if not re.search(r"not on the drive|not in the library|NOT_ON_DRIVE|"
                         r"NOT_IN_LIBRARY|sources wanted|absent|no copy", blob, re.I):
            continue
        found = have(t)
        if found:
            wrong.append((jf.stem, t, found[0][0], found[0][1]))
    print(f"\n{len(wrong)} work(s) recorded as absent that this search FINDS:\n")
    for src, t, f, how in wrong:
        print(f"  {src:<8} {t[:46]:<48}")
        print(f"           -> {rel(f)}  ({how})")
    if not wrong:
        print("  none — every declared absence holds up.")


def main():
    if LIB is None:
        no_library()
    if "--reindex" in sys.argv:
        files(rebuild=True)
        print(f"indexed {len(_FILES):,} files across {len(SHELVES)} shelves "
              f"-> {CACHE}")
        return
    if "--audit" in sys.argv:
        audit()
        return

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__.split("WHY")[0])
        return
    q = " ".join(args)
    found = have(q)
    print(f"\n{q}\n")
    if not found:
        print(f"  NOT BY NAME — searched {len(files()):,} files across "
              f"{len(SHELVES)} shelves and "
              f"{len(manifest_titles()):,} manifest entries in {LIB}.\n")
        print("  BEFORE DRAWING ANY CONCLUSION FROM THIS: SAY YOU ARE STUCK.")
        print(f"  Tell {B.AUTHOR} \"I cannot find X, can you get it?\" in those")
        print("  words. The author's rule: \"I always go get the primary source,")
        print("  and you stop without asking for help.\" A search that missed is")
        print("  a fact about the search, never about the world.\n")
        # A NAME SEARCH IS NOT THE LAST SURFACE, and stopping here is how a book
        # that IS on the shelf gets written down as missing. A filename cannot
        # find a work bound inside a larger volume; a full-text or semantic
        # search can.
        print("  THE NAME SEARCH IS NOT FINISHED. Before writing this down as")
        print("  absent, search the text, which finds a work bound inside a")
        print("  larger one:\n")
        print(f"      tools/find-source.sh \"<a distinctive phrase from the work>\"")
        print(f"      tools/find-source.sh --editions \"{q}\"\n")
        print("  and any semantic index of the library you keep. Only after")
        print("  those may a record say the work is not in the library.")
        return
    print(f"  HAVE — {len(found)} cop{'y' if len(found) == 1 else 'ies'}, best first:\n")
    for f, how in found[:8]:
        print(f"    {rel(f)}")
        if how != "filename":
            print(f"        via {how}")


if __name__ == "__main__":
    main()

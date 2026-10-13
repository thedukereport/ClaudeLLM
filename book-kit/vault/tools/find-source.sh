#!/usr/bin/env python3
"""find-source.sh — look for a passage or a book across the whole library.

    ./find-source.sh "reflection and choice"
    ./find-source.sh "a necessary evil" --limit 20
    ./find-source.sh --editions "Common Sense"   # EVERY copy, best for citation first

WHY --editions EXISTS

    The author, on finding EPUBs used for books the library holds as PDFs:
    "you may actually have the resources, and you're just not looking in the
    right place because you use the first one you find and quit looking."

    The citation rule says an EPUB has no pages, so a note built on one cites
    by chapter or section and gives no page. An agent reading the EPUB writes
    a note with no locator, correctly under the rule. But the same book is
    often on the shelf as a scanned PDF carrying the printed page numbers, and
    nothing told anybody to look. Every other search answers "is it here";
    none answered "is there a BETTER copy here", so the first hit won.

    --editions finds every copy and ranks them by what a citation can be
    built on:

        1  scanned PDF of a print edition    printed page numbers survive
        2  other PDF                         may keep the pagination
        3  EPUB / MOBI / AZW3                no pages; cite by structure
        4  plain or extracted text           no pages, no structure

    Read down from the top. Take the first one that gives a page, not the
    first one that exists.

WHY THIS EXISTS

    The author: "The failures usually happen because some too-narrow grep or
    RegEx fails, and you default to 'it's not here.'"

    Claims were once logged as not in the library on the strength of a search
    BY FILENAME, while the library held an extracted-text cache that a
    filename search never touches. A book inside a collection, catalogued
    under another title, or held only as text is invisible that way.

    A failed lookup is a fact about the QUERY until every surface has been
    tried. This tries them all and says which ones it tried, so "not found"
    means something.

THE SURFACES

    1. `text_cache/` full text     extracted text under hash names, if your
                                   library keeps one (a folder of that name at
                                   the library root)
    2. filenames, every shelf
    3. full text of every plain-text file in the library (.txt .xml .md .html)
    4. a semantic index, if you set `[library] semantic_search` in book.toml
       to a command with {query} in it. The literal surfaces match
       CHARACTERS; a paraphrased passage, a book filed under another title,
       or an OCR'd page where "rn" became "m" are reachable only semantically.

    The text inside PDFs and EPUBs is NOT read here. For a PDF candidate, run
    find-page.sh, which opens it.

READING THE CACHE

    A text_cache file is named by hash, so a hit is identified by reading the
    head of the file. Filenames lie.

WHAT IT DOES NOT DO

    It does not decide whether the passage supports anything. It reports where
    the words are. A hit is a coordinate.
"""
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

LIB = B.library_root()
CACHE = LIB / "text_cache" if LIB else None
TEXTY = (".txt", ".xml", ".md", ".html", ".htm")
SEMANTIC = (B.CONFIG.get("library", {}) or {}).get("semantic_search", "")


def identify(path: Path) -> str:
    """What book is this hash-named file? Read its head."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:400]
    except Exception:
        return "(unreadable)"
    head = re.sub(r"\s+", " ", head).strip()
    # Strip the scanning boilerplate that buries the real title.
    head = re.sub(r"Digitized by the Internet Archive.*?(?=[A-Z]{2})", "", head)
    return head[:130] or "(empty)"


def _pattern(needle: str):
    """Whole-word for a single word, literal for a phrase, whitespace-tolerant.

    Whole-word by default: searching for a short word without word boundaries
    returned longer words that contain it, the same too-narrow/too-loose
    failure this script exists to stop, committed by the script itself on its
    first run. A phrase may break across lines in a text file, so any run of
    whitespace between its words matches.
    """
    words = needle.split()
    if len(words) == 1:
        return re.compile(rf"\b{re.escape(words[0])}\b", re.I)
    return re.compile(r"\s+".join(re.escape(w) for w in words), re.I)


def grep(root: Path, needle: str, limit: int, exclude=None):
    """Files under `root` whose text holds the needle.

    Uses the system grep for speed when the needle is one word or a phrase on
    one line; falls back to reading the files in Python when grep is absent
    or a phrase may span a line break.
    """
    if root is None or not root.is_dir():
        return []
    pat = _pattern(needle)
    out = []
    if shutil.which("grep"):
        if " " not in needle.strip():
            cmd = ["grep", "-rlI", "-i", "-E", rf"\b{re.escape(needle)}\b", str(root)]
        else:
            cmd = ["grep", "-rlI", "-i", "-F", needle, str(root)]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=600).stdout
            out = [Path(p) for p in res.splitlines() if p]
        except Exception:
            out = []
    seen = {str(p) for p in out}
    # Python pass: catches phrases broken across lines, and covers a machine
    # with no grep. Plain-text files only.
    for f in root.rglob("*"):
        if len(out) >= limit * 4:
            break
        if str(f) in seen or not f.is_file() or f.suffix.lower() not in TEXTY:
            continue
        if exclude and exclude in f.parents:
            continue
        try:
            if pat.search(f.read_text(encoding="utf-8", errors="replace")):
                out.append(f)
        except OSError:
            continue
    if exclude:
        out = [p for p in out if exclude not in p.parents]
    return out[:limit]


def context(path: Path, needle: str, width=110) -> str:
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    m = _pattern(needle).search(txt)
    if not m:
        return ""
    s = max(0, m.start() - width)
    return re.sub(r"\s+", " ", txt[s:m.end() + width]).strip()


RANK = [
    (1, "scanned PDF of a print edition", "printed page numbers survive"),
    (2, "PDF", "may keep the pagination — open it and look"),
    (3, "EPUB / MOBI / AZW3", "no pages; cite by chapter or section"),
    (4, "plain or extracted text", "no pages, no structure"),
]


def rank_of(path: Path) -> int:
    s = path.suffix.lower()
    if s == ".pdf":
        n = path.name.lower()
        scanned = any(k in n for k in ("ocr", "scan", "archive", "facsimile",
                                       "reprint", "1st", "first ed"))
        return 1 if scanned else 2
    if s in (".epub", ".mobi", ".azw3", ".azw", ".fb2"):
        return 3
    return 4


def editions(title: str, limit: int = 40):
    """Every copy of a work in the library, best-for-citation first.

    Matching is on the words of the title, not the whole string, because the
    same book is filed under a subtitle in one folder and without it in
    another. A search that demanded the exact title found one copy and
    reported it as the only one.
    """
    words = [w for w in re.findall(r"[A-Za-z]{4,}", title.lower())
             if w not in ("the", "and", "with", "from", "that", "their", "this")]
    if not words:
        words = [title.lower()]
    # Score every file, then keep the best. Demanding most of the query's words
    # appear in the filename once reported three books absent that were on the
    # shelf under a shorter or differently punctuated title. And the whole
    # library is searched, not a list of folders: fuller copies turned up in a
    # folder of duplicates.
    scored = []
    for f in LIB.rglob("*"):
        if not f.is_file() or f.suffix == "" or (CACHE and CACHE in f.parents):
            continue
        n = f.name.lower()
        score = sum(1 for w in words if w in n)
        if score:
            scored.append((score, f))
    hits = []
    if scored:
        best = max(s for s, _ in scored)
        # Take the best tier, and the tier below it when the best is thin --
        # a one-word match on a distinctive word is often the right book.
        keep = best if best >= 3 else max(1, best)
        hits = [f for s, f in scored if s >= keep]
    print(f'Every copy of "{title}" in the library, best for citation first.\n')
    if not hits:
        print(f"   no filename match anywhere under {LIB}")
        print("   Try fewer words, the author's surname, or a distinctive phrase")
        print("   through the normal search — filenames lie.")
        return
    for r, label, why in RANK:
        # Biggest first inside a tier. Files have turned out not to be the
        # books their names claim (a photo insert alone, a two-page review),
        # and the fuller copy was larger and filed elsewhere. Size is a weak
        # signal, but it is the one that separates a stub from a book.
        group = sorted((h for h in hits if rank_of(h) == r),
                       key=lambda f: -f.stat().st_size)
        if not group:
            continue
        print(f"  {r}. {label}  — {why}")
        for f in group[:limit]:
            kb = f.stat().st_size / 1e3
            size = f"{kb / 1e3:.0f} MB" if kb >= 1000 else f"{kb:.0f} KB"
            print(f"       {f.relative_to(LIB)}   {size}")
        print()
    best = min(rank_of(h) for h in hits)
    if best >= 3:
        print("  No PDF here. Under the citation rule this work is cited by")
        print("  chapter or section heading, never by a page number.")
    else:
        print("  Cite from the PDF. Do not take a page number from an EPUB or")
        print("  from a converted file, and do not stop at the first copy.")


def semantic_search(needle: str, limit: int = 6):
    """Ask the semantic index. Returns a list of lines, [] for no hit, or None
    if no index is configured or it cannot be run from here."""
    if not SEMANTIC:
        return None
    cmd = SEMANTIC.replace("{query}", shlex.quote(needle)).replace("{k}", str(limit))
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
    except Exception:
        return None
    if out.returncode != 0:
        # A missing package or an index on another machine is the normal case
        # off the author's own computer, and it is not a fact about the query.
        return None
    lines = [s.strip()[:150] for s in out.stdout.splitlines()
             if s.strip() and not s.strip().startswith(("=", "-", "Loading", "Query:"))]
    return lines[:limit * 3]


def main():
    argv = sys.argv[1:]
    limit = 12
    if "--limit" in argv:
        k = argv.index("--limit")
        limit = int(argv[k + 1])
        del argv[k:k + 2]
    args = [a for a in argv if not a.startswith("--")]
    if LIB is None:
        print("NO LIBRARY FOUND. None of the roots in book.toml [library] roots exists")
        print("on this machine. Nothing was searched, so nothing may be recorded as absent.")
        sys.exit(2)
    if "--editions" in sys.argv:
        if not args:
            print('give a title: ./find-source.sh --editions "Common Sense"')
            return
        editions(" ".join(args))
        return
    if not args:
        print(__doc__.split("WHY")[0])
        return
    needle = " ".join(args)

    print(f'Searching the library for: "{needle}"')
    print(f"Root: {LIB}\n")
    found_any = False

    # 1. the extracted-text cache -- the surface filename searches miss
    print("1. text_cache/ — extracted full text")
    if CACHE and CACHE.is_dir():
        hits = grep(CACHE, needle, limit)
        if hits:
            found_any = True
            for h in hits:
                print(f"   {h.name[:12]}…  {identify(h)}")
                c = context(h, needle)
                if c:
                    print(f"       …{c[:150]}…")
        else:
            print(f"   no hit across {sum(1 for _ in CACHE.glob('*'))} cached files")
    else:
        print("   no text_cache/ folder in this library")

    # 2. filenames, every shelf
    print("\n2. filenames, every shelf")
    names = [f for f in LIB.rglob("*")
             if f.is_file() and needle.lower() in f.name.lower()
             and not (CACHE and CACHE in f.parents)]
    if names:
        found_any = True
        for f in names[:limit]:
            print(f"   {f.relative_to(LIB)}")
    else:
        print("   no filename match")

    # 3. full text of the plain-text files
    print("\n3. full text of plain-text files (" + " ".join(TEXTY) + ")")
    hits = grep(LIB, needle, limit, exclude=CACHE)
    if hits:
        found_any = True
        for h in hits:
            print(f"   {h.relative_to(LIB)}")
            c = context(h, needle)
            if c:
                print(f"       …{c[:200]}…")
    else:
        print("   no hit")

    # 4. the semantic index -- the only surface that is not literal
    print("\n4. semantic index")
    sem = semantic_search(needle, limit=6)
    sem_ran = sem is not None
    if sem is None:
        if SEMANTIC:
            print("   could not run the configured index from here:")
            print(f"     {SEMANTIC}")
        else:
            print("   none configured ([library] semantic_search in book.toml)")
    elif sem:
        found_any = True
        for line in sem:
            print("   " + line)
    else:
        print("   no semantic hit")

    unread = sum(1 for f in LIB.rglob("*")
                 if f.is_file() and f.suffix.lower() in (".pdf", ".epub", ".mobi", ".azw3"))
    print("\n" + "-" * 68)
    if found_any:
        print("FOUND. Open the file before quoting it; a hit is a coordinate.")
        return
    if sem_ran:
        print("NOT FOUND on any surface above, the semantic index included.")
    else:
        # A surface that did not run is not a surface that found nothing. The
        # author: "There should not be one source in this book that you have
        # not opened." A negative taken without every surface is the same
        # defect one level up.
        print("NOT FOUND on the LITERAL surfaces above.")
        print("")
        print("NO SEMANTIC INDEX RAN, so this is not a finished search and must")
        print("not be written down as one.")
    if unread:
        print(f"The text inside {unread} PDF/EPUB file(s) was not read by this search.")
        print("Open a likely candidate with find-page.sh before recording an absence.")
    print("Before writing anything down, also try: a distinctive PHRASE from the")
    print("passage rather than the title; the author's surname alone; a word")
    print("that would survive OCR damage.")
    print("")
    print("For LATIN, try the spelling variants before recording a negative: a")
    print("passage was twice reported missing because an edition spelled one")
    print("vowel differently from the corpus text. Also swap i/j and u/v, which")
    print("a corpus may fold and a raw search does not.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""bookconfig.py — the one place every tool learns where the book lives.

    import bookconfig as B
    B.VAULT, B.CHAPTERS, B.FACT, B.CLAIMS, B.EVENTS, B.LIBRARY_ROOTS ...
    B.chapter_files()        every chapter file, backups left out
    B.chapter_file(5)        the file for chapter 5, or None
    B.chapter_number(path)   5 for "Chapter 05 - Title.md"
    B.ledger_file(5)         the chapter's fact-check ledger (one, or it stops)
    B.claims_file(5)         Fact Check/Claims/Ch 05.jsonl
    B.coord(5, 112)          "Ch05/L112"

WHERE THE SETTINGS COME FROM

    `book.toml` at the top of the vault (copy `book.toml.example` and fill it
    in). The vault is found in this order: the BOOK_VAULT environment
    variable; else the folder above `tools/`. Tests point BOOK_VAULT at a copy
    of the sample vault, so no test ever touches your real book.

WHY ONE FILE

    The system this kit comes from had its folder paths and chapter names
    typed into some eighty scripts. When the library drive moved, six scripts
    fell back to a path that no longer existed and reported books missing that
    were on the shelf. One settings file means one place to change, and a
    script that cannot find a setting stops and says which one.

FILE NAMES THE TOOLS EXPECT (change the patterns in book.toml if yours differ)

    Chapters/Chapter 01 - Title.md         one file per chapter
    Fact Check/Ch. 01 — Title.md           one ledger per chapter
    Fact Check/Claims/Ch 01.jsonl          one Claims file per chapter
    Fact Check/events/2026-10.jsonl        the event log, one file per month
"""
import os
import re
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
VAULT = Path(os.environ.get("BOOK_VAULT") or TOOLS.parent).resolve()


def _parse_toml(text):
    """A small reader for the subset book.toml uses: [sections], key = "string",
    numbers, true/false, and one-line lists. Used only when tomllib is absent
    (Python 3.10)."""
    data, cur = {}, None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip() if not raw.strip().startswith('"') else raw.strip()
        if not line:
            continue
        m = re.match(r"^\[([A-Za-z0-9_.-]+)\]$", line)
        if m:
            cur = data.setdefault(m.group(1), {})
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        tgt = cur if cur is not None else data
        tgt[k] = _value(v)
    return data


def _value(v):
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_value(x.strip()) for x in re.findall(r'"[^"]*"|[^,\s][^,]*', inner)] if inner else []
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1].replace('\\"', '"')
    if v in ("true", "false"):
        return v == "true"
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def _load():
    p = VAULT / "book.toml"
    if not p.exists():
        raise SystemExit(
            f"No book.toml in {VAULT}. Copy book.toml.example to book.toml and fill it in "
            f"(or set BOOK_VAULT to the vault folder).")
    text = p.read_text(encoding="utf-8")
    try:
        import tomllib  # Python 3.11+
        return tomllib.loads(text)
    except ModuleNotFoundError:
        return _parse_toml(text)


CONFIG = _load()
_book = CONFIG.get("book", {})
_paths = CONFIG.get("paths", {})
_lib = CONFIG.get("library", {})
_page = CONFIG.get("page", {})
_wf = CONFIG.get("workflow", {})
_out = CONFIG.get("output", {})


def need(section, key):
    """A setting the calling tool cannot work without."""
    v = CONFIG.get(section, {}).get(key)
    if v in (None, "", []):
        raise SystemExit(f"book.toml has no [{section}] {key}. This tool needs it.")
    return v


def _vpath(key, default):
    return VAULT / _paths.get(key, default)


TITLE = _book.get("title", "Untitled book")
AUTHOR = _book.get("author", "the author")          # how the tools refer to you in messages
AUTHOR_ACTOR = _book.get("author_actor", "author")  # the actor name your rulings carry in the event log

CHAPTERS = _vpath("chapters", "Chapters")
APPENDICES = _vpath("appendices", "Appendices")
FACT = _vpath("fact_check", "Fact Check")
CLAIMS = _vpath("claims", "Fact Check/Claims")
EVENTS = _vpath("events", "Fact Check/events")
HANDOFFS = _vpath("handoffs", "Handoffs")
METHODOLOGY = _vpath("methodology", "Methodology")
SNAPSHOT = _vpath("page_snapshot", "Handoffs/editor-tools/page-snapshot")
CARDS = _vpath("card_reads", "Handoffs/editor-tools/cards")
WORD_LISTS = METHODOLOGY / "Word Lists.md"
ASKS = FACT / "Asks.md"
LOCKS = FACT / "Locks.md"
PUNCH_LIST = VAULT / _paths.get("punch_list", "Punch List.md")
UAT_LOG = METHODOLOGY / "UAT Log.md"

CHAPTER_GLOB = _book.get("chapter_glob", "Chapter [0-9][0-9]*.md")
CHAPTER_NUM_RE = re.compile(_book.get("chapter_number_regex", r"^Chapter\s+0*(\d+)"))
LEDGER_GLOB = _book.get("ledger_glob", "Ch. {nn} — *.md")

def _abs(p):
    q = Path(os.path.expanduser(p))
    return q if q.is_absolute() else (VAULT / q)


LIBRARY_ROOTS = [_abs(p) for p in _lib.get("roots", [])]   # a relative root is read from the vault
CHECKED_SHELF = _lib.get("checked_shelf", "")   # a subfolder you have checked by hand, read first
LIBRARY_INDEX = FACT / _lib.get("index_file", "Library Index.json")

PAGE_URL = _page.get("url", "")
OUT_OF_WORKFLOW = set(int(x) for x in _wf.get("out_of_workflow", []))
PDF_OUT = _abs(_out["pdf_dir"]) if _out.get("pdf_dir") else None
SNAPSHOT_DEST = _abs(_out["snapshot_dir"]) if _out.get("snapshot_dir") else None


def is_backup(p) -> bool:
    """One exclusion, shared by every tool that globs your files. A glob that
    reads its own backups invents work: twice, in the system this kit comes
    from, a count came from the .bak copies beside the live files."""
    n = Path(p).name
    return ".bak" in n or n.startswith("_") or n.startswith(".") or "backup" in n.lower()


def library_root():
    """The first library root that exists on this machine, or None."""
    return next((r for r in LIBRARY_ROOTS if r.is_dir()), None)


def chapter_number(path):
    m = CHAPTER_NUM_RE.match(Path(path).name)
    return int(m.group(1)) if m else None


def chapter_files():
    if not CHAPTERS.is_dir():
        return []
    return sorted((p for p in CHAPTERS.glob(CHAPTER_GLOB) if not is_backup(p)),
                  key=lambda p: (chapter_number(p) or 0, p.name))


def chapter_file(n):
    return next((p for p in chapter_files() if chapter_number(p) == int(n)), None)


def ledger_file(n, must=True):
    hits = [p for p in FACT.glob(LEDGER_GLOB.format(nn=f"{int(n):02d}", n=int(n))) if not is_backup(p)]
    if len(hits) == 1:
        return hits[0]
    if not must:
        return hits[0] if hits else None
    raise SystemExit(f"Ch{int(n):02d}: expected one ledger matching '{LEDGER_GLOB}', found {len(hits)}: "
                     f"{[h.name for h in hits]}. Which one is the ledger is not a guess.")


def claims_file(n):
    return CLAIMS / f"Ch {int(n):02d}.jsonl"


def coord(n, line):
    return f"Ch{int(n):02d}/L{int(line)}"


if __name__ == "__main__":
    print(f"vault        {VAULT}")
    print(f"book         {TITLE} — {AUTHOR}")
    print(f"chapters     {CHAPTERS}  ({len(chapter_files())} files)")
    print(f"fact check   {FACT}")
    print(f"library      {library_root() or 'none found of ' + str([str(r) for r in LIBRARY_ROOTS])}")
    print(f"page         {PAGE_URL or '(not set)'}")
    print(f"out of workflow: {sorted(OUT_OF_WORKFLOW) or 'none'}")

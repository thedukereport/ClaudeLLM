#!/usr/bin/env python3
"""find-page.sh — what page is this passage on, in the PRINT edition?

    ./find-page.sh "Common Sense" "a necessary evil"
    ./find-page.sh --file "PDF/Thomas Paine - Common Sense.pdf" "a phrase"
    ./find-page.sh "Common Sense" "a necessary evil" --context 400

    A --file path may be absolute or relative to the library root.

WHY THIS EXISTS

    The author: "I caught you using ePubs for books we have as PDFs, so you
    may actually have the resources, and you're just not looking in the right
    place because you use the first one you find and quit looking."

    The citation rule forbids inventing a page number for an EPUB, and it is
    right to. But the rule was doing work it was never meant to do: agents
    reached for the EPUB, correctly declined to give a page, and the note went
    out anchored on nothing, while the scanned PDF of the same book, carrying
    the printed pagination, was on the shelf.

    So: `./find-source.sh --editions "<title>"` says which copy to open. This
    file opens it and reports the page.

WHAT "PAGE" MEANS HERE, AND THE TRAP IN IT

    A PDF has two numbers for every leaf: the PDF's own sheet index, and the
    number printed on the paper. They differ by the front matter (title page,
    copyright, contents, preface) and a citation must use the PRINTED one.

    This reports both. It reads the printed folio off the head and foot of the
    page when one is there, and says so. Where it finds none, it reports the
    sheet index and says the printed number is unconfirmed, because a sheet
    index written into a footnote is a fiction.

WHAT IT NEEDS TO READ A PDF

    The Python package `pdfplumber` (pip install pdfplumber), or, failing
    that, the `pdftotext` command from poppler-utils. With neither, it says
    so and stops: a PDF it cannot open says nothing about the book.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

LIB = B.library_root()

# A folio on its own line, and a folio at the edge of a running head or foot.
#
# The bare-line form alone missed most scanned academic books, where the page
# number shares its line with the running title ("38 | The Title of the
# Chapter"), and OCR turns the rule into an i or an l. Requiring a line of
# nothing but digits reported "no printed folio" on a book that prints one on
# every page.
FOLIO_ALONE = re.compile(r"^\s*\[?(\d{1,4}|[ivxlcdm]{1,7})\]?\s*$", re.I)
FOLIO_HEAD = re.compile(r"^\s*\[?(\d{1,4})\]?\s*[|│il]?\s+[A-Z(]")
# A running head is often ALL CAPS, and the folio is printed to its right. A
# character class that demanded a lowercase letter before the number read
# "RUNNING HEAD 429" as no folio at all, and an agent was sent away from a
# book that paginates on every page. Any letter now qualifies; a bare year is
# excluded instead, since a date at the end of a line is the false positive
# that class was guarding against.
FOLIO_TAIL = re.compile(r"[A-Za-z.,)”]\s+[|│il]?\s*\[?(\d{1,4})\]?\s*$")
YEARISH = re.compile(r"^(1[5-9]\d\d|20[0-4]\d)$")


class NoReader(Exception):
    pass


def pick(title: str):
    """The best PDF for the title. The checked shelf first; anything else is
    a fallback, and this says so when it has to fall back.

    The author, on the shelf he had curated by hand for months: that is the
    library. Three faults were in the first version, and all three were
    heuristics nobody asked him about:

      1. A third "shelf" that was one author's folder, promoted to the same
         standing as the curated library.
      2. A match that accepted a filename holding all but two of the title's
         words, so a two-word title matched on nothing at all. The same
         threshold, used elsewhere, pointed several records at the wrong book.
      3. Ranking what survived BY FILE SIZE, on the idea that a bigger file
         is a fuller scan. The author, seeing it: "File size???"

    What it does now: every title word must be in the filename, the checked
    shelf is searched alone, and a hit elsewhere is returned only when the
    checked shelf has none, labelled so the caller can say where it came from.
    """
    words = [w for w in re.findall(r"[A-Za-z]{4,}", title.lower())
             if w not in ("the", "and", "with", "from", "that", "their", "this")]
    if not words or LIB is None:
        return []

    def scan(root, deep=True):
        if not root.is_dir():
            return []
        it = root.rglob("*") if deep else root.iterdir()
        out = [f for f in it if f.is_file() and f.suffix.lower() == ".pdf"
               and all(w in f.name.lower() for w in words)]   # EVERY word
        return sorted(out, key=lambda f: f.name)

    checked = LIB / B.CHECKED_SHELF if B.CHECKED_SHELF else None
    if checked is not None:
        hits = scan(checked)
        if hits:
            return hits[:4]
    others = sorted(d for d in LIB.iterdir()
                    if d.is_dir() and d != checked and not d.name.startswith("."))
    for shelf in others:
        found = scan(shelf)
        if found:
            if checked is not None:
                print(f"  NOT ON THE CHECKED SHELF ({B.CHECKED_SHELF}/). Falling back to "
                      f"{shelf.name}/ — the checked shelf has no PDF of this title.")
            return found[:4]
    return scan(LIB, deep=False)[:4]


def printed_folio(page_text: str):
    """The number printed on the paper, read off the first and last lines.

    Returns (folio, where it was found) so a caller can report the evidence.
    A folio sharing its line with a running title is the normal case in a
    scanned academic book, not an exception.
    """
    lines = [l.strip() for l in page_text.splitlines() if l.strip()]
    for cand in (lines[:1] + lines[-1:]):
        m = FOLIO_ALONE.match(cand)
        if m:
            return m.group(1), "on its own line"
    for cand in (lines[:1] + lines[-1:]):
        m = FOLIO_HEAD.match(cand)
        if m:
            return m.group(1), "beside the running title"
        m = FOLIO_TAIL.search(cand)
        if m and not YEARISH.match(m.group(1)):
            return m.group(1), "at the foot or beside the running head"
    return None, None


def pages(pdf: Path):
    """The text of each page, in order. pdfplumber first, pdftotext second."""
    try:
        import pdfplumber
    except ImportError:
        pdfplumber = None
    if pdfplumber is not None:
        with pdfplumber.open(pdf) as doc:
            return [page.extract_text() or "" for page in doc.pages]
    if shutil.which("pdftotext"):
        out = subprocess.run(["pdftotext", "-layout", str(pdf), "-"],
                             capture_output=True, text=True, timeout=600)
        if out.returncode != 0:
            raise RuntimeError(out.stderr.strip()[:200] or "pdftotext failed")
        text = out.stdout
        return text.split("\f")[:-1] if text.endswith("\f") else text.split("\f")
    raise NoReader()


def search(pdf: Path, phrase: str, context: int):
    needle = re.sub(r"\s+", " ", phrase).lower()
    loose = re.compile(r"\s+".join(re.escape(w) for w in needle.split()), re.I)
    found = []
    for i, txt in enumerate(pages(pdf), 1):
        flat = re.sub(r"[-‐‑]\s*\n\s*", "", txt)
        flat = re.sub(r"\s+", " ", flat)
        m = loose.search(flat)
        if not m:
            continue
        folio, how = printed_folio(txt)
        s = max(0, m.start() - context // 2)
        found.append((i, folio, how, flat[s:m.end() + context // 2]))
    return found


def main():
    argv = sys.argv[1:]
    context = 260
    if "--context" in argv:
        k = argv.index("--context")
        context = int(argv[k + 1])
        del argv[k:k + 2]
    if "--file" in argv:
        k = argv.index("--file")
        p = Path(argv[k + 1])
        if not p.is_absolute() and LIB is not None:
            p = LIB / p
        pdfs, phrase = [p], argv[k + 2] if len(argv) > k + 2 else ""
    else:
        args = [a for a in argv if not a.startswith("--")]
        if len(args) < 2:
            print(__doc__.split("WHY")[0])
            return
        if LIB is None:
            print("NO LIBRARY FOUND. None of the roots in book.toml [library] roots exists")
            print("on this machine. Nothing was searched.")
            sys.exit(2)
        pdfs, phrase = pick(args[0]), args[1]
        if not pdfs:
            print(f'no PDF in the library matching every word of "{args[0]}"')
            print("run:  ./find-source.sh --editions \"" + args[0] + '"')
            return

    for pdf in pdfs:
        print(f"\n{pdf.parent.name}/{pdf.name}")
        try:
            hits = search(pdf, phrase, context)
        except NoReader:
            print("   CANNOT READ PDFs ON THIS MACHINE: neither the Python package")
            print("   pdfplumber nor the pdftotext command is installed.")
            print("   Install one (pip install pdfplumber, or poppler-utils) and run")
            print("   this again. This says nothing about the book or the passage.")
            sys.exit(2)
        except Exception as e:
            print(f"   could not read: {e}")
            continue
        if not hits:
            print("   phrase not on any page of this copy")
            continue
        for sheet, folio, how, frag in hits[:6]:
            if folio:
                print(f"   PRINTED PAGE {folio}   ({how}; PDF sheet {sheet})")
            else:
                print(f"   PDF sheet {sheet} — no printed folio on the page; "
                      "do NOT cite this number")
            print(f"       …{frag.strip()}…")
        return


if __name__ == "__main__":
    main()

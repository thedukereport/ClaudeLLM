#!/usr/bin/env python3
"""check-ellipsis.sh — print the words an ellipsis took out of a quotation, when the source is in the library.

    tools/check-ellipsis.sh 27            # one chapter
    tools/check-ellipsis.sh --all         # every chapter (the same as no number)
    tools/check-ellipsis.sh --all --list  # coordinates only, no source opening
    tools/check-ellipsis.sh 27 --max 400  # widen the cut it will print

WHY THIS EXISTS

    Twice in the original book a quotation was cut at the point where the
    source turns around. In one case the quotation stopped just before the
    speaker's own reason, given in the very next sentence of the source.
    Stopped early, the passage read as a man hiding the clause that unmakes
    his promise. Read whole, he declined the clause as redundant, and the
    writer, who was in the room, took his side.

    The author, on being shown that: "Do we need to scan all ellipsis now?"
    The book had 101 ellipses with words on both sides.

WHAT A MACHINE CAN AND CANNOT DO HERE

    IT CANNOT judge. Whether the elided words qualify, reverse, or merely
    shorten is a reading, and only a reader who knows what the quotation is
    being used to PROVE can make it.

    IT CAN do the expensive half. Given the words before the ellipsis and the
    words after it, this opens the source in the library, finds both, and
    prints everything between them. That turns 101 source-openings into 101
    short reads, each with the cut already on the page.

    So the output is a worksheet, not a verdict. Every row says RECOVERED,
    NOT FOUND, or NO SOURCE, and a person rules on the RECOVERED ones:
      compression    the cut only shortens;
      qualification  the cut limits the claim, so the quotation grows to take
                     it back in;
      reversal       the cut goes against the use the paragraph makes of it,
                     which changes what the section argues.

HOW IT FINDS THE SOURCE

    The note on the quotation names the work in italics. The work's file is
    found, in this order: the `drive_path` of a Claims row whose `title`
    matches (an absolute path, or a path relative to a library root); then a
    file in a library root whose name holds the title. NO SOURCE means
    neither found a file.

THE WHITESPACE LESSON, WHICH IS WHY THIS TOOL EXISTS AT ALL

    The first search for a phrase from the source reported it ABSENT from the
    whole book. It was there. The line broke between two of its words, and a
    plain substring search cannot see across the break. A failed lookup is a
    fact about the query, and this rule was nearly broken by the tool written
    to enforce it.

    So EVERY comparison here runs on text with all whitespace collapsed to
    single spaces and curly quotes, dashes and ligatures folded to ASCII. A
    tool that searches raw extracted text will lie to you.

NEEDS
    Python standard library for .txt, .md and .epub sources. Reading a .pdf
    needs the `pypdf` package; without it a PDF source reports NO SOURCE with
    the reason.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

VAULT = B.VAULT
CACHE = VAULT / ".ellipsis-cache"
SOURCE_SUFFIXES = (".pdf", ".txt", ".md", ".epub")

ELL = re.compile(r"(…|\.\s?\.\s?\.)")
QUOTE = re.compile(r"[“\"]([^”\"]{25,3000})[”\"]")
NOTEREF = re.compile(r"\[\^([A-Za-z0-9_\-]+)\]")


def flat(s: str) -> str:
    """Collapse a string to something two copies of the same sentence share.

    Whitespace to single spaces: this is the line-break lesson above. Curly
    quotes, dashes and ligatures to ASCII, because a PDF and a markdown file
    will not agree on them. Case folded.
    """
    s = unicodedata.normalize("NFKD", s)
    s = (s.replace("‘", "'").replace("’", "'")
           .replace("“", '"').replace("”", '"')
           .replace("—", "-").replace("–", "-")
           .replace("‐", "-").replace("­", ""))
    s = re.sub(r"[^\x00-\x7f]", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def source_text(path: Path) -> str:
    """The whole source as one flat string, cached in .ellipsis-cache/.

    STREAMED, NOT LOADED. Holding every page of a 1,300-page PDF in memory
    killed the process twice in the original system. pypdf a page at a time
    costs seconds and survives.
    """
    CACHE.mkdir(exist_ok=True)
    key = CACHE / (re.sub(r"[^A-Za-z0-9]+", "_", path.stem)[:120] + ".txt")
    if key.exists():
        return key.read_text(encoding="utf-8", errors="replace")
    out = []
    try:
        if path.suffix.lower() == ".pdf":
            import pypdf
            r = pypdf.PdfReader(str(path))
            for i in range(len(r.pages)):
                try:
                    out.append(r.pages[i].extract_text() or "")
                except Exception:
                    pass
        elif path.suffix.lower() in (".txt", ".md"):
            out.append(path.read_text(encoding="utf-8", errors="replace"))
        elif path.suffix.lower() == ".epub":
            import zipfile
            with zipfile.ZipFile(path) as z:
                for n in z.namelist():
                    if n.lower().endswith((".xhtml", ".html", ".htm")):
                        out.append(re.sub(r"<[^>]+>", " ",
                                          z.read(n).decode("utf-8", "replace")))
    except Exception as e:
        return f"__ERROR__ {e}"
    t = flat("\n".join(out))
    # Every write goes through vaultlog, the one door that logs it.
    import vaultlog
    vaultlog.write_file(key, t, tool="check-ellipsis.sh", why="source text cache", backup=False)
    return t


def ledger_paths():
    """{flattened title: drive_path} for every work the Claims files place in the library."""
    out = {}
    if not B.CLAIMS.is_dir():
        return out
    for f in sorted(B.CLAIMS.glob("*.jsonl")):
        if B.is_backup(f):
            continue
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            t, p = (o.get("title") or "").strip(), (o.get("drive_path") or "")
            if t and p:
                out.setdefault(flat(t), p)
    return out


def library_files():
    """{flattened file stem: path} for every readable source under the library roots."""
    out = {}
    for root in B.LIBRARY_ROOTS:
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() in SOURCE_SUFFIXES and not B.is_backup(p):
                out.setdefault(flat(p.stem), p)
    return out


def resolve(p):
    """A Claims drive_path as a file on this machine, or None."""
    q = Path(p).expanduser()
    if q.is_absolute():
        return q if q.exists() else None
    for root in B.LIBRARY_ROOTS:
        if (root / q).exists():
            return root / q
    return (VAULT / q) if (VAULT / q).exists() else None


ITALIC = re.compile(r"(?<!\*)\*(?!\*)([^*\n]{6,120})\*(?!\*)")


def note_source(note_body: str, paths: dict, files: dict = None):
    """(file, title) for the work a note cites, or (None, None).

    `paths` is ledger_paths(); `files` is library_files(). The Claims row wins
    when it names a file that opens.
    """
    files = files or {}
    for m in ITALIC.finditer(note_body):
        k = flat(m.group(1))
        if k in paths and resolve(paths[k]):
            return resolve(paths[k]), m.group(1)
        for t, p in paths.items():
            if len(k) > 12 and (k in t or t in k) and resolve(p):
                return resolve(p), m.group(1)
    for m in ITALIC.finditer(note_body):
        k = flat(m.group(1))
        if len(k) < 8:
            continue
        for stem, p in files.items():
            if k in stem:
                return p, m.group(1)
    return None, None


def notes_of(text: str):
    """{slug: note text, continuation lines included}."""
    out = {}
    for m in re.finditer(r"(?m)^\[\^([A-Za-z0-9_\-]+)\]:(.*(?:\n(?!\[\^|\n).*)*)", text):
        out[m.group(1)] = m.group(2)
    return out


def find_cut(src: str, head: str, tail: str, cap: int):
    """Everything between the last words before the ellipsis and the first after.

    Returns (cut, head anchor, tail anchor), or (None, None, None). Both
    anchors are shortened from the outside in until they are found, because a
    quotation often starts mid-sentence and its first words may have an
    editorial capital the source does not have.
    """
    for hlen in (14, 10, 7, 5):
        h = " ".join(flat(head).split()[-hlen:])
        if len(h) < 12:
            continue
        i = src.find(h)
        if i < 0:
            continue
        for tlen in (14, 10, 7, 5):
            t = " ".join(flat(tail).split()[:tlen])
            if len(t) < 12:
                continue
            j = src.find(t, i + len(h))
            if 0 <= j - (i + len(h)) <= cap:
                return src[i + len(h):j].strip(), h, t
    return None, None, None


def interior_ellipses(text):
    """[(line, slug, head, tail)] for every ellipsis with words on both sides of it."""
    rows = []
    for ln, line in enumerate(text.splitlines(), 1):
        for qm in QUOTE.finditer(line):
            q = qm.group(1)
            for e in ELL.finditer(q):
                if not (e.start() > 3 and e.end() < len(q) - 3):
                    continue
                head, tail = q[:e.start()], q[e.end():]
                slug = None
                m = NOTEREF.search(line[qm.end():qm.end() + 60])
                if m:
                    slug = m.group(1)
                elif line.startswith("[^"):
                    slug = re.match(r"\[\^([A-Za-z0-9_\-]+)\]", line).group(1)
                rows.append((ln, slug, head, tail))
    return rows


def main():
    args = sys.argv[1:]
    nums = {int(a) for a in args if a.isdigit()}
    cap = 400
    if "--max" in args:
        cap = int(args[args.index("--max") + 1])
    listing = "--list" in args
    paths = ledger_paths()
    files = library_files()

    print("\n  Ellipses with words on BOTH sides. One at the end of a quotation")
    print("  is compression; one in the middle can hide a reversal.\n")
    if not listing:
        print(f"  Claims rows name a library file for {len(paths)} work(s); "
              f"the library roots hold {len(files)} readable file(s).")
        print("  Opening sources. The first run on a big book takes a minute; cached after.\n")

    tally = {"RECOVERED": 0, "NOT FOUND": 0, "NO SOURCE": 0}
    for f in B.chapter_files():
        n = B.chapter_number(f)
        if nums and n not in nums:
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        notes = notes_of(text)
        rows = interior_ellipses(text)
        if not rows:
            continue
        print(f"--- Ch{n:02d}: {len(rows)} interior ellipsis/es")
        for ln, slug, head, tail in rows:
            tag = B.coord(n, ln)
            body = notes.get(slug, "") if slug else ""
            fp, title = note_source(body, paths, files) if body else (None, None)
            if listing or not fp:
                if not listing:
                    tally["NO SOURCE"] += 1
                print(f"    {tag:<12} [^{slug or '?'}]  {'listed' if listing else 'NO SOURCE'}")
                print(f"       ...{head.strip()[-60:]}  [CUT]  {tail.strip()[:60]}...")
                continue
            src = source_text(fp)
            if src.startswith("__ERROR__"):
                tally["NO SOURCE"] += 1
                print(f"    {tag:<12} [^{slug}]  NO SOURCE — {src[:80]}")
                continue
            cut, h, t = find_cut(src, head, tail, cap)
            if cut is None:
                tally["NOT FOUND"] += 1
                print(f"    {tag:<12} [^{slug}]  NOT FOUND in {fp.name[:44]}")
                print(f"       ...{head.strip()[-56:]}  [CUT]  {tail.strip()[:56]}...")
            else:
                tally["RECOVERED"] += 1
                print(f"    {tag:<12} [^{slug}]  RECOVERED from {fp.name[:44]} — "
                      f"{len(cut.split())} word(s) cut")
                print(f"       before: ...{head.strip()[-56:]}")
                print(f"       ** CUT: {cut[:cap]}")
                print(f"       after : {tail.strip()[:56]}...")
            print()
    if not listing:
        print(f"\n  RECOVERED {tally['RECOVERED']}   NOT FOUND {tally['NOT FOUND']}"
              f"   NO SOURCE {tally['NO SOURCE']}")
    print("\n  A RECOVERED row is a coordinate, not a verdict. Read the cut against")
    print("  what the quotation is being used to prove. Most ellipses are honest")
    print("  compression; the two that were not, were not obvious from the quote.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

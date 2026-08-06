#!/usr/bin/env python3
"""
Latin Resources — MCP Server
Exposes the local Latin corpus (Perseus TEI XML: Virgil, Horace, Cicero,
Caesar, Livy, Tacitus, Seneca, Lucretius, Juvenal, Sallust, Suetonius,
Pliny the Elder, Jerome, Tertullian, + Latin Library text files) as MCP
tools: full-corpus substring search and reference-addressed passage
retrieval.

Run with:
    /usr/bin/python3 /Volumes/PRO-BLADE/Alexandria/Latin-resources/latin_mcp_server.py

CLI test mode (no MCP):
    latin_mcp_server.py index                      # (re)build the corpus index
    latin_mcp_server.py search armiger [--author virgil] [--max 25]
    latin_mcp_server.py passage virgil Aeneid 5.250-257
    latin_mcp_server.py authors

Stdlib only. Same newline-delimited JSON-RPC stdio pattern as
greek_mcp_server.py and alexandria_mcp_server.py.

Project rule this server enforces (Transcription Gate, Latin extension):
Latin text is TRANSCRIBED from these tools, never generated from memory.
The server quotes; Claude translates the quoted text in prose and marks
the translation as its own.
"""

import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
INDEX = HERE / "latin-corpus-index.jsonl"
LEXICON = HERE / "lewis_short.sqlite"   # Lewis & Short (Perseus lexica, CC BY-SA 4.0)
CHUNK = 12  # verse lines per index segment


# ── text utilities ──────────────────────────────────────────────────

def fold(s):
    """Lowercase, strip diacritics, normalize u/v and i/j for search."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("v", "u").replace("j", "i")
    return s


def strip_tags(el):
    """All visible text inside an element, whitespace-normalized."""
    txt = "".join(el.itertext())
    return re.sub(r"\s+", " ", txt).strip()


def strip_ns(tag):
    return tag.split("}")[-1] if "}" in tag else tag


# ── corpus discovery and parsing ────────────────────────────────────

def discover_authors():
    out = []
    for d in sorted(HERE.iterdir()):
        if d.is_dir() and (d / "manifest.json").exists():
            try:
                m = json.loads((d / "manifest.json").read_text())
            except Exception:
                continue
            out.append((d.name, m))
    return out


def parse_tei(path):
    """Yield (location, text) segments from one Perseus TEI file.

    Verse: <l n="..."> lines grouped CHUNK at a time inside their div
    hierarchy.  Prose: each <p> under its div hierarchy.  Div labels use
    the n= attribute of numbered textparts (book/chapter/section/poem)."""
    try:
        root = ET.parse(str(path)).getroot()
    except ET.ParseError:
        return
    body = None
    for el in root.iter():
        if strip_ns(el.tag) == "body":
            body = el
            break
    if body is None:
        return

    def walk(el, divpath):
        buf, buf_first, buf_last = [], None, None

        def flush():
            nonlocal buf, buf_first, buf_last
            if buf:
                loc = ".".join(divpath) if divpath else "—"
                if buf_first is not None:
                    loc = f"{loc}.{buf_first}" + (
                        f"-{buf_last}" if buf_last != buf_first else "")
                yield_segments.append((loc, " ".join(buf)))
                buf, buf_first, buf_last = [], None, None

        for child in el:
            tag = strip_ns(child.tag)
            if tag == "div" or tag.startswith("div"):
                for _ in flush() or ():
                    pass
                n = child.get("n")
                sub = child.get("subtype") or child.get("type") or ""
                if n and sub not in ("edition", "translation"):
                    walk(child, divpath + [n])
                else:
                    walk(child, divpath)
            elif tag == "l":
                n = child.get("n")
                txt = strip_tags(child)
                if not txt:
                    continue
                if buf_first is None:
                    buf_first = n or "?"
                buf_last = n or buf_last
                buf.append(txt)
                if len(buf) >= CHUNK:
                    for _ in flush() or ():
                        pass
            elif tag in ("p", "sp", "quote", "said"):
                for _ in flush() or ():
                    pass
                txt = strip_tags(child)
                if txt:
                    loc = ".".join(divpath) if divpath else "—"
                    yield_segments.append((loc, txt))
            else:
                walk(child, divpath)
        for _ in flush() or ():
            pass

    yield_segments = []
    walk(body, [])
    for seg in yield_segments:
        yield seg


def parse_txt(path):
    """Latin Library plain-text transcriptions: paragraph segments."""
    text = path.read_text(errors="replace")
    for i, para in enumerate(re.split(r"\n\s*\n", text), 1):
        para = re.sub(r"\s+", " ", para).strip()
        if len(para) > 40:
            yield (f"¶{i}", para)


# ── index build / search ────────────────────────────────────────────

def build_index():
    n_seg = 0
    with INDEX.open("w", encoding="utf-8") as out:
        for slug, manifest in discover_authors():
            works = manifest.get("works", [])
            for w in works:
                f = HERE / slug / w["file"]
                title = w.get("title", w["file"])
                if not f.exists():
                    continue
                segs = parse_tei(f) if f.suffix == ".xml" else parse_txt(f)
                for loc, txt in segs:
                    rec = {"a": slug, "w": title, "l": loc,
                           "t": txt, "f": fold(txt)}
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    n_seg += 1
        # loose standalone files (Latin Library .txt/.html without manifest)
        for f in sorted(HERE.glob("*.txt")):
            for loc, txt in parse_txt(f):
                rec = {"a": f.stem, "w": f.stem, "l": loc,
                       "t": txt, "f": fold(txt)}
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_seg += 1
    return f"Indexed {n_seg} segments → {INDEX.name}"


def ensure_index():
    if not INDEX.exists():
        build_index()


def search(word, author=None, max_results=25):
    ensure_index()
    q = fold(word)
    hits, total = [], 0
    with INDEX.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if author and rec["a"] != author:
                continue
            pos = rec["f"].find(q)
            if pos < 0:
                continue
            total += 1
            if len(hits) < max_results:
                lo, hi = max(0, pos - 120), pos + len(q) + 120
                ctx = rec["t"][lo:hi].strip()
                hits.append(f"[{rec['a']}] {rec['w']} {rec['l']}\n    …{ctx}…")
    if not hits:
        return f"No hits for '{word}'" + (f" in {author}" if author else "")
    head = (f"{total} segment(s) match '{word}'"
            + (f" in {author}" if author else "")
            + f"; showing {len(hits)}:\n\n")
    return head + "\n\n".join(hits)


def authors():
    lines = []
    for slug, manifest in discover_authors():
        works = ", ".join(w.get("title", "?") for w in manifest.get("works", []))
        lines.append(f"{slug}: {works}")
    return "\n".join(lines) or "No authors found."


# ── Lewis & Short Latin dictionary (Perseus lexica, CC BY-SA 4.0) ────

_LEX = None


def _lex_db():
    """Open the Lewis & Short SQLite once, read-only."""
    global _LEX
    if _LEX is None:
        _LEX = sqlite3.connect(f"file:{LEXICON}?mode=ro", uri=True)
    return _LEX


def _lex_norm(s):
    """Headword normalization matching the DB's 'norm' column: fold diacritics,
    lowercase, j→i, v→u, keep only a–z (so 'Virtūs' and 'uirtus' both hit)."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("j", "i").replace("v", "u")
    return re.sub(r"[^a-z]", "", s)


def lewis_short(word, max_entries=3, full_text=False):
    """Look up a Latin word in Lewis & Short. Headword match first (with u/v,
    i/j, macron folding), then stem/prefix, then full-text over definitions.

    Dictionary text is TRANSCRIBED from this tool; Claude supplies translations
    in prose, marked as its own — same Transcription Gate as the corpus tools."""
    if not LEXICON.exists():
        return ("ERROR: lewis_short.sqlite not found next to this server — the "
                "Lewis & Short dictionary database is missing.")
    if not word or not word.strip():
        return "ERROR: empty query."
    db = _lex_db()
    nk = _lex_norm(word)
    note = ""
    rows = []
    if not full_text and nk:
        rows = db.execute(
            "SELECT headword, text FROM entries WHERE norm = ? ORDER BY key LIMIT ?",
            (nk, max_entries)).fetchall()
        if not rows:
            rows = db.execute(
                "SELECT headword, text FROM entries WHERE norm LIKE ? "
                "ORDER BY length(norm), key LIMIT ?", (nk + "%", max_entries)).fetchall()
            if rows:
                note = f"(no exact headword '{word}'; showing nearest by stem)\n\n"
        if not rows and len(nk) > 3:
            # crude lemma recovery: trim inflectional endings and retry exact
            for k in range(1, 5):
                stem = nk[:-k]
                if len(stem) < 3:
                    break
                r = db.execute("SELECT headword, text FROM entries WHERE norm = ? "
                               "ORDER BY key LIMIT ?", (stem, max_entries)).fetchall()
                if r:
                    rows = r
                    note = f"(no exact '{word}'; matched likely lemma by trimming to '{stem}')\n\n"
                    break
    if not rows:
        q = re.sub(r'["*]', " ", word.strip())
        try:
            rows = db.execute(
                "SELECT e.headword, e.text FROM fts JOIN entries e ON e.id = fts.rowid "
                "WHERE fts MATCH ? ORDER BY rank LIMIT ?", (f'"{q}"', max_entries)).fetchall()
        except sqlite3.OperationalError:
            rows = []
        if rows:
            note = f"(no headword '{word}'; showing entries whose definition mentions it)\n\n"
        else:
            return f"No Lewis & Short entry or definition match for '{word}'."
    out = []
    for head, text in rows:
        if len(text) > 3000:
            text = text[:3000].rstrip() + " …[entry truncated — narrow the query for the rest]"
        out.append(f"▸ {head}\n{text}")
    header = (f"Lewis & Short — '{word}' "
              f"({len(out)} entr{'y' if len(out) == 1 else 'ies'}):\n\n")
    return note + header + "\n\n".join(out)


def passage(author, work, reference):
    """reference: 'book.line' / 'book.line-line' (verse) or
    'book.chapter' (prose) or 'line'/'line-line' for single-book works."""
    matches = [(slug, m) for slug, m in discover_authors() if slug == author]
    if not matches:
        return f"ERROR: unknown author '{author}'. Try: " + \
            ", ".join(s for s, _ in discover_authors())
    slug, manifest = matches[0]
    wq = work.lower()
    cand = [w for w in manifest.get("works", [])
            if wq in w.get("title", "").lower()]
    if not cand:
        return ("ERROR: no work matching '%s' for %s. Works: %s" %
                (work, author,
                 ", ".join(w.get("title", "?") for w in manifest["works"])))
    f = HERE / slug / cand[0]["file"]
    title = cand[0]["title"]

    m = re.match(r"^(?:(\d+)\.)?(?:(\d+)\.)?(\d+)(?:-(\d+))?$", reference.strip())
    if not m:
        return ("ERROR: reference format is 'book.poem.line-line' (three-level works "
                "like Horace's Carmina), 'book.line-line', or 'line'.")
    book, poem, first, last = m.group(1), m.group(2), int(m.group(3)), m.group(4)
    last = int(last) if last else first
    # two-part refs like '5.250' put the book in group 1 only when a third
    # part exists; normalize: if only two parts given, group(1) is None and
    # group(2) holds the leading number
    if book is None and poem is not None:
        book, poem = poem, None

    out, cur_book = [], None
    stack = []

    def walk(el, divpath):
        nonlocal cur_book
        for child in el:
            tag = strip_ns(child.tag)
            if tag == "div":
                n = child.get("n")
                walk(child, divpath + ([n] if n else []))
            elif tag == "l":
                n = child.get("n")
                if book:
                    if poem:
                        if len(divpath) < 2 or divpath[-2] != book or divpath[-1] != poem:
                            continue
                    elif not divpath or divpath[-1] != book:
                        continue
                try:
                    ln = int(n)
                except (TypeError, ValueError):
                    continue
                if first <= ln <= last:
                    out.append(f"{ln}  {strip_tags(child)}")
            elif tag == "p":
                bk = divpath[0] if divpath else None
                ch = divpath[1] if len(divpath) > 1 else None
                if book and bk == book and ch and first <= int_or(ch) <= last:
                    out.append(f"{bk}.{ch}  {strip_tags(child)}")
            else:
                walk(child, divpath)

    def int_or(s):
        try:
            return int(s)
        except ValueError:
            return -1

    try:
        root = ET.parse(str(f)).getroot()
    except ET.ParseError as e:
        return f"ERROR: XML parse failure in {f.name}: {e}"
    walk(root, [])
    if not out:
        return (f"No lines found for {title} {reference} — check book/line "
                f"numbers against the printed edition.")
    loc = ".".join(p for p in (book, poem) if p)
    ref = f"{title} {loc}.{first}" if loc else f"{title} {first}"
    if last != first:
        ref += f"-{last}"
    return f"{author}, {ref} (Perseus {f.name}):\n\n" + "\n".join(out)


# ── MCP plumbing ────────────────────────────────────────────────────

def handle_initialize(params):
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "latin-resources", "version": "1.0.0"},
    }


TOOLS = [
    {
        "name": "latin_corpus_search",
        "description": (
            "Full-text search across the local Latin corpus (Virgil, Horace, "
            "Cicero, Caesar, Livy, Tacitus, Seneca, Lucretius, Juvenal, "
            "Sallust, Suetonius, Pliny the Elder, Jerome, Tertullian, "
            "Augustine, Aquinas). Case-, u/v- and i/j-insensitive substring "
            "match; returns citations with context. Latin quoted in the "
            "manuscript is TRANSCRIBED from this tool's output, never from "
            "memory; Claude supplies the translation in prose, marked as its own."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "word": {"type": "string",
                         "description": "Latin word or phrase, e.g. 'armiger' or 'fulminis'"},
                "author": {"type": "string",
                           "description": "Optional author slug (see latin_authors)"},
                "max_results": {"type": "number", "description": "Default 25"},
            },
            "required": ["word"],
        },
    },
    {
        "name": "latin_passage",
        "description": (
            "Retrieve a passage by reference from the local Perseus Latin "
            "texts, e.g. author='virgil', work='Aeneid', reference='5.250-257'. "
            "Single-book works take 'line' or 'first-last'. Returns numbered "
            "Latin lines for transcription."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "author": {"type": "string", "description": "Author slug, e.g. 'virgil'"},
                "work": {"type": "string", "description": "Work title or substring, e.g. 'Aeneid'"},
                "reference": {"type": "string", "description": "'5.250-257', '1.1-11', or '45'"},
            },
            "required": ["author", "work", "reference"],
        },
    },
    {
        "name": "lewis_short",
        "description": (
            "Look up a Latin word in Lewis & Short, 'A Latin Dictionary' (1879; "
            "Perseus lexica, CC BY-SA 4.0) — the Latin counterpart to the Greek "
            "LSJ tool. Headword lookup is case-, macron-, u/v- and i/j-insensitive "
            "('virtus', 'uirtus', 'Virtūs' all match); if there's no exact headword "
            "it falls back to nearest stem, then to full-text search of the "
            "definitions. Returns the dictionary entry (senses + citations) for "
            "transcription; Claude supplies any translation in prose, marked as its own."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "word": {"type": "string",
                         "description": "Latin headword or form, e.g. 'virtus', 'amor', 'bellum'"},
                "max_entries": {"type": "number",
                                "description": "Max entries to return (default 3; homographs count separately)"},
                "full_text": {"type": "boolean",
                              "description": "Search definition text instead of headwords (default false)"},
            },
            "required": ["word"],
        },
    },
    {
        "name": "latin_authors",
        "description": "List the local Latin authors and works this server indexes.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "latin_reindex",
        "description": "Rebuild the Latin corpus index after adding new texts.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def handle_tools_list(params):
    return {"tools": TOOLS}


def handle_tools_call(params):
    name = params.get("name")
    args = params.get("arguments", {}) or {}
    try:
        if name == "latin_corpus_search":
            text = search(args.get("word", ""), args.get("author"),
                          int(args.get("max_results", 25)))
        elif name == "latin_passage":
            text = passage(args.get("author", ""), args.get("work", ""),
                           args.get("reference", ""))
        elif name == "lewis_short":
            text = lewis_short(args.get("word", ""),
                               int(args.get("max_entries", 3)),
                               bool(args.get("full_text", False)))
        elif name == "latin_authors":
            text = authors()
        elif name == "latin_reindex":
            text = build_index()
        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                    "isError": True}
    except Exception as e:
        return {"content": [{"type": "text",
                             "text": f"ERROR: {type(e).__name__}: {e}"}],
                "isError": True}
    result = {"content": [{"type": "text", "text": text}]}
    if text.startswith("ERROR"):
        result["isError"] = True
    return result


HANDLERS = {
    "initialize": handle_initialize,
    "tools/list": handle_tools_list,
    "tools/call": handle_tools_call,
}


def process_message(msg):
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params", {})
    if msg_id is None:
        return None
    handler = HANDLERS.get(method)
    if handler:
        try:
            result = handler(params)
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": msg_id,
                    "error": {"code": -32000, "message": f"{type(e).__name__}: {e}"}}
    return {"jsonrpc": "2.0", "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main():
    if len(sys.argv) > 1:  # CLI test mode
        cmd = sys.argv[1]
        if cmd == "index":
            print(build_index())
        elif cmd == "authors":
            print(authors())
        elif cmd == "search":
            argv = sys.argv[2:]
            author = None
            maxr = 25
            if "--author" in argv:
                i = argv.index("--author")
                author = argv[i + 1]
                del argv[i:i + 2]
            if "--max" in argv:
                i = argv.index("--max")
                maxr = int(argv[i + 1])
                del argv[i:i + 2]
            print(search(" ".join(argv), author, maxr))
        elif cmd == "passage":
            print(passage(sys.argv[2], sys.argv[3], sys.argv[4]))
        elif cmd == "lookup":
            print(lewis_short(" ".join(sys.argv[2:]) or ""))
        else:
            print(__doc__)
        return
    print("[latin-resources] MCP server starting...", file=sys.stderr)
    print(f"[latin-resources] Corpus dir: {HERE}", file=sys.stderr)
    ensure_index()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[latin-resources] Bad JSON: {e}", file=sys.stderr)
            continue
        response = process_message(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

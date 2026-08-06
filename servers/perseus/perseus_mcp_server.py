#!/usr/bin/env python3
"""
Perseus Canonical — MCP Server
Exposes the COMPLETE Perseus Digital Library canonical repositories
(canonical-greekLit + canonical-latinLit, every edition and translation)
as MCP tools: full-corpus substring search and reference-addressed
passage retrieval.

Corpus: /Volumes/PRO-BLADE/Alexandria/Perseus-canonical/
    canonical-greekLit-master/data/   (~2,500+ TEI XML files)
    canonical-latinLit-master/data/   (~1,000+ TEI XML files)

Run with:
    /usr/bin/python3 /Volumes/PRO-BLADE/Alexandria/Perseus-canonical/perseus_mcp_server.py

CLI test mode (no MCP):
    perseus_mcp_server.py index
    perseus_mcp_server.py authors [substring]
    perseus_mcp_server.py search WORD [--author athenaeus] [--lang grc] [--max 25]
    perseus_mcp_server.py passage athenaeus Deipnosophistae 9.392 [--lang grc]

Stdlib only. Same newline-delimited JSON-RPC stdio pattern as
latin_mcp_server.py / greek_mcp_server.py / alexandria_mcp_server.py.

Project rule this server enforces (Transcription Gate):
Greek and Latin are TRANSCRIBED from these tools, never generated from
memory. The server quotes; Claude translates the quoted text in prose
and marks the translation as its own.
"""

import json
import re
import sys
import unicodedata
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
REPOS = [HERE / "canonical-greekLit-master" / "data",
         HERE / "canonical-latinLit-master" / "data"]
INDEX = HERE / "perseus-corpus-index.jsonl"
AUTHORS = HERE / "perseus-authors.json"
CHUNK = 12  # verse lines per index segment


# ── text utilities ──────────────────────────────────────────────────

def fold(s):
    """Lowercase, strip diacritics/breathings/accents, normalize u/v i/j."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("v", "u").replace("j", "i")
    return s


def strip_tags(el):
    txt = "".join(el.itertext())
    return re.sub(r"\s+", " ", txt).strip()


def strip_ns(tag):
    return tag.split("}")[-1] if "}" in tag else tag


def slugify(name):
    s = fold(name)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "unknown"


def lang_of(filename):
    """perseus-grc2.xml -> grc ; perseus-lat1 -> lat ; perseus-eng3 -> eng"""
    m = re.search(r"\.perseus-([a-z]+)\d*\.xml$", filename)
    if m:
        return m.group(1)
    m = re.search(r"\.([a-z]{2,4})\d*\.xml$", filename)
    return m.group(1) if m else "unk"


# ── canonical-repo metadata (__cts__.xml) ───────────────────────────

def read_cts(path, wanted):
    """Return the text of the first element whose local tag is in `wanted`."""
    try:
        root = ET.parse(str(path)).getroot()
    except (ET.ParseError, OSError):
        return None
    for el in root.iter():
        if strip_ns(el.tag) in wanted:
            t = strip_tags(el)
            if t:
                return t
    return None


def discover():
    """Walk both repos. Yield dicts: author slug, group name, work title,
    urn-ish id, language, file path."""
    for data in REPOS:
        if not data.is_dir():
            continue
        for group in sorted(data.iterdir()):
            if not group.is_dir():
                continue
            gname = read_cts(group / "__cts__.xml", {"groupname"}) or group.name
            aslug = slugify(gname)
            for work in sorted(group.iterdir()):
                if not work.is_dir():
                    continue
                wtitle = read_cts(work / "__cts__.xml", {"title"}) or work.name
                for f in sorted(work.glob("*.xml")):
                    if f.name == "__cts__.xml":
                        continue
                    yield {"aslug": aslug, "author": gname, "title": wtitle,
                           "id": f"{group.name}.{work.name}",
                           "lang": lang_of(f.name), "file": f}


# ── index build ─────────────────────────────────────────────────────

def parse_tei(path):
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

    yield_segments = []

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
            if tag == "div":
                flush()
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
                    flush()
            elif tag in ("p", "sp", "quote", "said"):
                flush()
                txt = strip_tags(child)
                if txt:
                    loc = ".".join(divpath) if divpath else "—"
                    yield_segments.append((loc, txt))
            else:
                walk(child, divpath)
        flush()

    walk(body, [])
    for seg in yield_segments:
        yield seg


def build_index():
    n_seg, n_file = 0, 0
    catalog = {}
    with INDEX.open("w", encoding="utf-8") as out:
        for w in discover():
            n_file += 1
            entry = catalog.setdefault(w["aslug"], {"author": w["author"],
                                                    "works": {}})
            wk = entry["works"].setdefault(w["title"], {"id": w["id"],
                                                        "files": {}})
            wk["files"][w["lang"]] = str(w["file"].relative_to(HERE))
            for loc, txt in parse_tei(w["file"]):
                rec = {"a": w["aslug"], "w": w["title"], "g": w["lang"],
                       "l": loc, "t": txt, "f": fold(txt)}
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_seg += 1
    AUTHORS.write_text(json.dumps(catalog, ensure_ascii=False, indent=1))
    return f"Indexed {n_seg} segments from {n_file} files → {INDEX.name}"


def ensure_index():
    if not INDEX.exists() or not AUTHORS.exists():
        build_index()


# ── search / authors / passage ──────────────────────────────────────

def search(word, author=None, lang=None, max_results=25):
    ensure_index()
    q = fold(word)
    hits, total = [], 0
    with INDEX.open(encoding="utf-8") as fh:
        for line in fh:
            if q not in line:          # fast raw check before JSON parse
                continue
            rec = json.loads(line)
            if q not in rec["f"]:
                continue
            if author and rec["a"] != author:
                continue
            if lang and rec["g"] != lang:
                continue
            total += 1
            if len(hits) < max_results:
                pos = rec["f"].find(q)
                lo, hi = max(0, pos - 120), pos + len(q) + 120
                ctx = rec["t"][lo:hi].strip()
                hits.append(f"[{rec['a']}|{rec['g']}] {rec['w']} {rec['l']}\n    …{ctx}…")
    scope = (f" in {author}" if author else "") + (f" [{lang}]" if lang else "")
    if not hits:
        return f"No hits for '{word}'{scope}"
    return (f"{total} segment(s) match '{word}'{scope}; showing {len(hits)}:\n\n"
            + "\n\n".join(hits))


def authors_list(substring=None):
    ensure_index()
    catalog = json.loads(AUTHORS.read_text())
    lines = []
    for slug in sorted(catalog):
        entry = catalog[slug]
        if substring and fold(substring) not in fold(slug + " " + entry["author"]):
            continue
        works = "; ".join(f"{t} ({','.join(sorted(w['files']))})"
                          for t, w in sorted(entry["works"].items()))
        lines.append(f"{slug} — {entry['author']}: {works}")
    if not lines:
        return f"No authors matching '{substring}'."
    if len(lines) > 120 and not substring:
        return (f"{len(lines)} authors indexed. Pass a substring to filter "
                f"(e.g. 'athen'). First 120:\n" + "\n".join(lines[:120]))
    return "\n".join(lines)


def passage(author, work, reference, lang=None):
    ensure_index()
    catalog = json.loads(AUTHORS.read_text())
    if author not in catalog:
        near = [s for s in catalog if fold(author) in s][:10]
        return ("ERROR: unknown author '%s'.%s" %
                (author, (" Near matches: " + ", ".join(near)) if near else
                 " Use perseus_authors to browse."))
    entry = catalog[author]
    wq = work.lower()
    cand = [(t, w) for t, w in entry["works"].items() if wq in t.lower()]
    if not cand:
        return ("ERROR: no work matching '%s' for %s. Works: %s" %
                (work, author, "; ".join(entry["works"])))
    title, winfo = cand[0]
    files = winfo["files"]
    pick = None
    for pref in ([lang] if lang else []) + ["grc", "lat", "eng"]:
        if pref in files:
            pick = files[pref]
            break
    if pick is None:
        pick = next(iter(files.values()))
    f = HERE / pick

    m = re.match(r"^(?:(\d+)\.)?(?:(\d+)\.)?(\d+)(?:-(\d+))?$", reference.strip())
    if not m:
        return ("ERROR: reference format is 'book.poem.line-line', "
                "'book.line-line', or 'line'.")
    book, poem, first, last = m.group(1), m.group(2), int(m.group(3)), m.group(4)
    last = int(last) if last else first
    if book is None and poem is not None:
        book, poem = poem, None

    out = []

    def int_or(s):
        try:
            return int(s)
        except (TypeError, ValueError):
            return -1

    def walk(el, divpath):
        for child in el:
            tag = strip_ns(child.tag)
            if tag == "div":
                n = child.get("n")
                sub = child.get("subtype") or child.get("type") or ""
                if n and sub not in ("edition", "translation"):
                    walk(child, divpath + [n])
                else:
                    walk(child, divpath)
            elif tag == "l":
                n = child.get("n")
                if book:
                    if poem:
                        if len(divpath) < 2 or divpath[-2] != book or divpath[-1] != poem:
                            continue
                    elif not divpath or divpath[-1] != book:
                        continue
                ln = int_or(n)
                if first <= ln <= last:
                    out.append(f"{ln}  {strip_tags(child)}")
            elif tag == "p":
                bk = divpath[0] if divpath else None
                ch = divpath[-1] if divpath else None
                if book:
                    if bk == book and first <= int_or(ch) <= last:
                        out.append(f"{'.'.join(divpath)}  {strip_tags(child)}")
                elif first <= int_or(ch) <= last:
                    out.append(f"{'.'.join(divpath)}  {strip_tags(child)}")
            else:
                walk(child, divpath)

    try:
        root = ET.parse(str(f)).getroot()
    except ET.ParseError as e:
        return f"ERROR: XML parse failure in {Path(pick).name}: {e}"
    walk(root, [])
    if not out:
        return (f"No text found for {title} {reference} in {Path(pick).name} — "
                f"check the reference against the edition's numbering "
                f"(some prose works cite by Casaubon/Stephanus pages).")
    loc = ".".join(p for p in (book, poem) if p)
    ref = f"{title} {loc}.{first}" if loc else f"{title} {first}"
    if last != first:
        ref += f"-{last}"
    return f"{author}, {ref} (Perseus {Path(pick).name}):\n\n" + "\n".join(out[:200])


# ── MCP plumbing ────────────────────────────────────────────────────

def handle_initialize(params):
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "perseus", "version": "1.0.0"},
    }


TOOLS = [
    {
        "name": "perseus_search",
        "description": (
            "Full-text search across the COMPLETE local Perseus canonical "
            "library — every Greek and Latin author Perseus publishes, all "
            "editions and translations (canonical-greekLit + canonical-"
            "latinLit). Case-, accent-, u/v- and i/j-insensitive substring "
            "match; returns citations with context. Greek/Latin quoted in "
            "the manuscript is TRANSCRIBED from this tool's output, never "
            "from memory."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "word": {"type": "string",
                         "description": "Greek/Latin/English word or phrase"},
                "author": {"type": "string",
                           "description": "Optional author slug (see perseus_authors)"},
                "lang": {"type": "string",
                         "description": "Optional: grc, lat, or eng"},
                "max_results": {"type": "number", "description": "Default 25"},
            },
            "required": ["word"],
        },
    },
    {
        "name": "perseus_passage",
        "description": (
            "Retrieve a passage by reference from the local Perseus canonical "
            "texts, e.g. author='athenaeus', work='Deipnosophistae', "
            "reference='9.47'. Prefers the original language; pass lang='eng' "
            "for a translation where Perseus has one. Returns numbered text "
            "for transcription."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "author": {"type": "string", "description": "Author slug"},
                "work": {"type": "string", "description": "Work title or substring"},
                "reference": {"type": "string", "description": "'9.47', '5.250-257', or '45'"},
                "lang": {"type": "string", "description": "Optional: grc, lat, eng"},
            },
            "required": ["author", "work", "reference"],
        },
    },
    {
        "name": "perseus_authors",
        "description": (
            "Browse the local Perseus catalog: author slugs, work titles, and "
            "available languages. Pass a substring to filter (e.g. 'athen')."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "substring": {"type": "string",
                              "description": "Optional filter, e.g. 'plutarch'"},
            },
        },
    },
    {
        "name": "perseus_reindex",
        "description": "Rebuild the Perseus corpus index after updating the repos.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def handle_tools_list(params):
    return {"tools": TOOLS}


def handle_tools_call(params):
    name = params.get("name")
    args = params.get("arguments", {}) or {}
    try:
        if name == "perseus_search":
            text = search(args.get("word", ""), args.get("author"),
                          args.get("lang"), int(args.get("max_results", 25)))
        elif name == "perseus_passage":
            text = passage(args.get("author", ""), args.get("work", ""),
                           args.get("reference", ""), args.get("lang"))
        elif name == "perseus_authors":
            text = authors_list(args.get("substring"))
        elif name == "perseus_reindex":
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
            print(authors_list(sys.argv[2] if len(sys.argv) > 2 else None))
        elif cmd == "search":
            argv = sys.argv[2:]
            author = lang = None
            maxr = 25
            for flag, var in (("--author", "author"), ("--lang", "lang"),
                              ("--max", "maxr")):
                if flag in argv:
                    i = argv.index(flag)
                    val = argv[i + 1]
                    del argv[i:i + 2]
                    if var == "author":
                        author = val
                    elif var == "lang":
                        lang = val
                    else:
                        maxr = int(val)
            print(search(" ".join(argv), author, lang, maxr))
        elif cmd == "passage":
            lang = None
            argv = sys.argv[2:]
            if "--lang" in argv:
                i = argv.index("--lang")
                lang = argv[i + 1]
                del argv[i:i + 2]
            print(passage(argv[0], argv[1], argv[2], lang))
        else:
            print(__doc__)
        return
    print("[perseus] MCP server starting...", file=sys.stderr)
    print(f"[perseus] Corpus dir: {HERE}", file=sys.stderr)
    ensure_index()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[perseus] Bad JSON: {e}", file=sys.stderr)
            continue
        response = process_message(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

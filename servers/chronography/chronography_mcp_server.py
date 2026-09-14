#!/usr/bin/env python3
"""
Ancient Chronography / Synchronism — MCP Server

Public-domain primary sources of ancient chronography and synchronism,
searchable full-text (FTS5, accent-insensitive Greek/Latin):

  eusebius-latin        Eusebius, Chronici Canones — Jerome's Latin
                        (ed. Fotheringham, Oxford 1923)                    [PD]
  eusebius-armenian-de  Eusebius, Chronik — Armenian version, German tr.
                        (Karst, GCS 20, Leipzig 1911)                      [PD]
  syncellus             George Syncellus, Ecloga Chronographica
                        (ed. Dindorf, CSHB, Bonn 1829) — preserves the
                        Manetho, Berossus & Julius Africanus fragments     [PD]

Julius Africanus (Chronographiai) is not a separate corpus: his work survives
only as fragments quoted inside Eusebius and Syncellus, so search returns him
wherever those two cite him.

Data: chronography.sqlite next to this file (built by build_chronography.py).

Run with:
    /path/to/python3 chronography_mcp_server.py

CLI test mode (no MCP):
    chronography_mcp_server.py search "Nabonassar"
    chronography_mcp_server.py search "Ithobal*" --source eusebius-armenian-de
    chronography_mcp_server.py get syncellus 412
    chronography_mcp_server.py inventory
    chronography_mcp_server.py canon

Stdlib only; same newline-delimited JSON-RPC stdio pattern as the other
Alexandria MCP servers.

ATTRIBUTION: every search/get result carries the source's public-domain
attribution string. Transcription Gate: Greek/Latin text is TRANSCRIBED from
this tool's output, never generated from memory — polytonic Greek OCR in the
1829 Syncellus scan is rough, so verify before quoting.
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "chronography.sqlite"

_DB = None


def db():
    global _DB
    if _DB is None:
        _DB = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    return _DB


# ── Ptolemy, Canon of Kings (#6) ────────────────────────────────────
# The regnal-year table is NOT reproduced here: transcribing reconstructed
# numbers from memory would fabricate the very data it claims to preserve.
# Ptolemy's own astronomical basis (the Almagest) is already on the Perseus
# server; this pointer routes there and to the standard PD reference edition.
CANON_NOTE = (
    "Ptolemy's Canon of Kings (Basileion Anagraphe / Canon Basileon)\n"
    "\n"
    "The Canon is the king-list of Babylonian, Persian, Macedonian and Roman\n"
    "rulers with regnal years that Ptolemy used as the chronological backbone\n"
    "for dating his astronomical observations. It is anchored to the era of\n"
    "Nabonassar (747 BC, Thoth 1).\n"
    "\n"
    "This server does NOT store the regnal-year table — reconstructed numbers\n"
    "must be read from an edition, not recalled, or the dates are fabricated.\n"
    "Where to read it:\n"
    "  • Ptolemy's astronomy (the Canon's basis), Almagest — on the local\n"
    "    Perseus server: perseus_search 'Ptolemy' / perseus_authors.\n"
    "  • The Nabonassar era and the king-list are cross-referenced throughout\n"
    "    Eusebius and Syncellus here: search 'Nabonassar' on this server.\n"
    "  • Standard PD reference: the Canon as printed with the Almagest\n"
    "    (Halma's edition, Paris 1813–1816) and in the Handy Tables.\n"
    "\n"
    "Quote regnal years only from one of those editions, with the edition named."
)


# ── query helpers ───────────────────────────────────────────────────

def fts_query(user):
    """User string → safe FTS5 MATCH expression.

    Each whitespace token is quoted (so brackets/punctuation can't break the
    parser); a trailing '*' is kept as a prefix search; tokens AND together;
    an explicit "quoted phrase" is preserved."""
    user = (user or "").strip()
    if not user:
        return None
    if user.startswith('"') and user.endswith('"') and len(user) > 1:
        return user
    out = []
    for tok in user.split():
        star = tok.endswith("*")
        core = tok.strip("*").replace('"', "")
        if not core:
            continue
        out.append(f'"{core}"*' if star else f'"{core}"')
    return " ".join(out) or None


def _attr(source):
    row = db().execute("SELECT attribution FROM sources WHERE id=?", (source,)).fetchone()
    return row[0] if row else source


# ── tools ───────────────────────────────────────────────────────────

def search(query, max_results=15, source=None):
    m = fts_query(query)
    if not m:
        return "ERROR: empty query."
    sql = ("SELECT d.source, d.seq, d.lang, "
           "snippet(docs_fts, 0, '«', '»', ' … ', 14) "
           "FROM docs_fts JOIN docs d ON d.id = docs_fts.rowid "
           "WHERE docs_fts MATCH ?")
    params = [m]
    if source:
        sql += " AND d.source = ?"
        params.append(source)
    sql += " ORDER BY rank LIMIT ?"
    params.append(max_results)
    try:
        rows = db().execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        return f"ERROR: bad search expression ({e})."
    if not rows:
        where = f" in {source}" if source else ""
        return f"No chronography passages match '{query}'{where}."
    cnt_sql = "SELECT count(*) FROM docs_fts JOIN docs d ON d.id=docs_fts.rowid WHERE docs_fts MATCH ?"
    cnt_p = [m]
    if source:
        cnt_sql += " AND d.source=?"
        cnt_p.append(source)
    total = db().execute(cnt_sql, cnt_p).fetchone()[0]
    out = [f"{total} passage(s) match '{query}'"
           + (f" in {source}" if source else "") + f"; showing {len(rows)}:\n"]
    seen = set()
    for src, seq, lang, snip in rows:
        out.append(f"▸ {src}  §{seq}  ({lang})")
        out.append(f"    …{snip}…")
        out.append(f"    get {src} {seq}")
        seen.add(src)
    out.append("")
    for src in sorted(seen):
        out.append(f"  {src}: {_attr(src)}")
    return "\n".join(out)


def get_passage(source, seq, context=1):
    if not source:
        return "ERROR: source required (e.g. 'syncellus')."
    try:
        seq = int(seq)
    except (TypeError, ValueError):
        return "ERROR: seq must be an integer segment number."
    lo, hi = seq - max(0, int(context)), seq + max(0, int(context))
    rows = db().execute(
        "SELECT seq, lang, text FROM docs WHERE source=? AND seq BETWEEN ? AND ? ORDER BY seq",
        (source, lo, hi)).fetchall()
    if not rows:
        return (f"No passage {source} §{seq}. Use 'inventory' for source ids and "
                f"segment counts, or 'search' to locate a segment.")
    head = _attr(source)
    body = []
    for s, lang, text in rows:
        marker = "»»" if s == seq else "  "
        body.append(f"{marker} §{s} ({lang})\n{text}")
    return (f"{source}  §{seq}\n{head}\n"
            f"(public domain — transcribe the text below; translate in your own prose)\n\n"
            + "\n\n".join(body))


def inventory():
    d = db()
    rows = d.execute("SELECT id, author, title, edition, lang, quality, segments "
                     "FROM sources ORDER BY id").fetchall()
    tot = d.execute("SELECT count(*) FROM docs").fetchone()[0]
    out = ["Ancient Chronography / Synchronism corpus:",
           f"  {len(rows)} sources · {tot:,} segments (~180 words each)\n"]
    for sid, author, title, edition, lang, quality, segs in rows:
        out.append(f"▸ {sid}  ({segs:,} segments, {lang})")
        out.append(f"    {author}, {title}")
        out.append(f"    {edition}")
        out.append(f"    OCR quality: {quality}")
    out.append("")
    out.append("Julius Africanus (Chronographiai): fragments only — search across")
    out.append("  eusebius-* and syncellus (no separate corpus).")
    out.append("Ptolemy, Canon of Kings: run 'canon' (pointer, not a stored table).")
    return "\n".join(out)


def canon():
    return CANON_NOTE


# ── MCP plumbing ────────────────────────────────────────────────────

def handle_initialize(params):
    return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
            "serverInfo": {"name": "chronography", "version": "1.0.0"}}


TOOLS = [
    {
        "name": "search",
        "description": (
            "Full-text search across public-domain ancient chronography: Eusebius's "
            "Chronicle (Jerome's Latin + Karst's German of the Armenian) and George "
            "Syncellus's Ecloga Chronographica (which preserves the Manetho, Berossus "
            "and Julius Africanus fragments). Accent-insensitive Greek/Latin; prefix "
            "('Ithobal*') and multi-term (AND) queries. Optional 'source' filter. "
            "Returns snippets, a get-command for each hit, and the PD attribution for "
            "every source cited. Primary sources — transcribe from get, don't paraphrase "
            "from memory; the 1829 Syncellus Greek OCR is rough."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "Name/word/phrase; '*' for prefix, e.g. 'Nabonassar' or 'Ithobal*'"},
                "source": {"type": "string",
                           "description": "Optional filter: eusebius-latin | eusebius-armenian-de | syncellus"},
                "max_results": {"type": "number", "description": "Default 15"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get",
        "description": (
            "Retrieve a chronography passage by source id + segment number (from a "
            "search hit's 'get' line), with neighbouring segments for context. Returns "
            "the public-domain text to transcribe plus the source attribution."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string",
                           "description": "eusebius-latin | eusebius-armenian-de | syncellus"},
                "seq": {"type": "number", "description": "Segment number, e.g. 412"},
                "context": {"type": "number", "description": "Neighbour segments each side (default 1)"},
            },
            "required": ["source", "seq"],
        },
    },
    {
        "name": "inventory",
        "description": (
            "List the chronography sources: ids, authors, editions, languages, OCR "
            "quality flags and segment counts. Note where Africanus (fragments) and "
            "Ptolemy's Canon (canon tool) live."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "canon",
        "description": (
            "Ptolemy's Canon of Kings: what it is, its Nabonassar-era anchor, and where "
            "to read the regnal-year table (the numbers are NOT stored here — Almagest on "
            "the Perseus server; Nabonassar cross-refs in Eusebius/Syncellus via search)."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def handle_tools_list(params):
    return {"tools": TOOLS}


def handle_tools_call(params):
    name = params.get("name")
    args = params.get("arguments", {}) or {}
    try:
        if name == "search":
            text = search(args.get("query", ""), int(args.get("max_results", 15)),
                          args.get("source") or None)
        elif name == "get":
            text = get_passage(args.get("source", ""), args.get("seq"),
                               int(args.get("context", 1)))
        elif name == "inventory":
            text = inventory()
        elif name == "canon":
            text = canon()
        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                    "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"ERROR: {type(e).__name__}: {e}"}],
                "isError": True}
    return {"content": [{"type": "text", "text": text}]}


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
            return {"jsonrpc": "2.0", "id": msg_id, "result": handler(params)}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": msg_id,
                    "error": {"code": -32000, "message": f"{type(e).__name__}: {e}"}}
    return {"jsonrpc": "2.0", "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main():
    if len(sys.argv) > 1:  # CLI test mode
        cmd = sys.argv[1]
        if cmd == "search":
            rest = sys.argv[2:]
            src = None
            if "--source" in rest:
                i = rest.index("--source")
                src = rest[i + 1] if i + 1 < len(rest) else None
                rest = rest[:i] + rest[i + 2:]
            print(search(" ".join(rest), source=src))
        elif cmd == "get":
            print(get_passage(sys.argv[2] if len(sys.argv) > 2 else "",
                              sys.argv[3] if len(sys.argv) > 3 else 0))
        elif cmd == "inventory":
            print(inventory())
        elif cmd == "canon":
            print(canon())
        else:
            print(__doc__)
        return
    print("[chronography] MCP server starting...", file=sys.stderr)
    print(f"[chronography] DB: {DB_PATH}", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[chronography] Bad JSON: {e}", file=sys.stderr)
            continue
        resp = process_message(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

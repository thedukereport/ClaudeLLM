#!/usr/bin/env python3
"""
Duke Databank of Documentary Papyri (DDbDP) — MCP Server

Exposes ~67,600 documentary Greek & Latin papyri, ostraca and tablets
(the DDbDP EpiDoc corpus from papyri.info, CC BY) as MCP tools:
full-text search (accent-insensitive Greek) and document retrieval.

Data: papyri/idp.data → DDbDP, © Duke Databank of Documentary Papyri,
licensed CC BY 3.0. Built into papyri.sqlite next to this file.

Run with:
    /path/to/rag_env/bin/python papyri_mcp_server.py

CLI test mode (no MCP):
    papyri_mcp_server.py search "βασιλ*"
    papyri_mcp_server.py get p.oxy.40.2901
    papyri_mcp_server.py get 45214            # by Trismegistos (TM) number
    papyri_mcp_server.py stats

Stdlib only; same newline-delimited JSON-RPC stdio pattern as the other
Alexandria MCP servers.

Transcription Gate (papyri extension): Greek/Latin papyrus text is
TRANSCRIBED from this tool's output, never generated from memory. The
server quotes; Claude supplies any translation in prose, marked as its own.
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "papyri.sqlite"

_DB = None


def db():
    global _DB
    if _DB is None:
        _DB = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    return _DB


# ── query helpers ───────────────────────────────────────────────────

def fts_query(user):
    """Turn a user string into a safe FTS5 MATCH expression.

    Each whitespace token becomes a quoted term (so punctuation/EpiDoc
    brackets can't break the parser); a trailing '*' is kept as a prefix
    search. Tokens are AND-ed. A quoted multiword phrase is preserved."""
    user = user.strip()
    if not user:
        return None
    if user.startswith('"') and user.endswith('"') and len(user) > 1:
        return user  # explicit phrase
    out = []
    for tok in user.split():
        star = tok.endswith("*")
        core = tok.strip('*').replace('"', "")
        if not core:
            continue
        out.append(f'"{core}"*' if star else f'"{core}"')
    return " ".join(out) or None


def _link(xmlid):
    return f"https://papyri.info/ddbdp/{xmlid}"


# ── tools ───────────────────────────────────────────────────────────

def search_papyri(query, max_results=15):
    m = fts_query(query)
    if not m:
        return "ERROR: empty query."
    try:
        rows = db().execute(
            "SELECT d.id, d.tm, d.langs, d.text, "
            "snippet(fts, 1, '«', '»', ' … ', 12) "
            "FROM fts JOIN docs d ON d.rowid = fts.rowid "
            "WHERE fts MATCH ? ORDER BY rank LIMIT ?",
            (m, max_results)).fetchall()
    except sqlite3.OperationalError as e:
        return f"ERROR: bad search expression ({e})."
    if not rows:
        return f"No papyri match '{query}'."
    total = db().execute("SELECT count(*) FROM fts WHERE fts MATCH ?", (m,)).fetchone()[0]
    out = [f"{total} papyrus/papyri match '{query}'; showing {len(rows)}:\n"]
    for xmlid, tm, langs, _txt, snip in rows:
        out.append(f"▸ {xmlid}"
                   + (f"  [TM {tm}]" if tm else "")
                   + (f"  ({langs})" if langs else ""))
        out.append(f"    …{snip}…")
        out.append(f"    {_link(xmlid)}")
    return "\n".join(out)


def get_papyrus(ident):
    ident = (ident or "").strip()
    if not ident:
        return "ERROR: empty identifier."
    row = db().execute(
        "SELECT id, tm, hybrid, langs, text FROM docs "
        "WHERE id = ? OR tm = ? OR hybrid = ? LIMIT 1",
        (ident, ident, ident)).fetchone()
    if not row and ident.isdigit():
        row = db().execute("SELECT id,tm,hybrid,langs,text FROM docs WHERE tm=? LIMIT 1",
                           (ident,)).fetchone()
    if not row:
        # forgiving: try the papyri.info hybrid form (series;vol;num) ↔ xml:id
        alt = ident.replace(";", ".")
        row = db().execute("SELECT id,tm,hybrid,langs,text FROM docs WHERE id=? LIMIT 1",
                           (alt,)).fetchone()
    if not row:
        return (f"No papyrus found for '{ident}'. Use a papyri.info id "
                f"(e.g. 'p.oxy.40.2901') or a TM number (e.g. '45214').")
    xmlid, tm, hybrid, langs, text = row
    head = [f"{xmlid}"]
    if tm:
        head.append(f"TM {tm}")
    if hybrid:
        head.append(hybrid)
    if langs:
        head.append(langs)
    return (f"{'  ·  '.join(head)}\n{_link(xmlid)}\n"
            f"(DDbDP, CC BY — transcribe the text below; translate in your own prose)\n\n"
            f"{text}")


def stats():
    d = db()
    tot = d.execute("SELECT count(*) FROM docs").fetchone()[0]
    with_tm = d.execute("SELECT count(*) FROM docs WHERE tm IS NOT NULL AND tm<>''").fetchone()[0]
    grc = d.execute("SELECT count(*) FROM docs WHERE langs LIKE '%grc%'").fetchone()[0]
    lat = d.execute("SELECT count(*) FROM docs WHERE langs LIKE '%la%'").fetchone()[0]
    return ("Duke Databank of Documentary Papyri (DDbDP), local corpus:\n"
            f"  documents      : {tot:,}\n"
            f"  with TM number : {with_tm:,}\n"
            f"  contain Greek  : {grc:,}\n"
            f"  contain Latin  : {lat:,}\n"
            "  source         : papyri.info (idp.data/DDbDP), CC BY 3.0")


# ── MCP plumbing ────────────────────────────────────────────────────

def handle_initialize(params):
    return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
            "serverInfo": {"name": "papyri-ddbdp", "version": "1.0.0"}}


TOOLS = [
    {
        "name": "search_papyri",
        "description": (
            "Full-text search across ~67,600 documentary papyri (Duke Databank / "
            "DDbDP, CC BY): letters, contracts, petitions, receipts, accounts in "
            "Greek and Latin. Accent-insensitive Greek search; supports prefix "
            "('βασιλ*') and multi-term (AND) queries. Returns papyri.info citations "
            "with a matching snippet. Primary documentary sources — quote the "
            "transcription from get_papyrus, translate in your own prose."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "Greek or Latin word/phrase; '*' for prefix, e.g. 'βασιλ*' or 'centurio'"},
                "max_results": {"type": "number", "description": "Default 15"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_papyrus",
        "description": (
            "Retrieve one papyrus's full transcription + identifiers by papyri.info "
            "id (e.g. 'p.oxy.40.2901') or Trismegistos TM number (e.g. '45214'). "
            "Returns the EpiDoc edition text (with editorial brackets) for transcription "
            "and a papyri.info link."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string",
                       "description": "papyri.info id (p.oxy.40.2901) or TM number (45214)"},
            },
            "required": ["id"],
        },
    },
    {
        "name": "papyri_stats",
        "description": "Report the local DDbDP corpus size and language coverage.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def handle_tools_list(params):
    return {"tools": TOOLS}


def handle_tools_call(params):
    name = params.get("name")
    args = params.get("arguments", {}) or {}
    try:
        if name == "search_papyri":
            text = search_papyri(args.get("query", ""), int(args.get("max_results", 15)))
        elif name == "get_papyrus":
            text = get_papyrus(args.get("id", ""))
        elif name == "papyri_stats":
            text = stats()
        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                    "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"ERROR: {type(e).__name__}: {e}"}],
                "isError": True}
    result = {"content": [{"type": "text", "text": text}]}
    if text.startswith("ERROR") or text.startswith("No "):
        pass
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
            print(search_papyri(" ".join(sys.argv[2:])))
        elif cmd == "get":
            print(get_papyrus(sys.argv[2] if len(sys.argv) > 2 else ""))
        elif cmd == "stats":
            print(stats())
        else:
            print(__doc__)
        return
    print("[papyri-ddbdp] MCP server starting...", file=sys.stderr)
    print(f"[papyri-ddbdp] DB: {DB_PATH}", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[papyri-ddbdp] Bad JSON: {e}", file=sys.stderr)
            continue
        resp = process_message(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

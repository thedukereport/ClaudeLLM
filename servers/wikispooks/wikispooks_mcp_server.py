#!/usr/bin/env python3
"""
WikiSpooks — MCP Server
Exposes the local WikiSpooks archive (~37k MediaWiki articles) as MCP tools:
full-text search and full-article retrieval, straight out of the local SQLite
corpus built by build_wikispooks_corpus.py.

Run with:
    /usr/bin/python3 /Volumes/PRO-BLADE/WikiSpooks/wikispooks_mcp_server.py

Stdlib only — no venv required. Connects to Claude Desktop / Cowork via stdio
transport. Same JSON-RPC pattern as greek_mcp_server.py / alexandria_mcp_server.py.

The corpus is a local, offline copy of the WikiSpooks wiki — resilient to the
live site going down. Quote and attribute from THIS tool: cite as WikiSpooks,
community-edited, with the article title and retrieval date.
"""

import os
import re
import sys
import json
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get(
    "WIKISPOOKS_DB",
    str(Path(__file__).resolve().parent / "wikispooks.sqlite"),
)

_conn = None


def db():
    """Open the corpus once (read-only), reuse across calls."""
    global _conn
    if _conn is None:
        uri = f"file:{DB_PATH}?mode=ro"
        _conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    return _conn


def fts_query(text):
    """Turn free user text into a safe FTS5 MATCH string (AND of quoted terms)."""
    toks = re.findall(r"[^\s\"']+", text)
    return " AND ".join(f'"{t}"' for t in toks) if toks else '""'


# ── MCP handlers ────────────────────────────────────────────────────
def handle_initialize(params):
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "wikispooks", "version": "1.0.0"},
    }


TOOLS = [
    {
        "name": "search_wikispooks",
        "description": (
            "Full-text search across the local WikiSpooks archive (~37,000 "
            "articles — people, organisations, events, deep-politics topics). "
            "Returns ranked article titles with a matching snippet. Then call "
            "get_wikispooks_article for the full text. WikiSpooks is a "
            "community-edited deep-politics wiki; attribute claims to it by "
            "article title. Query is keyword/phrase "
            "based, e.g. 'Operation Gladio', 'Bilderberg 1954', 'Le Cercle'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords or phrase to search for"},
                "max_results": {"type": "integer", "description": "Max results (default 10)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_wikispooks_article",
        "description": (
            "Return the full plain text of a WikiSpooks article by title "
            "(as shown by search_wikispooks). Title match is exact-ish: spaces "
            "and underscores are interchangeable and matching is "
            "case-insensitive. Use after search_wikispooks to read an article."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Article title, e.g. 'Operation Gladio'"}
            },
            "required": ["title"],
        },
    },
]


def handle_tools_list(params):
    return {"tools": TOOLS}


def _search(query, max_results):
    max_results = max(1, min(int(max_results or 10), 50))
    try:
        rows = db().execute(
            "SELECT title, snippet(fts, 1, '»', '«', ' … ', 14), rank "
            "FROM fts WHERE fts MATCH ? ORDER BY rank LIMIT ?",
            (fts_query(query), max_results),
        ).fetchall()
    except sqlite3.OperationalError as e:
        return f"Search error: {e}"
    if not rows:
        return f"No WikiSpooks articles matched: {query!r}"
    out = [f"{len(rows)} result(s) for {query!r} "
           f"(use get_wikispooks_article for full text):\n"]
    for i, (title, snip, _rank) in enumerate(rows, 1):
        out.append(f"{i}. {title.replace('_', ' ')}\n     …{snip.strip()}…")
    return "\n".join(out)


def _get_article(title):
    t = (title or "").strip()
    variants = {t, t.replace(" ", "_"), t.replace("_", " ")}
    conn = db()
    row = None
    for v in variants:
        row = conn.execute(
            "SELECT title, plaintext FROM articles WHERE title = ? COLLATE NOCASE", (v,)
        ).fetchone()
        if row:
            break
    if not row:  # fall back to a fuzzy prefix match
        row = conn.execute(
            "SELECT title, plaintext FROM articles WHERE title LIKE ? COLLATE NOCASE "
            "ORDER BY length(title) LIMIT 1", (t.replace(" ", "_") + "%",)
        ).fetchone()
    if not row:
        return f"No WikiSpooks article titled {title!r}. Try search_wikispooks first."
    body = row[1] or "(empty article)"
    if len(body) > 60000:
        body = body[:60000] + "\n\n[... truncated ...]"
    return f"# {row[0].replace('_', ' ')}\n(Source: WikiSpooks, community-edited)\n\n{body}"


def handle_tools_call(params):
    name = params.get("name")
    args = params.get("arguments", {})
    if name == "search_wikispooks":
        text = _search(args.get("query", ""), args.get("max_results", 10))
    elif name == "get_wikispooks_article":
        text = _get_article(args.get("title", ""))
    else:
        return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}
    return {"content": [{"type": "text", "text": text}]}


# ── JSON-RPC dispatch (stdio) ───────────────────────────────────────
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
        return None  # notification
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
    print(f"[wikispooks] MCP server starting; db={DB_PATH}", file=sys.stderr)
    if not Path(DB_PATH).exists():
        print(f"[wikispooks] WARNING: corpus not found at {DB_PATH} — "
              f"run build_wikispooks_corpus.py first.", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[wikispooks] Bad JSON: {e}", file=sys.stderr)
            continue
        response = process_message(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

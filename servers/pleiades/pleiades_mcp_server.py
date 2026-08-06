#!/usr/bin/env python3
"""
Pleiades — MCP Server
Exposes the local Pleiades gazetteer of ancient places (~42k places, CC-BY)
as MCP tools: search by name and full place lookup with coordinates, dating,
feature types, and all attested/transliterated names.

Run with:
    /usr/bin/python3 /Volumes/PRO-BLADE/Pleiades/pleiades_mcp_server.py

Stdlib only. Same JSON-RPC/stdio pattern as greek_mcp_server.py.
Data: pleiades.sqlite, built by build_pleiades_corpus.py. Source: pleiades.stoa.org.
"""

import os
import re
import sys
import json
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get("PLEIADES_DB",
                         str(Path(__file__).resolve().parent / "pleiades.sqlite"))
_conn = None


def db():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False)
    return _conn


def fts_prefix(text):
    """AND of prefix tokens, so 'tartess' matches Tartessos, 'iber' matches Iberia."""
    toks = [t for t in re.findall(r"[A-Za-z0-9Ͱ-Ͽἀ-῿]+", text)]
    return " AND ".join(f"{t}*" for t in toks) if toks else '""'


# ── DATA LAYER ──────────────────────────────────────────────────────
def do_search(query, max_results=10):
    max_results = max(1, min(int(max_results or 10), 50))
    try:
        rows = db().execute(
            "SELECT p.title, p.lat, p.lng, p.feature_types, p.time_periods, p.names "
            "FROM fts JOIN places p ON p.id = fts.rowid "
            "WHERE fts MATCH ? ORDER BY rank LIMIT ?",
            (fts_prefix(query), max_results)).fetchall()
    except sqlite3.OperationalError as e:
        return f"Search error: {e}"
    if not rows:
        return f"No Pleiades places matched: {query!r}"
    out = [f"{len(rows)} place(s) for {query!r} (use get_place for full detail):\n"]
    for i, (title, lat, lng, ft, tp, names) in enumerate(rows, 1):
        coord = f"{lat:.4f}, {lng:.4f}" if lat is not None else "no coords"
        bits = [f"{i}. {title}  [{coord}]"]
        if tp:
            bits.append(f" · {tp}")
        if ft:
            bits.append(f" · {ft}")
        line = "".join(bits)
        if names:
            alt = names if len(names) <= 90 else names[:90] + "…"
            line += f"\n     names: {alt}"
        out.append(line)
    return "\n".join(out)


def do_get(title):
    t = (title or "").strip()
    conn = db()
    cols = ("title,description,lat,lng,feature_types,time_periods,time_range,uri,names")
    row = conn.execute(
        f"SELECT {cols} FROM places WHERE title = ? COLLATE NOCASE", (t,)).fetchone()
    if not row:
        row = conn.execute(
            f"SELECT {cols} FROM places WHERE title LIKE ? COLLATE NOCASE "
            "ORDER BY length(title) LIMIT 1", (t + "%",)).fetchone()
    if not row:
        # Fall back to the name index — 'Gades' is an attested name of 'Gadir'.
        try:
            hit = conn.execute(
                "SELECT p.id FROM fts JOIN places p ON p.id=fts.rowid "
                "WHERE fts MATCH ? ORDER BY rank LIMIT 1", (fts_prefix(t),)).fetchone()
        except sqlite3.OperationalError:
            hit = None
        if hit:
            row = conn.execute(f"SELECT {cols} FROM places WHERE id=?", (hit[0],)).fetchone()
    if not row:
        return f"No Pleiades place titled {title!r}. Try search_place first."
    (ttl, desc, lat, lng, ft, tp, tr, uri, names) = row
    lines = [f"# {ttl}"]
    if lat is not None:
        lines.append(f"Coordinates: {lat}, {lng}")
    if tp:
        lines.append(f"Time periods: {tp}" + (f" ({tr})" if tr else ""))
    if ft:
        lines.append(f"Feature types: {ft}")
    if names:
        lines.append(f"Attested / transliterated names: {names}")
    if uri:
        lines.append(f"Pleiades: {uri}")
    if desc:
        lines.append(f"\n{desc}")
    return "\n".join(lines)


# ── TOOLS ───────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "search_place",
        "description": (
            "Search the Pleiades gazetteer of the ancient world (~42,000 places). "
            "Matches modern titles AND attested/transliterated ancient names "
            "(prefix matching, so 'tartess' finds Tartessos, 'iber' finds "
            "Iberia). Returns places with coordinates, dating, and feature "
            "types. Use to locate/verify any ancient place — city, region, "
            "river, sanctuary. Then call get_place for full detail."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Place or ancient name, e.g. 'Gades' or 'Tartess'"},
                "max_results": {"type": "integer", "description": "Max results (default 10)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_place",
        "description": (
            "Full Pleiades record for one ancient place by title (as shown by "
            "search_place): coordinates, time periods, feature types, every "
            "attested and transliterated name, the Pleiades URI, and the "
            "description. Title match is case-insensitive with prefix fallback."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"title": {"type": "string", "description": "Place title, e.g. 'Gades'"}},
            "required": ["title"],
        },
    },
]


def handle_tools_call(params):
    name = params.get("name")
    args = params.get("arguments", {})
    if name == "search_place":
        text = do_search(args.get("query", ""), args.get("max_results", 10))
    elif name == "get_place":
        text = do_get(args.get("title", ""))
    else:
        return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}
    return {"content": [{"type": "text", "text": text}]}


# ── JSON-RPC plumbing ───────────────────────────────────────────────
def handle_initialize(params):
    return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
            "serverInfo": {"name": "pleiades", "version": "1.0.0"}}


def handle_tools_list(params):
    return {"tools": TOOLS}


HANDLERS = {"initialize": handle_initialize, "tools/list": handle_tools_list,
            "tools/call": handle_tools_call}


def process_message(msg):
    method, msg_id, params = msg.get("method"), msg.get("id"), msg.get("params", {})
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
    print(f"[pleiades] MCP server starting; db={DB_PATH}", file=sys.stderr)
    if not Path(DB_PATH).exists():
        print(f"[pleiades] WARNING: {DB_PATH} missing — run build_pleiades_corpus.py", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[pleiades] Bad JSON: {e}", file=sys.stderr)
            continue
        resp = process_message(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

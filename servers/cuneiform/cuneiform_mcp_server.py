#!/usr/bin/env python3
"""
Cuneiform Chronicles — MCP Server

Primary cuneiform ROYAL INSCRIPTIONS & HISTORIOGRAPHIC texts (Assyrian,
Babylonian, and earlier Sumerian/Akkadian) — the sources that carry regnal,
campaign and synchronism data — from the CDLI bulk data dump, searchable
full-text (FTS5, accent-insensitive).

11,795 texts with transliteration, e.g. Neo-Assyrian royal annals (2,675),
Neo-Babylonian (412) and Achaemenid material, plus Sumerian royal inscriptions
(Gudea/Lagash II, Ur III) as deep-background coverage.

Scope note: the ancient chronicle TEXTS are public domain, but the modern
critical editions of the Babylonian Chronicle series (Grayson ABC; Glassner)
are under copyright and are NOT installed. This corpus is the openly re-usable
CDLI transliterations — royal inscriptions richly, chronicle/king-list/eponym
texts where an open edition exists. Use `inventory` for the honest breakdown.

Source & licence (CDLI Terms of Use, https://cdli.earth/terms-of-use):
transliterations "may be freely copied, aggregated and re-used ... with
reference to CDLI". Photographs and line art are copyrighted and not included.

Data: cuneiform.sqlite next to this file (built by build_cuneiform.py).

Run with:
    /path/to/python3 cuneiform_mcp_server.py

CLI test mode:
    cuneiform_mcp_server.py search "Sennacherib"
    cuneiform_mcp_server.py search "Marduk" --period Neo-Babylonian
    cuneiform_mcp_server.py get P463129
    cuneiform_mcp_server.py inventory

Stdlib only; same JSON-RPC stdio pattern as the other Alexandria MCP servers.

Transcription Gate: cuneiform transliteration (ATF, with editorial marks) is
TRANSCRIBED from this tool's output, never generated from memory; translation
is Claude's own prose, marked as such.
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "cuneiform.sqlite"

_DB = None


def db():
    global _DB
    if _DB is None:
        _DB = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    return _DB


def _attr():
    row = db().execute("SELECT v FROM meta WHERE k='attribution'").fetchone()
    return row[0] if row else "Cuneiform Digital Library Initiative (CDLI) — cdli.earth"


def _link(pnum):
    num = pnum[1:] if pnum.startswith("P") else pnum
    return f"https://cdli.earth/artifacts/{num.lstrip('0') or '0'}"


def fts_query(user):
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


def search(query, max_results=15, period=None, genre=None):
    m = fts_query(query)
    if not m:
        return "ERROR: empty query."
    sql = ("SELECT d.pnum, d.designation, d.period, d.language, d.genre, "
           "snippet(docs_fts, 0, '«', '»', ' … ', 14) "
           "FROM docs_fts JOIN docs d ON d.id = docs_fts.rowid "
           "WHERE docs_fts MATCH ?")
    params = [m]
    if period:
        sql += " AND d.period LIKE ?"
        params.append(f"%{period}%")
    if genre:
        sql += " AND d.genre LIKE ?"
        params.append(f"%{genre}%")
    sql += " ORDER BY rank LIMIT ?"
    params.append(max_results)
    try:
        rows = db().execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        return f"ERROR: bad search expression ({e})."
    if not rows:
        filt = "".join(f" [{k}={v}]" for k, v in (("period", period), ("genre", genre)) if v)
        return f"No cuneiform texts match '{query}'{filt}."
    out = [f"Matches for '{query}'"
           + "".join(f" [{k}={v}]" for k, v in (("period", period), ("genre", genre)) if v)
           + f" — showing {len(rows)}:\n"]
    for pnum, desig, per, lang, gen, snip in rows:
        head = f"▸ {pnum}"
        if desig:
            head += f"  {desig}"
        out.append(head)
        meta = "  ·  ".join(x for x in (per, lang, gen) if x)
        if meta:
            out.append(f"    {meta}")
        out.append(f"    …{snip}…")
        out.append(f"    get {pnum}   ·   {_link(pnum)}")
    out.append("")
    out.append(_attr())
    return "\n".join(out)


def get(pnum):
    pnum = (pnum or "").strip()
    if not pnum:
        return "ERROR: empty identifier."
    if not pnum.startswith("P") and pnum.isdigit():
        pnum = "P" + pnum.zfill(6)
    row = db().execute(
        "SELECT pnum, designation, genre, subgenre, period, provenience, language, text "
        "FROM docs WHERE pnum = ? LIMIT 1", (pnum,)).fetchone()
    if not row:
        return (f"No cuneiform text '{pnum}'. Use a CDLI P-number (e.g. 'P463129') "
                f"from a search hit, or run 'search' to find one.")
    p, desig, gen, sub, per, prov, lang, text = row
    head = [p]
    for x in (desig, per, lang):
        if x:
            head.append(x)
    lines = ["  ·  ".join(head)]
    detail = "  ·  ".join(x for x in (gen, sub, prov) if x)
    if detail:
        lines.append(detail)
    lines.append(_link(p))
    lines.append(_attr())
    lines.append("(transcribe the ATF transliteration below — editorial marks are the "
                 "editor's; translate in your own prose)\n")
    lines.append(text)
    return "\n".join(lines)


def inventory():
    d = db()
    tot = d.execute("SELECT count(*) FROM docs").fetchone()[0]
    out = ["Cuneiform Chronicles — royal inscriptions & historiographic texts",
           f"  {tot:,} texts with transliteration (CDLI open ATF)\n",
           "By period (top 12):"]
    for per, c in d.execute("SELECT period, count(*) c FROM docs GROUP BY period "
                            "ORDER BY c DESC LIMIT 12").fetchall():
        out.append(f"  {c:6}  {per or '(unspecified)'}")
    out.append("\nBy language (top 8):")
    for lang, c in d.execute("SELECT language, count(*) c FROM docs GROUP BY language "
                             "ORDER BY c DESC LIMIT 8").fetchall():
        out.append(f"  {c:6}  {lang or '(unspecified)'}")
    out.append("\nScope: openly re-usable CDLI transliterations only. The modern")
    out.append("critical editions of the Babylonian Chronicle series (Grayson ABC;")
    out.append("Glassner) are under copyright and are deliberately NOT installed —")
    out.append("this corpus is the royal inscriptions and the open historiographic")
    out.append("texts (chronicle / king-list / eponym) that carry synchronism data.")
    out.append("For Assyrian & Babylonian material, filter search with e.g.")
    out.append("  period='Neo-Assyrian'  ·  period='Neo-Babylonian'  ·  period='Achaemenid'")
    out.append("")
    out.append(_attr())
    return "\n".join(out)


# ── MCP plumbing ────────────────────────────────────────────────────

def handle_initialize(params):
    return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
            "serverInfo": {"name": "cuneiform-chronicles", "version": "1.0.0"}}


TOOLS = [
    {
        "name": "search",
        "description": (
            "Full-text search across ~11,800 cuneiform royal inscriptions & "
            "historiographic texts (CDLI open transliterations): Assyrian & Babylonian "
            "royal annals, king-lists, eponym and historical texts, plus earlier "
            "Sumerian/Akkadian royal inscriptions. Accent-insensitive; prefix ('Sennach*') "
            "and multi-term (AND) queries. Filter by 'period' (e.g. 'Neo-Assyrian', "
            "'Neo-Babylonian', 'Achaemenid') or 'genre'. Returns CDLI P-numbers, snippets "
            "and cdli.earth links. Primary sources — transcribe from get, translate yourself."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Word/name/phrase; '*' for prefix"},
                "period": {"type": "string",
                           "description": "Optional period filter, e.g. 'Neo-Assyrian', 'Neo-Babylonian', 'Achaemenid'"},
                "genre": {"type": "string", "description": "Optional genre filter, e.g. 'Royal/Monumental'"},
                "max_results": {"type": "number", "description": "Default 15"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get",
        "description": (
            "Retrieve one cuneiform text's full ATF transliteration + metadata by CDLI "
            "P-number (e.g. 'P463129'), with a cdli.earth link and the CDLI attribution."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pnum": {"type": "string", "description": "CDLI P-number, e.g. 'P463129'"},
            },
            "required": ["pnum"],
        },
    },
    {
        "name": "inventory",
        "description": (
            "Report the corpus: totals, breakdown by period and language, the CDLI "
            "attribution, and the honest scope note (which chronicle editions are "
            "excluded by copyright and how to filter to Assyrian/Babylonian)."
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
                          args.get("period") or None, args.get("genre") or None)
        elif name == "get":
            text = get(args.get("pnum", ""))
        elif name == "inventory":
            text = inventory()
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
            period = genre = None
            for flag, setter in (("--period", "period"), ("--genre", "genre")):
                if flag in rest:
                    i = rest.index(flag)
                    val = rest[i + 1] if i + 1 < len(rest) else None
                    if setter == "period":
                        period = val
                    else:
                        genre = val
                    rest = rest[:i] + rest[i + 2:]
            print(search(" ".join(rest), period=period, genre=genre))
        elif cmd == "get":
            print(get(sys.argv[2] if len(sys.argv) > 2 else ""))
        elif cmd == "inventory":
            print(inventory())
        else:
            print(__doc__)
        return
    print("[cuneiform-chronicles] MCP server starting...", file=sys.stderr)
    print(f"[cuneiform-chronicles] DB: {DB_PATH}", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[cuneiform-chronicles] Bad JSON: {e}", file=sys.stderr)
            continue
        resp = process_message(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

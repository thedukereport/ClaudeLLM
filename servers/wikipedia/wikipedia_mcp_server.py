#!/usr/bin/env python3
"""
Local Wikipedia — MCP Server
Exposes an offline Wikipedia (a Kiwix ZIM archive) as MCP tools: full-text
search and full-article retrieval, using the ZIM's own built-in search index.

Run with (needs libzim in the venv):
    /Volumes/PRO-BLADE/Alexandria/RAG_system/rag_env/bin/python \
        /Volumes/PRO-BLADE/Wikipedia/wikipedia_mcp_server.py

Requires:  pip install libzim   (into the venv you launch it with)
Data:      the newest *.zim in this folder (drop a Kiwix Wikipedia ZIM here),
           or set WIKIPEDIA_ZIM to an explicit path.

Same JSON-RPC/stdio pattern as the other Alexandria MCP servers. Cite as
Wikipedia, community-edited, with the article title and the ZIM edition date.
"""

import os
import re
import sys
import json
import glob
import html
from pathlib import Path

from libzim.reader import Archive
from libzim.search import Query, Searcher
from libzim.suggestion import SuggestionSearcher

HERE = Path(__file__).resolve().parent
_archive = None


def find_zim():
    env = os.environ.get("WIKIPEDIA_ZIM")
    if env and Path(env).exists():
        return env
    cands = sorted(glob.glob(str(HERE / "*.zim")))
    return cands[-1] if cands else None   # newest by name (dated filenames sort)


def archive():
    global _archive
    if _archive is None:
        p = find_zim()
        if not p:
            raise RuntimeError(f"No Wikipedia ZIM found in {HERE} (or $WIKIPEDIA_ZIM).")
        _archive = Archive(p)
    return _archive


def strip_html(s):
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _resolve(entry):
    return entry.get_redirect_entry() if entry.is_redirect else entry


def _text_of(entry):
    return bytes(_resolve(entry).get_item().content).decode("utf-8", "replace")


# ── DATA LAYER ──────────────────────────────────────────────────────
def do_search(query, max_results=8):
    a = archive()
    max_results = max(1, min(int(max_results or 8), 25))
    if not a.has_fulltext_index:
        # No full-text index in this ZIM — fall back to title suggestions.
        try:
            ss = SuggestionSearcher(a).suggest(query)
            paths = list(ss.getResults(0, max_results))
        except Exception as e:
            return f"Search error (no fulltext index): {e}"
        titles = []
        for p in paths:
            try:
                titles.append(a.get_entry_by_path(p).title)
            except Exception:
                titles.append(p)
        return "Title matches (no full-text index in this ZIM):\n" + \
               "\n".join(f"{i}. {t}" for i, t in enumerate(titles, 1))

    search = Searcher(a).search(Query().set_query(query))
    n = search.getEstimatedMatches()
    if not n:
        return f"No Wikipedia articles matched: {query!r}"
    paths = list(search.getResults(0, max_results))
    out = [f"{len(paths)} of ~{n:,} matches for {query!r} (use get_wikipedia_article for full text):\n"]
    for i, path in enumerate(paths, 1):
        try:
            e = a.get_entry_by_path(path)
            title = e.title
            snip = strip_html(_text_of(e))[:220]
            out.append(f"{i}. {title}\n     {snip}…")
        except Exception:
            out.append(f"{i}. {path}")
    return "\n".join(out)


def do_get(title):
    a = archive()
    t = (title or "").strip()
    entry = None
    if a.has_entry_by_title(t):
        entry = a.get_entry_by_title(t)
    if entry is None:                       # fuzzy title, then full-text
        try:
            for p in list(SuggestionSearcher(a).suggest(t).getResults(0, 1)):
                entry = a.get_entry_by_path(p)
        except Exception:
            entry = None
    if entry is None and a.has_fulltext_index:
        try:
            for p in list(Searcher(a).search(Query().set_query(t)).getResults(0, 1)):
                entry = a.get_entry_by_path(p)
        except Exception:
            entry = None
    if entry is None:
        return f"No Wikipedia article found for {title!r}. Try search_wikipedia first."
    entry = _resolve(entry)
    body = strip_html(_text_of(entry))
    if len(body) > 60000:
        body = body[:60000] + "\n\n[... truncated ...]"
    return f"# {entry.title}\n(Source: Wikipedia, community-edited)\n\n{body}"


# ── TOOLS ───────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "search_wikipedia",
        "description": (
            "Full-text search across the local offline Wikipedia (Kiwix ZIM). "
            "Returns ranked article titles with a matching snippet; then call "
            "get_wikipedia_article for the full text. Community-edited "
            "reference; attribute claims to it by article title. "
            "Keyword/phrase queries."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords or phrase"},
                "max_results": {"type": "integer", "description": "Max results (default 8)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_wikipedia_article",
        "description": (
            "Return the full plain text of a Wikipedia article by title (as shown "
            "by search_wikipedia). Resolves redirects and falls back to a fuzzy "
            "title / full-text match if the exact title isn't found."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"title": {"type": "string", "description": "Article title, e.g. 'Bretton Woods system'"}},
            "required": ["title"],
        },
    },
]


def handle_tools_call(params):
    name = params.get("name")
    args = params.get("arguments", {})
    if name == "search_wikipedia":
        text = do_search(args.get("query", ""), args.get("max_results", 8))
    elif name == "get_wikipedia_article":
        text = do_get(args.get("title", ""))
    else:
        return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}
    return {"content": [{"type": "text", "text": text}]}


# ── JSON-RPC plumbing ───────────────────────────────────────────────
def handle_initialize(params):
    return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
            "serverInfo": {"name": "wikipedia", "version": "1.0.0"}}


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
    z = find_zim()
    print(f"[wikipedia] MCP server starting; zim={z or 'NONE FOUND'}", file=sys.stderr)
    if not z:
        print(f"[wikipedia] WARNING: drop a Kiwix .zim into {HERE} (or set WIKIPEDIA_ZIM).", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[wikipedia] Bad JSON: {e}", file=sys.stderr)
            continue
        resp = process_message(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

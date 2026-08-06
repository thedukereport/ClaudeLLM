#!/usr/bin/env python3
"""
Project Gutenberg — MCP Server (multi-ZIM)

Exposes an offline Project Gutenberg library as MCP tools. Unlike the Wikipedia
server (one archive), this one opens EVERY *.zim in its folder and searches
across all of them, so you can install as many Library-of-Congress subject
subsets as you like and query them as a single library.

The LCC class is parsed out of the filename (gutenberg_en_lcc-<class>_<date>.zim),
so every hit is tagged with its subject — "[Religion/Philosophy]", "[World
history]" — which is the main reason to prefer the subsets over the single
206 GB bundle.

Run with (needs libzim in the venv):
    /Volumes/PRO-BLADE/mcp_env/bin/python \
        /Volumes/PRO-BLADE/Gutenberg/gutenberg_mcp_server.py

Requires:  pip install libzim
Data:      any number of Kiwix Gutenberg ZIMs in this folder (see
           download_gutenberg.py). Newest file wins per subject.

Everything in Project Gutenberg is public domain in the US. Cite the author,
title, and Project Gutenberg as the source.
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
_archives = None            # list of (subject_label, lcc_code, Archive, filename)

# Library of Congress classification -> human subject
LCC = {
    "a": "General works", "b": "Philosophy, Psychology, Religion",
    "c": "Archaeology, genealogy, historical sciences", "d": "World history",
    "e": "History of the Americas", "f": "History of the Americas (local)",
    "g": "Geography, Anthropology, Recreation", "h": "Social sciences",
    "j": "Political science", "k": "Law", "l": "Education", "m": "Music",
    "n": "Fine arts", "p": "Language & literature (general)",
    "pa": "Classical (Greek & Latin)", "pb": "Modern & Celtic languages",
    "pc": "Romance languages", "pd": "Germanic languages", "pe": "English language",
    "pf": "West Germanic languages", "pg": "Slavic & Baltic", "ph": "Finno-Ugric, Basque",
    "pj": "Oriental & Semitic", "pk": "Indo-Iranian",
    "pl": "Languages of E. Asia, Africa, Oceania", "pm": "Indigenous & artificial languages",
    "pn": "Literature (general), criticism, drama", "pq": "Romance literatures",
    "pr": "English literature", "ps": "American literature", "pt": "Germanic literature",
    "pz": "Fiction & juvenile literature", "q": "Science", "r": "Medicine",
    "s": "Agriculture", "t": "Technology", "u": "Military science",
    "v": "Naval science", "z": "Bibliography & library science",
}


def _parse(fn):
    """gutenberg_en_lcc-pj_2026-03.zim -> ('pj', '2026-03')"""
    m = re.search(r"lcc-([a-z]+)_([\d-]+)\.zim$", fn)
    return (m.group(1), m.group(2)) if m else (None, "")


def archives():
    """Open every ZIM in the folder once. Newest file wins per LCC class."""
    global _archives
    if _archives is None:
        env = os.environ.get("GUTENBERG_DIR")
        base = Path(env) if env else HERE
        best = {}
        for p in sorted(glob.glob(str(base / "*.zim"))):
            code, date = _parse(os.path.basename(p))
            key = code or os.path.basename(p)
            if key not in best or date > best[key][0]:
                best[key] = (date, p, code)
        _archives = []
        for key, (date, p, code) in sorted(best.items()):
            try:
                a = Archive(p)
            except Exception as e:
                print(f"[gutenberg] skip {p}: {e}", file=sys.stderr)
                continue
            label = LCC.get(code, "Project Gutenberg") if code else "Project Gutenberg"
            _archives.append((label, code, a, os.path.basename(p)))
        if not _archives:
            raise RuntimeError(
                f"No Gutenberg ZIMs found in {base}. Run download_gutenberg.py "
                f"(or set GUTENBERG_DIR).")
    return _archives


def strip_html(s):
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    # Gutenberg HTML is padded with whitespace-only lines; \n{3,} misses them
    # because each "blank" line holds a space. Collapse properly.
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"(?:[ \t]*\n){3,}", "\n\n", s)
    return s.strip()


def _resolve(entry):
    return entry.get_redirect_entry() if entry.is_redirect else entry


# Each book appears in a Kiwix Gutenberg ZIM three times:
#   "Title.50336"        -> the actual text        (text/html)   <- what we want
#   "Title.50336.epub"   -> the ebook              (binary)
#   "Title_cover.50336"  -> Kiwix's cover/nav page (text/html, ~97 KB of chrome)
# Search indexes the text AND the cover, so results duplicate unless we collapse
# them to one key and always read the text entry.
_COVER = re.compile(r"^(.*)_cover\.(\d+)$")


def _book_key(path):
    """Collapse the three faces of a book to one identity."""
    if path.endswith(".epub"):
        path = path[:-5]
    m = _COVER.match(path)
    return f"{m.group(1)}.{m.group(2)}" if m else path


def _prefer_text(a, entry):
    """Given a cover entry, swap in the real text entry."""
    m = _COVER.match(entry.path)
    if m:
        try:
            return a.get_entry_by_path(f"{m.group(1)}.{m.group(2)}")
        except Exception:
            pass
    return entry


def _is_chrome(path, mime):
    return (path.endswith(".epub") or path in ("Home", "mainPage")
            or not (mime or "").startswith("text/html"))


def _text_of(entry):
    return bytes(_resolve(entry).get_item().content).decode("utf-8", "replace")


# ── DATA LAYER ──────────────────────────────────────────────────────
def do_search(query, subject=None, max_results=10):
    arcs = archives()
    if subject:
        s = subject.lower().strip()
        arcs = [x for x in arcs if x[1] == s or s in x[0].lower()]
        if not arcs:
            return (f"No installed subset matches subject {subject!r}. "
                    f"Use list_subjects to see what's installed.")
    max_results = max(1, min(int(max_results or 10), 30))
    per = max(2, max_results // max(1, len(arcs)) + 1)

    buckets = []
    for label, code, a, fn in arcs:
        if not a.has_fulltext_index:
            continue
        try:
            search = Searcher(a).search(Query().set_query(query))
            n = search.getEstimatedMatches()
            if not n:
                continue
            hits, seen = [], set()
            for path in list(search.getResults(0, per * 3)):   # over-fetch: covers dedupe away
                key = _book_key(path)
                if key in seen:
                    continue
                try:
                    e = a.get_entry_by_path(path)
                    if _is_chrome(e.path, e.get_item().mimetype):
                        continue
                    e = _prefer_text(a, e)
                    seen.add(key)
                    body = strip_html(_text_of(e))
                    # Gutenberg pages are full of blank lines — collapse ALL
                    # whitespace for the snippet, and skip the repeated title.
                    flat = re.sub(r"\s+", " ", body).strip()
                    if flat.lower().startswith(e.title.lower()):
                        flat = flat[len(e.title):].lstrip(" .—-")
                    hits.append((e.title, flat[:200]))
                    if len(hits) >= per:
                        break
                except Exception:
                    continue
            if hits:
                buckets.append((label, code, n, hits))
        except Exception as e:
            print(f"[gutenberg] search error in {fn}: {e}", file=sys.stderr)

    if not buckets:
        return f"No Gutenberg books matched: {query!r}"

    # round-robin so one big subject can't crowd out the rest
    out, shown, i = [], 0, 0
    total = sum(b[2] for b in buckets)
    out.append(f"~{total:,} matches for {query!r} across {len(buckets)} subject(s). "
               f"Use get_book with a title for the full text.\n")
    while shown < max_results:
        progressed = False
        for label, code, n, hits in buckets:
            if i < len(hits):
                title, snip = hits[i]
                out.append(f"{shown+1}. {title}  [{label}]\n     {snip}…")
                shown += 1; progressed = True
                if shown >= max_results:
                    break
        if not progressed:
            break
        i += 1
    return "\n".join(out)


def do_get(title, subject=None):
    arcs = archives()
    if subject:
        s = subject.lower().strip()
        arcs = [x for x in arcs if x[1] == s or s in x[0].lower()] or arcs
    t = (title or "").strip()

    def try_path(a, p, label):
        try:
            e = a.get_entry_by_path(p)
            if _is_chrome(e.path, e.get_item().mimetype):
                return None
            return _render(_prefer_text(a, e), label)
        except Exception:
            return None

    for label, code, a, fn in arcs:                   # 1) exact title
        try:
            if a.has_entry_by_title(t):
                e = _prefer_text(a, a.get_entry_by_title(t))
                if not _is_chrome(e.path, e.get_item().mimetype):
                    return _render(e, label)
        except Exception:
            pass
    for label, code, a, fn in arcs:                   # 2) fuzzy title
        try:
            for p in list(SuggestionSearcher(a).suggest(t).getResults(0, 4)):
                r = try_path(a, p, label)
                if r:
                    return r
        except Exception:
            pass
    for label, code, a, fn in arcs:                   # 3) full text
        try:
            if not a.has_fulltext_index:
                continue
            for p in list(Searcher(a).search(Query().set_query(t)).getResults(0, 4)):
                r = try_path(a, p, label)
                if r:
                    return r
        except Exception:
            pass
    return (f"No Gutenberg book found for {title!r}. Try search_gutenberg first, "
            f"or check list_subjects — the relevant subset may not be installed.")


def _render(entry, label):
    entry = _resolve(entry)
    body = strip_html(_text_of(entry))
    if len(body) > 60000:
        body = body[:60000] + "\n\n[... truncated — ask for a later section ...]"
    return f"# {entry.title}\n(Project Gutenberg — {label}; public domain)\n\n{body}"


def do_list():
    try:
        arcs = archives()
    except RuntimeError as e:
        return str(e)
    out = [f"{len(arcs)} Gutenberg subset(s) installed:\n"]
    total = 0
    for label, code, a, fn in arcs:
        n = a.article_count
        total += n
        idx = "" if a.has_fulltext_index else "  (no full-text index)"
        out.append(f"• lcc-{code or '?':<3} {label:<42} {n:>7,} entries{idx}")
    out.append(f"\nTotal: {total:,} entries. All public domain (US).")
    return "\n".join(out)


# ── TOOLS ───────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "search_gutenberg",
        "description": (
            "Full-text search across the offline Project Gutenberg library "
            "(public-domain books). Searches every installed Library-of-Congress "
            "subject subset at once and tags each hit with its subject. Optionally "
            "restrict with 'subject' — an LCC code ('b', 'd', 'pa') or a word from "
            "the subject name ('religion', 'history', 'classical'). Then call "
            "get_book for the full text. Source: Project Gutenberg; public domain."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords or phrase"},
                "subject": {"type": "string",
                            "description": "Optional LCC code or subject word, e.g. 'b', 'religion'"},
                "max_results": {"type": "integer", "description": "Max results (default 10)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_book",
        "description": (
            "Return the full plain text of a Gutenberg book/page by title (as shown "
            "by search_gutenberg). Resolves redirects, falls back to fuzzy title then "
            "full-text match. Long texts are truncated. Optional 'subject' filter."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title, e.g. 'The Republic'"},
                "subject": {"type": "string", "description": "Optional LCC code or subject word"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "list_subjects",
        "description": "List the installed Gutenberg subject subsets with entry counts.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def handle_tools_call(params):
    name = params.get("name")
    a = params.get("arguments", {})
    if name == "search_gutenberg":
        text = do_search(a.get("query", ""), a.get("subject"), a.get("max_results", 10))
    elif name == "get_book":
        text = do_get(a.get("title", ""), a.get("subject"))
    elif name == "list_subjects":
        text = do_list()
    else:
        return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}
    return {"content": [{"type": "text", "text": text}]}


# ── JSON-RPC plumbing ───────────────────────────────────────────────
def handle_initialize(params):
    return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
            "serverInfo": {"name": "gutenberg", "version": "1.0.0"}}


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
    base = os.environ.get("GUTENBERG_DIR", str(HERE))
    n = len(glob.glob(os.path.join(base, "*.zim")))
    print(f"[gutenberg] MCP server starting; dir={base}; {n} zim file(s)", file=sys.stderr)
    if not n:
        print(f"[gutenberg] WARNING: no .zim files yet — run download_gutenberg.py",
              file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[gutenberg] Bad JSON: {e}", file=sys.stderr)
            continue
        resp = process_message(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

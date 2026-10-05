#!/usr/bin/env python3
"""
Wiktionary — MCP Server (offline, stdlib only)

Exposes the English edition of Wiktionary (enwiktionary, hundreds of languages
with English glosses) as MCP tools: definitions/senses, etymology, pronunciation
(IPA), translations, descendants, lexical relations, and full-text gloss search.
Because one headword (e.g. "a", "deror", "libertas") can exist in many languages,
every tool takes an optional `lang` filter (a language name like "Latin" or a
code like "la", "grc", "he", "sux").

Data built into wiktionary.sqlite by build_wiktionary.py (kaikki.org /
wiktextract, CC BY-SA 4.0). All local. Stdlib only.

Run with any Python 3, e.g.:
    /Volumes/PRO-BLADE/Alexandria/RAG_system/rag_env/bin/python \
        /Volumes/PRO-BLADE/Wiktionary/wiktionary_mcp_server.py

CLI test:
    wiktionary_mcp_server.py define libertas la
    wiktionary_mcp_server.py etymology eleutheria grc
    wiktionary_mcp_server.py pronunciation water en
    wiktionary_mcp_server.py descendants libertas la
    wiktionary_mcp_server.py relations free derived en
    wiktionary_mcp_server.py languages deror
    wiktionary_mcp_server.py search "to set free"
"""

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("WIKTIONARY_DB", HERE / "wiktionary.sqlite"))
_DB = None

REL_FIELDS = {"derived", "related", "synonyms", "antonyms", "hypernyms",
              "hyponyms", "holonyms", "meronyms"}
REL_ALIAS = {"synonym": "synonyms", "antonym": "antonyms", "derived_terms": "derived",
             "broader": "hypernyms", "narrower": "hyponyms", "parts": "meronyms",
             "wholes": "holonyms", "related_terms": "related"}


def db():
    global _DB
    if _DB is None:
        _DB = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    return _DB


def _norm_lang(lang):
    """Accept a language name or code; return (clause, param) for a WHERE filter."""
    if not lang:
        return "", None
    lang = lang.strip()
    # a short token is treated as a code, a longer one as a language name
    if len(lang) <= 3 and lang.islower():
        return " AND lang_code=?", lang
    return " AND lower(lang)=?", lang.lower()


def _fetch(word, lang=None, pos=None):
    clause, lp = _norm_lang(lang)
    q = ("SELECT id, word, lang, lang_code, pos, etymology, data "
         "FROM entries WHERE word_lc=?")
    p = [(word or "").strip().lower()]
    if lp is not None:
        q += clause
        p.append(lp)
    if pos:
        q += " AND pos=?"
        p.append(pos.strip().lower())
    q += " ORDER BY lang, pos"
    rows = []
    for r in db().execute(q, p).fetchall():
        try:
            data = json.loads(r[6]) if r[6] else {}
        except json.JSONDecodeError:
            data = {}
        rows.append({"id": r[0], "word": r[1], "lang": r[2], "lang_code": r[3],
                     "pos": r[4], "etymology": r[5], "data": data})
    return rows


def _hdr(e):
    return f"{e['word']}  ({e['lang']} [{e['lang_code']}], {e['pos'] or '?'})"


def _no_entry(word, lang):
    tail = f" in {lang}" if lang else ""
    other = ""
    if lang:
        langs = [r[0] for r in db().execute(
            "SELECT DISTINCT lang FROM entries WHERE word_lc=? ORDER BY lang",
            [(word or '').strip().lower()]).fetchall()]
        if langs:
            other = " Present in: " + ", ".join(langs[:25]) + "."
    return f"No Wiktionary entry for '{word}'{tail}.{other}"


# ── tools ───────────────────────────────────────────────────────────

def define(word, lang=None, pos=None):
    word = (word or "").strip()
    if not word:
        return "ERROR: empty word."
    entries = _fetch(word, lang, pos)
    if not entries:
        return _no_entry(word, lang)
    out = []
    for e in entries:
        out.append("\n" + _hdr(e))
        senses = e["data"].get("senses", []) or []
        n = 0
        for s in senses:
            glosses = s.get("glosses") or s.get("raw_glosses") or []
            if not glosses:
                continue
            n += 1
            tags = s.get("tags") or []
            tagstr = f" [{', '.join(tags)}]" if tags else ""
            out.append(f"  {n}.{tagstr} {'; '.join(glosses)}")
            for ex in (s.get("examples") or [])[:2]:
                t = ex.get("text")
                if t:
                    tr = ex.get("english") or ex.get("translation")
                    out.append(f"       e.g. {t}" + (f"  — {tr}" if tr else ""))
        if n == 0:
            out.append("  (no glosses recorded)")
    out.append("\n(Wiktionary via wiktextract / kaikki.org, CC BY-SA 4.0)")
    return "\n".join(out)


def etymology(word, lang=None):
    word = (word or "").strip()
    entries = _fetch(word, lang)
    if not entries:
        return _no_entry(word, lang)
    out, found = [], False
    for e in entries:
        ety = e["etymology"]
        if ety:
            found = True
            out.append(f"\n{_hdr(e)}\n  {ety}")
    if not found:
        return f"No etymology recorded for '{word}'" + (f" in {lang}" if lang else "") + "."
    return "\n".join(out)


def pronunciation(word, lang=None):
    word = (word or "").strip()
    entries = _fetch(word, lang)
    if not entries:
        return _no_entry(word, lang)
    out, found = [], False
    for e in entries:
        ipas = []
        for s in e["data"].get("sounds", []) or []:
            ipa = s.get("ipa")
            if ipa:
                tags = s.get("tags") or []
                ipas.append(ipa + (f" ({', '.join(tags)})" if tags else ""))
            elif s.get("enpr"):
                ipas.append(f"enPR: {s['enpr']}")
        if ipas:
            found = True
            out.append(f"\n{_hdr(e)}\n  " + "\n  ".join(dict.fromkeys(ipas)))
    if not found:
        return f"No pronunciation recorded for '{word}'" + (f" in {lang}" if lang else "") + "."
    return "\n".join(out)


def translations(word, lang=None, max_results=60):
    word = (word or "").strip()
    entries = _fetch(word, lang or "en")
    if not entries:
        return _no_entry(word, lang or "English")
    out, found = [], False
    for e in entries:
        tr = e["data"].get("translations", []) or []
        if not tr:
            continue
        found = True
        out.append(f"\n{_hdr(e)}")
        by_sense = {}
        for t in tr[:max_results]:
            key = t.get("sense") or ""
            by_sense.setdefault(key, []).append(t)
        for sense, items in by_sense.items():
            if sense:
                out.append(f"  — {sense}")
            for t in items:
                langname = t.get("lang") or t.get("code") or "?"
                w = t.get("word") or ""
                roman = t.get("roman")
                out.append(f"     {langname}: {w}" + (f" ({roman})" if roman else ""))
    if not found:
        return f"No translations recorded for '{word}' (translations live on the English entry)."
    return "\n".join(out)


def descendants(word, lang=None):
    word = (word or "").strip()
    entries = _fetch(word, lang)
    if not entries:
        return _no_entry(word, lang)
    out, found = [], False
    for e in entries:
        ds = e["data"].get("descendants", []) or []
        if not ds:
            continue
        found = True
        out.append(f"\n{_hdr(e)} → descendants:")
        for d in ds:
            w = d.get("word") or ""
            tags = d.get("tags") or []
            out.append(f"   {w}" + (f"  [{', '.join(tags)}]" if tags else ""))
    if not found:
        return f"No descendants recorded for '{word}'" + (f" in {lang}" if lang else "") + "."
    return "\n".join(out)


def relations(word, relation, lang=None):
    word = (word or "").strip()
    rel = (relation or "").strip().lower()
    rel = REL_ALIAS.get(rel, rel)
    if rel not in REL_FIELDS:
        return ("ERROR: relation must be one of: " + ", ".join(sorted(REL_FIELDS)) +
                " (aliases: " + ", ".join(sorted(REL_ALIAS)) + ").")
    entries = _fetch(word, lang)
    if not entries:
        return _no_entry(word, lang)
    out, found = [], False
    for e in entries:
        items = e["data"].get(rel, []) or []
        if not items:
            continue
        found = True
        words = []
        for it in items:
            w = it.get("word")
            if w:
                words.append(w)
        out.append(f"\n{_hdr(e)} → {rel}:\n  " + ", ".join(dict.fromkeys(words)))
    if not found:
        return f"'{word}' has no '{rel}'" + (f" in {lang}" if lang else "") + "."
    return "\n".join(out)


def languages(word):
    word = (word or "").strip()
    rows = db().execute(
        "SELECT DISTINCT lang, lang_code FROM entries WHERE word_lc=? ORDER BY lang",
        [word.lower()]).fetchall()
    if not rows:
        return _no_entry(word, None)
    return (f"'{word}' has Wiktionary entries in {len(rows)} language(s):\n  " +
            "\n  ".join(f"{lang} [{code}]" for lang, code in rows))


def search_glosses(query, lang=None, max_results=20):
    q = re.sub(r'["*]', " ", (query or "").strip())
    if not q:
        return "ERROR: empty query."
    toks = " ".join(f'"{t}"' for t in q.split())
    sql = ("SELECT word, lang_code, gloss FROM gloss_fts WHERE gloss_fts MATCH ?")
    params = [toks]
    _, lp = _norm_lang(lang)
    if lp is not None and lang and (len(lang) <= 3 and lang.islower()):
        sql += " AND lang_code=?"
        params.append(lp)
    sql += " LIMIT ?"
    params.append(max_results)
    try:
        rows = db().execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        return f"ERROR: {e}"
    if not rows:
        return f"No glosses match '{query}'" + (f" in {lang}" if lang else "") + "."
    out = [f"Glosses matching '{query}':"]
    for w, code, gloss in rows:
        out.append(f"  {w} [{code}]: {gloss}")
    return "\n".join(out)


# ── MCP plumbing ────────────────────────────────────────────────────

TOOLS = [
    {"name": "define",
     "description": ("Define a word via Wiktionary: every sense with part of speech, "
                     "usage tags, and examples. One headword can exist in many "
                     "languages, so pass optional 'lang' (name like 'Latin' or code "
                     "like 'la','grc','he','sux') and optional 'pos' to narrow it."),
     "inputSchema": {"type": "object", "properties": {
         "word": {"type": "string"},
         "lang": {"type": "string", "description": "language name or code (optional)"},
         "pos": {"type": "string", "description": "noun|verb|adj|... (optional)"}},
         "required": ["word"]}},
    {"name": "etymology",
     "description": "Wiktionary etymology (word origin and history) for a word, per language entry. Optional 'lang' filter.",
     "inputSchema": {"type": "object", "properties": {
         "word": {"type": "string"}, "lang": {"type": "string"}}, "required": ["word"]}},
    {"name": "pronunciation",
     "description": "IPA pronunciation(s) for a word from Wiktionary, with accent tags. Optional 'lang' filter.",
     "inputSchema": {"type": "object", "properties": {
         "word": {"type": "string"}, "lang": {"type": "string"}}, "required": ["word"]}},
    {"name": "translations",
     "description": ("Translations of a word into other languages (recorded on the "
                     "English entry), grouped by sense. Optional 'lang' (defaults to English)."),
     "inputSchema": {"type": "object", "properties": {
         "word": {"type": "string"}, "lang": {"type": "string"},
         "max_results": {"type": "integer"}}, "required": ["word"]}},
    {"name": "descendants",
     "description": ("Descendant words that evolved/borrowed from this word in later "
                     "languages (e.g. Latin libertas → Romance forms). Optional 'lang'."),
     "inputSchema": {"type": "object", "properties": {
         "word": {"type": "string"}, "lang": {"type": "string"}}, "required": ["word"]}},
    {"name": "relations",
     "description": ("Lexical relations for a word: derived, related, synonyms, antonyms, "
                     "hypernyms, hyponyms, holonyms, meronyms. Optional 'lang'."),
     "inputSchema": {"type": "object", "properties": {
         "word": {"type": "string"},
         "relation": {"type": "string", "description": "derived|related|synonyms|antonyms|hypernyms|hyponyms|holonyms|meronyms"},
         "lang": {"type": "string"}}, "required": ["word", "relation"]}},
    {"name": "languages",
     "description": "List every language that has a Wiktionary entry for this headword (disambiguation helper).",
     "inputSchema": {"type": "object", "properties": {"word": {"type": "string"}}, "required": ["word"]}},
    {"name": "search_glosses",
     "description": "Full-text search Wiktionary definitions (glosses) for a word or phrase; returns matching headwords. Optional 'lang' code filter.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "lang": {"type": "string"},
         "max_results": {"type": "integer"}}, "required": ["query"]}},
]


def handle_tools_call(params):
    name = params.get("name"); a = params.get("arguments", {}) or {}
    try:
        if name == "define":
            text = define(a.get("word", ""), a.get("lang"), a.get("pos"))
        elif name == "etymology":
            text = etymology(a.get("word", ""), a.get("lang"))
        elif name == "pronunciation":
            text = pronunciation(a.get("word", ""), a.get("lang"))
        elif name == "translations":
            text = translations(a.get("word", ""), a.get("lang"), int(a.get("max_results", 60)))
        elif name == "descendants":
            text = descendants(a.get("word", ""), a.get("lang"))
        elif name == "relations":
            text = relations(a.get("word", ""), a.get("relation", ""), a.get("lang"))
        elif name == "languages":
            text = languages(a.get("word", ""))
        elif name == "search_glosses":
            text = search_glosses(a.get("query", ""), a.get("lang"), int(a.get("max_results", 20)))
        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"ERROR: {type(e).__name__}: {e}"}], "isError": True}
    return {"content": [{"type": "text", "text": text}]}


HANDLERS = {
    "initialize": lambda p: {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                             "serverInfo": {"name": "wiktionary", "version": "1.0.0"}},
    "tools/list": lambda p: {"tools": TOOLS},
    "tools/call": handle_tools_call,
}


def process_message(msg):
    method, msg_id, params = msg.get("method"), msg.get("id"), msg.get("params", {})
    if msg_id is None:
        return None
    h = HANDLERS.get(method)
    if h:
        try:
            return {"jsonrpc": "2.0", "id": msg_id, "result": h(params)}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32000, "message": f"{type(e).__name__}: {e}"}}
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main():
    if len(sys.argv) > 1:  # CLI test
        cmd = sys.argv[1]; args = sys.argv[2:]
        fn = {
            "define": lambda: define(args[0], args[1] if len(args) > 1 else None,
                                     args[2] if len(args) > 2 else None),
            "etymology": lambda: etymology(args[0], args[1] if len(args) > 1 else None),
            "pronunciation": lambda: pronunciation(args[0], args[1] if len(args) > 1 else None),
            "translations": lambda: translations(args[0], args[1] if len(args) > 1 else None),
            "descendants": lambda: descendants(args[0], args[1] if len(args) > 1 else None),
            "relations": lambda: relations(args[0], args[1] if len(args) > 1 else "",
                                           args[2] if len(args) > 2 else None),
            "languages": lambda: languages(args[0]),
            "search": lambda: search_glosses(" ".join(args)),
        }.get(cmd)
        print(fn() if fn else __doc__)
        return
    print(f"[wiktionary] MCP server starting; db {'OK' if DB_PATH.exists() else 'MISSING'}", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[wiktionary] Bad JSON: {e}", file=sys.stderr)
            continue
        resp = process_message(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

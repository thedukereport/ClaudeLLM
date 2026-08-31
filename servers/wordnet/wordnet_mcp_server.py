#!/usr/bin/env python3
"""
WordNet — MCP Server (offline, stdlib only)

Exposes Open English WordNet (the maintained successor to Princeton WordNet,
CC BY 4.0) as MCP tools: definitions/senses, synonyms, antonyms, the
hypernym/hyponym (broader/narrower) hierarchy and other relations, and
full-text search of the glosses. ~107k synsets, ~127k words. All local.

Data built into wordnet.sqlite by build_wordnet.py. Stdlib only.

Run with any Python 3 (no packages needed), e.g.:
    /Volumes/PRO-BLADE/Alexandria/RAG_system/rag_env/bin/python \
        /Volumes/PRO-BLADE/WordNet/wordnet_mcp_server.py

CLI test:
    wordnet_mcp_server.py define bank
    wordnet_mcp_server.py synonyms happy
    wordnet_mcp_server.py related dog hyponym
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "wordnet.sqlite"
_DB = None

POS_FULL = {"n": "noun", "v": "verb", "a": "adj", "s": "adj", "r": "adv"}
POS_IN = {"noun": "n", "verb": "v", "adj": "a", "adjective": "a", "adv": "r",
          "adverb": "r", "n": "n", "v": "v", "a": "a", "r": "r", "s": "s"}

# friendly relation name → set of WN-LMF synset relTypes
REL = {
    "hypernym": {"hypernym", "instance_hypernym"},       # broader / "is a kind of"
    "hyponym": {"hyponym", "instance_hyponym"},           # narrower / kinds
    "meronym": {"mero_part", "mero_member", "mero_substance"},   # parts
    "holonym": {"holo_part", "holo_member", "holo_substance"},   # wholes
    "similar": {"similar"},
    "also": {"also"},
    "entails": {"entails"},
    "causes": {"causes"},
    "attribute": {"attribute"},
}
REL_ALIAS = {"broader": "hypernym", "narrower": "hyponym", "kinds": "hyponym",
             "part": "meronym", "parts": "meronym", "whole": "holonym",
             "wholes": "holonym", "like": "similar"}


def db():
    global _DB
    if _DB is None:
        _DB = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    return _DB


def _norm_pos(pos):
    if not pos:
        return None
    return POS_IN.get(pos.strip().lower())


def _synset_words(sid, exclude=None):
    rows = db().execute("SELECT DISTINCT lemma FROM words WHERE synset_id=? ORDER BY lemma", (sid,)).fetchall()
    return [r[0] for r in rows if not exclude or r[0].lower() != exclude]


def _synsets_for(word, pos=None):
    q = "SELECT DISTINCT synset_id, pos FROM words WHERE lemma_lc=?"
    p = [word.lower()]
    if pos:
        q += " AND pos=?"; p.append(pos)
    return db().execute(q, p).fetchall()


def define(word, pos=None):
    word = (word or "").strip()
    if not word:
        return "ERROR: empty word."
    p = _norm_pos(pos)
    rows = _synsets_for(word, p)
    if not rows:
        return f"No WordNet entry for '{word}'" + (f" ({pos})" if pos else "") + "."
    # group by part of speech
    out = [f"WordNet — {word}  ({len(rows)} sense{'s' if len(rows)!=1 else ''}):"]
    n = 0
    for sid, wpos in rows:
        s = db().execute("SELECT definition, examples FROM synsets WHERE id=?", (sid,)).fetchone()
        if not s:
            continue
        n += 1
        syns = _synset_words(sid, exclude=word.lower())
        line = f"\n{n}. ({POS_FULL.get(wpos, wpos)}) {s[0]}"
        if syns:
            line += f"\n     synonyms: {', '.join(syns[:12])}"
        if s[1]:
            line += f"\n     e.g. {s[1].split(' | ')[0]}"
        out.append(line)
    out.append("\n(WordNet — Open English WordNet, CC BY 4.0)")
    return "\n".join(out)


def synonyms(word, pos=None):
    word = (word or "").strip()
    p = _norm_pos(pos)
    rows = _synsets_for(word, p)
    if not rows:
        return f"No WordNet entry for '{word}'."
    seen, groups = set(), []
    for sid, wpos in rows:
        words = [w for w in _synset_words(sid, exclude=word.lower())]
        if words:
            groups.append(f"  ({POS_FULL.get(wpos, wpos)}) {', '.join(words[:15])}")
        seen.update(w.lower() for w in words)
    if not seen:
        return f"'{word}' has WordNet senses but no listed synonyms."
    return f"Synonyms of '{word}':\n" + "\n".join(groups)


def antonyms(word):
    word = (word or "").strip()
    senses = db().execute("SELECT sense_id FROM words WHERE lemma_lc=?", (word.lower(),)).fetchall()
    if not senses:
        return f"No WordNet entry for '{word}'."
    ants = []
    for (sid,) in senses:
        for (tgt,) in db().execute("SELECT target_sense FROM wrel WHERE source_sense=? AND reltype='antonym'", (sid,)).fetchall():
            r = db().execute("SELECT DISTINCT lemma, pos FROM words WHERE sense_id=?", (tgt,)).fetchone()
            if r:
                ants.append(f"{r[0]} ({POS_FULL.get(r[1], r[1])})")
    if not ants:
        return f"No antonyms recorded for '{word}'."
    return f"Antonyms of '{word}': " + ", ".join(dict.fromkeys(ants))


def related(word, relation, pos=None):
    word = (word or "").strip()
    rel = (relation or "").strip().lower()
    rel = REL_ALIAS.get(rel, rel)
    types = REL.get(rel)
    if not types:
        return ("ERROR: relation must be one of: " + ", ".join(sorted(REL)) +
                " (aliases: " + ", ".join(sorted(REL_ALIAS)) + ").")
    p = _norm_pos(pos)
    rows = _synsets_for(word, p)
    if not rows:
        return f"No WordNet entry for '{word}'."
    ph = ",".join("?" * len(types))
    out, n = [f"'{word}' → {rel}:"], 0
    for sid, wpos in rows:
        base = db().execute("SELECT definition FROM synsets WHERE id=?", (sid,)).fetchone()
        tgts = db().execute(f"SELECT DISTINCT target FROM srel WHERE source=? AND reltype IN ({ph})",
                            [sid, *types]).fetchall()
        if not tgts:
            continue
        n += 1
        out.append(f"\n[{POS_FULL.get(wpos, wpos)}] {base[0] if base else sid}")
        for (t,) in tgts:
            tw = _synset_words(t)
            td = db().execute("SELECT definition FROM synsets WHERE id=?", (t,)).fetchone()
            out.append(f"   → {', '.join(tw[:6]) or t}"
                       + (f" — {td[0]}" if td and td[0] else ""))
    if n == 0:
        return f"'{word}' has no '{rel}' relations in WordNet."
    return "\n".join(out)


def search_glosses(query, max_results=15):
    q = re.sub(r'["*]', " ", (query or "").strip())
    if not q:
        return "ERROR: empty query."
    toks = " ".join(f'"{t}"' for t in q.split())
    try:
        rows = db().execute(
            "SELECT s.id, s.pos, s.definition FROM syn_fts f JOIN synsets s ON s.rowid=f.rowid "
            "WHERE syn_fts MATCH ? ORDER BY rank LIMIT ?", (toks, max_results)).fetchall()
    except sqlite3.OperationalError as e:
        return f"ERROR: {e}"
    if not rows:
        return f"No glosses match '{query}'."
    out = [f"Glosses matching '{query}':"]
    for sid, pos, defi in rows:
        words = _synset_words(sid)
        out.append(f"  ({POS_FULL.get(pos, pos)}) {', '.join(words[:5])}: {defi}")
    return "\n".join(out)


# ── MCP plumbing ────────────────────────────────────────────────────

TOOLS = [
    {"name": "define",
     "description": ("Define an English word via WordNet: every sense, with part of "
                     "speech, definition, synonyms (the synset's other words), and an "
                     "example. Optional 'pos' filter (noun|verb|adj|adv)."),
     "inputSchema": {"type": "object", "properties": {
         "word": {"type": "string"},
         "pos": {"type": "string", "description": "noun | verb | adj | adv (optional)"}},
         "required": ["word"]}},
    {"name": "synonyms",
     "description": "List WordNet synonyms of a word, grouped by sense/part of speech.",
     "inputSchema": {"type": "object", "properties": {
         "word": {"type": "string"}, "pos": {"type": "string"}}, "required": ["word"]}},
    {"name": "antonyms",
     "description": "List WordNet antonyms (opposites) of a word.",
     "inputSchema": {"type": "object", "properties": {"word": {"type": "string"}}, "required": ["word"]}},
    {"name": "related",
     "description": ("Traverse a WordNet relation from a word: hypernym (broader / 'is a "
                     "kind of'), hyponym (narrower / kinds), meronym (parts), holonym "
                     "(wholes), similar, also, entails, causes, attribute. Returns the "
                     "related synsets with their words and glosses."),
     "inputSchema": {"type": "object", "properties": {
         "word": {"type": "string"},
         "relation": {"type": "string", "description": "hypernym|hyponym|meronym|holonym|similar|entails|causes|attribute (aliases: broader/narrower/part/whole)"},
         "pos": {"type": "string"}}, "required": ["word", "relation"]}},
    {"name": "search_glosses",
     "description": "Full-text search WordNet definitions (glosses) for a word or phrase; returns matching synsets.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"}, "max_results": {"type": "integer"}}, "required": ["query"]}},
]


def handle_tools_call(params):
    name = params.get("name"); a = params.get("arguments", {}) or {}
    try:
        if name == "define":
            text = define(a.get("word", ""), a.get("pos"))
        elif name == "synonyms":
            text = synonyms(a.get("word", ""), a.get("pos"))
        elif name == "antonyms":
            text = antonyms(a.get("word", ""))
        elif name == "related":
            text = related(a.get("word", ""), a.get("relation", ""), a.get("pos"))
        elif name == "search_glosses":
            text = search_glosses(a.get("query", ""), int(a.get("max_results", 15)))
        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"ERROR: {type(e).__name__}: {e}"}], "isError": True}
    return {"content": [{"type": "text", "text": text}]}


HANDLERS = {
    "initialize": lambda p: {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                             "serverInfo": {"name": "wordnet", "version": "1.0.0"}},
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
        fn = {"define": lambda: define(args[0], args[1] if len(args) > 1 else None),
              "synonyms": lambda: synonyms(args[0]),
              "antonyms": lambda: antonyms(args[0]),
              "related": lambda: related(args[0], args[1] if len(args) > 1 else ""),
              "search": lambda: search_glosses(" ".join(args))}.get(cmd)
        print(fn() if fn else __doc__)
        return
    print(f"[wordnet] MCP server starting; db {'OK' if DB_PATH.exists() else 'MISSING'}", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[wordnet] Bad JSON: {e}", file=sys.stderr)
            continue
        resp = process_message(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

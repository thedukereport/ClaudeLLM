#!/usr/bin/env python3
"""
Scriptures — combined MCP server over an offline corpus of open religious texts.

One SQLite/FTS5 database (scriptures.sqlite) holds several corpora, each row
tagged with its own reference and license:

  quran    Qur'an — Arabic (verified) + English + per-aya, ref "Quran S:A"
  enoch    1 Enoch (R. H. Charles), ref "Enoch C:V"                  [public domain]
  tanakh   Hebrew Bible + English, ref "Book C:V"                    [Sefaria, CC BY-NC]
  talmud   Babylonian Talmud, Hebrew/Aramaic + English, ref "Tractate 2a:1"
  mishnah  Mishnah, Hebrew + English, ref "Mishnah Tractate C:M"
  ethiopian Ethiopian (Tewahedo) canon — 36 books, Ge'ez + translit + English,
            ref "Book C:V"  [Ge'ez CC BY-SA (Beta Masaheft); English public domain]

Run (stdlib only — no venv packages needed, but launched with the rag_env python
to match the other servers):
    /Volumes/PRO-BLADE/Alexandria/RAG_system/rag_env/bin/python \
        /Volumes/PRO-BLADE/Scriptures/scriptures_mcp_server.py

Primary texts across traditions. Every result carries its corpus, reference, and
license. The Sefaria layers are CC BY-NC (personal research — do not
redistribute/resell). For scholarly citation, quote by the reference shown, not
by file path.
"""

import os
import re
import sys
import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB_PATH = os.environ.get("SCRIPTURES_DB", str(HERE / "scriptures.sqlite"))
_con = None

CORPORA = {
    "quran":   "Qur'an (Arabic + English), ref 'Quran S:A'",
    "enoch":   "1 Enoch / Book of Enoch, Charles tr. (public domain), ref 'Enoch C:V'",
    "tanakh":  "Hebrew Bible + English (Sefaria, CC BY-NC), ref 'Book C:V'",
    "talmud":  "Babylonian Talmud, Aramaic + English (Sefaria, CC BY-NC), ref 'Tractate 2a:1'",
    "mishnah": "Mishnah, Hebrew + English (Sefaria, CC BY-NC), ref 'Mishnah Tractate C:M'",
    "ethiopian": "Ethiopian (Tewahedo) canon — 36 books incl. Jubilees, Meqabyan, "
                 "Kebra Nagast, 4 Baruch, Tobit/Judith/Sirach/Wisdom. Ge'ez "
                 "(CC BY-SA, Beta Masaheft) + transliteration + English "
                 "(Charles/Brenton-LXX/KJV, public domain). ref 'Book C:V'; "
                 "langs gez | translit | en | en-kjv",
}

LEXICONS = {
    "bdb":     "Brown-Driver-Briggs Hebrew lexicon (public domain) — for Tanakh Hebrew",
    "jastrow": "Jastrow, Dict. of the Targumim/Talmud (public domain) — for Talmud/Mishnah Aramaic",
    "lane":    "Lane's Arabic-English Lexicon, by Qur'anic root (public domain) — for the Qur'an",
}


def con():
    global _con
    if _con is None:
        if not Path(DB_PATH).exists():
            raise RuntimeError(f"scriptures.sqlite not found at {DB_PATH}. "
                               f"Run build_scriptures.py first.")
        _con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        _con.row_factory = sqlite3.Row
    return _con


# ── FTS query hygiene ───────────────────────────────────────────────
def fts_query(user):
    """Make a safe FTS5 MATCH string. Preserve a quoted "phrase"; otherwise
    AND the bare word tokens (dropping FTS operators that would error)."""
    user = (user or "").strip()
    if not user:
        return None
    if user.count('"') >= 2:                      # user gave an explicit phrase
        return user
    toks = re.findall(r"[^\s]+", user)
    toks = [re.sub(r'[":^*(){}\[\]]', "", t) for t in toks]
    toks = [t for t in toks if t]
    return " ".join(toks) if toks else None


# ── DATA LAYER ──────────────────────────────────────────────────────
def do_search(query, corpus=None, lang=None, max_results=8):
    m = fts_query(query)
    if not m:
        return "Empty query."
    max_results = max(1, min(int(max_results or 8), 30))
    where, params = ["docs_fts MATCH ?"], [m]
    if corpus:
        where.append("d.corpus = ?"); params.append(corpus.lower())
    if lang:
        where.append("d.lang = ?"); params.append(lang.lower())
    sql = (f"SELECT d.corpus, d.book, d.ref, d.lang, d.license, "
           f"snippet(docs_fts, 0, '[[', ']]', '…', 12) AS snip, bm25(docs_fts) AS r "
           f"FROM docs_fts JOIN docs d ON d.id = docs_fts.rowid "
           f"WHERE {' AND '.join(where)} ORDER BY r LIMIT ?")
    params.append(max_results)
    try:
        rows = con().execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        return f"Search error: {e}. Try simpler keywords or a \"quoted phrase\"."
    if not rows:
        scope = f" in {corpus}" if corpus else ""
        return f"No matches for {query!r}{scope}."
    out = [f"{len(rows)} match(es) for {query!r} "
           f"(use get_passage with the ref for full text):\n"]
    for r in rows:
        out.append(f"[{r['corpus']}] {r['ref']} ({r['lang']})\n     {r['snip']}")
    lic = sorted({r['license'] for r in rows})
    out.append("\nLicense: " + " | ".join(lic))
    return "\n".join(out)


def do_get(ref, lang=None, corpus=None):
    ref = (ref or "").strip()
    if not ref:
        return "Provide a reference, e.g. 'Genesis 1:1', 'Quran 2:255', 'Berakhot 2a:1'."
    where, params = [], []
    # exact ref, or all verses of a chapter/daf when the segment part is omitted
    where.append("(d.ref = ? OR d.ref LIKE ?)")
    params += [ref, ref + ":%"]
    if lang:
        where.append("d.lang = ?"); params.append(lang.lower())
    if corpus:
        where.append("d.corpus = ?"); params.append(corpus.lower())
    sql = (f"SELECT corpus, book, ref, lang, body, license FROM docs d "
           f"WHERE {' AND '.join(where)} "
           f"ORDER BY d.id LIMIT 400")
    rows = con().execute(sql, params).fetchall()
    if not rows:
        return (f"No passage found for {ref!r}. Use search_scriptures first, "
                f"or check the reference format (e.g. 'Isaiah 53:5', 'Quran 112:1', "
                f"'Shabbat 31a:6', 'Mishnah Avot 1:1').")
    # group by ref, showing languages together
    by_ref = {}
    for r in rows:
        by_ref.setdefault(r["ref"], {})[r["lang"]] = r["body"]
    corpus_name = rows[0]["corpus"]
    lic = sorted({r["license"] for r in rows})
    head = f"# {ref}  ({corpus_name})\n"
    lines = [head]
    for rref, langs in by_ref.items():
        lines.append(f"\n[{rref}]")
        for lg in ("he", "ar", "en"):
            if lg in langs:
                lines.append(f"  ({lg}) {langs[lg]}")
        for lg, body in langs.items():
            if lg not in ("he", "ar", "en"):
                lines.append(f"  ({lg}) {body}")
    lines.append("\nLicense: " + " | ".join(lic))
    return "\n".join(lines)


def do_list():
    rows = con().execute(
        "SELECT corpus, COUNT(DISTINCT ref) n FROM docs GROUP BY corpus "
        "ORDER BY corpus").fetchall()
    counts = {r["corpus"]: r["n"] for r in rows}
    out = ["Corpora in this server:\n"]
    for c, desc in CORPORA.items():
        out.append(f"• {c}  ({counts.get(c, 0):,} refs) — {desc}")
    try:
        lex = con().execute(
            "SELECT lexicon, COUNT(*) n FROM lex GROUP BY lexicon "
            "ORDER BY lexicon").fetchall()
        if lex:
            out.append("\nLexicons (use lookup_word):")
            for r in lex:
                out.append(f"• {r['lexicon']}  ({r['n']:,} entries) — {LEXICONS.get(r['lexicon'],'')}")
    except sqlite3.OperationalError:
        pass
    return "\n".join(out)


# Hebrew points/cantillation + Arabic harakat/tatweel — strip for matching
_DIA = re.compile("[֑-ׇً-ْٰـ]")


def do_lookup(word, lexicon=None, max_results=6):
    w = (word or "").strip()
    if not w:
        return ("Provide a word to look up (Hebrew, Aramaic, or Arabic), "
                "e.g. 'שלום', 'גברא', or the Arabic root 'رحم'.")
    max_results = max(1, min(int(max_results or 6), 20))
    p = _DIA.sub("", w)
    base = ("SELECT lexicon, headword, root, definition, license FROM lex "
            "WHERE {cond}{lex} ORDER BY length(headword) LIMIT ?")
    lexf, lparams = "", []
    if lexicon:
        lexf = " AND lexicon = ?"; lparams = [lexicon.lower()]
    try:
        # 1) exact (diacritic-insensitive) headword; 2) prefix; 3) FTS
        rows = con().execute(base.format(cond="headword_plain = ?", lex=lexf),
                             [p] + lparams + [max_results]).fetchall()
        if not rows:
            rows = con().execute(base.format(cond="headword_plain LIKE ?", lex=lexf),
                                 [p + "%"] + lparams + [max_results]).fetchall()
        if not rows:
            q = " ".join(re.findall(r"\w+", w)) or w
            fsql = ("SELECT l.lexicon, l.headword, l.root, l.definition, l.license "
                    "FROM lex_fts f JOIN lex l ON l.id = f.rowid "
                    "WHERE lex_fts MATCH ?" +
                    (" AND l.lexicon = ?" if lexicon else "") +
                    " ORDER BY bm25(lex_fts) LIMIT ?")
            rows = con().execute(fsql, [q] + lparams + [max_results]).fetchall()
    except sqlite3.OperationalError as e:
        return (f"Lookup error: {e}. (Have the lexicons been built? "
                f"Run build_lexicons.py.)")
    if not rows:
        return f"No lexicon entry found for {word!r}."
    out = [f"Lexicon entries for {word!r}:\n"]
    for r in rows:
        rt = f" [root {r['root']}]" if r["root"] else ""
        out.append(f"[{r['lexicon']}] {r['headword']}{rt}\n     {r['definition']}")
    out.append("\n" + " | ".join(sorted({r["license"] for r in rows})))
    return "\n".join(out)


# ── TOOLS ───────────────────────────────────────────────────────────
TOOLS = [
    {
        "name": "search_scriptures",
        "description": (
            "Full-text search across an offline multi-tradition scripture corpus: "
            "Qur'an (Arabic+English), 1 Enoch, Hebrew Bible/Tanakh, Babylonian "
            "Talmud, Mishnah, and the Ethiopian (Tewahedo) canon — 36 books in Ge'ez "
            "+ transliteration + English, including Jubilees, Meqabyan, Kebra Nagast, "
            "4 Baruch and the deuterocanon. Returns ranked references with matching "
            "snippets; then call get_passage with a ref for the full text. Optionally "
            "restrict by 'corpus' (quran|enoch|tanakh|talmud|mishnah|ethiopian) and "
            "'lang' (he|ar|en|gez|translit|en-kjv). "
            "Results carry corpus, reference, and license; Sefaria layers are "
            "CC BY-NC (personal research). Cite by the reference shown."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords, or a \"quoted phrase\""},
                "corpus": {"type": "string",
                           "description": "Optional: quran|enoch|tanakh|talmud|mishnah|ethiopian"},
                "lang": {"type": "string", "description": "Optional: he|ar|en|gez|translit|en-kjv"},
                "max_results": {"type": "integer", "description": "Max results (default 8)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_passage",
        "description": (
            "Return the full text of a passage by reference, with all available "
            "languages (Hebrew/Aramaic, Arabic, English) shown together. Give a "
            "single ref like 'Genesis 1:1', 'Quran 2:255', 'Berakhot 2a:1', "
            "'Mishnah Avot 1:1' — or a chapter/daf like 'Genesis 1' or 'Berakhot 2a' "
            "to get every verse/line in it. Optional 'lang' and 'corpus' filters."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ref": {"type": "string",
                        "description": "Reference, e.g. 'Isaiah 53:5' or 'Shabbat 31a'"},
                "lang": {"type": "string", "description": "Optional: he|ar|en"},
                "corpus": {"type": "string", "description": "Optional corpus filter"},
            },
            "required": ["ref"],
        },
    },
    {
        "name": "lookup_word",
        "description": (
            "Look up a Hebrew, Aramaic, or Arabic word in the lexicons for "
            "word-level / etymological analysis: BDB (Biblical Hebrew), Jastrow "
            "(Talmudic/Targumic Aramaic), and Lane (Arabic, keyed by Qur'anic "
            "root). Diacritic-insensitive — paste the word with or without "
            "vowel-points. Matches the headword exactly, then by prefix, then "
            "searches definitions. Optionally restrict to one 'lexicon' "
            "(bdb|jastrow|lane). All three are public domain."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "word": {"type": "string",
                         "description": "Hebrew/Aramaic/Arabic word or root, e.g. 'שלום', 'גברא', 'رحم'"},
                "lexicon": {"type": "string", "description": "Optional: bdb|jastrow|lane"},
                "max_results": {"type": "integer", "description": "Max entries (default 6)"},
            },
            "required": ["word"],
        },
    },
    {
        "name": "list_corpora",
        "description": "List the corpora and lexicons in this server with counts and license notes.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def handle_tools_call(params):
    name = params.get("name")
    a = params.get("arguments", {})
    if name == "search_scriptures":
        text = do_search(a.get("query", ""), a.get("corpus"), a.get("lang"),
                         a.get("max_results", 8))
    elif name == "get_passage":
        text = do_get(a.get("ref", ""), a.get("lang"), a.get("corpus"))
    elif name == "lookup_word":
        text = do_lookup(a.get("word", ""), a.get("lexicon"), a.get("max_results", 6))
    elif name == "list_corpora":
        text = do_list()
    else:
        return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                "isError": True}
    return {"content": [{"type": "text", "text": text}]}


# ── JSON-RPC plumbing ───────────────────────────────────────────────
def handle_initialize(params):
    return {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
            "serverInfo": {"name": "scriptures", "version": "1.0.0"}}


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
    print(f"[scriptures] MCP server starting; db={DB_PATH} "
          f"{'OK' if Path(DB_PATH).exists() else 'MISSING'}", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[scriptures] Bad JSON: {e}", file=sys.stderr)
            continue
        resp = process_message(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

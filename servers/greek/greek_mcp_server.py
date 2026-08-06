#!/usr/bin/env python3
"""
Greek Resources — MCP Server
Exposes the local Greek corpora (Byzantine NT, SBLGNT, LXX, LSJ lexicon,
multi-edition apparatus, and the mechanical chapter auditor) as MCP tools.

Run with:
    /usr/bin/python3 /Volumes/PRO-BLADE/Alexandria/Greek-resources/greek_mcp_server.py

Stdlib only — no venv required. Connects to Claude Desktop / Cowork / Dispatch
via stdio transport. Same JSON-RPC pattern as alexandria_mcp_server.py.

Project rule this server exists to enforce (Greek Transcription Gate):
Greek text is TRANSCRIBED from these tools, never generated from memory.
NT standard is the Byzantine textform (verse_byz).
"""

import json
import sys
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOOKUP = HERE / "greek_lookup.py"
AUDIT = HERE / "greek_audit.py"


def run_cli(script, *args, timeout=120):
    try:
        r = subprocess.run(
            [sys.executable, str(script), *args],
            capture_output=True, text=True, timeout=timeout,
        )
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if not out and err:
            return f"(no output; stderr: {err[:500]})"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return f"ERROR: {script.name} timed out after {timeout}s"
    except Exception as e:
        return f"ERROR running {script.name}: {type(e).__name__}: {e}"


# ── MCP handlers ────────────────────────────────────────────────────

def handle_initialize(params):
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "greek-resources", "version": "1.0.0"},
    }


TOOLS = [
    {
        "name": "verse_byz",
        "description": (
            "PRIMARY Greek NT tool — Byzantine textform reading for any Greek "
            "New Testament verse, with divergence notes where modern critical "
            "editions (NA28/SBL/etc.) differ. Reframing Reality's NT standard "
            "is Byzantine: quote Greek from THIS tool's output, never from "
            "memory. Reference format: 'John 1:14', 'Matt 26:23', 'Rom 12:1-3'."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string",
                              "description": "e.g. 'Matt 18:20' or 'Luke 4:18-19'"}
            },
            "required": ["reference"],
        },
    },
    {
        "name": "lsj",
        "description": (
            "LSJ (Liddell-Scott-Jones) lexicon entry for a Greek word. "
            "Accepts Unicode Greek (λόγος) or Perseus beta-code (logos). "
            "Indexes LEMMAS — inflected forms may legitimately miss."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "word": {"type": "string", "description": "Greek word or beta-code"}
            },
            "required": ["word"],
        },
    },
    {
        "name": "editions",
        "description": (
            "Multi-edition view of a Greek NT verse (NA, SBL, TH, Treg, WH, "
            "Byz, TR) — use when textual-criticism divergence is itself the "
            "subject under discussion."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "e.g. 'John 12:6'"}
            },
            "required": ["reference"],
        },
    },
    {
        "name": "verse_sblgnt",
        "description": "SBLGNT reading of a Greek NT verse (reference edition; project standard is verse_byz).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "e.g. 'Acts 11:26'"}
            },
            "required": ["reference"],
        },
    },
    {
        "name": "greek_audit_chapter",
        "description": (
            "Mechanical Greek-quote audit of a chapter file: extracts every "
            "Greek run, verifies quotes verbatim against Byzantine NT and LXX, "
            "returns a MATCH/MISMATCH table with the actual readings. Run "
            "before and after any chapter pass that touches Greek. Pass the "
            "absolute path to the chapter .md file."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "chapter_path": {"type": "string",
                                 "description": "Absolute path to the chapter .md file"}
            },
            "required": ["chapter_path"],
        },
    },
    {
        "name": "verse_lxx",
        "description": (
            "LXX (Septuagint) reading for an Old Testament verse or verse range, "
            "using Swete's edition (Perseus / First Thousand Years of Greek). "
            "Reference format: 'Gen 14:13', 'Ex 1:15-22', 'Jonah 1:9', 'Dan 3:1'. "
            "For books with both LXX and Theodotion versions (Daniel, Susanna, "
            "Bel and Dragon), the default is the LXX version — request the "
            "Theodotion version by suffixing '-th' (e.g. 'Dan-th 3:1'). "
            "Quote Greek from THIS tool's output, never from memory."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string",
                              "description": "e.g. 'Gen 14:13' or 'Ex 1:15-22'"}
            },
            "required": ["reference"],
        },
    },
    {
        "name": "editions_lxx",
        "description": (
            "Multi-edition view of an LXX verse, showing every available "
            "recension. For Daniel, Susanna, and Bel and Dragon this returns "
            "both the LXX (Old Greek) and Theodotion versions. For Isaiah and "
            "Sirach it returns both attested manuscript traditions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string",
                              "description": "e.g. 'Dan 3:1' or 'Sus 1:1'"}
            },
            "required": ["reference"],
        },
    },
    {
        "name": "lxx_search",
        "description": (
            "Concordance search across the entire LXX (Swete's edition). "
            "Returns every occurrence of a Greek substring with book/chapter/"
            "verse citation and surrounding context. Search is diacritic- and "
            "case-insensitive by default, so 'εβραι' finds Ἑβραίων, Ἐβραίας, "
            "Ἑβραῖος, etc. Use for questions like 'how many times does "
            "Ἑβραῖος appear in the LXX?' or 'find every mention of Θαρσις'. "
            "Substring match — expect some false positives (e.g. 'θαρσι' "
            "matches ἀκαθαρσίας too)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "word": {"type": "string",
                         "description": "Greek word or substring, e.g. 'Ἑβραῖος' or 'εβραι'"},
                "max_results": {"type": "integer",
                                "description": "Max results to return (default 50)"},
                "book_filter": {"type": "string",
                                "description": "Optional substring of book title to restrict search, e.g. 'Ψαλμοί'"},
            },
            "required": ["word"],
        },
    },
    {
        "name": "lxx_books",
        "description": (
            "List the 57 books of the LXX indexed on this server, with their "
            "Greek titles, TLG codes, and accepted reference abbreviations. Use "
            "when uncertain about the correct book name for verse_lxx."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "proper_noun_geo",
        "description": (
            "William Smith, Dictionary of Greek and Roman Geography (1854) — "
            "look up a place name (city, region, river, mountain, sea) as it "
            "appears in ancient sources. Accepts Latin form (Hispania, Iberia, "
            "Tartessus), English form (Spain), or Greek. Returns the full entry "
            "with citations to Strabo, Pliny, Ptolemy, Stephanus of Byzantium, "
            "etc. 10,292 entries. Use for the toponym / geographic-name axis of "
            "the 'proper nouns have lost meaning' investigation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "word": {"type": "string", "description": "Place name, e.g. 'Iberia' or 'Tartessus'"}
            },
            "required": ["word"],
        },
    },
    {
        "name": "proper_noun_bio",
        "description": (
            "William Smith, Dictionary of Greek and Roman Biography and "
            "Mythology — look up a person, god, hero, or mythological figure. "
            "Accepts Latin form (Homerus), English form (Homer), Greek form. "
            "Returns the full entry with source citations. 19,893 entries, "
            "often with multiple senses per name (Homer 1, 2, 3 etc.). Use for "
            "the personal-name / theonym axis of the 'proper nouns have lost "
            "meaning' investigation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "word": {"type": "string", "description": "Personal name, e.g. 'Homer' or 'Baal'"}
            },
            "required": ["word"],
        },
    },
    {
        "name": "proper_noun_ant",
        "description": (
            "William Smith, Dictionary of Greek and Roman Antiquities (1890) — "
            "look up a Greco-Roman institution, custom, office, ritual, or "
            "classical vocabulary term (agora, boule, colonia, tophet, hieron, "
            "etc.). 3,409 entries. Use for the cultural-terminology axis of "
            "the 'proper nouns have lost meaning' investigation, and for "
            "functional-vocabulary lookups where a descriptor may have narrowed "
            "into a proper noun."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "word": {"type": "string", "description": "Term or concept, e.g. 'agora' or 'colonia'"}
            },
            "required": ["word"],
        },
    },
    {
        "name": "proper_noun_search",
        "description": (
            "Substring search across all three of William Smith's dictionaries "
            "(Geography + Biography + Antiquities) — returns a ranked list of "
            "matching entry keys with their corpus tag ([GEO]/[BIO]/[ANT]). "
            "Use when uncertain of the exact form (e.g. is 'Homer' under "
            "'Homer' or 'Homerus'?), when hunting for related entries "
            "(all 'Iber-' places), or as first-pass discovery before drilling "
            "into a specific entry with proper_noun_geo/_bio/_ant."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "word": {"type": "string",
                         "description": "Search term, e.g. 'iber' or 'tophet'"},
                "max_results": {"type": "integer",
                                "description": "Max results to return (default 40)"},
            },
            "required": ["word"],
        },
    },
    {
        "name": "middle_liddell",
        "description": (
            "Liddell-Scott Intermediate Greek-English Lexicon (Middle Liddell) "
            "— the compact companion to the full LSJ, with cleaner "
            "definitions suited to quick reference. 36,491 entries. Use as a "
            "faster/lighter alternative to lsj for common vocabulary; use lsj "
            "when the full range of senses, sources, or morphology matters. "
            "Accepts Unicode Greek (ἀγορά, Ἑβραῖος) or Perseus beta-code."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "word": {"type": "string", "description": "Greek word (Unicode or beta-code)"}
            },
            "required": ["word"],
        },
    },
    {
        "name": "corpus_search",
        "description": (
            "Full-text search across the ENTIRE classical Greek corpus — all "
            "~46 authors (Plato, Aristotle, Homer, Herodotus, Thucydides, "
            "Galen, Ptolemy, Philo, Josephus, the patristics, and more; 550 "
            "works). Diacritic- and case-insensitive substring match; returns "
            "citations (author, work, Stephanus/Bekker/chapter location) with "
            "surrounding context. Use for 'where does Plato say X', 'find "
            "every classical use of κρίσις', or locating a passage to quote "
            "under the transcription gate. Substring match — κρίσις also "
            "matches ἔκκρισις. NT/LXX have their own dedicated tools."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "word": {"type": "string",
                         "description": "Greek word or phrase, e.g. 'ἀνεξέταστος βίος'"},
                "author": {"type": "string",
                           "description": "Optional author slug to restrict search, e.g. 'plato', 'galen_first1k' (see corpus_authors)"},
                "max_results": {"type": "integer",
                                "description": "Max results (default 25)"},
            },
            "required": ["word"],
        },
    },
    {
        "name": "corpus_authors",
        "description": "List the author slugs searchable via corpus_search.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def handle_tools_list(params):
    return {"tools": TOOLS}


def handle_tools_call(params):
    name = params.get("name")
    args = params.get("arguments", {})

    if name == "verse_byz":
        text = run_cli(LOOKUP, "verse-byz", args.get("reference", ""))
    elif name == "lsj":
        text = run_cli(LOOKUP, "lsj", args.get("word", ""))
    elif name == "editions":
        text = run_cli(LOOKUP, "editions", args.get("reference", ""))
    elif name == "verse_sblgnt":
        text = run_cli(LOOKUP, "verse", args.get("reference", ""))
    elif name == "greek_audit_chapter":
        p = args.get("chapter_path", "")
        if not Path(p).is_file():
            return {"content": [{"type": "text",
                                 "text": f"Chapter file not found: {p}"}],
                    "isError": True}
        text = run_cli(AUDIT, p, timeout=300)
    elif name == "verse_lxx":
        text = run_cli(LOOKUP, "lxx", args.get("reference", ""))
    elif name == "editions_lxx":
        text = run_cli(LOOKUP, "lxx-editions", args.get("reference", ""))
    elif name == "lxx_search":
        word = args.get("word", "")
        max_r = str(args.get("max_results", 50))
        book_f = args.get("book_filter", "")
        cli_args = ["lxx-search", word, max_r]
        if book_f:
            cli_args.append(book_f)
        text = run_cli(LOOKUP, *cli_args)
    elif name == "lxx_books":
        text = run_cli(LOOKUP, "lxx-books")
    elif name == "proper_noun_geo":
        text = run_cli(LOOKUP, "smith-geo", args.get("word", ""))
    elif name == "proper_noun_bio":
        text = run_cli(LOOKUP, "smith-bio", args.get("word", ""))
    elif name == "proper_noun_ant":
        text = run_cli(LOOKUP, "smith-ant", args.get("word", ""))
    elif name == "proper_noun_search":
        word = args.get("word", "")
        max_r = str(args.get("max_results", 40))
        text = run_cli(LOOKUP, "smith-search", word, max_r)
    elif name == "middle_liddell":
        text = run_cli(LOOKUP, "middle-liddell", args.get("word", ""))
    elif name == "corpus_search":
        cli_args = ["corpus-search", args.get("word", "")]
        if args.get("author"):
            cli_args += ["--author", args["author"]]
        if args.get("max_results"):
            cli_args += ["--max", str(args["max_results"])]
        text = run_cli(LOOKUP, *cli_args)
    elif name == "corpus_authors":
        text = run_cli(LOOKUP, "corpus-authors")
    else:
        return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                "isError": True}

    is_error = text.startswith("ERROR")
    result = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    return result


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
            result = handler(params)
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": msg_id,
                    "error": {"code": -32000, "message": f"{type(e).__name__}: {e}"}}
    return {"jsonrpc": "2.0", "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main():
    print("[greek-resources] MCP server starting...", file=sys.stderr)
    print(f"[greek-resources] Corpus dir: {HERE}", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[greek-resources] Bad JSON: {e}", file=sys.stderr)
            continue
        response = process_message(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

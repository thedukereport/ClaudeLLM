# Add a Local MCP Server (Cowork)

Every local server (alexandria-rag, greek-resources, wikispooks) is the same
skeleton: line-delimited **JSON-RPC 2.0 over stdio**, stdlib-only. To add one,
copy the template and fill three sections — the plumbing never changes.

**Template:** `/Volumes/PRO-BLADE/Alexandria/mcp_server_template.py`

## Steps

1. **Copy** the template to a new file next to its data
   (e.g. `/Volumes/PRO-BLADE/<Corpus>/mycorpus_mcp_server.py`).
2. **Edit only the 3 marked sections:**
   - **(1) CONFIG** — `SERVER_NAME` (becomes `mcp__<name>__*`, dashes→underscores).
   - **(2) DATA LAYER** — how you load/query the corpus: SQLite (`sqlite3`, stdlib),
     a JSON index, or shell out to a CLI (see `greek_mcp_server.py`'s `run_cli`).
   - **(3) TOOLS** — the tool schemas + the `handle_tools_call` dispatch.
     Convention: a `search_*` tool (ranked hits + snippets) and a `get_*` tool
     (full record). Write descriptions that say WHAT it searches, WHEN to use it,
     an example query, and the source's provenance (who publishes/edits it, which
     edition) so results stay attributable.
3. **Test locally** (no restart needed):
   ```bash
   printf '%s\n' \
     '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
     '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
     '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"YOURTOOL","arguments":{"query":"x"}}}' \
     | /Volumes/PRO-BLADE/Alexandria/RAG_system/rag_env/bin/python mycorpus_mcp_server.py
   ```
   You want valid JSON responses for all three.
4. **Register** in the Claude Desktop config's `mcpServers` (same file as the others),
   using the rag_env Python for consistency:
   ```json
   "mycorpus": {
     "command": "/Volumes/PRO-BLADE/Alexandria/RAG_system/rag_env/bin/python",
     "args": ["/Volumes/PRO-BLADE/<Corpus>/mycorpus_mcp_server.py"]
   }
   ```
5. **Fully quit and reopen Claude.** The `mcp__mycorpus__*` tools appear.
6. **Record it** in `How To/Canonical Paths.md` (new location → new row, same commit).

## Rules of thumb

- **Stdlib-only** unless the data layer forces a dependency (then use the rag_env Python).
- **PRO-BLADE must be mounted** — server, data, and interpreter all live there.
- **Record provenance** in the tool description and in returned results: what the
  source is, who edits it, which edition. Attribution makes claims traceable.
  Don't editorialize about a source's reliability — that's the researcher's call,
  not the tool's.
- Heavy one-time corpus builds run as their OWN script (like
  `build_wikispooks_corpus.py`), never inside the MCP server. The server only reads.

## Existing servers (templates to crib from)

| Server | Data layer | File |
|---|---|---|
| alexandria-rag | FAISS + query_rag (needs rag_env) | `RAG_system/alexandria_mcp_server.py` |
| greek-resources | shells out to `greek_lookup.py` | `Greek-resources/greek_mcp_server.py` |
| wikispooks | SQLite FTS5 (stdlib) | `WikiSpooks/wikispooks_mcp_server.py` |
| latin-resources | XML corpora via `latin_lookup` | `Latin-resources/latin_mcp_server.py` |
| perseus | XML canonical library (156 authors, 2,299 texts) | `Perseus-canonical/perseus_mcp_server.py` |
| pleiades | SQLite FTS5 (stdlib) | `Pleiades/pleiades_mcp_server.py` |
| wikipedia | Kiwix ZIM via `libzim` (its own index) | `Wikipedia/wikipedia_mcp_server.py` |
| scriptures | SQLite FTS5, two tables — texts + lexicons (stdlib) | `Scriptures/scriptures_mcp_server.py` |
| gutenberg | **Many** ZIMs at once via `libzim`, hits tagged by subject | `Gutenberg/gutenberg_mcp_server.py` |

**Pick your closest match.** Most new corpora want the `pleiades` / `wikispooks`
pattern: a `build_*.py` script that makes one SQLite/FTS5 file, and a server that
only reads it. `scriptures` is the one to copy if a single server should expose
several corpora, or texts *and* reference works, through one set of tools.
`wikipedia` shows how to lean on a format's own built-in index instead of FTS5.

## Setting all of this up somewhere else

To replicate the whole stack on another machine — data acquisition, the Python
environment, the config file, verification, and licensing — follow
**`Set Up the MCP Servers with Claude Cowork.md`**. This document is only about
writing a *new* server.

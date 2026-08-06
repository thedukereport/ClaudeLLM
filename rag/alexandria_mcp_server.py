#!/usr/bin/env python3
"""
Alexandria RAG — MCP Server
Exposes semantic search over 6,000+ books as an MCP tool.

Run with:
    /path/to/rag_env/bin/python alexandria_mcp_server.py

Connects to Claude Desktop / Cowork via stdio transport.
"""

import json
import sys
import os
from pathlib import Path

# Add RAG system to path so we can import query_rag
RAG_DIR = Path(__file__).parent
sys.path.insert(0, str(RAG_DIR))

# Index lives one directory up (in the Alexandria root)
INDEX_DIR = RAG_DIR.parent

# ── Lazy-loaded singleton ──────────────────────────────────────────
_querier = None

def get_querier():
    """Load the RAG index once, reuse across calls."""
    global _querier
    if _querier is None:
        # Suppress the loading prints from query_rag
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            from query_rag import RAGQuerier
            _querier = RAGQuerier(
                index_dir=str(INDEX_DIR),
                model_name="all-MiniLM-L6-v2"
            )
        finally:
            sys.stdout = old_stdout
        # Log to stderr (visible in terminal, invisible to MCP)
        print(f"[alexandria] Index loaded: {len(_querier.metadata)} chunks", file=sys.stderr)
    return _querier


# ── MCP Protocol (JSON-RPC over stdio) ─────────────────────────────

def handle_initialize(params):
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {
            "name": "alexandria-rag",
            "version": "1.0.0"
        }
    }

def handle_tools_list(params):
    return {
        "tools": [
            {
                "name": "search_books",
                "description": (
                    "Semantic search across Mr. Duke's Alexandria library "
                    "(6,000+ books). Returns the most relevant passages for "
                    "a natural-language query. Use for sourcing, verification, "
                    "cross-referencing, and finding primary-source material."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Natural language search query. Be specific: "
                                "'Venetian oligarchy and banking' works better "
                                "than just 'Venice'."
                            )
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "Number of results to return (default 5, max 20)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "index_info",
                "description": (
                    "Report the Alexandria index's current state: index type, "
                    "chunk and book counts, metric, and IVF tuning (nlist / "
                    "nprobe). Use to confirm configuration, e.g. the active nprobe."
                ),
                "inputSchema": {"type": "object", "properties": {}}
            }
        ]
    }

def handle_tools_call(params):
    tool_name = params.get("name")
    args = params.get("arguments", {})

    if tool_name == "index_info":
        try:
            info = get_querier().get_index_info()
            books = len(set(m["file"] for m in get_querier().metadata))
            lines = [
                "Alexandria index:",
                f"  index type : {info.get('index_type')}",
                f"  chunks     : {info.get('ntotal', 0):,}",
                f"  books      : {books:,}",
                f"  metric     : {info.get('metric')}",
            ]
            if "nlist" in info:
                lines.append(f"  nlist      : {info['nlist']:,}")
                lines.append(f"  nprobe     : {info['nprobe']}   "
                             f"(searches ~{100*info['nprobe']//max(1, info['nlist'])}% of clusters)")
            if "ef_search" in info:
                lines.append(f"  ef_search  : {info['ef_search']}")
            return {"content": [{"type": "text", "text": "\n".join(lines)}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"index_info error: {e}"}],
                    "isError": True}

    if tool_name != "search_books":
        return {
            "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
            "isError": True
        }

    query = args.get("query", "")
    k = min(args.get("num_results", 5), 20)

    if not query.strip():
        return {
            "content": [{"type": "text", "text": "Empty query. Please provide a search term."}],
            "isError": True
        }

    try:
        querier = get_querier()
        results = querier.search(query, k=k)

        if not results:
            return {
                "content": [{"type": "text", "text": f"No results found for: '{query}'. Try rephrasing."}]
            }

        # Format results
        lines = [f"Alexandria RAG — {len(results)} results for: '{query}'\n"]
        for r in results:
            lines.append(f"[{r['rank']}] {r['title']}")
            lines.append(f"    File: {r['file']}")
            lines.append(f"    Similarity: {r['similarity']:.1%}")
            lines.append(f"    Excerpt: {r['preview']}")
            lines.append("")

        return {
            "content": [{"type": "text", "text": "\n".join(lines)}]
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Search error: {str(e)}"}],
            "isError": True
        }


# ── JSON-RPC dispatch ──────────────────────────────────────────────

HANDLERS = {
    "initialize": handle_initialize,
    "tools/list": handle_tools_list,
    "tools/call": handle_tools_call,
}

def process_message(msg):
    """Process a single JSON-RPC message and return a response (or None for notifications)."""
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params", {})

    # Notifications (no id) — just acknowledge
    if msg_id is None:
        # notifications/initialized is the main one; no response needed
        return None

    handler = HANDLERS.get(method)
    if handler:
        result = handler(params)
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}
    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }

def main():
    """Run the MCP server on stdio."""
    print("[alexandria] MCP server starting...", file=sys.stderr)
    print(f"[alexandria] Index dir: {INDEX_DIR}", file=sys.stderr)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            print(f"[alexandria] Bad JSON: {e}", file=sys.stderr)
            continue

        response = process_message(msg)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

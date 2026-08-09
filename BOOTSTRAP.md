# BOOTSTRAP — build the ClaudeLLM local research stack

**You are Claude, reading this because a user dropped this file into a fresh Cowork / Claude Desktop session.** Your job is to set up, *with them*, a private local-first research stack on their computer (local corpora and local search; Claude itself still runs in the cloud, so retrieved passages reach it as context): a local PDF-library RAG plus a suite of MCP servers over open corpora. The full code lives in a public GitHub repo (below). This file is your playbook.

Repo: **https://github.com/thedukereport/ClaudeLLM**

---

## Prime directives

1. **Interview before you build.** Assume the user may have *little or no* technical experience. Ask the questions in Step 1 first, in plain language, and wait for answers. Never dump a wall of commands.
2. **Adapt to their OS.** This was authored on an Apple-Silicon Mac, but the user may be on **Windows** or Linux. Detect the OS and translate every path and command. Do not paste macOS paths (`/Volumes/...`) at a Windows user.
3. **One step at a time.** Run a step, confirm it worked, explain what happened in a sentence, then continue. If a command fails, read the error and fix it before moving on — don't barrel ahead.
4. **No data ships in the repo.** Every corpus is downloaded by its `build_*.py` on *this* machine. Some corpora are **CC BY-NC (personal research only)** — tell the user which, and never imply they can republish those.
5. **Don't fabricate.** If you're unsure whether a tool/drive/path exists, check with a command. Use the detailed guides in `docs/` when you need specifics.

---

## Step 0 — Get the code

Ask where they'd like it, then:

```
git clone https://github.com/thedukereport/ClaudeLLM.git
```

If `git` is missing: macOS → `xcode-select --install`; Windows → install Git for Windows or `winget install Git.Git`.

---

## Step 1 — Interview the user

Ask these (adapt wording to their level; one or two at a time, not all at once):

1. **What computer?** macOS, Windows, or Linux? (Apple Silicon or Intel Mac?) — determines paths, commands, and whether GPU embedding is available.
2. **Where should everything live?** An external drive is ideal (corpora get large). Get a folder path. On Windows this is a drive letter like `D:\ClaudeLLM`; on Mac a path like `/Volumes/YourDrive/ClaudeLLM` or `~/ClaudeLLM`.
3. **What do they want to search?** Walk the menu (`servers/` list below) and let them pick. Most start with **scriptures + pleiades** (tiny, minutes to build) and add heavy ones (Wikipedia ~115 GB, Gutenberg up to ~207 GB) later.
4. **Do they have their own PDF/EPUB library** they want semantic search over? If yes, they want the **RAG** (`rag/`). If no, skip it — the MCP servers stand alone.
5. **Do they have Claude Desktop installed, with Cowork?** Required for the servers to appear as tools.
6. **Roughly how much free disk** do they have? Sets expectations (scriptures+places ≈ 500 MB; everything ≈ 300+ GB).

Summarize their choices back to them before building.

---

## Step 2 — OS-specific translation (keep this in mind the whole way)

| Thing | macOS / Linux | Windows |
|---|---|---|
| Base path | `/Volumes/DRIVE/ClaudeLLM` or `~/ClaudeLLM` | `D:\ClaudeLLM` |
| Python | `python3` | `python` |
| Make a venv | `python3 -m venv env` | `python -m venv env` |
| venv Python | `env/bin/python` | `env\Scripts\python.exe` |
| Path separator | `/` | `\` |
| Auto-start dashboard | `launchd` (`.plist`) | Task Scheduler |
| GPU embedding (RAG) | **MPS** on Apple Silicon | **CUDA** if an NVIDIA GPU, else **CPU** |

**Mac-only pieces — flag these to Windows/Intel users and offer the alternative:**
- The `dashboard/` control panel uses macOS `launchd`; on Windows, run the RAG web UI directly (`python rag/app.py`) or wire a Task Scheduler job.
- GPU-accelerated embedding uses Apple's **MPS**. On Windows/Linux the RAG's embedding step should run on **CUDA** (NVIDIA) or **CPU** — set the device accordingly (see `docs/Build a Local RAG with Claude Cowork.md`). CPU works everywhere, just slower; it's a one-time build.

---

## Step 3 — Python environment

The MCP servers are **stdlib-only except two packages**. Create one environment for the servers:

```
# macOS/Linux
python3 -m venv "<BASE>/mcp_env"
"<BASE>/mcp_env/bin/pip" install --upgrade pip
"<BASE>/mcp_env/bin/pip" install libzim duckdb
```
```
# Windows (PowerShell)
python -m venv "<BASE>\mcp_env"
& "<BASE>\mcp_env\Scripts\pip" install --upgrade pip
& "<BASE>\mcp_env\Scripts\pip" install libzim duckdb
```

- `libzim` — only needed for `wikipedia` and `gutenberg` (Kiwix ZIM files).
- `duckdb` — only needed for the `atlas` geo-temporal database.
- Everything else is plain Python.

The **RAG** (`rag/`) needs its own heavier environment (PyTorch, FAISS, sentence-transformers) — see `docs/Build a Local RAG with Claude Cowork.md`. Keep it separate from `mcp_env`.

---

## Step 4 — Build the corpora they chose (start small)

Each server folder has its own builder. Recommended order: prove the setup with the tiny ones first.

| Server (`servers/…`) | Build command (run inside that folder) | Size | Notes |
|---|---|---|---|
| `scriptures` | `python build_scriptures.py` → `python build_lexicons.py` → `python build_ethiopian.py` | ~240 MB | resumable downloads; Sefaria layers are **CC BY-NC** |
| `pleiades` | `python build_pleiades_corpus.py` | ~17 MB | CC BY |
| `latin` | copy Perseus TEI per author (see docs) → `python build_lewis_short.py` | ~350 MB | L&S self-downloads |
| `greek` | provide the open Greek corpora (see docs) | varies | |
| `perseus` | download the two PerseusDL tarballs → `python build_resume.py` (repeat until COMPLETE) | ~1.5 GB | resumable |
| `papyri` | `python build_papyri.py` | ~100 MB | CC BY; clones DDbDP EpiDoc |
| `gutenberg` | `python download_gutenberg.py --list` → `--set core` | 11 GB → 207 GB | you choose subsets; needs `libzim` |
| `wikipedia` | download a Kiwix `.zim` into the folder (see docs) | 12–115 GB | needs `libzim` |
| `wikispooks` | provide the MediaWiki dump → `python build_wikispooks_corpus.py` | ~260 MB | verify license before republishing |
| `atlas` | `python build_atlas.py` (after pleiades) | small | needs `duckdb` |

Copy each server's `.py` files into a working folder on the drive first (the repo keeps them under `servers/<name>/`). The detailed, click-by-click instructions with expected output are in **`docs/Set Up the MCP Servers with Claude Cowork.md`** — follow it for any server the user picks.

---

## Step 5 — Register the servers with Claude Desktop

Claude Desktop reads one JSON file:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add an entry per built server under `mcpServers`, pointing at the shared `mcp_env` Python and the server file. Example (macOS paths — translate for Windows):

```json
{
  "mcpServers": {
    "scriptures": { "command": "<BASE>/mcp_env/bin/python", "args": ["<BASE>/servers/scriptures/scriptures_mcp_server.py"] },
    "pleiades":   { "command": "<BASE>/mcp_env/bin/python", "args": ["<BASE>/servers/pleiades/pleiades_mcp_server.py"] }
  }
}
```

**Only list servers the user actually built.** Validate the JSON (`python -m json.tool <file>`), then have them fully quit and reopen Claude Desktop — servers load only at startup.

---

## Step 6 — (Optional) the personal-PDF RAG

If they have their own library, set up `rag/`. This is the heaviest part (PyTorch/FAISS) and the one with real OS/GPU differences. **Follow `docs/Build a Local RAG with Claude Cowork.md` end to end.** Key rules from that guide:
- Keep the embedding step and the index-building step in **separate processes** (they each bundle OpenMP; loading both in one process crashes on macOS).
- Extraction is memory-heavy — cap parallel workers (default 4) or it can exhaust RAM.
- On Apple Silicon, embedding uses the GPU (MPS) with a memory watchdog; on Windows/Linux use CUDA or CPU.

---

## Step 7 — Verify

In a new Cowork chat, ask things only these servers could answer, e.g.:
- *"List the corpora in the scriptures server."*
- *"Get me Jubilees 1:1 from the Ethiopian canon."* (Ge'ez + English)
- *"Search Pleiades for Gadeira."*
- *"Look up virtus in Lewis & Short."*
- *"Search the papyri for βασιλ*."*

If a server doesn't appear: re-check its JSON entry, confirm both paths exist, and restart Claude Desktop. The `docs/` guides have a Troubleshooting section.

---

## Where to go deeper

- `docs/Set Up the MCP Servers with Claude Cowork.md` — the full, novice-friendly, per-server walkthrough with expected output and a licensing table.
- `docs/Build a Local RAG with Claude Cowork.md` — the RAG deep dive.
- `docs/Add an MCP Server.md` — how to add a brand-new corpus of their own.
- `docs/Canonical Paths.md` — the original author's path registry (an example layout).

**Now start at Step 0, then interview the user. Be patient, translate for their OS, and build only what they ask for.**

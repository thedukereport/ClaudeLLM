# Build Your Own Local RAG (Like Peter's) with Claude Cowork

*A complete, hand-held guide to building a private, local semantic search engine over your own library of PDFs and ebooks — the same system Peter built. No cloud, no subscriptions, everything runs on your own Mac.*

> **How to use this guide.** Read Parts 1–7 in order. Every command is shown in a grey box — you copy it, paste it into the Terminal, and press Return. You do **not** need to understand the code. When something needs explaining, it's explained in plain language. The complete source code for every file is in **Appendix B** at the very end. The easiest path of all is to work through this *with Claude Cowork open* — paste any command that confuses you, or any error you see, straight into Cowork and ask "what does this mean / what do I do?"

---

## What this is, in plain language

Imagine a research assistant who has read every book in your library and can instantly find the passages that answer a question — not by matching keywords, but by understanding **meaning**. Ask "what did the founders think about central banking?" and it finds the relevant pages even if none of them contain those exact words.

That's what you're building. The technical name is a **RAG** — "Retrieval-Augmented Generation." For our purposes it's a **meaning-based search engine for your own book collection**, with a friendly web dashboard, running entirely on your computer. Your books never leave your Mac.

**What you'll end up with:**

- A web page (opened in your browser) where you type questions and get back the most relevant passages from your library.
- A dashboard to add new books, check your library for damaged files, and fine-tune the search.
- A system that searches ~3 million passages in a few thousandths of a second.

---

## How it works (the shelf picture)

You don't need this to use the system, but it makes everything else make sense.

1. **Extraction.** The computer reads the text out of every PDF and ebook. (This is the slow part — hours the first time.)
2. **Embedding.** Each chunk of text is turned into a list of numbers that captures its *meaning*. Similar meanings get similar numbers. This runs on your Mac's graphics chip (GPU) and is fast.
3. **Indexing.** All those number-lists are sorted onto "shelves" so searches don't have to check every one. This is the **index**.
4. **Searching.** Your question gets turned into numbers the same way, and the system checks the most promising shelves for the closest matches.

Two dials control the search, and you'll tune them later:

- **nlist** — how many shelves you sort everything onto.
- **nprobe** — how many shelves you actually check when answering a question. Check more shelves = more thorough but slower. There's a sweet spot, and the dashboard finds it for you.

---

## The one big gotcha (please read this)

This system is split into several separate small programs instead of one big one. There's a **critical reason**, and if you (or Cowork) try to "simplify" it into one program, it will crash.

The tool that creates the embeddings (PyTorch) and the tool that builds the index (FAISS) each quietly bundle their own copy of a low-level component called **OpenMP**. On a Mac, when both copies get loaded into the *same* running program and the index tries to do heavy work, the two copies collide and the program dies instantly — no error message, just "segmentation fault."

**The fix, which is baked into this design:** never build the index in the same program that made the embeddings. So there's one script that does embeddings (uses PyTorch) and a *separate* script that builds the index (never touches PyTorch). They hand data to each other through files on disk.

You don't have to do anything about this — it's already handled. Just **don't merge the scripts**, and if Cowork ever suggests combining the embedding step and the index-building step into one program, say no and point it at this paragraph.

---

## What's current (updated 2026-08-08)

A running snapshot of how the live system behaves today. The step-by-step parts below still apply; this section captures the hardening added since the first build so the guide matches what's actually on the machine.

**It runs natively on Apple Silicon (arm64), and that's now enforced.** The Python from python.org is a "universal" binary — it contains *both* an Intel and an Apple-Silicon version, and it inherits which one to run from whatever launches it. If a launcher is running under Rosetta (Intel), it hands that Intel-ness down, and the interpreter then can't load the Apple-Silicon PyTorch/FAISS libraries — the web UI crash-loops with *"incompatible architecture (have 'arm64', need 'x86_64')."* The launcher (`servers` wrapper and the `com.dukemedia.rrdash` login item) now prefixes every launch with `arch -arm64` to pin the native slice. If you ever see that error or a repeating "Rosetta support ending" prompt, the cause is an Intel process launching the RAG; the fix is `arch -arm64`.

**Embeddings run on the Mac GPU (MPS) again, safely.** The GPU is the default (`ALEX_EMBED_DEVICE=mps`, auto-falls back to CPU if unavailable). Three things keep it from ever freezing the Mac the way earlier full rebuilds did: the embedding matrix is **streamed straight to disk** (never fully held in RAM), the GPU cache is flushed every batch, and an **RSS watchdog** prints memory each phase and aborts *gracefully* if the process crosses a ceiling (warn at 30 GB, abort at 42 GB — tunable via `ALEX_RSS_WARN_GB` / `ALEX_RSS_ABORT_GB`). Worst case it stops cleanly and you set `ALEX_EMBED_DEVICE=cpu`; it can't take the machine down. Watch the `[mem] … GB RSS` lines in the log to see the curve stay flat.

**One heavy job at a time, always out-of-process.** Full build, incremental update, rebuild, and PDF scan each run as a separate process, and each is guarded by an atomic single-run lock (a lockfile for the CLI, a claimed flag in the web app) so a double-click can't launch two embeds at once — the specific mistake that used to exhaust RAM. The web dashboard also **releases its own loaded index (~8 GB) for the duration of a rebuild** and reloads it when finished, so the build isn't competing with a stale copy.

**Incremental updates work and are the normal way to grow the library.** "Update Index" re-embeds only added/changed books, drops removed ones, and rebuilds keeping your tuned `nlist`/`nprobe`/metric. It relies on two small files every full build now writes — `alexandria_manifest.json` (per-file signature) and `alexandria_embeddings.npy` — so run at least one full build with the current code before relying on incremental.

**Current index:** IVFFlat, cosine (inner product on normalized vectors), `nlist 1024`, `nprobe 128`, model `intfloat/multilingual-e5-small` (384-dim), 1,994,790 chunks across 5,853 books, 3.08 GB.

**The model changed, and the reason matters.** `all-MiniLM-L6-v2` is English-only. On a library holding Greek, Latin, Hebrew and German it scored a Greek passage against its own English translation at 0.116 — below any usable threshold, so those books were not ranked low, they were unreachable. `multilingual-e5-small` scores the same pair at 0.91. Both are 384-dimensional, which is the trap: point the wrong one at an index built by the other and nothing errors, the dimensions line up, and every result is quiet nonsense. That is why the index now writes an `embedding_model.json` sidecar naming the model, its prefixes and its chunk size, and why `query_rag.py` reads that file and **overrides** whatever model name it was handed. e5 also requires prefixes — `passage: ` at index time, `query: ` at search time — and omitting them costs real accuracy while erroring not at all.

**Local MCP servers** (ten of them, letting Claude query the corpora directly, managed by Claude Desktop / Cowork over stdio): Alexandria RAG, Greek, Latin (with the Lewis & Short dictionary), Perseus, WikiSpooks, Pleiades, Wikipedia (offline Kiwix), Scriptures (Qur'an / Enoch / Tanakh / Talmud / Mishnah / Ethiopian Tewahedo canon), Project Gutenberg, and Papyri (Duke Databank, ~67.6k documentary papyri). Setup and config live in *"Set Up the MCP Servers with Claude Cowork."* After a rebuild, restart the Alexandria MCP server (or Claude Desktop) so it loads the fresh index instead of the one it holds in memory.

---

## Part 1 — Set up your workspace

**1a. Install Python 3.10.** This system was built and tested on Python 3.10. Go to [python.org/downloads](https://www.python.org/downloads/release/python-31011/), download the macOS installer for Python 3.10, and run it. To confirm it worked, open the **Terminal** app (press `Cmd+Space`, type "Terminal", press Return) and paste:

```
python3 --version
```

You should see something starting with `Python 3.10`.

**1b. Choose where everything lives.** You need a folder for the program files, a folder for your books, and space for the index (budget roughly 2× the size of your PDF collection). Peter keeps his on an external SSD; an internal drive is fine too. For this guide we'll assume a main folder called `Alexandria` with the program in `Alexandria/RAG_system` and books in `Alexandria/PDF`. Create them:

```
mkdir -p ~/Alexandria/RAG_system
mkdir -p ~/Alexandria/PDF
```

(Replace `~/Alexandria` with any location you like — e.g. `/Volumes/YourDrive/Alexandria` for an external drive. If you do, use that path everywhere below.)

**1c. Create a "virtual environment"** — a private, self-contained Python setup so this project's parts don't interfere with anything else on your Mac. Paste these one line at a time:

```
cd ~/Alexandria/RAG_system
python3 -m venv rag_env
source rag_env/bin/activate
```

After the third line, your Terminal prompt will start with `(rag_env)`. That means the environment is active. **You must run that `source ...` line every time you open a new Terminal window** to work on this — think of it as "turning the project on."

**1d. Install the required libraries.** With `(rag_env)` showing, paste:

```
pip install pdfplumber==0.10.4 ebooklib==0.18.0 sentence-transformers==2.7.0 faiss-cpu==1.8.0 numpy==1.24.3 pandas==2.0.3 tqdm==4.65.0 lxml==4.9.3 beautifulsoup4==4.12.2 flask
```

This downloads a few gigabytes and takes several minutes. When it finishes without red error text, you're set. (These exact versions matter — the newest versions of some of these have caused problems, so stick with these numbers.)

---

## Part 2 — Get the code

There are two ways to get the actual program files into `~/Alexandria/RAG_system`. Pick one.

**Option A — Copy Peter's files (easiest).** Ask Peter to share his `RAG_system` folder (he can zip it and send it, or drop it in a shared drive). Copy every file into your `~/Alexandria/RAG_system` folder — the `.py` files, the `templates` folder, and the `static` folder. This is the surest way to get something *exactly* like his. Then skip to Part 3.

**Option B — Have Claude Cowork build them from this guide.** Open Claude Cowork, point it at your `RAG_system` folder, and give it **Appendix B** of this document (the full source). Ask it: *"Create each of these files exactly as written in this document, in my RAG_system folder."* Cowork will write out every file. This is handy if you can't get the folder from Peter. Either way you end up with the same set of files.

Here's what the files are, so it's not a black box:

| File | What it does |
|---|---|
| `index_books.py` | The main indexer: reads your books, makes embeddings, and coordinates everything. Also has the "add just new books" and "check for corrupt files" shortcuts. |
| `extract_text.py` | Reads text out of PDFs/ebooks **in parallel** (using all your CPU cores) and **caches** it, so you never re-read the same book twice. |
| `build_index_cli.py` | Builds the search index. This is the **PyTorch-free** program (remember the big gotcha). |
| `query_rag.py` | The search engine itself — turns your question into numbers and finds matches. |
| `scan_pdfs.py` | Quickly checks every PDF for corruption without re-indexing. |
| `app.py` | The web dashboard — the thing you actually click around in. |
| `templates/` & `static/` | The look of the web pages (HTML, styling, buttons). |
| `alexandria_mcp_server.py` | *Optional:* lets Claude itself search your library directly. |

---

## Part 3 — Point it at your books

Put your PDFs (and ebooks, if you have them) into `~/Alexandria/PDF`. Subfolders are fine — the system looks through all of them.

Create a tiny settings file so the dashboard knows where things are. Paste this whole block (it writes the file for you):

```
cat > ~/Alexandria/RAG_system/rag_config.json <<'EOF'
{
  "books_dir": "/Users/YOURNAME/Alexandria/PDF",
  "index_dir": "/Users/YOURNAME/Alexandria"
}
EOF
```

**Important:** replace `YOURNAME` with your actual Mac username (find it by running `whoami` in Terminal), or use your external-drive path if that's where things live.

---

## Part 4 — Build the index for the first time

This is the big one-time job. It runs in **two stages** (remember the gotcha — embeddings and index-building are kept separate). Make sure the web dashboard is **not** running while you do this.

**Stage 1 — read every book and make embeddings.** This is the slow part: a few hours the first time, because it has to read thousands of PDFs. Good news — it reads them in parallel across all your CPU cores, and it *caches* the text, so you only ever pay this once. Paste (as always, with `(rag_env)` showing):

```
python3 index_books.py --input ~/Alexandria/PDF --output ~/Alexandria --embeddings-only
```

You'll see it working through your books, then a burst at the end where your GPU does the embedding. Let it finish completely.

**Stage 2 — build the index.** This is fast (seconds to a minute):

```
python3 build_index_cli.py --index-dir ~/Alexandria --index-type ivfflat --metric ip --nlist 1024 --nprobe 128 --from-npy ~/Alexandria/alexandria_embeddings.npy
```

A few of those words explained:
- `ivfflat` — the type of index (the "shelves" approach). Best balance of speed and accuracy for a big library.
- `ip` / cosine — how it measures "closeness of meaning." This is the correct setting for the embedding model used here; it noticeably improves results.
- `nlist 1024` — sort into 1,024 shelves.
- `nprobe 128` — check 128 shelves per question by default (you'll confirm this number in Part 6).

When it prints `✓ Done`, your index is built.

---

## Part 5 — Run the web dashboard

Start it:

```
python3 app.py
```

Wait a few seconds while it loads the index, then open your web browser and go to:

```
http://127.0.0.1:5050
```

> **Use `127.0.0.1`, not `localhost`.** On some Macs `localhost` doesn't resolve properly; `127.0.0.1` always works. They mean the same thing ("this computer").

Leave the Terminal window with `app.py` running — **that window *is* the server.** Closing it, or pressing `Ctrl+C` in it, shuts the website down. To use the Terminal for other commands, open a **second** Terminal tab with `Cmd+T`.

Take a tour of the tabs down the left side: **Search** (ask questions), **Tuning** (fine-tune the search — next part), **Management** (add books, check for damaged files), **Guide** (built-in optimization notes), and **Books** (browse what's indexed).

---

## Part 6 — Tune the search (find the sweet spot)

Your index works now, but let's make sure it's set to the best balance of accuracy and speed for *your* library.

1. Click the **Tuning** tab.
2. Find the **Recall vs Latency Sweep** box and click **Run sweep**. It runs a couple dozen test searches at different settings and draws a graph in a few seconds.
3. Read the graph. The **green line** is "how often it finds the genuinely best matches." The **blue line** is "how long a search takes." Green shoots up and then flattens; blue stays low then climbs steeply at the end.
4. Below the graph it prints a recommendation — an **efficiency elbow** (fastest setting that's still very accurate) and a **near-exact** setting (essentially perfect). For a big library, the near-exact number is a great default.
5. **Bake in your chosen number.** The simplest way: on the same Tuning tab, use the **Rebuild Index** panel — set Index type to IVFFlat, Metric to Cosine, nlist to 1024, nprobe to your chosen number (e.g. 128), and click **Rebuild Index**. It rebuilds in seconds and reloads automatically.

That's it — "baking in" just means saving that setting as the permanent default so every search uses it.

> The numbers wobble a little each time you run the sweep (it uses random test questions), and the timings depend on how busy your Mac is. Don't chase the exact number — anywhere in the flat part of the green curve is excellent.

---

## Part 7 — Everyday use

**Search.** Click the **Search** tab, type a question, press Return. That's the whole point of the system.

**Add new books.** Drop new PDFs into your `~/Alexandria/PDF` folder, then go to **Management → ➕ Update Index**. This only reads and embeds the *new* books (and drops any you deleted) — minutes, not hours — and keeps your tuned settings. This is the everyday way to grow your library.

**Check for damaged PDFs.** Go to **Management → 🩺 PDF Health Check → Scan Library**. It checks every PDF for corruption and lists any bad ones (also saved to a file called `problem_pdfs.txt`). Corrupt files aren't dangerous — they just extract poorly — but it's nice to know which to re-download.

**Re-tune.** After adding a lot of books, you can re-run the sweep (Part 6) to confirm your setting still lands in the sweet spot.

---

## PDF fidelity routines (keeping extraction honest)

Search quality is capped by extraction quality: a passage the extractor never read can't be found. These are the routines the system runs to keep the text faithful and to stop one bad file from wrecking a run. They're already built in — this is what's happening under the hood.

**Parallel, cached, PyTorch-free extraction.** `extract_text.py` reads text from every PDF/EPUB across several CPU cores and writes each book's text to an on-disk cache, keyed by the file's path + modification time + size. Unchanged books are read straight from cache on later runs, so re-indexing (for a new model, a new chunk size, or a few added books) skips the multi-hour extraction entirely. Change a file and its signature changes, so it's automatically re-read.

**A per-file watchdog, scaled to the file.** A single corrupt PDF can send the parser (pdfminer) into an effectively infinite loop and freeze the whole run, so each file is parsed under a `SIGALRM` timer. The limit was a flat 90 seconds until it truncated a 2,437-page, 200 MB volume that pdfplumber simply could not read that fast: the book was abandoned, 20 KB of Google Books front matter stayed in the cache, and it indexed as six chunks in place of 6,522. Nothing flagged it. The budget now scales — the 90-second floor, or six seconds per megabyte, capped at 30 minutes (`ALEX_EXTRACT_TIMEOUT`, `ALEX_EXTRACT_SECONDS_PER_MB`, `ALEX_EXTRACT_TIMEOUT_MAX`). An ordinary book is unaffected; a genuine infinite loop still dies at the ceiling.

**A memory cap so one bloated extraction can't crash the Mac.** A malformed PDF can extract to gigabytes of garbage text; chunking that can exhaust RAM. Any single document over **~50 MB of extracted text** (`ALEX_MAX_DOC_CHARS`, ≈ a 10,000-page book) is truncated with a warning rather than allowed to balloon.

**Recoverable-damage reporting.** pdfminer emits warnings like *"Data-loss while decompressing corrupted data"* with no filename. The system captures those per-file and writes the offending paths to **`problem_pdfs.txt`** so you know which books extracted imperfectly and might be worth re-downloading. The text that could be recovered is still indexed.

**Chunking sized from the model's real token limit.** Chunk size is no longer a constant. `chunk_params_for()` reads `max_seq_length` off the loaded model and derives words from it at roughly 1.45 subword tokens per word, with the overlap at a fifth of the chunk: a 512-token model such as e5-small takes **353 words with 70 of overlap**, where a 256-token model takes 200 with 40. Hard-coding one number meant that switching models in the dropdown silently mis-sized every chunk — too big and the tail of each one is truncated away unread, too small and you waste the model. Every chunk is normalized so search uses cosine similarity.

**A standalone health check (no re-indexing).** `scan_pdfs.py` — reachable from **Management → 🩺 PDF Health Check** — checks the library for corruption independently of indexing, in three modes: **incremental** (skip files unchanged since the last scan, per the manifest — the default), **verify** (re-hash even unchanged files), and **full** (rescan everything). Results stream to the dashboard and to `problem_pdfs.txt`. Add `--include-epub` to cover ebooks.

**An alignment guard on every build.** Row *i* of the embeddings must map to metadata row *i*, or every search result gets attributed to the wrong book. `build_index_cli.py` refuses to build from an embeddings file whose row count disagrees with `alexandria_metadata.json`, and falls back to reconstructing exact vectors from the live index when a saved `.npy` is stale. This is why the two files are always written together.

**Everyday cadence.** Drop new PDFs in, run **Update Index** (incremental), and periodically run the **PDF Health Check** to catch newly-added damaged files. To preview exactly what an incremental run will do without touching anything, run it from Terminal with `--incremental --dry-run`: it reports manifest/`.npy` presence, vector↔metadata alignment, any stale lock, and the precise add/change/remove counts, then exits.

---

## The failures that don't announce themselves

Every problem in the Troubleshooting section below tells you it happened. These
don't. They leave a book in the library list, with a plausible chunk count, that
returns nothing — or worse, returns something wrong. They are the ones worth
knowing about in advance, because none of them will ever raise an error.

Each was found by accident. That is the point.

**A text layer laid on top of a text layer.** OCR adds an invisible text layer;
it never removes one. Run OCR on a book that already has good text and every
word ends up in the file twice, so the extractor emits the page, then emits it
again. On 2026-08-08 this happened to 73 books at once, because the work queue
was written as a union with its own previous contents and therefore could only
grow — an entry added when a book had no text survived the book being replaced
with a good copy, and came round again years later. The signature is unmistakable
once you look for it: word count doubles while the proportion of real words does
not move at all. That only happens when the same words are written twice. The
guard now lives in the OCR pass itself, not just in the queue, because the queue
is only one of several ways a file can arrive at the pass.

**An English word-list used to judge a Latin book.** Every quality test in this
system began life as "what fraction of the extracted words are common English
words." Migne's *Patrologia Latina* scores 3% on that test and is flawless Latin;
Chalybäus scores 4% and is flawless German; Greek and Hebrew do not survive the
`[A-Za-z]` token pattern at all. Books like these read as unrecoverable garbage
and get queued for the very OCR pass that would destroy them. The test now
calibrates on the document's own vocabulary instead: real writing reuses its
words heavily — a type-token ratio around 0.08 for a novel, 0.15 for Migne —
while OCR noise almost never repeats, and lands near 0.37. That measure works in
any language because it never asks what language it is reading.

**Page sampling that lands on the same kind of page every time.** Typescript and
mimeograph are printed on one side, so the versos are blank. An evenly spaced
sample takes an even stride and therefore hits blank pages every single time: one
850-page volume measured **zero words per page across eight probes** while
actually holding 227,754 words. A file that reads as empty is a file every guard
waves straight through. Probe consecutive *pairs* of pages, or extract the whole
document — never single pages at a fixed interval.

**Two columns read straight across the gutter.** pdfplumber follows page
geometry, so on a two-column book it takes line 1 of column A, then line 1 of
column B, then line 2 of A. Every word is real and in the right language. Every
sentence is destroyed. The book indexes, reports a healthy chunk count, and
cannot be retrieved even by an exact sentence copied off its own page. In a
random sample of 60 books, **12 were affected**. `pdftotext -raw` follows the
content stream instead and reads such a page correctly — comparing the two
orderings on one page is a cheap detector for the whole library.

**What they have in common.** In each case the pipeline reported success, the
counts looked reasonable, and the damage was only visible if you read the text.
A count is not evidence. If you take one habit from this guide, take this one:
after any bulk operation, open the actual text of two or three books and read a
paragraph.


---

## Troubleshooting (the greatest hits)

**The web UI crash-loops with "incompatible architecture (have 'arm64', need 'x86_64')," or a "Rosetta support ending" prompt keeps appearing.** Something is launching the RAG with the *Intel* slice of the universal Python, under Rosetta, and it can't load the Apple-Silicon PyTorch/FAISS libraries. The launcher pins the native slice with `arch -arm64` (in the `servers` wrapper and the `com.dukemedia.rrdash` login item); if you start things by hand, prefix with `arch -arm64` too. Confirm a process is native in Activity Monitor — the **Kind** column should read **Apple**, not **Intel**.

**An embed climbs in memory / you want to watch it.** Every embed now prints `[mem] … GB RSS` lines by phase, and a watchdog aborts *gracefully* if it crosses the ceiling (warn 30 GB, abort 42 GB — `ALEX_RSS_WARN_GB` / `ALEX_RSS_ABORT_GB`). If it ever aborts, fall back to CPU for that run with `ALEX_EMBED_DEVICE=cpu`. On Apple Silicon the GPU (MPS) is the default and normally sits far below the warn line.

**"Another indexing run is already active" / a stale `.indexing.lock`.** Only one embed runs at a time by design. If a previous run was hard-killed it can leave a stale lock; the message tells you the PID and the exact `rm` to clear it. `--incremental --dry-run` also reports whether a lock is present and whether it's live or stale.

**`zsh: killed` when running `app.py` or a build.** The program was force-quit. Usually that's the Mac running low on memory (close other big apps and try again), or you (or a `kill` command) stopped it on purpose. It is **not** a code crash and your data is safe. Just start the program again.

**"Segmentation fault" during an index build.** This is the OpenMP gotcha from the top of this guide — it means the index build got tangled up with PyTorch. It should never happen if you use the two-stage build (`index_books.py --embeddings-only` then `build_index_cli.py`). If it does, you or Cowork likely merged the steps — don't.

**The whole Mac froze or rebooted while indexing (kernel panic).** Extraction is memory-heavy, and running too many parallel parsers at once can exhaust RAM and swap until macOS force-restarts. The system defaults to a modest 4 workers to prevent this. If it ever recurs — for example on a library of huge, image-heavy scans — lower it further with `--workers 2`. Your index is safe: extraction happens before anything is written to it.

**The website won't load.** Make sure `app.py` is still running in its Terminal window, and use `http://127.0.0.1:5050` (not `localhost`). If the page looks stale, hard-refresh with `Cmd+Shift+R`.

**Why port 5050 and not 5000.** macOS AirPlay Receiver (the ControlCenter process) listens on port 5000 and launchd revives it whenever anything kills it. A web app on 5000 loses that fight in confusing ways — phantom "already running" reports, 403 pages served by AirPlay. Use 5050 (or anything except 5000/7000), or turn AirPlay Receiver off in System Settings → General → AirDrop & Handoff. The `-sTCP:LISTEN` flag on lsof matters too: without it, browser tabs connected to the port masquerade as the server.

**"Address already in use" / a stuck server.** An old copy is still holding the connection. Clear it, then restart:

```
lsof -ti:5050 -sTCP:LISTEN | xargs kill -9
python3 app.py
```

**I changed a setting from the command line but the website still shows the old one.** The running website loaded the index into memory when it started and doesn't notice changes made from the Terminal. **Restart it** (`Ctrl+C` in its window, then `python3 app.py`). Rebuilds done *from the Tuning tab* reload automatically; command-line rebuilds need a restart.

**A book is in the library list but never appears in results.** Check its chunk
count in `alexandria_manifest.json` against the book's size. Six chunks for a
2,000-page volume means extraction was abandoned — most often the per-file
watchdog on a very large file (see above). Re-extract it and mark its manifest
entry stale so the next incremental run picks it up. **Mark it stale; do not
delete it.** `run_incremental` computes `added` as *on disk but not in metadata*
and `changed` as *manifest signature differs*, so a book that is already in the
metadata with no manifest entry falls through both branches and can never be
re-embedded. Give the entry a signature that cannot match instead — `{"sig": "0 0"}`.

**A book returns nothing even for an exact sentence from its own page.** Its
text is probably column-interleaved (see above). Compare one page through
`pdftotext -raw` against `pdftotext -layout`: if the same words come back in a
very different order, the book has columns and the indexed copy is scrambled.

**A filename promises one book and the file contains another.** A volume titled
*Patrologia Graeca* Vol. 6, Justin Martyr held Gregory of Tours in Latin, with
zero pages of Greek in 647. Nothing in the pipeline compares a book's contents to
its name, and a wrong title in a citation is worse than a missing one. When
renaming, the path is the key in the text cache (a SHA-1 of it), the ledger and
the manifest — move all three with the file or you orphan the cache and the book
re-extracts from scratch.

**I typed a question and got `zsh: no matches found`.** You typed it into the Terminal by mistake. Questions for Claude go in the Cowork chat window; only commands go in the Terminal.

---

## Why it's built the way it is (design notes)

For the curious, here are the deliberate choices, each of which came from a real problem:

- **Two-stage builds (embeddings, then index) in separate programs** — prevents the PyTorch/FAISS OpenMP crash. The single most important rule.
- **Cosine similarity (normalized inner product)** — the embedding model is trained for it; using plain distance quietly hurts result quality.
- **Chunk size derived from the model, not hard-coded** — a chunk longer than the model's token limit has its tail silently discarded, and the loss is invisible. Reading `max_seq_length` off the model means changing models in the dropdown cannot quietly break the chunking.
- **A sidecar naming the embedding model** — two different 384-dimensional models load against each other's indexes without complaint and return nonsense. The sidecar makes the mismatch impossible rather than merely unlikely.
- **Parallel extraction with an on-disk cache** — extraction is the slow phase; doing it across several cores and caching the text means you pay the cost once, not every time.
- **A deliberately modest worker count (4 by default)** — PDF parsing is memory-heavy, and running one parser per core on a many-core machine can exhaust RAM and swap badly enough to *crash the whole Mac* (a kernel panic). Four parallel parsers is safe and still far faster than one at a time. A "less is more" choice learned the hard way.
- **Incremental updates re-extract only the new books** — adding books processes just those, never the whole library, so a routine update can't set off a mass parallel extraction.
- **In-app tuning with a real measured graph** — you set nprobe from evidence, not guesswork.

---

## Working with Claude Cowork

This whole system was built and refined *with* Claude Cowork, and your friend can lean on it the same way:

- **To build the files:** give Cowork Appendix B and ask it to create each file.
- **To understand an error:** paste the error into Cowork and ask what it means.
- **To change something:** describe what you want ("add a button that…", "make searches return 10 results") and let Cowork edit the code.
- **The one thing to hold firm on:** never let it merge the embedding step and the index-building step into one program (the OpenMP gotcha).

---

## Appendix A — What each file does (reference)

- **`index_books.py`** — orchestrates indexing. Reads books (via the cache), makes embeddings, saves them. Flags: `--embeddings-only` (stage 1 of a full build), `--incremental` (add/remove changed books only), `--scan-only` (corruption check). Also holds the chunking logic (sized from the model's token limit) and normalizes embeddings for cosine.
- **`extract_text.py`** — PyTorch-free. Extracts PDF/EPUB text in parallel across a *capped* number of cores (4 by default — PDF parsing is memory-heavy, so too many at once can crash the Mac) and caches each file's text on disk, keyed by the file's modification time and size (so changed files are re-read, unchanged ones reused).
- **`build_index_cli.py`** — PyTorch-free. Builds any index type (Flat, IVFFlat, IVFPQ, HNSW) from saved embeddings or an existing index, with cosine or L2. This is the program that *must* stay separate from PyTorch.
- **`query_rag.py`** — loads the index and model, turns a question into a normalized vector, searches, and returns ranked passages. Detects the index type and supports live tuning (nprobe / efSearch).
- **`scan_pdfs.py`** — PyTorch-free, parallel PDF corruption scanner. Writes `problem_pdfs.txt`.
- **`app.py`** — the Flask web server and all its API endpoints: search, tuning sweep, rebuild, incremental update, PDF scan. Runs heavy jobs as separate processes so the web app never does dangerous in-process index work.
- **`templates/*.html`, `static/*`** — the dashboard pages and styling.
- **`alexandria_mcp_server.py`** — optional MCP server so Claude can query the library directly.

---

## Appendix B — Full source code

*Every file below is reproduced exactly. Create each one in your `RAG_system` folder (put the `templates/…` files in a `templates` subfolder and the `static/…` files in a `static` subfolder). Or hand this whole section to Claude Cowork and ask it to create the files for you.*

<!-- SOURCE-APPENDIX -->

### `requirements.txt`

```text
pdfplumber==0.10.4
ebooklib==0.18.0
sentence-transformers==2.7.0
faiss-cpu==1.8.0
numpy==1.24.3
pandas==2.0.3
tqdm==4.65.0
lxml==4.9.3
beautifulsoup4==4.12.2

```

### `extract_text.py`

```python
#!/usr/bin/env python3
"""
Alexandria — parallel PDF/EPUB text extractor with on-disk cache (TORCH-FREE).

Extraction is the slow phase of indexing (single-threaded pdfplumber over
thousands of books = ~13-14 h). This module parallelizes it across CPU cores
and caches each book's extracted text to disk, keyed by path + mtime + size.

Result:
  * First run: extraction runs in parallel (~hours → a few hours).
  * Later runs: unchanged books are read straight from cache (seconds), so
    re-indexing for a new model / chunk size / a few added books skips the
    14-hour extraction entirely.

This file imports ONLY pdf/epub libraries — never torch/faiss — so its worker
processes stay light and there is no OpenMP conflict.

Run standalone to (re)populate the cache:
    python3 extract_text.py --input /Volumes/PRO-BLADE/Alexandria/PDF \
        --cache-dir /Volumes/PRO-BLADE/Alexandria/text_cache
"""

import os
import sys
import time
import hashlib
import logging
import argparse
import warnings
from pathlib import Path
from multiprocessing import Pool, cpu_count

warnings.filterwarnings("ignore")


# --------------------------------------------------------------------------- #
# Cache helpers (also imported by index_books.py)
# --------------------------------------------------------------------------- #
def _key(path):
    return hashlib.sha1(os.path.abspath(path).encode("utf-8")).hexdigest()


def cache_files(cache_dir, path):
    k = _key(path)
    d = Path(cache_dir)
    return d / (k + ".txt"), d / (k + ".meta")


def _sig(path):
    """A cheap fingerprint of the source file: modification time + size."""
    st = os.stat(path)
    return f"{st.st_mtime_ns} {st.st_size}"


def is_cached(cache_dir, path):
    """True if a fresh cached extraction exists for this file."""
    txt, meta = cache_files(cache_dir, path)
    if not (txt.exists() and meta.exists()):
        return False
    try:
        return meta.read_text().strip() == _sig(path)
    except OSError:
        return False


def read_cached_text(cache_dir, path):
    txt, _ = cache_files(cache_dir, path)
    try:
        return txt.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def write_cache(cache_dir, path, text):
    txt, meta = cache_files(cache_dir, path)
    txt.parent.mkdir(parents=True, exist_ok=True)
    txt.write_text(text, encoding="utf-8")
    meta.write_text(_sig(path))


# --------------------------------------------------------------------------- #
# Extraction (torch-free)
# --------------------------------------------------------------------------- #
def _extract_pdf(path):
    """Return (text, [pdfminer warnings]) for a PDF."""
    import pdfplumber

    msgs = []

    class _Col(logging.Handler):
        def __init__(self):
            super().__init__(logging.WARNING)

        def emit(self, record):
            msgs.append(record.getMessage())

    lg = logging.getLogger("pdfminer")
    handler = _Col()
    lg.addHandler(handler)
    lg.setLevel(logging.WARNING)
    text = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text.append(t)
    finally:
        lg.removeHandler(handler)
    return "\n".join(text), sorted(set(msgs))


def _extract_epub(path):
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup

    text = []
    book = epub.read_epub(path)
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            try:
                soup = BeautifulSoup(item.get_content(), "html.parser")
                content = soup.get_text(separator=" ", strip=True)
                if content:
                    text.append(content)
            except Exception:
                continue
    return "\n".join(text), []


import signal


class _ExtractTimeout(Exception):
    pass


def _on_alarm(signum, frame):
    raise _ExtractTimeout()


# A single malformed PDF can send pdfminer into an effectively infinite loop and
# DEADLOCK the whole worker pool — one bad file freezes the entire index build
# (observed 2026-07). Each worker runs one file on its main thread, so a SIGALRM
# watchdog aborts that file and records it as an error, letting the run continue
# instead of hanging forever.
#
# The limit has to scale with the book. A flat 90 seconds silently truncated
# Michael L. Rodkinson's *New Edition of the Babylonian Talmud* — 2,437 pages,
# 200 MB, 1,043,500 words — which pdfplumber cannot read anywhere near that fast.
# What stayed in the cache was 20 KB of Google Books front matter, and that is
# what got embedded: the book indexed, reported six chunks, appeared in the
# library list, and would never have returned a passage. Nothing distinguished it
# from a book that genuinely holds two thousand words (2026-08-08).
#
# Scaling by file size costs one stat and bounds the damage either way: a normal
# book still gets the old 90-second floor, a 200 MB volume gets twenty minutes,
# and a genuine infinite loop still dies at the ceiling.
PER_FILE_TIMEOUT = int(os.environ.get("ALEX_EXTRACT_TIMEOUT", "90"))
TIMEOUT_CEILING = int(os.environ.get("ALEX_EXTRACT_TIMEOUT_MAX", "1800"))
SECONDS_PER_MB = float(os.environ.get("ALEX_EXTRACT_SECONDS_PER_MB", "6"))


def timeout_for(path):
    """Seconds to allow this file: the floor, or six seconds a megabyte, capped."""
    try:
        mb = os.path.getsize(path) / 1_000_000
    except OSError:
        return PER_FILE_TIMEOUT
    return int(max(PER_FILE_TIMEOUT, min(TIMEOUT_CEILING, mb * SECONDS_PER_MB)))


def extract_one(task):
    """Worker: extract one book to cache. Returns (path, status, [issues])."""
    path, cache_dir, use_cache = task
    if use_cache and is_cached(cache_dir, path):
        return (path, "cached", [])
    armed = False
    try:
        low = path.lower()
        if not (low.endswith(".pdf") or low.endswith(".epub")):
            return (path, "skip", [])
        budget = timeout_for(path)
        try:
            signal.signal(signal.SIGALRM, _on_alarm)
            signal.alarm(budget)
            armed = True
        except (ValueError, AttributeError):
            armed = False          # not on the main thread / unsupported platform
        if low.endswith(".pdf"):
            text, warns = _extract_pdf(path)
        else:
            text, warns = _extract_epub(path)
        write_cache(cache_dir, path, text)
        status = "ok" if text.strip() else "empty"
        return (path, status, warns)
    except _ExtractTimeout:
        return (path, "error",
                [f"timeout: extraction exceeded {budget}s "
                 f"({os.path.getsize(path)/1e6:.0f} MB) — malformed, or raise "
                 f"ALEX_EXTRACT_SECONDS_PER_MB"])
    except Exception as e:
        return (path, "error", [f"{type(e).__name__}: {e}"])
    finally:
        if armed:
            signal.alarm(0)


def find_books(input_dir, include_epub):
    root = Path(input_dir)
    exts = {".pdf"} | ({".epub"} if include_epub else set())
    return sorted(str(p) for p in root.rglob("*") if p.suffix.lower() in exts)


def run_extract(input_dir, cache_dir, workers=None, include_epub=False,
                use_cache=True, output_dir=None):
    """Parallel-extract every book into the cache. Returns a summary dict."""
    # Cap workers hard. PDF parsing (pdfplumber) is MEMORY-heavy — image-rich
    # PDFs can use hundreds of MB to GBs each. Too many parallel workers exhaust
    # RAM/swap and can kernel-panic the Mac (watchdog timeout). 4 is a safe
    # default even on many-core machines; override with --workers if you know
    # your library is light and your RAM is ample.
    workers = workers or max(1, min(cpu_count() - 1, 4))
    books = find_books(input_dir, include_epub)
    if not books:
        print(f"No books found under {input_dir}")
        return {"total": 0}

    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    print(f"Extracting {len(books):,} books with {workers} workers "
          f"(cache: {cache_dir}) ...", flush=True)

    counts = {"cached": 0, "ok": 0, "empty": 0, "error": 0, "skip": 0}
    problems = []
    tasks = [(b, cache_dir, use_cache) for b in books]
    t0 = time.perf_counter()
    with Pool(workers) as pool:
        for i, (path, status, issues) in enumerate(
                pool.imap_unordered(extract_one, tasks, chunksize=4), 1):
            counts[status] = counts.get(status, 0) + 1
            if status == "error" or issues:
                problems.append((path, issues or [status]))
            if i % 250 == 0 or i == len(books):
                rate = (time.perf_counter() - t0) / i
                eta = rate * (len(books) - i) / 60
                print(f"  ...{i:,}/{len(books):,}  "
                      f"(cached {counts['cached']:,}, extracted {counts['ok']:,}, "
                      f"errors {counts['error']}) ~{eta:.0f} min left", flush=True)

    if problems and output_dir:
        report = Path(output_dir) / "problem_pdfs.txt"
        with open(report, "w") as f:
            f.write(f"# {len(problems)} books had extraction issues — {time.ctime()}\n\n")
            for path, iss in sorted(problems):
                f.write(f"{path}\n    {'; '.join(iss)}\n")
        print(f"⚠ {len(problems)} book(s) with issues — see {report}", flush=True)

    mins = (time.perf_counter() - t0) / 60
    print(f"✓ Extraction done in {mins:.1f} min — "
          f"{counts['cached']:,} from cache, {counts['ok']:,} freshly extracted, "
          f"{counts['empty']:,} empty, {counts['error']} errors.", flush=True)
    return {"total": len(books), **counts, "minutes": round(mins, 1)}


def main():
    ap = argparse.ArgumentParser(description="Parallel torch-free book text extractor")
    ap.add_argument("--input", required=True, help="Directory of books")
    ap.add_argument("--cache-dir", required=True, help="Where to store cached text")
    ap.add_argument("--workers", type=int, default=None,
                    help="Parallel workers (default: min(cores-1, 4); PDF parsing is "
                         "memory-heavy, so keep this modest to avoid swap exhaustion).")
    ap.add_argument("--include-epub", action="store_true", default=False)
    ap.add_argument("--no-cache", action="store_true", default=False,
                    help="Ignore existing cache and re-extract everything")
    ap.add_argument("--output", default=None, help="Dir for problem_pdfs.txt")
    args = ap.parse_args()
    run_extract(args.input, args.cache_dir, workers=args.workers,
                include_epub=args.include_epub, use_cache=not args.no_cache,
                output_dir=args.output or args.cache_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `scan_pdfs.py`

```python
#!/usr/bin/env python3
"""
Alexandria — fast PDF integrity scanner (TORCH-FREE).

Walks every PDF and decompresses each stream via pdfminer — the exact code path
that emits "Data-loss while decompressing corrupted data" during real indexing —
WITHOUT chunking, embedding, or building any index. It just finds the corrupt
files and writes their paths to problem_pdfs.txt.

~0.8 s/PDF, parallel across CPU cores (no torch/faiss, so no OpenMP conflict).
For ~3,800 PDFs that's roughly 12 minutes on 4 cores vs the ~13-hour full
extraction.

Usage:
    python3 scan_pdfs.py --input /Volumes/PRO-BLADE/Alexandria/PDF
    python3 scan_pdfs.py --input /Volumes/PRO-BLADE/Alexandria/PDF --workers 4
"""

import os
import sys
import time
import logging
import argparse
import warnings
from pathlib import Path
from multiprocessing import Pool, cpu_count

warnings.filterwarnings("ignore")


def scan_one(path):
    """Decompress every stream in one PDF; return (path, [messages]) if any
    pdfminer warning fired or the file couldn't be parsed, else None."""
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdftypes import PDFStream

    msgs = []

    class _Col(logging.Handler):
        def __init__(self):
            super().__init__(logging.WARNING)

        def emit(self, record):
            msgs.append(record.getMessage())

    lg = logging.getLogger("pdfminer")
    handler = _Col()
    lg.addHandler(handler)
    lg.setLevel(logging.WARNING)
    try:
        with open(path, "rb") as f:
            doc = PDFDocument(PDFParser(f))
            for xref in doc.xrefs:
                for oid in list(xref.get_objids()):
                    try:
                        obj = doc.getobj(oid)
                        if isinstance(obj, PDFStream):
                            obj.get_data()  # triggers FlateDecode → warning if corrupt
                    except Exception:
                        pass  # individual object errors are common & non-fatal
    except Exception as e:
        msgs.append(f"parse error: {type(e).__name__}: {e}")
    finally:
        lg.removeHandler(handler)

    uniq = sorted(set(msgs))
    return (path, uniq) if uniq else None


def find_pdfs(input_dir):
    root = Path(input_dir)
    return sorted(p for p in root.rglob("*") if p.suffix.lower() == ".pdf")


def main():
    ap = argparse.ArgumentParser(description="Fast PDF integrity scanner (torch-free)")
    ap.add_argument("--input", required=True, help="Directory of PDFs to scan")
    ap.add_argument("--output", default=None,
                    help="Where to write problem_pdfs.txt (default: --input dir)")
    ap.add_argument("--workers", type=int, default=max(1, cpu_count() - 1),
                    help="Parallel worker processes")
    args = ap.parse_args()

    pdfs = [str(p) for p in find_pdfs(args.input)]
    if not pdfs:
        print(f"No PDFs found under {args.input}")
        return 0

    print(f"Scanning {len(pdfs):,} PDFs with {args.workers} workers ...")
    t0 = time.perf_counter()
    problems = []
    with Pool(args.workers) as pool:
        for i, res in enumerate(pool.imap_unordered(scan_one, pdfs, chunksize=4), 1):
            if res:
                problems.append(res)
                print(f"  ⚠ {Path(res[0]).name}: {'; '.join(res[1])}")
            if i % 250 == 0:
                rate = (time.perf_counter() - t0) / i
                eta = rate * (len(pdfs) - i) / 60
                print(f"  ...{i:,}/{len(pdfs):,}  ({rate:.2f}s/pdf, ~{eta:.0f} min left)")

    out_dir = Path(args.output or args.input)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = out_dir / "problem_pdfs.txt"
    with open(report, "w") as f:
        f.write(f"# {len(problems)} of {len(pdfs)} PDFs had issues — {time.ctime()}\n")
        f.write("# These triggered pdfminer warnings or failed to parse.\n")
        f.write("# Text may still extract partially; consider re-sourcing them.\n\n")
        for path, m in sorted(problems):
            f.write(f"{path}\n    {'; '.join(m)}\n")

    mins = (time.perf_counter() - t0) / 60
    print(f"\nDone in {mins:.1f} min. {len(problems)} of {len(pdfs):,} PDFs flagged.")
    print(f"Report: {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### `build_index_cli.py`

```python
#!/usr/bin/env python3
"""
Alexandria RAG — standalone FAISS index builder (TORCH-FREE).

This script deliberately imports ONLY numpy + faiss. It must never import
torch / sentence_transformers: torch, sklearn and faiss each bundle their own
libomp.dylib, and loading two OpenMP runtimes into one process segfaults FAISS
the instant it enters a parallel section (k-means training, HNSW graph build)
on macOS Apple Silicon. Keeping torch out of THIS process is the whole fix.

It builds any of the FAISS index families from existing embeddings:
    flat     IndexFlatL2            exact, 100% accurate, slowest
    ivfflat  IndexIVFFlat           cluster buckets, fast, ~exact (tune nprobe)
    ivfpq    IndexIVFPQ             clusters + compression, smallest/fastest
    hnsw     IndexHNSWFlat          graph index, very fast queries, high RAM

Vectors come from one of:
    --from-index PATH   reconstruct exact vectors from an existing FAISS index
                        (defaults to <index-dir>/alexandria.index)
    --from-npy PATH     load a saved float32 embeddings matrix (.npy)

Outputs into --index-dir:
    alexandria.index            the new index (old one backed up once)
    alexandria.index.<t>.backup backup of whatever was there before
    index_params.json           records index type + params (UI reads this)

Usage:
    python3 build_index_cli.py --index-dir /Volumes/PRO-BLADE/Alexandria \
        --index-type ivfflat --nlist 1000 --nprobe 50
"""

import os
# --- OpenMP safety guards: set BEFORE importing faiss -----------------------
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "4")

import sys
import json
import time
import shutil
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
import faiss

VALID_TYPES = ("flat", "ivfflat", "ivfpq", "hnsw")


def log(msg):
    """Print and flush immediately so a parent process can stream progress."""
    print(msg, flush=True)


def nearest_divisor(d, m):
    """Return the divisor of d closest to m (PQ requires m | d)."""
    divisors = [i for i in range(1, d + 1) if d % i == 0]
    return min(divisors, key=lambda x: abs(x - m))


def load_vectors(args):
    """Load exact float32 vectors from an existing index or an .npy file."""
    if args.from_npy:
        log(f"Loading embeddings from {args.from_npy} ...")
        vectors = np.load(args.from_npy)
    else:
        src = args.from_index or str(Path(args.index_dir) / "alexandria.index")
        if not Path(src).exists():
            raise FileNotFoundError(f"No source index at {src}")
        log(f"Loading source index {src} ...")
        src_index = faiss.read_index(src)
        n = src_index.ntotal
        log(f"  source has {n:,} vectors; reconstructing ...")
        # IVF indexes need a direct map before reconstruct_n works.
        try:
            src_index.make_direct_map()
        except Exception:
            pass
        vectors = src_index.reconstruct_n(0, n)

    vectors = np.ascontiguousarray(vectors, dtype="float32")
    # Cosine similarity = inner product on L2-normalized vectors. all-MiniLM
    # (and bge/e5/gte) are trained for cosine, so normalize by default.
    if args.metric == "ip":
        faiss.normalize_L2(vectors)
        log("  normalized vectors (cosine / inner-product mode)")
    log(f"✓ Vectors ready: {vectors.shape[0]:,} x {vectors.shape[1]}")
    return vectors


def build_index(vectors, args):
    """Construct the requested FAISS index from in-memory vectors."""
    n, d = vectors.shape
    faiss.omp_set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
    t = args.index_type
    metric = faiss.METRIC_INNER_PRODUCT if args.metric == "ip" else faiss.METRIC_L2
    flat_cls = faiss.IndexFlatIP if args.metric == "ip" else faiss.IndexFlatL2
    params = {"index_type": t, "metric": args.metric, "dimension": d, "ntotal": int(n)}

    log(f"\n=== Building {t.upper()} index ({args.metric}) for {n:,} vectors (dim {d}) ===")
    start = time.time()

    if t == "flat":
        index = flat_cls(d)
        index.add(vectors)

    elif t == "ivfflat":
        nlist = args.nlist
        quantizer = flat_cls(d)
        index = faiss.IndexIVFFlat(quantizer, d, nlist, metric)
        log(f"  nlist={nlist}; training centroids ...")
        index.train(vectors)
        index.add(vectors)
        index.nprobe = args.nprobe
        params.update(nlist=nlist, nprobe=args.nprobe)

    elif t == "ivfpq":
        nlist = args.nlist
        m = args.pq_m
        if d % m != 0:
            snapped = nearest_divisor(d, m)
            log(f"  ⚠ pq_m={m} does not divide d={d}; using m={snapped}")
            m = snapped
        nbits = args.pq_nbits
        quantizer = flat_cls(d)
        index = faiss.IndexIVFPQ(quantizer, d, nlist, m, nbits, metric)
        log(f"  nlist={nlist}, pq_m={m}, nbits={nbits}; training ...")
        index.train(vectors)
        index.add(vectors)
        index.nprobe = args.nprobe
        params.update(nlist=nlist, nprobe=args.nprobe, pq_m=m, pq_nbits=nbits)

    elif t == "hnsw":
        M = args.hnsw_m
        index = faiss.IndexHNSWFlat(d, M, metric)
        index.hnsw.efConstruction = args.hnsw_efc
        log(f"  M={M}, efConstruction={args.hnsw_efc}; building graph ...")
        index.add(vectors)
        index.hnsw.efSearch = args.hnsw_efs
        params.update(hnsw_m=M, hnsw_ef_construction=args.hnsw_efc,
                      hnsw_ef_search=args.hnsw_efs)
    else:
        raise ValueError(f"Unknown index type: {t}")

    params["build_seconds"] = round(time.time() - start, 1)
    log(f"✓ Built in {params['build_seconds']}s ({index.ntotal:,} vectors)")
    return index, params


def quick_accuracy(index, vectors, args, n_queries=200, k=10):
    """Top-k overlap vs exact Flat search, on a random sample of queries."""
    if args.index_type == "flat":
        return 100.0
    n = vectors.shape[0]
    sample = vectors[np.random.choice(n, min(n_queries, n), replace=False)]
    flat_cls = faiss.IndexFlatIP if args.metric == "ip" else faiss.IndexFlatL2
    flat = flat_cls(vectors.shape[1])
    flat.add(vectors)
    _, I_true = flat.search(sample, k)
    _, I_new = index.search(sample, k)
    overlap = np.mean([len(set(I_true[i]) & set(I_new[i])) / k
                       for i in range(sample.shape[0])]) * 100
    return round(float(overlap), 1)


def save_index(index, params, args):
    """Save the new index, back up the old one, and write index_params.json."""
    index_dir = Path(args.index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    index_path = index_dir / "alexandria.index"

    if index_path.exists() and not args.no_backup:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = index_dir / f"alexandria.index.{stamp}.backup"
        shutil.copy(index_path, backup)
        log(f"✓ Backed up previous index → {backup.name}")

    faiss.write_index(index, str(index_path))
    size_gb = index_path.stat().st_size / 1e9
    params["index_size_gb"] = round(size_gb, 3)
    params["built_at"] = datetime.now().isoformat()

    with open(index_dir / "index_params.json", "w") as f:
        json.dump(params, f, indent=2)
    log(f"✓ Saved {index_path.name} ({size_gb:.2f} GB)")
    log(f"✓ Wrote index_params.json")


def main():
    p = argparse.ArgumentParser(description="Torch-free FAISS index builder")
    p.add_argument("--index-dir", default="/Volumes/PRO-BLADE/Alexandria")
    p.add_argument("--index-type", choices=VALID_TYPES, default="ivfflat")
    p.add_argument("--metric", choices=("ip", "l2"), default="ip",
                   help="ip = cosine (normalized inner product, recommended); l2 = Euclidean")
    p.add_argument("--from-index", help="Source FAISS index to reconstruct vectors from")
    p.add_argument("--from-npy", help="Source embeddings .npy file")
    # IVF
    p.add_argument("--nlist", type=int, default=1000)
    p.add_argument("--nprobe", type=int, default=50)
    # PQ
    p.add_argument("--pq-m", type=int, default=64, help="PQ subquantizers (must divide dim)")
    p.add_argument("--pq-nbits", type=int, default=8)
    # HNSW
    p.add_argument("--hnsw-m", type=int, default=32)
    p.add_argument("--hnsw-efc", type=int, default=200, help="efConstruction")
    p.add_argument("--hnsw-efs", type=int, default=64, help="efSearch")
    p.add_argument("--no-backup", action="store_true")
    p.add_argument("--no-accuracy", action="store_true", help="Skip the accuracy check")
    args = p.parse_args()

    log("=" * 70)
    log(f"Alexandria index builder — {args.index_type.upper()}")
    log("=" * 70)

    vectors = load_vectors(args)
    index, params = build_index(vectors, args)

    if not args.no_accuracy:
        log("\nMeasuring top-10 overlap vs exact Flat search ...")
        acc = quick_accuracy(index, vectors, args)
        params["accuracy_vs_flat_pct"] = acc
        log(f"✓ Top-10 overlap: {acc}%")

    save_index(index, params, args)
    log("\n✓ Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

```

### `query_rag.py`

```python
#!/usr/bin/env python3
"""
Alexandria RAG Query Interface
Search through your indexed book collection using semantic similarity.
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

# Baked-in default for IVF indexes. 128 is the recall/latency knee for the
# current index: ~99% recall vs an exhaustive scan at <10 ms/query, measured by
# the Recall-vs-Latency sweep (2026-07). Below this you lose real recall; above
# it latency climbs while recall is already flat. Applied on every load, so the
# MCP server, the web UI, and any rebuild all start here. It is a FLOOR, not a
# cap — a higher value deliberately persisted in the index is left untouched.
DEFAULT_NPROBE = 128


class RAGQuerier:
    """Query semantic search index."""

    def __init__(self, index_dir: str = ".", model_name: str = "all-MiniLM-L6-v2"):
        """Load index and metadata."""
        index_dir = Path(index_dir)

        index_path = index_dir / "alexandria.index"
        metadata_path = index_dir / "alexandria_metadata.json"

        if not index_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(
                f"Index files not found in {index_dir}. "
                "Run index_books.py first."
            )

        # Which model built this index? Do not guess. multilingual-e5-small and
        # all-MiniLM-L6-v2 are BOTH 384-dim, so loading the wrong one raises no
        # dimension error -- it returns confident nonsense. index_books.py
        # records the answer beside the index; trust that over any default.
        self.query_prefix = ""
        _meta = index_dir / "embedding_model.json"
        if _meta.exists():
            try:
                _m = json.loads(_meta.read_text())
                if _m.get("model"):
                    model_name = _m["model"]
                self.query_prefix = _m.get("query_prefix", "") or ""
            except Exception as _e:
                print(f"  ! could not read embedding_model.json: {_e}")
        else:
            print("  ! no embedding_model.json beside the index -- assuming "
                  f"{model_name}. If the index was built with another model, "
                  "results will be silently wrong.")

        print(f"Loading embedding model: {model_name}"
              + (f"  (query prefix {self.query_prefix!r})" if self.query_prefix else ""))
        self.model = SentenceTransformer(model_name)

        print(f"Loading FAISS index from {index_path}")
        self.index = faiss.read_index(str(index_path))

        # This process also has torch loaded (SentenceTransformer). torch and
        # faiss each bundle their own OpenMP runtime, and heavy parallel FAISS
        # work (e.g. an exhaustive nprobe=nlist scan) can segfault the process
        # on macOS. Pin FAISS to ONE thread here so all in-process search/sweep
        # is crash-proof. The multi-threaded index BUILD runs separately in a
        # torch-free subprocess (build_index_cli.py), so it keeps full speed.
        faiss.omp_set_num_threads(1)

        # Detect index family so we know which knobs are tunable at search time.
        self.is_ivf = hasattr(self.index, "nprobe")
        self.is_hnsw = hasattr(self.index, "hnsw")
        self.index_type = type(self.index).__name__
        # Detect metric: inner product (cosine, on normalized vectors) vs L2.
        self.is_cosine = (self.index.metric_type == faiss.METRIC_INNER_PRODUCT)
        self.metric = "cosine" if self.is_cosine else "l2"

        # Apply the baked-in nprobe default (floor). See DEFAULT_NPROBE above.
        if self.is_ivf and self.index.nprobe < DEFAULT_NPROBE:
            self.index.nprobe = DEFAULT_NPROBE

        with open(metadata_path) as f:
            self.metadata = json.load(f)

        print(f"Loaded index with {len(self.metadata)} chunks from {len(set(m['file'] for m in self.metadata))} books")
        print(f"Index type: {self.index_type} (ivf={self.is_ivf}, hnsw={self.is_hnsw})")

    def get_index_info(self) -> Dict:
        """Report index type, vector count, and which params can be tuned live."""
        info = {
            "index_type": self.index_type,
            "metric": self.metric,
            "ntotal": int(self.index.ntotal),
            "tunable": [],
        }
        if self.is_ivf:
            info["nprobe"] = int(self.index.nprobe)
            info["nlist"] = int(getattr(self.index, "nlist", 0))
            info["tunable"].append("nprobe")
        if self.is_hnsw:
            info["ef_search"] = int(self.index.hnsw.efSearch)
            info["tunable"].append("ef_search")
        return info

    def set_search_params(self, nprobe: int = None, ef_search: int = None):
        """Apply live search-time tuning. No rebuild required."""
        if nprobe is not None and self.is_ivf:
            self.index.nprobe = int(nprobe)
        if ef_search is not None and self.is_hnsw:
            self.index.hnsw.efSearch = int(ef_search)

    def sweep(self, queries: List[str], values: List[int] = None, k: int = 10) -> Dict:
        """Measure recall + latency across the tunable param (nprobe for IVF,
        efSearch for HNSW). Recall is top-k overlap vs an exhaustive search of
        the SAME index (nprobe=nlist / very large efSearch), so 100% = exact.
        Encodes queries once, then only re-runs the cheap search per value."""
        import time
        if not (self.is_ivf or self.is_hnsw):
            return {"supported": False, "param": None, "points": []}

        # Defensive: keep FAISS single-threaded here. The reference pass scans
        # many/all clusters, and multi-threaded FAISS beside torch can segfault.
        faiss.omp_set_num_threads(1)

        _q = [self.query_prefix + q for q in queries] if self.query_prefix else queries
        emb = self.model.encode(_q, convert_to_numpy=True).astype("float32")
        if self.is_cosine:
            faiss.normalize_L2(emb)
        nq = len(queries)

        def recall_vs(ref, cur):
            return float(np.mean([len(set(ref[i]) & set(cur[i])) / k for i in range(nq)])) * 100

        if self.is_ivf:
            nlist = int(getattr(self.index, "nlist", 0)) or 1
            # Bound the "exhaustive" reference so the sweep stays fast even
            # single-threaded. 2048 clusters is effectively exact for recall.
            ref_nprobe = min(nlist, 2048)
            if not values:
                values = [v for v in [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048] if v <= ref_nprobe]
            orig = int(self.index.nprobe)
            self.index.nprobe = ref_nprobe                 # near-exhaustive reference
            _, ref = self.index.search(emb, k)
            points = []
            for v in values:
                self.index.nprobe = int(v)
                t0 = time.perf_counter(); _, cur = self.index.search(emb, k)
                dt = (time.perf_counter() - t0) * 1000.0
                points.append({"x": int(v), "recall": round(recall_vs(ref, cur), 1),
                               "latency_ms": round(dt / nq, 2)})
            self.index.nprobe = orig
            return {"supported": True, "param": "nprobe", "nlist": nlist, "points": points}

        # HNSW
        if not values:
            values = [8, 16, 32, 64, 128, 256, 512]
        orig = int(self.index.hnsw.efSearch)
        self.index.hnsw.efSearch = max(max(values), 1024)  # near-exhaustive reference
        _, ref = self.index.search(emb, k)
        points = []
        for v in values:
            self.index.hnsw.efSearch = int(v)
            t0 = time.perf_counter(); _, cur = self.index.search(emb, k)
            dt = (time.perf_counter() - t0) * 1000.0
            points.append({"x": int(v), "recall": round(recall_vs(ref, cur), 1),
                           "latency_ms": round(dt / nq, 2)})
        self.index.hnsw.efSearch = orig
        return {"supported": True, "param": "ef_search", "points": points}

    def search(self, query: str, k: int = 5,
               nprobe: int = None, ef_search: int = None) -> List[Dict]:
        """Search for similar passages, optionally overriding tuning params."""
        if nprobe is not None or ef_search is not None:
            self.set_search_params(nprobe=nprobe, ef_search=ef_search)

        # Encode query
        query_embedding = self.model.encode(
            [self.query_prefix + query], convert_to_numpy=True).astype("float32")
        # For cosine indexes, the query must be normalized the same way the
        # stored vectors were, so inner product equals cosine similarity.
        if self.is_cosine:
            faiss.normalize_L2(query_embedding)

        # Search index
        scores, indices = self.index.search(query_embedding, k)

        # Retrieve results
        results = []
        for i, idx in enumerate(indices[0]):
            if idx >= 0:
                meta = self.metadata[idx]
                score = float(scores[0][i])
                # IP score IS the cosine similarity; L2 needs the 1/(1+d) map.
                similarity = score if self.is_cosine else 1 / (1 + score)
                results.append({
                    "rank": i + 1,
                    "distance": score,
                    "similarity": similarity,
                    "file": meta["file"],
                    "title": meta["title"],
                    "chunk": meta["chunk_idx"],
                    "preview": meta["text_preview"],
                })

        return results

    def interactive_search(self):
        """Interactive search loop."""
        print("\n" + "=" * 70)
        print("Alexandria RAG - Semantic Search")
        print("=" * 70)
        print("Type your query and press Enter. Type 'quit' to exit.\n")

        while True:
            query = input("Query: ").strip()

            if query.lower() in ["quit", "exit", "q"]:
                break

            if not query:
                continue

            results = self.search(query, k=5)

            print(f"\nTop 5 results for: '{query}'")
            print("-" * 70)

            for result in results:
                print(f"\n[{result['rank']}] {result['title']}")
                print(f"    File: {result['file']}")
                print(f"    Chunk {result['chunk']} | Similarity: {result['similarity']:.2%}")
                print(f"    Preview: {result['preview']}")

            print("\n" + "=" * 70)

    def batch_search(self, queries: List[str], k: int = 5, output_file: str = None) -> List[Dict]:
        """Search multiple queries and optionally save results."""
        all_results = []

        for query in queries:
            results = self.search(query, k=k)
            all_results.append({
                "query": query,
                "results": results
            })

        if output_file:
            with open(output_file, "w") as f:
                json.dump(all_results, f, indent=2)
            print(f"Results saved to {output_file}")

        return all_results


def main():
    parser = argparse.ArgumentParser(description="Query Alexandria RAG")
    parser.add_argument("--index-dir", default=".", help="Directory containing index")
    parser.add_argument("--query", help="Single query (use for non-interactive mode)")
    parser.add_argument("--queries-file", help="JSON file with list of queries")
    parser.add_argument("--output", help="Output file for batch results")
    parser.add_argument("--k", type=int, default=5, help="Number of results to return")
    parser.add_argument("--model", default="all-MiniLM-L6-v2", help="SentenceTransformer model")

    args = parser.parse_args()

    # Initialize querier
    querier = RAGQuerier(index_dir=args.index_dir, model_name=args.model)

    # Mode: Single query
    if args.query:
        results = querier.search(args.query, k=args.k)
        print(f"\nTop {args.k} results for: '{args.query}'")
        print("=" * 70)
        for result in results:
            print(f"\n[{result['rank']}] {result['title']}")
            print(f"    File: {result['file']}")
            print(f"    Chunk {result['chunk']} | Similarity: {result['similarity']:.2%}")
            print(f"    Preview: {result['preview']}")

    # Mode: Batch queries from file
    elif args.queries_file:
        with open(args.queries_file) as f:
            queries = json.load(f)
        querier.batch_search(queries, k=args.k, output_file=args.output)

    # Mode: Interactive search
    else:
        querier.interactive_search()


if __name__ == "__main__":
    main()
```

### `index_books.py`

```python
#!/usr/bin/env python3
"""
Alexandria RAG Indexer
Extracts text from PDFs, generates embeddings, and builds a FAISS index.
By default, indexes PDF files only. Use --include-epub to also process EPUB files.
"""

import os
# ── Memory/thread safety (MUST run before numpy/torch/faiss import) ──────────
# The full-library embed crashed a 128 GB Mac twice: a single Python process hit
# 123 GB with load average 321. Two causes, both tamed here + in generate_embeddings:
#   1. MPS (Apple GPU) uses UNIFIED system RAM and its allocator accumulates
#      across the ~25k encode() calls of a full run unless the cache is flushed.
#   2. Unbounded thread fan-out (OpenMP/tokenizers) drove the load to 321.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
# GPU (MPS) is the DEFAULT again and is safe now that (a) the streaming embed
# never holds the matrix in RAM, (b) empty_cache runs every batch, (c) the web UI
# frees its index during a rebuild, (d) only one embed runs at a time (lockfile),
# and (e) an RSS watchdog aborts gracefully long before the machine can freeze.
# We deliberately do NOT set PYTORCH_MPS_*_WATERMARK_RATIO: setting the HIGH ratio
# below the default LOW ratio makes torch raise "invalid low watermark ratio" at
# model load (hit 2026-07). Memory is bounded by empty_cache + the watchdog, not
# by fighting the watermarks. Force CPU with ALEX_EMBED_DEVICE=cpu if ever needed.
import sys
import json
import logging
import argparse
import warnings
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np
from tqdm import tqdm
import pdfplumber
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
import faiss

warnings.filterwarnings("ignore")


# --------------------------------------------------------------------------- #
# Memory instrumentation — so a run TELLS us where RAM goes instead of us
# reading Activity Monitor tea leaves. _rss_gb() returns the process's current
# resident set in GB (psutil if present; falls back to resource peak).
# --------------------------------------------------------------------------- #
def _rss_gb() -> float:
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / 1e9
    except Exception:
        try:
            import resource
            m = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # macOS reports bytes; Linux reports kilobytes.
            return (m / 1e9) if sys.platform == "darwin" else (m / 1e6)
        except Exception:
            return -1.0


def _log_rss(phase: str) -> float:
    g = _rss_gb()
    if g >= 0:
        print(f"  [mem] {phase}: {g:.1f} GB RSS", flush=True)
    return g


# Files that triggered recoverable extraction issues (e.g. pdfminer's
# "Data-loss while decompressing corrupted data"). pdfminer logs those as bare
# warnings with NO filename, so we capture them per-file and record the path.
PROBLEM_PDFS = []  # list of (file_path, [messages])


class _PdfWarningCollector(logging.Handler):
    """Capture WARNING+ records emitted by pdfminer while one file is parsed."""
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def write_manifest(output_dir: str, metadata: list):
    """Record each indexed file's signature (mtime+size) and chunk count so a
    later --incremental run can detect which books changed."""
    from extract_text import _sig
    counts = {}
    for m in metadata:
        counts[m["file"]] = counts.get(m["file"], 0) + 1
    manifest = {}
    for fp, n in counts.items():
        try:
            manifest[fp] = {"sig": _sig(fp), "chunks": n}
        except OSError:
            manifest[fp] = {"sig": None, "chunks": n}
    (Path(output_dir) / "alexandria_manifest.json").write_text(json.dumps(manifest))
    print(f"✓ Manifest written ({len(manifest)} files)")


def write_problem_report(output_dir: str = "."):
    """Write the list of PDFs with recoverable extraction issues, if any."""
    if not PROBLEM_PDFS:
        return None
    out = Path(output_dir) / "problem_pdfs.txt"
    with open(out, "w") as f:
        f.write(f"# {len(PROBLEM_PDFS)} PDFs had recoverable extraction issues\n")
        f.write("# (text was still extracted where possible; consider replacing these)\n\n")
        for path, msgs in PROBLEM_PDFS:
            f.write(f"{path}\n    {'; '.join(sorted(set(msgs)))}\n")
    print(f"\n⚠ {len(PROBLEM_PDFS)} PDF(s) had recoverable issues — see {out}")
    return out

# Configuration
# NOTE: chunking counts whitespace WORDS, but all-MiniLM-L6-v2's tokenizer caps
# input at 256 SUBWORD tokens (~1.3 tokens/word). A 256-word chunk is ~330
# tokens, so the model would silently truncate the last ~25%. 200 words keeps
# each chunk at/under the model limit so the whole chunk actually gets embedded.
CHUNK_SIZE = 200  # words per chunk (kept under the 256-token model limit)

# Long-context models make the 200-word ceiling pointless: it exists only
# because MiniLM truncates at 256 subword tokens. 400 words (~520 tokens) fits
# any 512+ token model, keeps an argument intact instead of splitting it mid
# paragraph, and still localises a hit to roughly a page -- which matters when
# the result has to support a footnote. Overridable with ALEX_CHUNK_WORDS.
LONG_CONTEXT_CHUNK_SIZE = 400
LONG_CONTEXT_OVERLAP = 80


def prefixes_for(model_name: str) -> tuple:
    """(document prefix, query prefix). The e5 family is TRAINED with these; omit
    them and retrieval quality drops measurably. Both sides must agree, or the
    query lands in a different region of the space than the passages."""
    n = (model_name or "").lower()
    if "e5" in n:
        return "passage: ", "query: "
    return "", ""


def write_embedding_meta(output_dir, indexer):
    """Record WHICH model built this index, beside the index itself.

    Without this the querier defaults to all-MiniLM-L6-v2. multilingual-e5-small
    is also 384-dim, so querying an e5 index with MiniLM raises no dimension
    error -- it just returns quiet nonsense. This file is what prevents that."""
    meta = {
        "model": getattr(indexer, "model_name", None),
        "dim": indexer.embedding_dim,
        "doc_prefix": getattr(indexer, "doc_prefix", ""),
        "query_prefix": getattr(indexer, "query_prefix", ""),
        "max_seq_length": getattr(indexer.model, "max_seq_length", None),
        "chunk_words": chunk_params_for(indexer.model)[0],
    }
    (Path(output_dir) / "embedding_model.json").write_text(json.dumps(meta, indent=2))
    print(f"  recorded embedding model: {meta['model']} (dim {meta['dim']}, "
          f"prefix {meta['doc_prefix']!r})", flush=True)


def chunk_params_for(model) -> tuple:
    """Pick (words, overlap) from the loaded model's real token limit, so that
    switching models in the UI cannot silently mis-size chunks in either
    direction."""
    override = os.environ.get("ALEX_CHUNK_WORDS")
    if override:
        w = int(override)
        return w, max(1, int(w * 0.2))
    limit = getattr(model, "max_seq_length", 0) or 0
    # ~1.4 subword tokens per whitespace word; leave headroom so a chunk's tail
    # is never silently truncated. A 512-token model takes ~350 words, not the
    # 400 a coarse threshold would have handed it.
    if limit >= 2048:
        return LONG_CONTEXT_CHUNK_SIZE, LONG_CONTEXT_OVERLAP
    if limit >= 512:
        w = int(limit / 1.45)
        return w, max(1, int(w * 0.2))
    return CHUNK_SIZE, CHUNK_OVERLAP
CHUNK_OVERLAP = 40  # words of overlap between chunks
MODEL_NAME = "all-MiniLM-L6-v2"  # Fast, effective, 384-dim embeddings
BATCH_SIZE = 128  # Batch size for embedding generation
DUPLICATE_SIMILARITY_THRESHOLD = 0.95  # Threshold for flagging duplicates


class DuplicateDetector:
    """Detect duplicate documents using embedding similarity only."""

    def __init__(self, similarity_threshold: float = DUPLICATE_SIMILARITY_THRESHOLD):
        self.threshold = similarity_threshold
        self.documents = []  # List of (file_path, title, embedding)
        self.suspected_duplicates = []

    def register_document(self, file_path: str, title: str,
                         embedding_signature: Optional[np.ndarray] = None) -> Optional[Dict]:
        """
        Register a document and check for duplicates against previously indexed documents.

        Returns:
            Dict with duplicate info if suspected duplicate found, None otherwise.
        """
        if embedding_signature is None:
            return None

        # Check against all previously registered documents
        duplicate_found = None
        for prev_file, prev_title, prev_embedding in self.documents:
            similarity = self._cosine_similarity(embedding_signature, prev_embedding)

            if similarity >= self.threshold:
                duplicate_found = {
                    'new_file': file_path,
                    'new_title': title,
                    'existing_file': prev_file,
                    'existing_title': prev_title,
                    'similarity': float(similarity),
                }
                self.suspected_duplicates.append(duplicate_found)
                break

        # Register this document
        self.documents.append((file_path, title, embedding_signature))

        return duplicate_found

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def save_report(self, output_path: str):
        """Save duplicate detection report."""
        report = {
            'summary': {
                'total_documents': len(self.documents),
                'suspected_duplicates_count': len(self.suspected_duplicates),
                'similarity_threshold_used': self.threshold,
            },
            'suspected_duplicates': self.suspected_duplicates,
        }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n✓ Duplicate detection report saved to {output_file}")


class BookExtractor:
    """Extract text from PDF and EPUB files."""

    @staticmethod
    def extract_pdf(file_path: str) -> str:
        """Extract text from PDF.

        pdfminer logs corrupted-stream warnings (e.g. "Data-loss while
        decompressing corrupted data") without naming the file. We attach a
        temporary handler to the pdfminer logger so we can attribute any such
        warning to THIS file and record it for the end-of-run report.
        """
        text = []
        pdf_logger = logging.getLogger("pdfminer")
        collector = _PdfWarningCollector()
        prev_level = pdf_logger.level
        pdf_logger.setLevel(logging.WARNING)
        pdf_logger.addHandler(collector)
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text.append(page_text)
            if collector.messages:
                uniq = sorted(set(collector.messages))
                print(f"  ⚠ Recoverable issue in {file_path}: {'; '.join(uniq)}")
                PROBLEM_PDFS.append((file_path, collector.messages))
            return "\n".join(text)
        except Exception as e:
            print(f"  ⚠ Error extracting PDF {file_path}: {e}")
            PROBLEM_PDFS.append((file_path, [str(e)]))
            return ""
        finally:
            pdf_logger.removeHandler(collector)
            pdf_logger.setLevel(prev_level)

    @staticmethod
    def extract_epub(file_path: str) -> str:
        """Extract text from EPUB."""
        text = []
        try:
            book = epub.read_epub(file_path)
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    try:
                        soup = BeautifulSoup(item.get_content(), "html.parser")
                        content = soup.get_text(separator=" ", strip=True)
                        if content:
                            text.append(content)
                    except Exception:
                        continue
            return "\n".join(text)
        except Exception as e:
            print(f"  ⚠ Error extracting EPUB {file_path}: {e}")
            return ""


class TextChunker:
    """Split text into overlapping chunks."""

    @staticmethod
    def tokenize_simple(text: str) -> List[str]:
        """Simple whitespace tokenization."""
        return text.split()

    @classmethod
    def chunk_text(cls, text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
        """Split text into chunks with overlap."""
        tokens = cls.tokenize_simple(text)
        chunks = []

        for i in range(0, len(tokens), chunk_size - overlap):
            chunk_tokens = tokens[i : i + chunk_size]
            if chunk_tokens:
                chunks.append(" ".join(chunk_tokens))

        return chunks


class RAGIndexer:
    """Build FAISS index from book collection."""

    def __init__(self, model_name: str = MODEL_NAME, batch_size: int = BATCH_SIZE,
                 detect_duplicates: bool = False):
        """Initialize embedder and FAISS index."""
        print(f"Loading embedding model: {model_name}")
        # Device: DEFAULT TO MPS (Apple GPU) for speed. The earlier 25 GB climb
        # was MPS competing with a stale index in the web UI (~8 GB) + duplicate
        # MCP servers (~16 GB), not MPS alone — a single streaming embed is well
        # within 48 GB now. If MPS isn't available (non-Mac, older torch) we fall
        # back to CPU automatically. Force CPU with ALEX_EMBED_DEVICE=cpu.
        requested = os.environ.get("ALEX_EMBED_DEVICE", "mps").lower()
        device = requested
        if requested == "mps":
            try:
                import torch
                if not (hasattr(torch.backends, "mps") and
                        torch.backends.mps.is_available()):
                    print("  ⚠ MPS not available on this machine — using CPU.")
                    device = "cpu"
            except Exception:
                device = "cpu"
        self.model = SentenceTransformer(model_name, device=device)
        self.model_name = model_name
        self.doc_prefix, self.query_prefix = prefixes_for(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        self.batch_size = batch_size

        # BATCH_SIZE=128 was tuned for MiniLM: 22M params, 384 dims, 256-token
        # ceiling. A 568M-param 1024-dim model at that batch size drove a 48 GB
        # machine to 59 GB resident and 39 GB of swap -- 11 s/batch of pure
        # paging, a 40-hour ETA for work that takes well under an hour resident.
        # Scale the batch to the model, and cap the sequence window to what we
        # actually feed it (400-word chunks are ~520 tokens; 8192 is dead weight).
        try:
            if self.embedding_dim >= 1024:
                self.batch_size = int(os.environ.get("ALEX_BATCH_SIZE", "16"))
                if getattr(self.model, "max_seq_length", 0) > 1024:
                    self.model.max_seq_length = int(
                        os.environ.get("ALEX_MAX_SEQ", "1024"))
            elif os.environ.get("ALEX_BATCH_SIZE"):
                self.batch_size = int(os.environ["ALEX_BATCH_SIZE"])
        except Exception:
            pass
        print(f"  batch_size={self.batch_size}  dim={self.embedding_dim}  "
              f"max_seq={getattr(self.model, 'max_seq_length', '?')}", flush=True)

        # Cap torch's intra-op threads so embedding can't spawn a thread storm
        # (the crash showed load average 321). Safe if torch isn't present.
        try:
            import torch
            torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
        except Exception:
            pass

        if hasattr(self.model, 'device'):
            print(f"Using device: {self.model.device}")

        # Index will be created in build_index() after we have embeddings
        self.index = None
        self.metadata = []
        self.chunks = []
        self.document_file_paths = []  # Track which document each chunk belongs to

        # Initialize duplicate detector if enabled
        self.duplicate_detector = DuplicateDetector() if detect_duplicates else None

    def add_document(self, file_path: str, text: str, metadata: Dict) -> int:
        """Add document chunks to index."""
        if not text.strip():
            return 0

        # Guard against ONE pathological document exploding memory. A malformed
        # PDF can extract to GIGABYTES of garbage text; chunking that builds a
        # word list + chunk list large enough to OOM the machine (observed: a
        # single added PDF drove the process to 37 GB at 1% progress). ~50 MB of
        # text is already a ~10,000-page book — beyond that, truncate and warn.
        max_chars = int(os.environ.get("ALEX_MAX_DOC_CHARS", str(50_000_000)))
        if len(text) > max_chars:
            print(f"  ⚠ {Path(file_path).name}: {len(text)/1e6:.0f} MB of extracted "
                  f"text — truncating to {max_chars // 10**6} MB (malformed PDF?)",
                  flush=True)
            text = text[:max_chars]

        _cw, _co = chunk_params_for(getattr(self, "model", None))
        chunks = TextChunker.chunk_text(text, chunk_size=_cw, overlap=_co)
        for i, chunk in enumerate(chunks):
            self.chunks.append(chunk)
            self.document_file_paths.append(file_path)
            self.metadata.append({
                "file": metadata["file"],
                "title": metadata["title"],
                "chunk_idx": i,
                "total_chunks": len(chunks),
                "text_preview": chunk[:200] + "..." if len(chunk) > 200 else chunk,
            })

        return len(chunks)

    def generate_embeddings(self, show_progress: bool = True) -> np.ndarray:
        """STAGE 1 (uses torch via SentenceTransformer): embed all chunks.

        Returns a contiguous float32 matrix. This is the only stage that needs
        torch, so it is kept separate from FAISS index construction.
        """
        if not self.chunks:
            print("No chunks to embed.")
            return np.empty((0, self.embedding_dim), dtype="float32")

        import gc
        n = len(self.chunks)
        print(f"\nGenerating embeddings for {n} chunks...")

        # Preallocate ONE contiguous output matrix and fill it in place. The old
        # code accumulated a list, then np.vstack, then np.ascontiguousarray —
        # THREE full copies of the matrix resident at once. For 3.3M chunks that
        # is ~15 GB of avoidable churn on top of the real killer below.
        out = np.empty((n, self.embedding_dim), dtype="float32")

        # Is MPS (Apple GPU, unified RAM) in play? If so we must release its
        # allocator cache each batch, or it hoards every batch it ever saw and
        # the process climbs to 100 GB+ over a full run.
        mps_flush = None
        try:
            import torch
            if getattr(self.model, "device", None) is not None and \
               str(self.model.device).startswith("mps") and \
               hasattr(getattr(torch, "mps", None), "empty_cache"):
                mps_flush = torch.mps.empty_cache
        except Exception:
            pass

        iterator = tqdm(range(0, n, self.batch_size)) if show_progress else range(0, n, self.batch_size)
        for step, i in enumerate(iterator):
            batch = self.chunks[i : i + self.batch_size]
            # normalize_embeddings=True → unit vectors, so inner product == cosine.
            _b = [self.doc_prefix + c for c in batch] if self.doc_prefix else batch
            be = self.model.encode(
                _b, convert_to_numpy=True, show_progress_bar=False,
                normalize_embeddings=True)
            out[i : i + len(batch)] = be
            del be
            if mps_flush is not None:
                mps_flush()                      # hand memory back every batch
            if step % 200 == 0:
                gc.collect()

        return out

    def embed_and_save(self, output_dir: str = ".", show_progress: bool = True):
        """STAGE 1, MEMORY-BOUNDED: embed straight into a memory-mapped .npy on
        disk. Unlike generate_embeddings(), the full embedding matrix is NEVER
        resident in RAM — only one batch at a time. Essential on <=64 GB Macs,
        where a 3M-chunk matrix (~5 GB) plus the model plus MPS churn is enough
        to tip the machine into swap. Writes metadata + returns the .npy path."""
        import gc
        from numpy.lib.format import open_memmap
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        emb_path = output_dir / "alexandria_embeddings.npy"
        meta_path = output_dir / "alexandria_metadata.json"

        n = len(self.chunks)
        if n == 0:
            print("No chunks to embed.")
            np.save(emb_path, np.empty((0, self.embedding_dim), dtype="float32"))
            meta_path.write_text(json.dumps(self.metadata))
            return emb_path

        print(f"\nStreaming embeddings for {n} chunks → {emb_path.name} (memory-bounded)...")
        _log_rss("embed start")
        mm = open_memmap(emb_path, mode="w+", dtype="float32",
                         shape=(n, self.embedding_dim))

        # MPS memory management: empty_cache hands each batch's buffers back to
        # the allocator; synchronize forces the GPU queue to drain so nothing
        # lingers. Both are no-ops on CPU.
        mps_flush = None
        mps_sync = None
        try:
            import torch
            if getattr(self.model, "device", None) is not None and \
               str(self.model.device).startswith("mps"):
                if hasattr(getattr(torch, "mps", None), "empty_cache"):
                    mps_flush = torch.mps.empty_cache
                if hasattr(getattr(torch, "mps", None), "synchronize"):
                    mps_sync = torch.mps.synchronize
        except Exception:
            pass

        # RSS watchdog: hard insurance so a runaway (MPS or otherwise) can NEVER
        # freeze the Mac again. Warn at ALEX_RSS_WARN_GB, abort gracefully at
        # ALEX_RSS_ABORT_GB. Defaults sized for a 48 GB machine; a clean MPS embed
        # peaks well under the warn line, so these should never trip in practice.
        warn_gb = float(os.environ.get("ALEX_RSS_WARN_GB", "30"))
        abort_gb = float(os.environ.get("ALEX_RSS_ABORT_GB", "42"))
        warned = False

        it = tqdm(range(0, n, self.batch_size)) if show_progress else range(0, n, self.batch_size)
        for step, i in enumerate(it):
            batch = self.chunks[i : i + self.batch_size]
            _b = [self.doc_prefix + c for c in batch] if self.doc_prefix else batch
            be = self.model.encode(_b, convert_to_numpy=True,
                                   show_progress_bar=False, normalize_embeddings=True)
            mm[i : i + len(batch)] = be           # write straight to disk
            del be
            if mps_flush is not None:
                mps_flush()
            if step % 50 == 0 and mps_sync is not None:
                mps_sync()                         # drain the GPU queue
            if step % 100 == 0:
                mm.flush(); gc.collect()
            # Emit a parseable progress line the GUI can read, so the bar MOVES
            # during the long embed instead of sitting at the cached-extraction
            # number (which looks frozen and tempts a fatal second click).
            if step % 40 == 0:
                done = min(i + self.batch_size, n)
                print(f"  embedded {done:,}/{n:,} chunks", flush=True)
                g = _log_rss(f"embed {done:,}/{n:,}")
                if g >= 0 and g >= warn_gb and not warned:
                    print(f"  ⚠ RSS {g:.1f} GB is above the {warn_gb:.0f} GB warn line "
                          f"— watching closely.", flush=True)
                    warned = True
                if g >= 0 and g >= abort_gb:
                    mm.flush(); del mm; gc.collect()
                    raise MemoryError(
                        f"RSS {g:.1f} GB exceeded ALEX_RSS_ABORT_GB={abort_gb:.0f} GB; "
                        f"aborting the embed to protect the machine. The partial "
                        f".npy was flushed; rerun (or set ALEX_EMBED_DEVICE=cpu).")

        mm.flush()
        del mm                                     # close the memmap
        meta_path.write_text(json.dumps(self.metadata))
        print(f"✓ Embeddings streamed to {emb_path} ({n} x {self.embedding_dim})")
        print(f"✓ Metadata saved to {meta_path}")
        return emb_path

    def save_embeddings(self, embeddings: np.ndarray, output_dir: str = "."):
        """Persist the embedding matrix + metadata so a SEPARATE, torch-free
        process (build_index_cli.py) can construct any FAISS index from them.
        This is what avoids the dual-OpenMP segfault on macOS."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        emb_path = output_dir / "alexandria_embeddings.npy"
        metadata_path = output_dir / "alexandria_metadata.json"
        np.save(emb_path, embeddings)
        with open(metadata_path, "w") as f:
            json.dump(self.metadata, f, indent=2)
        print(f"✓ Embeddings saved to {emb_path} ({embeddings.shape[0]} x {embeddings.shape[1]})")
        print(f"✓ Metadata saved to {metadata_path}")

    def build_index(self, show_progress: bool = True) -> Tuple:
        """Generate embeddings and build a Flat FAISS index (in-process).

        NOTE: only the Flat index is safe to build in this (torch-loaded)
        process. For IVFFlat / IVFPQ / HNSW, save embeddings with
        save_embeddings() and build them with build_index_cli.py, which runs
        torch-free to avoid the dual-OpenMP segfault.
        """
        if not self.chunks:
            print("No chunks to index.")
            return self.index, self.metadata

        embeddings = self.generate_embeddings(show_progress=show_progress)

        # Build Flat index (reliable, no parallel construction → no segfault).
        # IndexFlatIP + normalized embeddings = cosine similarity search.
        print(f"\nBuilding Flat (cosine/IP) index for {embeddings.shape[0]} embeddings...")
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.index.add(embeddings)
        print(f"✓ Index built successfully ({embeddings.shape[0]} vectors)")

        # Compute document-level embedding signatures for duplicate detection
        if self.duplicate_detector:
            print("\nComputing document embeddings for duplicate detection...")
            self._compute_document_signatures(embeddings)

        return self.index, self.metadata

    def _compute_document_signatures(self, all_embeddings: np.ndarray):
        """Compute document embeddings and check for duplicates."""
        # Build mapping of file_path to chunk indices
        file_to_chunks = {}
        for i, file_path in enumerate(self.document_file_paths):
            if file_path not in file_to_chunks:
                file_to_chunks[file_path] = []
            file_to_chunks[file_path].append(i)

        # Process each unique document
        processed_files = set()
        for file_path, chunk_indices in file_to_chunks.items():
            if file_path in processed_files:
                continue
            processed_files.add(file_path)

            # Get embeddings for this document's chunks
            doc_embeddings = all_embeddings[chunk_indices]

            # Compute average embedding
            avg_embedding = np.mean(doc_embeddings, axis=0).astype('float32')

            # Find the title for this file
            title = None
            for m in self.metadata:
                if m['file'] == file_path:
                    title = m['title']
                    break

            if title:
                # Register with duplicate detector
                duplicate_found = self.duplicate_detector.register_document(
                    file_path=file_path,
                    title=title,
                    embedding_signature=avg_embedding
                )
                if duplicate_found:
                    print(f"  ⚠ Potential duplicate:")
                    print(f"    New: {Path(file_path).name}")
                    print(f"    Existing: {Path(duplicate_found['existing_file']).name}")
                    print(f"    Similarity: {duplicate_found['similarity']:.1%}")

    def save(self, output_dir: str = "."):
        """Save index and metadata."""
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)

        index_path = output_dir / "alexandria.index"
        metadata_path = output_dir / "alexandria_metadata.json"

        faiss.write_index(self.index, str(index_path))
        with open(metadata_path, "w") as f:
            json.dump(self.metadata, f, indent=2)

        print(f"\n✓ Index saved to {index_path}")
        print(f"✓ Metadata saved to {metadata_path}")

        # Save duplicate detection report if detector is enabled
        if self.duplicate_detector:
            report_path = output_dir / "duplicate_detection_report.json"
            self.duplicate_detector.save_report(str(report_path))


def scan_books(directory: str, pdf_only: bool = True) -> List[Tuple[str, str]]:
    """Scan directory for book files.

    Args:
        directory: Path to scan
        pdf_only: If True, only index PDF files. If False, also include EPUB files.
    """
    books = []
    directory = Path(directory)

    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return books

    # Determine which file types to scan
    if pdf_only:
        extensions = ["*.pdf", "*.PDF"]
        file_type_desc = "PDF files"
    else:
        extensions = ["*.pdf", "*.PDF", "*.epub", "*.EPUB"]
        file_type_desc = "PDF and EPUB files"

    print(f"Scanning {directory} for {file_type_desc}...")

    # Working trees that live under the library root but are NOT library books.
    # Without this, rglob sweeps in the pre-optimisation quarantine copies, and
    # every book that was repaired or OCR'd gets indexed twice -- once as the
    # searchable version and once as its damaged predecessor.
    SKIP_DIR_NAMES = {
        "_Optimization", "_retired", "_originals_pre_optimization",
        ".ocrwork", ".textcache", "_gaveston_page_scans",
    }

    # Files whose text layer is unreadable glyph codes. Indexing them injects
    # nonsense tokens that look like real content to the retriever.
    excluded = set()
    _cands = [Path(__file__).resolve().parent / "index_exclude.txt",
              directory / "_Optimization" / "index_exclude.txt",
              directory / "PDF" / "_Optimization" / "index_exclude.txt",
              directory.parent / "PDF" / "_Optimization" / "index_exclude.txt"]
    for cand in _cands:
        if cand.exists():
            for line in cand.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    excluded.add(os.path.realpath(line))
            print(f"  exclude list: {cand} ({len(excluded)} file(s))")

    skipped_dirs = skipped_excluded = 0
    seen = set()
    for ext in extensions:
        for file_path in directory.rglob(ext):
            if SKIP_DIR_NAMES.intersection(file_path.parts):
                skipped_dirs += 1
                continue
            real = os.path.realpath(str(file_path))
            if real in excluded:
                skipped_excluded += 1
                continue
            if real in seen:          # same file reached by two paths
                continue
            seen.add(real)
            books.append((str(file_path), file_path.stem))

    if skipped_dirs:
        print(f"  skipped {skipped_dirs} file(s) in working/quarantine directories")
    if skipped_excluded:
        print(f"  skipped {skipped_excluded} file(s) on the exclude list")
    print(f"  {len(books)} book(s) to index")

    return books


def run_incremental(args, cache_dir, dry_run=False):
    """Update the index in place: re-embed only added/changed books, drop removed
    ones, and rebuild the FAISS index keeping its tuned parameters.

    dry_run=True: report health + the pending diff and EXIT without embedding."""
    import subprocess, gc
    import faiss
    from extract_text import _sig, read_cached_text, is_cached, extract_one

    out = Path(args.output)
    index_path = out / "alexandria.index"
    meta_path = out / "alexandria_metadata.json"
    if not index_path.exists() or not meta_path.exists():
        print("No existing index/metadata found — run a full index first.")
        return 1

    faiss.omp_set_num_threads(1)  # safe in this torch-loaded process

    with open(meta_path) as f:
        metadata = json.load(f)
    emb_path = out / "alexandria_embeddings.npy"
    forced = set()
    if emb_path.exists():
        # Common path: the streamed .npy exists — memmap it (nothing resident) and
        # DON'T load the 4.7 GB FAISS index at all; we rebuild it from the .npy.
        existing = np.load(emb_path, mmap_mode="r")
    else:
        # Fallback only: no .npy on disk, so reconstruct exact vectors from the
        # index, then free the index immediately (it's ~4.7 GB and unused after).
        index = faiss.read_index(str(index_path))
        try:
            index.make_direct_map()
        except Exception:
            pass
        existing = np.ascontiguousarray(index.reconstruct_n(0, index.ntotal), dtype="float32")
        del index
        gc.collect()
    if len(metadata) != existing.shape[0]:
        if len(metadata) > existing.shape[0]:
            # Self-heal: tail metadata rows were written without vectors
            # (an extraction ran without the embedding stage). Drop the tail
            # rows and force their files through re-embedding.
            tail = metadata[existing.shape[0]:]
            forced = {m["file"] for m in tail}
            print(f"⚠ self-heal: {len(tail)} metadata rows have no vectors "
                  f"({len(forced)} file(s)) — re-embedding them.")
            metadata = metadata[:existing.shape[0]]
        else:
            print(f"⚠ vectors ({existing.shape[0]}) exceed metadata "
                  f"({len(metadata)}) — cannot self-heal; do a full re-index.")
            return 1

    # Diff disk against what's indexed
    books = scan_books(args.input, pdf_only=not args.include_epub)
    on_disk = {fp for fp, _ in books}
    titles = {fp: t for fp, t in books}
    indexed = {m["file"] for m in metadata}

    manifest_path = out / "alexandria_manifest.json"
    old_manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    added = on_disk - indexed
    removed = indexed - on_disk
    changed = set()
    for fp in (on_disk & indexed):
        prev = old_manifest.get(fp, {}).get("sig")
        try:
            if prev is not None and prev != _sig(fp):
                changed.add(fp)
        except OSError:
            pass
    reprocess = added | changed | forced
    drop = removed | changed | forced

    # ── --dry-run: health + pending-diff report, no embedding ──────────────
    if dry_run:
        lock = out / ".indexing.lock"
        lock_note = "absent (clear)"
        if lock.exists():
            try:
                holder = int((lock.read_text().strip() or "0"))
            except Exception:
                holder = 0
            lock_note = (f"PRESENT, held by LIVE pid {holder}" if _pid_alive(holder)
                         else f"PRESENT but STALE (pid {holder} gone) — delete: rm '{lock}'")
        print("\n=== incremental dry-run ===")
        print(f"  metadata rows      : {len(metadata):,}")
        print(f"  embedding vectors  : {existing.shape[0]:,}  "
              f"({'.npy on disk' if emb_path.exists() else 'reconstructed from index'})")
        print(f"  alignment          : {'OK' if len(metadata) == existing.shape[0] else 'MISMATCH'}"
              + ("" if len(metadata) == existing.shape[0] else "  ← would block the rebuild"))
        print(f"  manifest present   : {'yes' if manifest_path.exists() else 'NO (changed-file detection disabled until next full build)'}")
        print(f"  indexing lock      : {lock_note}")
        print(f"  books on disk      : {len(on_disk):,}")
        print(f"  → would ADD        : {len(added):,}")
        print(f"  → would re-embed CHANGED: {len(changed):,}")
        print(f"  → would REMOVE     : {len(removed):,}")
        if forced:
            print(f"  → self-heal re-embed: {len(forced):,} file(s) whose metadata had no vectors")
        for label, s in (("add", added), ("changed", changed), ("remove", removed)):
            for fp in list(sorted(s))[:5]:
                print(f"      [{label}] {fp}")
        verdict = ("nothing to do — index is up to date" if not reprocess and not removed
                   else "healthy — a real run would process the above")
        if len(metadata) != existing.shape[0] and not forced:
            verdict = "BLOCKED — vector/metadata mismatch; run a full rebuild"
        print(f"  VERDICT: {verdict}")
        print("=== end dry-run (nothing was embedded) ===\n")
        return 0

    if not reprocess and not removed:
        print("✓ Index already up to date — nothing added, changed or removed.")
        return 0
    print(f"Incremental update: +{len(added)} new, ~{len(changed)} changed, -{len(removed)} removed")

    # Keep vectors/metadata for files we're not dropping
    keep_mask = np.fromiter((m["file"] not in drop for m in metadata), dtype=bool, count=len(metadata))
    keep_emb = existing[keep_mask]
    keep_meta = [m for m, k in zip(metadata, keep_mask) if k]

    # Embed only the reprocess files
    add_emb = np.empty((0, existing.shape[1]), dtype="float32")
    add_meta = []
    if reprocess:
        indexer = RAGIndexer(model_name=args.model)
        # Extract ONLY the new/changed books (inline, one at a time — a handful,
        # so no parallel worker swarm that could exhaust memory). Cache them.
        for fp in sorted(reprocess):
            if not is_cached(cache_dir, fp):
                extract_one((fp, cache_dir, True))  # extracts + writes cache
            text = read_cached_text(cache_dir, fp)
            if text and text.strip():
                indexer.add_document(fp, text, {"file": fp, "title": titles.get(fp, Path(fp).stem)})
        if indexer.chunks:
            add_emb = indexer.generate_embeddings()
            add_meta = indexer.metadata

    # Concatenate kept + newly-embedded vectors. np.vstack already returns a
    # contiguous C-ordered float32 array (both inputs are float32), and fancy
    # indexing (existing[keep_mask]) is contiguous too — so the old extra
    # np.ascontiguousarray() was a needless third full copy of a ~5 GB matrix.
    if add_emb.shape[0]:
        new_emb = np.vstack([keep_emb, add_emb])
        del keep_emb
        gc.collect()
    else:
        new_emb = np.ascontiguousarray(keep_emb, dtype="float32")
    new_meta = keep_meta + add_meta

    np.save(out / "alexandria_embeddings.npy", new_emb)
    total_rows = new_emb.shape[0]
    del new_emb                        # free ~5 GB before the build subprocess
    gc.collect()
    with open(meta_path, "w") as f:
        json.dump(new_meta, f)
    write_manifest(out, new_meta)
    print(f"✓ Updated: {total_rows} chunks total "
          f"({len(keep_meta)} kept, {len(add_meta)} newly embedded)")

    # Rebuild the FAISS index torch-free, preserving the tuned parameters
    params = json.loads((out / "index_params.json").read_text()) if (out / "index_params.json").exists() else {}
    bcmd = [sys.executable, str(Path(__file__).parent / "build_index_cli.py"),
            "--index-dir", str(out),
            "--index-type", params.get("index_type", "ivfflat"),
            "--metric", params.get("metric", "ip"),
            "--from-npy", str(out / "alexandria_embeddings.npy"),
            "--nlist", str(params.get("nlist", 1024)),
            "--nprobe", str(params.get("nprobe", 128))]
    print("Rebuilding index (torch-free, preserving tuned params)...")
    return subprocess.call(bcmd)


_LOCK_PATH = None


def _pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True          # exists but owned by another user → treat as alive


def _acquire_index_lock(index_dir):
    """Create index_dir/.indexing.lock unless a LIVE process already holds it.
    Returns True on success. Guards CLI and GUI alike (the GUI shells out to
    this same script), so only one embed can run per index at a time."""
    global _LOCK_PATH
    import atexit
    lock = Path(index_dir) / ".indexing.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        # O_CREAT|O_EXCL is ATOMIC: exactly one process can create the file. Two
        # embeds spawned milliseconds apart can no longer both "win" — the loser
        # gets FileExistsError. (The old exists()-then-write() raced and let both
        # through; that is what put two embeds on a 48 GB Mac.) We deliberately do
        # NOT auto-reclaim stale locks — that reintroduces a delete/create race.
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        _LOCK_PATH = lock
        atexit.register(_release_index_lock)
        return True
    except FileExistsError:
        try:
            holder = int((lock.read_text().strip() or "0"))
        except Exception:
            holder = 0
        if _pid_alive(holder):
            print(f"\n⚠ Another indexing run is already active (PID {holder}).")
            print("  Refusing to start a second — two concurrent embeds exhaust RAM.")
        else:
            print(f"\n⚠ A stale lock from a hard-killed run is present (PID {holder}, gone).")
            print(f"  Delete it, then retry:\n    rm '{lock}'")
        return False


def _release_index_lock():
    """Remove the lock, but only if it is still OURS (never delete a live
    successor's lock)."""
    global _LOCK_PATH
    try:
        if _LOCK_PATH and _LOCK_PATH.exists() and \
           _LOCK_PATH.read_text().strip() == str(os.getpid()):
            _LOCK_PATH.unlink()
    except Exception:
        pass
    _LOCK_PATH = None


def main():
    parser = argparse.ArgumentParser(description="Build FAISS index from book collection")
    parser.add_argument("--input", required=True, help="Directory containing books")
    parser.add_argument("--output", default=".", help="Output directory for index")
    parser.add_argument("--model", default=MODEL_NAME, help="SentenceTransformer model name")
    parser.add_argument("--include-epub", action="store_true", default=False,
                        help="Include EPUB files in addition to PDFs (default: PDFs only)")
    parser.add_argument("--detect-duplicates", action="store_true", default=False,
                        help="Enable duplicate detection during indexing (generates detailed report)")
    parser.add_argument("--similarity-threshold", type=float, default=DUPLICATE_SIMILARITY_THRESHOLD,
                        help=f"Similarity threshold for duplicate detection (default: {DUPLICATE_SIMILARITY_THRESHOLD})")
    parser.add_argument("--embeddings-only", action="store_true", default=False,
                        help="STAGE 1: extract + embed + save .npy and metadata, then EXIT "
                             "(no FAISS index built). Build the index afterward with "
                             "build_index_cli.py in a separate torch-free process.")
    parser.add_argument("--scan-only", action="store_true", default=False,
                        help="Just check every PDF for corruption (fast, parallel, no "
                             "embedding) and write problem_pdfs.txt, then EXIT. Delegates "
                             "to the torch-free scan_pdfs.py.")
    parser.add_argument("--cache-dir", default=None,
                        help="Where extracted text is cached (default: <output>/text_cache). "
                             "Unchanged books are read from here instead of re-extracted.")
    parser.add_argument("--workers", type=int, default=None,
                        help="Parallel extraction workers (default: CPU count - 1).")
    parser.add_argument("--no-cache", action="store_true", default=False,
                        help="Ignore the text cache and re-extract every book.")
    parser.add_argument("--no-parallel-extract", action="store_true", default=False,
                        help="Skip the parallel pre-extraction pass; extract inline (slow).")
    parser.add_argument("--incremental", action="store_true", default=False,
                        help="Only process books that were ADDED, CHANGED or REMOVED since "
                             "the last index, re-embedding just those, then rebuild the index "
                             "(keeping its tuned nlist/nprobe/metric). Fast for small updates.")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="With --incremental: report health (manifest/.npy present, "
                             "vector↔metadata alignment, stale lock) and exactly what WOULD be "
                             "added/changed/removed, then EXIT without embedding. Diagnostic only.")

    args = parser.parse_args()
    cache_dir = args.cache_dir or str(Path(args.output) / "text_cache")

    if args.scan_only:
        # Delegate to the standalone torch-free scanner so worker processes stay
        # light (no torch/faiss) and fast. No lock — it doesn't embed.
        import subprocess
        script = Path(__file__).parent / "scan_pdfs.py"
        cmd = [sys.executable, str(script), "--input", args.input, "--output", args.output]
        return subprocess.call(cmd)

    # --dry-run diagnostic: read-only, embeds nothing, so it takes NO lock (and
    # reports whether a lock is present as part of its health check).
    if args.incremental and args.dry_run:
        return run_incremental(args, cache_dir, dry_run=True)

    # Cross-process lock: refuse to start if another embed (CLI *or* GUI) is
    # already running against this index dir. Two concurrent embeds OOM a 48 GB
    # Mac (observed: two 25 GB Python processes). Stale locks (from a hard kill)
    # are detected via PID liveness and overwritten.
    if not _acquire_index_lock(args.output):
        return 1

    if args.incremental:
        return run_incremental(args, cache_dir)

    # Scan for books (PDF-only by default)
    books = scan_books(args.input, pdf_only=not args.include_epub)

    if not books:
        if not args.include_epub:
            print("No PDF files found in the specified directory.")
        else:
            print("No PDF or EPUB files found.")
        return

    print(f"Found {len(books)} books")

    # Initialize indexer with duplicate detection if requested
    indexer = RAGIndexer(model_name=args.model, detect_duplicates=args.detect_duplicates)

    # --- Parallel pre-extraction (torch-free subprocess) -------------------
    # Extraction is the slow phase. Run it across all CPU cores in a separate
    # torch-free process that caches each book's text to disk. Unchanged books
    # are reused from cache, so repeat runs skip extraction almost entirely.
    if not args.no_parallel_extract:
        import subprocess
        ex = Path(__file__).parent / "extract_text.py"
        cmd = [sys.executable, str(ex), "--input", args.input,
               "--cache-dir", cache_dir, "--output", args.output]
        if args.include_epub:
            cmd.append("--include-epub")
        if args.no_cache:
            cmd.append("--no-cache")
        if args.workers:
            cmd += ["--workers", str(args.workers)]
        print("\nPre-extracting text (parallel, cached)...")
        rc = subprocess.call(cmd)
        if rc != 0:
            print("⚠ Parallel extraction returned non-zero; falling back to inline.")

    from extract_text import read_cached_text, is_cached

    # Process books: read cached text (fast); fall back to inline extraction
    # only if a book somehow isn't in the cache.
    extractor = BookExtractor()
    total_chunks = 0

    for file_path, title in tqdm(books, desc="Indexing books"):
        if not args.no_cache and is_cached(cache_dir, file_path):
            text = read_cached_text(cache_dir, file_path)
        elif file_path.lower().endswith(".pdf"):
            text = extractor.extract_pdf(file_path)
        elif file_path.lower().endswith(".epub"):
            text = extractor.extract_epub(file_path)
        else:
            continue

        if text:
            chunks = indexer.add_document(
                file_path,
                text,
                {"file": file_path, "title": title}
            )
            total_chunks += chunks

    print(f"\nTotal chunks created: {total_chunks}")
    write_problem_report(args.output)

    if args.embeddings_only:
        # STAGE 1 only: stream embeddings + metadata to disk (memory-bounded),
        # then exit so torch (and its OpenMP runtime) is gone before
        # build_index_cli.py constructs the index.
        indexer.embed_and_save(args.output)
        write_manifest(args.output, indexer.metadata)
        write_embedding_meta(args.output, indexer)
        print("\n✓ Stage 1 complete. Now build the index torch-free, e.g.:")
        print(f"  python3 build_index_cli.py --index-dir {args.output} "
              f"--index-type ivfflat --from-npy {Path(args.output)/'alexandria_embeddings.npy'}")
        return

    # Default full build — MEMORY-BOUNDED, identical to the GUI path:
    #   (1) STREAM embeddings to disk (the matrix is never resident in RAM), then
    #   (2) build the tuned index in a SEPARATE torch-free process.
    # This removes the last way to trigger the old in-process ~24 GB build that
    # OOM'd a 48 GB Mac. There is no longer a code path that holds the whole
    # embedding matrix in RAM.
    import subprocess, gc
    indexer.embed_and_save(args.output)
    write_manifest(args.output, indexer.metadata)
    write_embedding_meta(args.output, indexer)

    # Release the ~4 GB of chunk text now that it's embedded and on disk, BEFORE
    # the torch-free build subprocess loads the .npy and constructs the index.
    # Otherwise the parent holds all chunks resident while the child needs ~10 GB.
    indexer.chunks = []
    if not indexer.duplicate_detector:      # dup-detection still needs the paths
        indexer.document_file_paths = []
    gc.collect()
    _log_rss("after embed, chunks freed")

    # Optional duplicate detection reads the on-disk embeddings via mmap
    # (small slices), never a resident copy.
    if indexer.duplicate_detector:
        print("\nComputing document embeddings for duplicate detection...")
        emb_mm = np.load(Path(args.output) / "alexandria_embeddings.npy", mmap_mode="r")
        indexer._compute_document_signatures(emb_mm)
        dups = indexer.duplicate_detector.suspected_duplicates
        msg = f"⚠ {len(dups)} potential duplicate(s) — see report" if dups else "✓ No duplicates detected"
        print(f"  {msg}")
        indexer.duplicate_detector.save_report(
            str(Path(args.output) / "duplicate_detection_report.json"))

    # Build the tuned index torch-free (IVFFlat, nprobe 128), preserving any
    # saved index_params.json.
    params_path = Path(args.output) / "index_params.json"
    params = json.loads(params_path.read_text()) if params_path.exists() else {}
    bcmd = [sys.executable, str(Path(__file__).parent / "build_index_cli.py"),
            "--index-dir", str(args.output),
            "--index-type", params.get("index_type", "ivfflat"),
            "--metric", params.get("metric", "ip"),
            "--from-npy", str(Path(args.output) / "alexandria_embeddings.npy"),
            "--nlist", str(params.get("nlist", 1024)),
            "--nprobe", str(params.get("nprobe", 128))]
    print("\nBuilding index (torch-free subprocess, tuned params)...")
    rc = subprocess.call(bcmd)
    print("\n✓ Indexing complete! (memory-bounded, IVFFlat, nprobe 128)"
          if rc == 0 else f"\n⚠ Index build subprocess exited {rc}.")


if __name__ == "__main__":
    main()
```

### `app.py`

```python
#!/usr/bin/env python3
"""
Alexandria RAG Web UI
Management dashboard for semantic search across your book collection.
"""

import os
import re
import sys
import json
import subprocess
import threading
from pathlib import Path
from datetime import datetime
import traceback

# This process loads BOTH torch (SentenceTransformer) and faiss, each with its
# own OpenMP runtime. Set these guards BEFORE importing them to reduce the
# chance of a dual-OpenMP segfault. (query_rag also pins faiss to 1 thread.)
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from flask import Flask, render_template, request, jsonify, send_from_directory
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

from index_books import (RAGIndexer, BookExtractor, TextChunker, scan_books,
                         write_problem_report, write_manifest, PROBLEM_PDFS)
from query_rag import RAGQuerier

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['JSON_SORT_KEYS'] = False

# Global state
STATE = {
    'indexing': False,
    'progress': 0,
    'progress_message': '',
    'querier': None,
    'index_dir': '.',
    'books_dir': '.',
}

LOCK = threading.Lock()

def get_config_file():
    """Get config file path - stored in current working directory."""
    config_path = Path.cwd() / 'rag_config.json'
    return config_path

CONFIG_FILE = None  # Will be set by init_app()


def load_config():
    """Load saved configuration from file."""
    global STATE, CONFIG_FILE
    if CONFIG_FILE is None:
        CONFIG_FILE = get_config_file()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
                STATE['index_dir'] = config.get('index_dir', '.')
                STATE['books_dir'] = config.get('books_dir', '.')
                print(f"✓ Loaded config: books_dir={STATE['books_dir']}, index_dir={STATE['index_dir']}")
        except Exception as e:
            print(f"⚠ Could not load config: {e}")


def save_config():
    """Save current configuration to file."""
    global CONFIG_FILE
    try:
        if CONFIG_FILE is None:
            CONFIG_FILE = get_config_file()
        config = {
            'books_dir': STATE['books_dir'],
            'index_dir': STATE['index_dir'],
            'saved_at': datetime.now().isoformat()
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"✓ Saved config to {CONFIG_FILE}")
    except Exception as e:
        print(f"⚠ Could not save config: {e}")


def load_querier(index_dir='.'):
    """Load or reload the querier."""
    try:
        querier = RAGQuerier(index_dir=index_dir)
        STATE['querier'] = querier
        return True
    except Exception as e:
        print(f"Error loading querier: {e}")
        return False


def _free_querier():
    """Drop the in-memory index + metadata (~8 GB) and force a GC. Called before
    a rebuild/update so the loaded copy doesn't compete for RAM with the build
    subprocesses; the querier is reloaded from disk once the build completes."""
    import gc
    if STATE.get('querier') is not None:
        STATE['querier'] = None
        gc.collect()
        print("✓ Released loaded index for the duration of the build (~8 GB freed)")


def get_index_stats():
    """Get statistics about the current index."""
    index_path = Path(STATE['index_dir']) / 'alexandria.index'
    metadata_path = Path(STATE['index_dir']) / 'alexandria_metadata.json'

    if not index_path.exists() or not metadata_path.exists():
        return {
            'indexed': False,
            'chunks': 0,
            'books': 0,
            'index_size_mb': 0,
            'metadata_size_mb': 0,
            'created_at': None,
        }

    with open(metadata_path) as f:
        metadata = json.load(f)

    unique_books = len(set(m['file'] for m in metadata))
    index_size = index_path.stat().st_size / (1024 * 1024)
    metadata_size = metadata_path.stat().st_size / (1024 * 1024)
    created_at = datetime.fromtimestamp(index_path.stat().st_mtime).isoformat()

    return {
        'indexed': True,
        'chunks': len(metadata),
        'books': unique_books,
        'index_size_mb': round(index_size, 2),
        'metadata_size_mb': round(metadata_size, 2),
        'created_at': created_at,
    }


def scan_books_in_dir(directory):
    """Scan for books in directory."""
    books = scan_books(directory)
    return [{'path': path, 'title': title} for path, title in books]


# ============================================================================
# Routes
# ============================================================================

@app.route('/')
def dashboard():
    """Main dashboard."""
    stats = get_index_stats()
    return render_template('index.html', stats=stats)


@app.route('/search')
def search_page():
    """Search page."""
    return render_template('search.html')


@app.route('/indexing')
def indexing_page():
    """Indexing page."""
    return render_template('indexing.html')


@app.route('/management')
def management_page():
    """Index management page."""
    stats = get_index_stats()
    return render_template('management.html', stats=stats)


@app.route('/tuning')
def tuning_page():
    """Index tuning page — pick index type/params and tune search live."""
    return render_template('tuning.html')


@app.route('/guide')
def guide_page():
    """Optimization guide — recommendations rendered in-app."""
    return render_template('guide.html')


@app.route('/books')
def books_page():
    """Books browser page."""
    return render_template('books.html')


# ============================================================================
# API Routes - Search
# ============================================================================

@app.route('/api/search', methods=['POST'])
def api_search():
    """Search the index."""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        k = int(data.get('k', 5))
        # Live tuning knobs (ignored if the index type doesn't support them)
        nprobe = data.get('nprobe')
        ef_search = data.get('ef_search')

        if not query:
            return jsonify({'error': 'Query cannot be empty'}), 400

        if STATE['querier'] is None:
            return jsonify({'error': 'Index not loaded. Build index first.'}), 400

        results = STATE['querier'].search(
            query, k=k,
            nprobe=int(nprobe) if nprobe is not None else None,
            ef_search=int(ef_search) if ef_search is not None else None,
        )
        return jsonify({'success': True, 'query': query, 'results': results,
                        'index_info': STATE['querier'].get_index_info()})

    except Exception as e:
        print(f"Search error: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# API Routes - Indexing
# ============================================================================

@app.route('/api/scan-books', methods=['POST'])
def api_scan_books():
    """Scan for books in a directory."""
    try:
        data = request.get_json()
        directory = data.get('directory', '.')

        books = scan_books_in_dir(directory)
        return jsonify({'success': True, 'books': books, 'count': len(books)})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/start-indexing', methods=['POST'])
def api_start_indexing():
    """Start indexing in background."""
    try:
        data = request.get_json()
        books_dir = data.get('books_dir', '.')
        output_dir = data.get('output_dir', '.')
        model = data.get('model', 'all-MiniLM-L6-v2')

        # Atomic check-and-claim: without holding LOCK across BOTH the test and
        # the set, two near-simultaneous clicks can each pass the test before
        # either marks indexing started — spawning two full embeds at once
        # (observed: two 25 GB Python processes → OOM on a 48 GB Mac).
        with LOCK:
            if STATE['indexing']:
                return jsonify({'error': 'Indexing already in progress'}), 400
            STATE['indexing'] = True   # claim the slot before releasing the lock

        # Start indexing in background thread
        thread = threading.Thread(
            target=run_indexing,
            args=(books_dir, output_dir, model),
            daemon=True
        )
        thread.start()

        return jsonify({'success': True, 'message': 'Indexing started'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def run_indexing(books_dir, output_dir, model):
    """Run indexing in background."""
    with LOCK:
        STATE['indexing'] = True
        STATE['progress'] = 0
        STATE['progress_message'] = 'Initializing...'
        STATE['books_dir'] = books_dir
        STATE['index_dir'] = output_dir

    # Release the currently-loaded index (~8 GB: FAISS index + metadata) while the
    # rebuild subprocesses run — they need the RAM and would otherwise compete with
    # a stale copy this server no longer uses. Reloaded from disk when we finish.
    _free_querier()

    try:
        # Scan books
        STATE['progress_message'] = 'Scanning for books...'
        STATE['progress'] = 5
        books = scan_books(books_dir)

        if not books:
            STATE['progress_message'] = 'No books found'
            STATE['indexing'] = False
            return

        cache_dir = str(Path(output_dir) / 'text_cache')

        # --- Parallel, cached extraction (torch-free subprocess) --------------
        # This is the SAME fast path the CLI uses: extract across all cores and
        # cache each book's text, so re-runs skip extraction. (The old GUI path
        # extracted one book at a time with no cache — that was the 14+ hours.)
        STATE['progress_message'] = f'Found {len(books)} books. Extracting text (parallel, cached)...'
        STATE['progress'] = 8
        ex = Path(__file__).parent / 'extract_text.py'
        child_env = os.environ.copy()
        child_env['OMP_NUM_THREADS'] = '4'
        proc = subprocess.Popen(
            [sys.executable, str(ex), '--input', books_dir,
             '--cache-dir', cache_dir, '--output', output_dir],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            cwd=str(Path(__file__).parent), env=child_env)
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            STATE['progress_message'] = line
            if '...' in line and 'left' in line:
                try:
                    seg = line.split('...', 1)[1]
                    i, tot = seg.split('(')[0].strip().split('/')
                    i = int(i.replace(',', '')); tot = int(tot.replace(',', ''))
                    STATE['progress'] = 8 + int(i / tot * 52)  # 8..60 during extraction
                except Exception:
                    pass
        proc.wait()

        # ── STAGE 1: chunk + embed in an ISOLATED subprocess ───────────────
        # index_books.py --embeddings-only reads the cache we just built, chunks,
        # and embeds with the memory-safe path (preallocated matrix + MPS cache
        # flush + thread caps). Running it as a subprocess means a heavy embed
        # CANNOT take down this web server, memory is isolated, and it always
        # uses the current code — no rag-ui restart needed after an edit.
        STATE['progress_message'] = 'Embedding (isolated subprocess)...'
        STATE['progress'] = 62
        ib = Path(__file__).parent / 'index_books.py'
        emb_cmd = [sys.executable, str(ib), '--input', books_dir,
                   '--output', output_dir, '--cache-dir', cache_dir,
                   '--model', model, '--embeddings-only', '--no-parallel-extract']
        proc = subprocess.Popen(emb_cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                cwd=str(Path(__file__).parent), env=child_env)
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                STATE['progress_message'] = line
                # "embedded X/N chunks" → advance the bar 62..82 so it visibly
                # moves through the long embed (prevents the "looks stuck → click
                # again → two embeds" trap).
                m = re.search(r'embedded ([\d,]+)/([\d,]+) chunks', line)
                if m:
                    done = int(m.group(1).replace(',', ''))
                    tot = int(m.group(2).replace(',', '')) or 1
                    STATE['progress'] = 62 + int(done / tot * 20)
        if proc.wait() != 0:
            STATE['progress_message'] = 'Error: embedding subprocess failed (see terminal)'
            return

        # ── STAGE 2: build the tuned IVFFlat index, TORCH-FREE subprocess ───
        # No torch here → no dual-OpenMP segfault; produces the IVF index the
        # search side expects (nprobe 128), not a Flat one you'd rebuild later.
        STATE['progress_message'] = 'Building IVFFlat index (torch-free)...'
        STATE['progress'] = 84
        params_path = Path(output_dir) / 'index_params.json'
        params = json.loads(params_path.read_text()) if params_path.exists() else {}
        bcli = Path(__file__).parent / 'build_index_cli.py'
        b_cmd = [sys.executable, str(bcli), '--index-dir', output_dir,
                 '--index-type', params.get('index_type', 'ivfflat'),
                 '--metric', params.get('metric', 'ip'),
                 '--from-npy', str(Path(output_dir) / 'alexandria_embeddings.npy'),
                 '--nlist', str(params.get('nlist', 1024)),
                 '--nprobe', str(params.get('nprobe', 128))]
        bproc = subprocess.Popen(b_cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True,
                                 cwd=str(Path(__file__).parent), env=child_env)
        for line in bproc.stdout:
            line = line.rstrip()
            if line:
                STATE['progress_message'] = line
        if bproc.wait() != 0:
            STATE['progress_message'] = 'Error: index build subprocess failed (see terminal)'
            return

        # (the embedding subprocess already wrote problem_pdfs.txt)
        STATE['progress_message'] = 'Finalizing...'
        STATE['progress'] = 96
        STATE['index_dir'] = output_dir
        load_querier(output_dir)

        STATE['progress'] = 100
        STATE['progress_message'] = 'Complete! Built a tuned IVFFlat index (nprobe 128).'

    except Exception as e:
        STATE['progress_message'] = f'Error: {str(e)}'
        print(f"Indexing error: {e}")
        traceback.print_exc()

    finally:
        save_config()
        STATE['indexing'] = False


@app.route('/api/indexing-status', methods=['GET'])
def api_indexing_status():
    """Get current indexing status."""
    return jsonify({
        'indexing': STATE['indexing'],
        'progress': STATE['progress'],
        'message': STATE['progress_message'],
    })


# ============================================================================
# API Routes - Tuning & Rebuild (torch-free subprocess)
# ============================================================================

def _index_params_path():
    return Path(STATE['index_dir']) / 'index_params.json'


@app.route('/api/index-params', methods=['GET'])
def api_index_params():
    """Return current index type, live-tunable knobs, and last build params."""
    info = {}
    if STATE['querier'] is not None:
        try:
            info = STATE['querier'].get_index_info()
        except Exception as e:
            info = {'error': str(e)}
    saved = {}
    if _index_params_path().exists():
        try:
            saved = json.loads(_index_params_path().read_text())
        except Exception:
            saved = {}
    return jsonify({'live': info, 'build': saved})


@app.route('/api/nprobe-sweep', methods=['POST'])
def api_nprobe_sweep():
    """Sweep the tunable param and return recall + latency for a graph."""
    try:
        if STATE['querier'] is None:
            return jsonify({'error': 'Index not loaded. Build index first.'}), 400

        data = request.get_json() or {}
        k = int(data.get('k', 10))

        # Use provided test queries, else sample chunk previews as proxy queries.
        queries = [q for q in (data.get('queries') or []) if q and q.strip()]
        if not queries:
            import random
            previews = [m.get('text_preview', '') for m in STATE['querier'].metadata]
            previews = [p for p in previews if len(p) > 40]
            queries = random.sample(previews, min(25, len(previews))) if previews else []
        if not queries:
            return jsonify({'error': 'No queries available to sweep'}), 400

        result = STATE['querier'].sweep(queries, k=k)
        result['n_queries'] = len(queries)
        result['k'] = k
        return jsonify(result)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def run_rebuild(opts):
    """Rebuild the index in a SEPARATE torch-free process via build_index_cli.py.

    Running the FAISS build out-of-process is what prevents the dual-OpenMP
    segfault: this Flask process has torch loaded, the subprocess does not.
    """
    with LOCK:
        STATE['indexing'] = True
        STATE['progress'] = 5
        STATE['progress_message'] = f"Starting {opts['index_type']} rebuild..."

    # A rebuild reconstructs vectors from the live index in a child process; free
    # our resident copy first so the two don't both hold the index (~4.7 GB each).
    _free_querier()

    try:
        index_dir = STATE['index_dir']
        script = Path(__file__).parent / 'build_index_cli.py'
        cmd = [sys.executable, str(script),
               '--index-dir', index_dir,
               '--index-type', opts['index_type'],
               '--metric', opts.get('metric', 'ip')]

        # Reconstruct exact vectors from the LIVE index (always aligned with
        # metadata after a healthy build). Use the saved .npy only when no
        # index exists yet: a stale .npy silently scrambles the id->metadata
        # mapping (observed 2026-07-22 and 2026-07-24), and build_index_cli.py
        # now also hard-checks alignment as a second line of defense.
        live_index = Path(index_dir) / 'alexandria.index'
        npy = Path(index_dir) / 'alexandria_embeddings.npy'
        if live_index.exists():
            cmd += ['--from-index', str(live_index)]
        elif npy.exists():
            cmd += ['--from-npy', str(npy)]

        # Per-type parameters
        for flag, key in [('--nlist', 'nlist'), ('--nprobe', 'nprobe'),
                          ('--pq-m', 'pq_m'), ('--pq-nbits', 'pq_nbits'),
                          ('--hnsw-m', 'hnsw_m'), ('--hnsw-efc', 'hnsw_efc'),
                          ('--hnsw-efs', 'hnsw_efs')]:
            if opts.get(key) is not None:
                cmd += [flag, str(opts[key])]

        # The builder is torch-free, so it's safe (and desirable) to let it use
        # multiple threads even though THIS process is pinned to 1.
        child_env = os.environ.copy()
        child_env["OMP_NUM_THREADS"] = "4"
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                cwd=str(Path(__file__).parent), env=child_env)
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                STATE['progress_message'] = line
                if 'training' in line.lower() or 'graph' in line.lower():
                    STATE['progress'] = 40
                elif 'built' in line.lower():
                    STATE['progress'] = 70
                elif 'overlap' in line.lower():
                    STATE['progress'] = 85
                elif 'saved' in line.lower():
                    STATE['progress'] = 95
        proc.wait()

        if proc.returncode == 0:
            STATE['progress'] = 98
            STATE['progress_message'] = 'Reloading index...'
            load_querier(index_dir)
            STATE['progress'] = 100
            STATE['progress_message'] = 'Rebuild complete!'
        else:
            STATE['progress_message'] = f'Rebuild failed (exit {proc.returncode})'

    except Exception as e:
        STATE['progress_message'] = f'Error: {e}'
        traceback.print_exc()
    finally:
        STATE['indexing'] = False


@app.route('/api/rebuild-index', methods=['POST'])
def api_rebuild_index():
    """Kick off a torch-free index rebuild with the chosen type + params."""
    try:
        data = request.get_json() or {}
        index_type = data.get('index_type', 'ivfflat')
        if index_type not in ('flat', 'ivfflat', 'ivfpq', 'hnsw'):
            return jsonify({'error': f'Unknown index type: {index_type}'}), 400

        # Atomic check-and-claim under LOCK: a plain check-then-start lets two fast
        # clicks each spawn a build_index_cli process (~10 GB each). Claim the slot
        # here so the second click is rejected. run_rebuild's finally releases it.
        with LOCK:
            if STATE.get('scanning') or STATE['indexing']:
                return jsonify({'error': 'A scan or build is already in progress'}), 400
            STATE['indexing'] = True

        opts = {
            'index_type': index_type,
            'metric': data.get('metric', 'ip'),
            'nlist': data.get('nlist'),
            'nprobe': data.get('nprobe'),
            'pq_m': data.get('pq_m'),
            'pq_nbits': data.get('pq_nbits'),
            'hnsw_m': data.get('hnsw_m'),
            'hnsw_efc': data.get('hnsw_efc'),
            'hnsw_efs': data.get('hnsw_efs'),
        }
        thread = threading.Thread(target=run_rebuild, args=(opts,), daemon=True)
        thread.start()
        return jsonify({'success': True, 'message': f'{index_type} rebuild started'})

    except Exception as e:
        with LOCK:                       # release the slot if we claimed then failed
            STATE['indexing'] = False
        return jsonify({'error': str(e)}), 500


# ============================================================================
# API Routes - Incremental Update
# ============================================================================

def run_update():
    """Run index_books.py --incremental as a subprocess: re-embed only new/
    changed books and rebuild the index, then reload the querier."""
    STATE['indexing'] = True
    STATE['progress'] = 0
    STATE['progress_message'] = 'Starting incremental update...'
    # Incremental re-embeds only new/changed books but still rebuilds the index in
    # a child; free our resident copy for the duration, reload when done.
    _free_querier()
    try:
        ib = Path(__file__).parent / 'index_books.py'
        cmd = [sys.executable, str(ib), '--input', STATE['books_dir'],
               '--output', STATE['index_dir'], '--incremental']
        child_env = os.environ.copy()
        child_env['OMP_NUM_THREADS'] = '4'
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                cwd=str(Path(__file__).parent), env=child_env)
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            STATE['progress_message'] = line
            low = line.lower()
            if 'incremental update' in low or 'up to date' in low:
                STATE['progress'] = 15
            elif 'extracting' in low:
                STATE['progress'] = 30
            elif 'generating embeddings' in low:
                STATE['progress'] = 55
            elif low.startswith('✓ updated'):
                STATE['progress'] = 80
            elif 'building' in low and 'index' in low:
                STATE['progress'] = 88
            elif 'saved' in low:
                STATE['progress'] = 95
        proc.wait()
        if proc.returncode == 0:
            STATE['progress'] = 98
            STATE['progress_message'] = 'Reloading index...'
            load_querier(STATE['index_dir'])
            STATE['progress'] = 100
            STATE['progress_message'] = 'Update complete!'
        else:
            STATE['progress_message'] = f'Update failed (exit {proc.returncode})'
    except Exception as e:
        STATE['progress_message'] = f'Error: {e}'
        traceback.print_exc()
    finally:
        STATE['indexing'] = False


@app.route('/api/update-index', methods=['POST'])
def api_update_index():
    """Start an incremental update (add new / changed / removed books)."""
    try:
        # Atomic check-and-claim so two clicks can't launch two updates.
        with LOCK:
            if STATE.get('scanning') or STATE['indexing']:
                return jsonify({'error': 'A scan, build or update is already running'}), 400
            STATE['indexing'] = True
        thread = threading.Thread(target=run_update, daemon=True)
        thread.start()
        return jsonify({'success': True, 'message': 'Incremental update started'})
    except Exception as e:
        with LOCK:
            STATE['indexing'] = False
        return jsonify({'error': str(e)}), 500


# ============================================================================
# API Routes - PDF Health Check (torch-free scan subprocess)
# ============================================================================

def run_scan(books_dir, out_dir, mode='incremental'):
    """Run scan_pdfs.py as a background subprocess and stream progress into STATE.

    mode: 'incremental' (skip unchanged per manifest, default),
          'verify' (also re-hash unchanged files), 'full' (rescan everything).
    """
    STATE['scanning'] = True
    STATE['scan_progress'] = 0
    STATE['scan_message'] = f'Starting PDF scan ({mode})...'
    try:
        script = Path(__file__).parent / 'scan_pdfs.py'
        cmd = [sys.executable, str(script), '--input', books_dir, '--output', out_dir]
        if mode == 'verify':
            cmd.append('--verify')
        elif mode == 'full':
            cmd.append('--full')
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                cwd=str(Path(__file__).parent))
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            if '...' in line and 'left' in line:
                try:
                    seg = line.split('...', 1)[1]
                    i, tot = seg.split('(')[0].strip().split('/')
                    i = int(i.replace(',', '').strip())
                    tot = int(tot.replace(',', '').strip())
                    STATE['scan_progress'] = min(98, int(i / tot * 100))
                except Exception:
                    pass
                STATE['scan_message'] = line.strip()
            elif line.startswith('Scanning') or line.startswith('Done') or line.lstrip().startswith('⚠'):
                STATE['scan_message'] = line.strip()
        proc.wait()
        STATE['scan_progress'] = 100
        STATE['scan_message'] = 'Scan complete'
    except Exception as e:
        STATE['scan_message'] = f'Error: {e}'
        traceback.print_exc()
    finally:
        STATE['scanning'] = False


@app.route('/api/scan-pdfs', methods=['POST'])
def api_scan_pdfs():
    """Start a background PDF integrity scan."""
    try:
        data = request.get_json() or {}
        books_dir = data.get('books_dir') or STATE['books_dir']
        mode = data.get('mode', 'incremental')
        if mode not in ('incremental', 'verify', 'full'):
            return jsonify({'error': f'Unknown scan mode: {mode}'}), 400
        # Atomic check-and-claim so a scan can't overlap a build/update or a
        # second scan (run_scan's finally clears the flag).
        with LOCK:
            if STATE.get('scanning') or STATE['indexing']:
                return jsonify({'error': 'A scan or build is already running'}), 400
            STATE['scanning'] = True
        out_dir = STATE['index_dir']
        thread = threading.Thread(target=run_scan, args=(books_dir, out_dir, mode), daemon=True)
        thread.start()
        return jsonify({'success': True, 'message': f'PDF scan started ({mode})', 'books_dir': books_dir})
    except Exception as e:
        with LOCK:
            STATE['scanning'] = False
        return jsonify({'error': str(e)}), 500


@app.route('/api/scan-status', methods=['GET'])
def api_scan_status():
    """Progress of the running PDF scan."""
    return jsonify({
        'scanning': STATE.get('scanning', False),
        'progress': STATE.get('scan_progress', 0),
        'message': STATE.get('scan_message', ''),
    })


@app.route('/api/scan-results', methods=['GET'])
def api_scan_results():
    """Parsed problem_pdfs.txt from the last scan."""
    import re
    report = Path(STATE['index_dir']) / 'problem_pdfs.txt'
    if not report.exists():
        return jsonify({'exists': False})
    count = total = None
    problems = []
    for ln in report.read_text().splitlines():
        if ln.startswith('#') and 'had issues' in ln:
            m = re.search(r'#\s*(\d+)\s+of\s+([\d,]+)', ln)
            if m:
                count = int(m.group(1)); total = int(m.group(2).replace(',', ''))
        elif ln and not ln.startswith('#'):
            if ln.startswith('    '):
                if problems:
                    problems[-1]['issue'] = ln.strip()
            else:
                problems.append({'file': ln.strip(), 'issue': ''})
    return jsonify({'exists': True,
                    'count': count if count is not None else len(problems),
                    'total': total, 'problems': problems,
                    'modified': datetime.fromtimestamp(report.stat().st_mtime).isoformat()})


# ============================================================================
# API Routes - Management
# ============================================================================

@app.route('/api/index-stats', methods=['GET'])
def api_index_stats():
    """Get index statistics."""
    stats = get_index_stats()
    return jsonify(stats)


@app.route('/api/refresh-queues', methods=['POST'])
def api_refresh_queues():
    """Rebuild the work queues from what is actually on disk.

    The queues were hand-maintained, so any book added after they were written
    stayed invisible to every pass: 65 books sat with no text layer while the
    OCR queue reported empty and success. This asks the library instead."""
    try:
        data = request.get_json(silent=True) or {}
        do_apply = bool(data.get('apply'))
        books_dir = Path(STATE['books_dir'])
        script = books_dir / '_Optimization' / 'refresh_queues.py'
        if not script.exists():
            return jsonify({'error': f'refresh_queues.py not found at {script}'}), 404
        cmd = [sys.executable, str(script)]
        if do_apply:
            # OCR queue only. Writing index_exclude.txt from a button would let
            # one click remove 65 books from search with nothing reviewed.
            cmd.append('--apply-ocr')
        env = os.environ.copy()
        env['ALEX_ROOT'] = str(books_dir)
        env['ALEX_OUT'] = str(books_dir / '_Optimization')
        # Prefer the native arm64 poppler; /usr/local is the x86_64 prefix and
        # would run every pdfinfo/pdftotext under Rosetta.
        env['PATH'] = '/opt/homebrew/bin:' + env.get('PATH', '')
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=2400, env=env)
        return jsonify({'success': r.returncode == 0,
                        'applied': do_apply,
                        'output': (r.stdout + r.stderr)[-12000:]})
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'refresh_queues.py exceeded 40 minutes'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear-index', methods=['POST'])
def api_clear_index():
    """Delete the current index."""
    try:
        index_path = Path(STATE['index_dir']) / 'alexandria.index'
        metadata_path = Path(STATE['index_dir']) / 'alexandria_metadata.json'

        if index_path.exists():
            index_path.unlink()
        if metadata_path.exists():
            metadata_path.unlink()

        STATE['querier'] = None

        return jsonify({'success': True, 'message': 'Index cleared'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config', methods=['POST'])
def api_set_config():
    """Set configuration (index/books directories)."""
    try:
        data = request.get_json()
        index_dir = data.get('index_dir', '.')
        books_dir = data.get('books_dir', '.')

        STATE['index_dir'] = index_dir
        STATE['books_dir'] = books_dir

        # Save configuration
        save_config()

        # Try to load querier
        load_querier(index_dir)

        return jsonify({'success': True, 'message': 'Configuration updated and saved'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config', methods=['GET'])
def api_get_config():
    """Get current configuration."""
    return jsonify({
        'index_dir': STATE['index_dir'],
        'books_dir': STATE['books_dir'],
    })


# ============================================================================
# API Routes - Books
# ============================================================================

@app.route('/api/books', methods=['GET'])
def api_get_books():
    """Get list of indexed books."""
    try:
        if STATE['querier'] is None:
            return jsonify({'books': []})

        metadata = STATE['querier'].metadata
        books_dict = {}

        for entry in metadata:
            file_path = entry['file']
            title = entry['title']
            if file_path not in books_dict:
                books_dict[file_path] = {
                    'file': file_path,
                    'title': title,
                    'chunks': 0,
                }
            books_dict[file_path]['chunks'] += 1

        books = list(books_dict.values())
        books.sort(key=lambda x: x['title'].lower())

        return jsonify({'books': books, 'total': len(books)})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Static Files
# ============================================================================

@app.route('/static/<path:path>')
def send_static(path):
    """Serve static files."""
    return send_from_directory('static', path)


# ============================================================================
# Error Handlers
# ============================================================================

@app.route('/favicon.ico')
def favicon():
    """Browsers auto-request this; return empty so it doesn't 404-spam the log."""
    return ('', 204)


@app.errorhandler(404)
def not_found(e):
    """404 handler."""
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    """500 handler."""
    return render_template('500.html'), 500


# ============================================================================
# Initialization
# ============================================================================

def init_app():
    """Initialize app on startup."""
    global CONFIG_FILE
    print("Alexandria RAG - Web Management UI")
    print("=" * 50)

    # Initialize config file path
    CONFIG_FILE = get_config_file()
    print(f"Config file: {CONFIG_FILE}")
    print(f"Working directory: {Path.cwd()}")

    # Load saved configuration
    load_config()

    # Try to load existing index
    if load_querier(STATE['index_dir']):
        print("✓ Existing index loaded")
    else:
        print("⚠ No index found. Build one from the Indexing page.")

    print(f"\nBooks directory: {STATE['books_dir']}")
    print(f"Index directory: {STATE['index_dir']}")
    print("\nWeb UI starting at http://127.0.0.1:5050")
    print("=" * 50)


if __name__ == '__main__':
    init_app()
    # use_reloader=False prevents Flask from restarting when you click tabs
    # Bind to 127.0.0.1 directly — on this machine the 'localhost' hostname
    # doesn't resolve, so use the loopback IP.
    # Port 5050, NOT 5000: macOS AirPlay Receiver (ControlCenter) listens on
    # 5000 and launchd respawns it when killed. Moved 2026-07-02.
    app.run(debug=True, host='127.0.0.1', port=5050, use_reloader=False)
```

### `alexandria_mcp_server.py`

```python
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
            }
        ]
    }

def handle_tools_call(params):
    tool_name = params.get("name")
    args = params.get("arguments", {})

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

```

### `templates/base.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Alexandria RAG{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('send_static', path='style.css') }}">
    {% block head %}{% endblock %}
</head>
<body>
    <div class="app-container">
        <!-- Sidebar Navigation -->
        <nav class="sidebar">
            <div class="sidebar-header">
                <h1 class="app-title">Alexandria RAG</h1>
                <p class="app-subtitle">Semantic Search</p>
            </div>

            <ul class="nav-menu">
                <li><a href="/" class="nav-link {% if request.path == '/' %}active{% endif %}">
                    <span class="icon">📊</span> Dashboard
                </a></li>
                <li><a href="/search" class="nav-link {% if request.path == '/search' %}active{% endif %}">
                    <span class="icon">🔍</span> Search
                </a></li>
                <li><a href="/indexing" class="nav-link {% if request.path == '/indexing' %}active{% endif %}">
                    <span class="icon">⚙️</span> Indexing
                </a></li>
                <li><a href="/books" class="nav-link {% if request.path == '/books' %}active{% endif %}">
                    <span class="icon">📚</span> Books
                </a></li>
                <li><a href="/tuning" class="nav-link {% if request.path == '/tuning' %}active{% endif %}">
                    <span class="icon">🎛️</span> Tuning
                </a></li>
                <li><a href="/management" class="nav-link {% if request.path == '/management' %}active{% endif %}">
                    <span class="icon">🛠️</span> Management
                </a></li>
                <li><a href="/guide" class="nav-link {% if request.path == '/guide' %}active{% endif %}">
                    <span class="icon">📖</span> Guide
                </a></li>
            </ul>

            <div class="sidebar-footer">
                <p class="footer-text">Local RAG System</p>
            </div>
        </nav>

        <!-- Main Content -->
        <main class="main-content">
            <div class="content-wrapper">
                {% block content %}{% endblock %}
            </div>
        </main>
    </div>

    <script src="{{ url_for('send_static', path='script.js') }}"></script>
    {% block scripts %}{% endblock %}
</body>
</html>

```

### `templates/index.html`

```html
{% extends 'base.html' %}

{% block title %}Dashboard - Alexandria RAG{% endblock %}

{% block content %}
<div class="page-header">
    <h1>Dashboard</h1>
    <p class="subtitle">Your Alexandria RAG System Overview</p>
</div>

<div class="stats-grid">
    <!-- Index Status -->
    <div class="stat-card">
        <div class="stat-icon">📇</div>
        <div class="stat-content">
            <h3>Index Status</h3>
            <p class="stat-value" id="index-status">
                {% if stats.indexed %}Ready{% else %}Not Built{% endif %}
            </p>
            <p class="stat-detail">
                {% if stats.indexed %}
                    Built {{ stats.created_at|default('recently') }}
                {% else %}
                    <a href="/indexing">Build Index</a>
                {% endif %}
            </p>
        </div>
    </div>

    <!-- Books Count -->
    <div class="stat-card">
        <div class="stat-icon">📚</div>
        <div class="stat-content">
            <h3>Books Indexed</h3>
            <p class="stat-value">{{ stats.books }}</p>
            <p class="stat-detail">in your collection</p>
        </div>
    </div>

    <!-- Chunks -->
    <div class="stat-card">
        <div class="stat-icon">📑</div>
        <div class="stat-content">
            <h3>Text Chunks</h3>
            <p class="stat-value">{{ "{:,}".format(stats.chunks) }}</p>
            <p class="stat-detail">searchable passages</p>
        </div>
    </div>

    <!-- Index Size -->
    <div class="stat-card">
        <div class="stat-icon">💾</div>
        <div class="stat-content">
            <h3>Index Size</h3>
            <p class="stat-value">{{ stats.index_size_mb }} MB</p>
            <p class="stat-detail">
                {% if stats.indexed %}
                    {{ stats.index_size_mb + stats.metadata_size_mb }} MB total
                {% else %}
                    no data yet
                {% endif %}
            </p>
        </div>
    </div>
</div>

<!-- Quick Actions -->
<div class="quick-actions">
    <h2>Quick Start</h2>
    <div class="action-buttons">
        <a href="/search" class="btn btn-primary">
            <span>🔍</span> Search Your Books
        </a>
        <a href="/indexing" class="btn btn-secondary">
            <span>⚙️</span> Build or Update Index
        </a>
        <a href="/books" class="btn btn-secondary">
            <span>📚</span> Browse Books
        </a>
    </div>
</div>

<!-- Features -->
<div class="features-section">
    <h2>How It Works</h2>
    <div class="features-grid">
        <div class="feature">
            <div class="feature-icon">🔍</div>
            <h3>Semantic Search</h3>
            <p>Ask questions in natural language. Find relevant passages by meaning, not just keywords.</p>
        </div>
        <div class="feature">
            <div class="feature-icon">⚡</div>
            <h3>Fast & Local</h3>
            <p>Everything runs on your computer. No cloud, no privacy concerns. GPU-accelerated when available.</p>
        </div>
        <div class="feature">
            <div class="feature-icon">📖</div>
            <h3>Full Context</h3>
            <p>Results show the source book, exact passage, and relevance score. Know exactly where information comes from.</p>
        </div>
        <div class="feature">
            <div class="feature-icon">🔧</div>
            <h3>Easy Management</h3>
            <p>Build, update, or clear your index from this interface. No command line needed.</p>
        </div>
    </div>
</div>

<script>
// Refresh stats periodically
setInterval(() => {
    fetch('/api/index-stats')
        .then(r => r.json())
        .then(data => {
            document.getElementById('index-status').textContent =
                data.indexed ? 'Ready' : 'Not Built';
        });
}, 30000);
</script>
{% endblock %}

```

### `templates/search.html`

```html
{% extends 'base.html' %}

{% block title %}Search - Alexandria RAG{% endblock %}

{% block content %}
<div class="page-header">
    <h1>Search Your Books</h1>
    <p class="subtitle">Semantic search across your entire collection</p>
</div>

<!-- Search Interface -->
<div class="search-container">
    <div class="search-box">
        <input
            type="text"
            id="search-input"
            class="search-input"
            placeholder="Ask a question... e.g., 'What does this collection say about machine learning?'"
            autocomplete="off"
        >
        <button id="search-btn" class="btn btn-primary search-btn">
            <span>🔍</span> Search
        </button>
    </div>

    <div class="search-options">
        <label>
            Results to show:
            <input type="number" id="results-count" min="1" max="20" value="5" style="width: 60px;">
        </label>
    </div>
</div>

<!-- Loading State -->
<div id="search-loading" class="loading hidden">
    <div class="spinner"></div>
    <p>Searching your library...</p>
</div>

<!-- Results -->
<div id="results-container" class="results-container hidden">
    <div class="results-header">
        <h2>Results for "<span id="results-query"></span>"</h2>
        <p class="results-count"><span id="results-number">0</span> results found</p>
    </div>

    <div id="results-list" class="results-list">
        <!-- Results will be inserted here -->
    </div>
</div>

<!-- Empty State -->
<div id="empty-state" class="empty-state">
    <div class="empty-icon">🔍</div>
    <h2>Start Searching</h2>
    <p>Type a question above to search across all your books.</p>
    <p class="empty-tip">💡 Tip: Ask natural language questions like "How do I implement machine learning?" or "What are the main themes?"</p>
</div>

<!-- No Index State -->
<div id="no-index-state" class="empty-state hidden">
    <div class="empty-icon">⚠️</div>
    <h2>No Index Found</h2>
    <p>You need to build an index first before you can search.</p>
    <a href="/indexing" class="btn btn-primary">Build Index</a>
</div>

<style>
.search-container {
    margin-bottom: 2rem;
}

.search-box {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
}

.search-input {
    flex: 1;
    padding: 0.75rem 1rem;
    font-size: 1rem;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    font-family: inherit;
    transition: border-color 0.2s;
}

.search-input:focus {
    outline: none;
    border-color: #2196F3;
    box-shadow: 0 0 0 3px rgba(33, 150, 243, 0.1);
}

.search-btn {
    padding: 0.75rem 1.5rem;
}

.search-options {
    display: flex;
    gap: 1rem;
    font-size: 0.9rem;
}

.search-options label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.loading {
    text-align: center;
    padding: 2rem;
}

.loading.hidden {
    display: none;
}

.spinner {
    width: 40px;
    height: 40px;
    border: 4px solid #e0e0e0;
    border-top-color: #2196F3;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 1rem;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

.results-container {
    margin-top: 2rem;
}

.results-container.hidden {
    display: none;
}

.results-header {
    margin-bottom: 1.5rem;
    padding-bottom: 1rem;
    border-bottom: 2px solid #e0e0e0;
}

.results-header h2 {
    margin-bottom: 0.5rem;
}

.results-count {
    color: #666;
    font-size: 0.9rem;
}

.results-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.result-item {
    padding: 1.25rem;
    background: #f9f9f9;
    border: 1px solid #e0e0e0;
    border-left: 4px solid #2196F3;
    border-radius: 6px;
    transition: box-shadow 0.2s;
}

.result-item:hover {
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.result-rank {
    display: inline-block;
    background: #2196F3;
    color: white;
    width: 28px;
    height: 28px;
    line-height: 28px;
    text-align: center;
    border-radius: 50%;
    font-weight: bold;
    font-size: 0.9rem;
    margin-right: 0.75rem;
}

.result-header {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
}

.result-title {
    flex: 1;
    font-weight: 600;
    color: #1a1a1a;
    margin: 0;
}

.result-metadata {
    display: flex;
    gap: 1rem;
    font-size: 0.85rem;
    color: #666;
    margin-bottom: 0.75rem;
    flex-wrap: wrap;
}

.metadata-item {
    display: flex;
    align-items: center;
    gap: 0.25rem;
}

.similarity-badge {
    display: inline-block;
    background: #4CAF50;
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 500;
}

.result-preview {
    padding: 0.75rem;
    background: white;
    border-left: 2px solid #ddd;
    border-radius: 4px;
    color: #333;
    line-height: 1.5;
    font-size: 0.95rem;
}

.empty-state {
    text-align: center;
    padding: 3rem 1rem;
}

.empty-state.hidden {
    display: none;
}

.empty-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
    opacity: 0.6;
}

.empty-state h2 {
    margin-bottom: 0.5rem;
    color: #666;
}

.empty-state p {
    color: #999;
    margin-bottom: 0.5rem;
}

.empty-tip {
    font-style: italic;
    color: #aaa;
    margin-top: 1rem;
}
</style>

<script>
// Check if index exists on load
async function checkIndex() {
    const response = await fetch('/api/index-stats');
    const stats = await response.json();

    if (!stats.indexed) {
        document.getElementById('no-index-state').classList.remove('hidden');
        document.getElementById('search-input').disabled = true;
        document.getElementById('search-btn').disabled = true;
    }
}

// Search functionality
async function performSearch() {
    const query = document.getElementById('search-input').value.trim();
    if (!query) return;

    const k = parseInt(document.getElementById('results-count').value);

    // Show loading
    document.getElementById('search-loading').classList.remove('hidden');
    document.getElementById('results-container').classList.add('hidden');
    document.getElementById('empty-state').classList.add('hidden');

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, k })
        });

        if (!response.ok) {
            const error = await response.json();
            alert('Error: ' + error.error);
            document.getElementById('search-loading').classList.add('hidden');
            return;
        }

        const data = await response.json();
        displayResults(data);

    } catch (error) {
        alert('Search failed: ' + error.message);
    } finally {
        document.getElementById('search-loading').classList.add('hidden');
    }
}

function displayResults(data) {
    const resultsContainer = document.getElementById('results-list');
    resultsContainer.innerHTML = '';

    if (data.results.length === 0) {
        document.getElementById('results-container').classList.remove('hidden');
        document.getElementById('results-query').textContent = data.query;
        document.getElementById('results-number').textContent = '0';
        resultsContainer.innerHTML = '<p style="text-align: center; color: #999;">No results found. Try rephrasing your query.</p>';
        return;
    }

    data.results.forEach(result => {
        const item = document.createElement('div');
        item.className = 'result-item';

        const similarity = (result.similarity * 100).toFixed(1);

        item.innerHTML = `
            <div class="result-header">
                <span class="result-rank">${result.rank}</span>
                <h3 class="result-title">${escapeHtml(result.title)}</h3>
            </div>
            <div class="result-metadata">
                <span class="metadata-item">📄 ${result.file.split('/').pop()}</span>
                <span class="metadata-item">📍 Chunk ${result.chunk}</span>
                <span class="similarity-badge">${similarity}% match</span>
            </div>
            <div class="result-preview">${escapeHtml(result.preview)}</div>
        `;

        resultsContainer.appendChild(item);
    });

    document.getElementById('results-container').classList.remove('hidden');
    document.getElementById('results-query').textContent = data.query;
    document.getElementById('results-number').textContent = data.results.length;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Event listeners
document.getElementById('search-btn').addEventListener('click', performSearch);
document.getElementById('search-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') performSearch();
});

// Check index on load
checkIndex();
</script>
{% endblock %}

```

### `templates/indexing.html`

```html
{% extends 'base.html' %}

{% block title %}Indexing - Alexandria RAG{% endblock %}

{% block content %}
<div class="page-header">
    <h1>Index Management</h1>
    <p class="subtitle">Build or update your searchable index</p>
</div>

<!-- Configuration Section -->
<div class="section">
    <h2>Index Configuration</h2>

    <div class="form-group">
        <label for="books-dir">Books Directory</label>
        <input
            type="text"
            id="books-dir"
            class="form-input"
            placeholder="/Volumes/G-RAID MIRROR/Dropbox/Alexandria"
        >
        <p class="form-help">Directory containing your PDF and EPUB books</p>
    </div>

    <div class="form-group">
        <label for="output-dir">Index Output Directory</label>
        <input
            type="text"
            id="output-dir"
            class="form-input"
            placeholder="/Volumes/G-RAID MIRROR/Dropbox/Alexandria"
        >
        <p class="form-help">Where to save the index files (same directory recommended)</p>
    </div>

    <div class="form-group">
        <label for="embedding-model">Embedding Model</label>
        <select id="embedding-model" class="form-select">
            <optgroup label="Multilingual - handles Greek, Latin, Hebrew, German, French">
                <option value="intfloat/multilingual-e5-small" selected>multilingual-e5-small (384-dim, 512 tok, ~171/s - fastest, best cross-language)</option>
                <option value="intfloat/multilingual-e5-base">multilingual-e5-base (768-dim, 512 tok, ~86/s)</option>
                <option value="BAAI/bge-m3">bge-m3 (1024-dim, 8192 ctx, ~26/s - 18h for this corpus)</option>
            </optgroup>
            <optgroup label="English only">
                <option value="all-MiniLM-L6-v2">all-MiniLM-L6-v2 (384-dim, 256 tok - cannot match Greek/Latin)</option>
                <option value="all-mpnet-base-v2">all-mpnet-base-v2 (768-dim)</option>
                <option value="all-roberta-large-v1">all-roberta-large-v1 (1024-dim, slowest)</option>
            </optgroup>
            </select>
        <p class="form-help">
            Changing the model requires re-embedding every book - vectors from
            different models are not comparable. Measured on this machine:
            e5-small 171/s (2.8h), e5-base 86/s (5.5h), bge-m3 26/s (18h).
            Cross-language scores (Greek/Latin to English): e5-small 0.91/0.94,
            bge-m3 0.88/0.83, all-MiniLM 0.12/0.17 - below the 0.3 similarity
            threshold, which is why Greek and Latin never surfaced before.
        </p>
    </div>

    <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
        <button id="scan-btn" class="btn btn-secondary">
            📁 Scan for Books
        </button>
        <button id="save-config-btn" class="btn btn-secondary">
            💾 Save Paths
        </button>
    </div>
</div>

<!-- Books Summary -->
<div id="books-summary" class="section hidden">
    <h3>Found Books</h3>
    <div id="books-list" class="books-list"></div>
</div>

<!-- Indexing Control -->
<div class="section">
    <h2>Start Indexing</h2>
    <button id="index-btn" class="btn btn-primary btn-large">
        ⚙️ Build Index
    </button>
    <p class="section-help">First run: 30 minutes to several hours depending on collection size and hardware</p>
</div>

<!-- Progress Section -->
<div id="progress-section" class="section hidden">
    <h2>Indexing Progress</h2>

    <div class="progress-container">
        <div class="progress-bar">
            <div id="progress-fill" class="progress-fill"></div>
        </div>
        <div class="progress-text">
            <span id="progress-percent">0%</span>
        </div>
    </div>

    <p id="progress-message" class="progress-message">Initializing...</p>

    <div class="progress-details">
        <p><strong>Status:</strong> <span id="status-indicator">●</span> <span id="status-text">Starting...</span></p>
    </div>

    <button id="stop-btn" class="btn btn-danger" disabled>
        ⏹ Stop (Not available)
    </button>
</div>

<!-- Completion Section -->
<div id="completion-section" class="section hidden">
    <div class="success-box">
        <div class="success-icon">✓</div>
        <h3>Indexing Complete!</h3>
        <p id="completion-message">Your books are now searchable.</p>
        <a href="/search" class="btn btn-primary">Start Searching</a>
    </div>
</div>

<!-- Error Section -->
<div id="error-section" class="section hidden">
    <div class="error-box">
        <div class="error-icon">⚠️</div>
        <h3>Indexing Failed</h3>
        <p id="error-message">An error occurred during indexing.</p>
        <button id="error-retry-btn" class="btn btn-secondary">Try Again</button>
    </div>
</div>

<style>
.section {
    background: white;
    padding: 1.5rem;
    border-radius: 8px;
    margin-bottom: 1.5rem;
    border: 1px solid #e0e0e0;
}

.section.hidden {
    display: none;
}

.section h2,
.section h3 {
    margin-top: 0;
    margin-bottom: 1rem;
}

.form-group {
    margin-bottom: 1.25rem;
}

.form-group label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
    color: #333;
}

.form-input,
.form-select {
    width: 100%;
    padding: 0.75rem;
    font-size: 1rem;
    border: 1px solid #ddd;
    border-radius: 6px;
    font-family: monospace;
    box-sizing: border-box;
}

.form-input:focus,
.form-select:focus {
    outline: none;
    border-color: #2196F3;
    box-shadow: 0 0 0 3px rgba(33, 150, 243, 0.1);
}

.form-help {
    font-size: 0.85rem;
    color: #666;
    margin-top: 0.25rem;
}

.section-help {
    color: #666;
    font-size: 0.9rem;
    margin-top: 0.5rem;
}

.btn-large {
    padding: 1rem 2rem;
    font-size: 1.1rem;
}

.books-list {
    background: #f9f9f9;
    padding: 1rem;
    border-radius: 6px;
    max-height: 300px;
    overflow-y: auto;
}

.book-item {
    padding: 0.5rem;
    margin-bottom: 0.5rem;
    background: white;
    border-left: 3px solid #2196F3;
    padding-left: 0.75rem;
}

.book-item:last-child {
    margin-bottom: 0;
}

.book-title {
    font-weight: 500;
    color: #333;
}

.book-path {
    font-size: 0.8rem;
    color: #999;
    font-family: monospace;
}

.progress-container {
    margin: 1.5rem 0;
}

.progress-bar {
    width: 100%;
    height: 30px;
    background: #e0e0e0;
    border-radius: 6px;
    overflow: hidden;
    position: relative;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #4CAF50, #45a049);
    width: 0%;
    transition: width 0.3s ease;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: bold;
    font-size: 0.9rem;
}

.progress-text {
    text-align: center;
    margin-top: 0.5rem;
    font-weight: bold;
    color: #333;
}

.progress-message {
    text-align: center;
    color: #666;
    font-size: 0.95rem;
    margin: 1rem 0;
}

.progress-details {
    background: #f9f9f9;
    padding: 1rem;
    border-radius: 6px;
    margin: 1rem 0;
    font-size: 0.9rem;
}

.progress-details p {
    margin: 0.5rem 0;
}

#status-indicator {
    color: #FFA500;
    animation: pulse 1.5s infinite;
}

#status-indicator.complete {
    color: #4CAF50;
    animation: none;
}

#status-indicator.error {
    color: #f44336;
    animation: none;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.success-box,
.error-box {
    text-align: center;
    padding: 2rem;
    border-radius: 8px;
}

.success-box {
    background: #e8f5e9;
    border: 2px solid #4CAF50;
}

.error-box {
    background: #ffebee;
    border: 2px solid #f44336;
}

.success-icon,
.error-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
}

.success-box h3 {
    color: #2e7d32;
    margin-bottom: 0.5rem;
}

.error-box h3 {
    color: #c62828;
    margin-bottom: 0.5rem;
}

.success-box p,
.error-box p {
    color: #333;
    margin-bottom: 1rem;
}

.btn-danger {
    background: #f44336;
    color: white;
}

.btn-danger:hover {
    background: #da190b;
}

.btn-danger:disabled {
    background: #ccc;
    cursor: not-allowed;
}
</style>

<script>
let indexing = false;
const booksDir = document.getElementById('books-dir');
const outputDir = document.getElementById('output-dir');
const embeddingModel = document.getElementById('embedding-model');
const scanBtn = document.getElementById('scan-btn');
const saveConfigBtn = document.getElementById('save-config-btn');
const indexBtn = document.getElementById('index-btn');

// Load saved configuration on page load
async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        booksDir.value = config.books_dir || '';
        outputDir.value = config.index_dir || '';
        console.log('✓ Loaded config:', config);
    } catch (error) {
        console.log('No saved config yet:', error);
    }
}

// Call on page load
loadConfig();

// Save configuration without indexing
saveConfigBtn.addEventListener('click', async () => {
    const booksDirectory = booksDir.value.trim() || '.';
    const outputDirectory = outputDir.value.trim() || '.';

    saveConfigBtn.disabled = true;
    const originalText = saveConfigBtn.textContent;
    saveConfigBtn.textContent = '⏳ Saving...';

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                books_dir: booksDirectory,
                index_dir: outputDirectory
            })
        });

        const data = await response.json();

        if (response.ok) {
            alert('✓ Paths saved successfully!');
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        alert('Save failed: ' + error.message);
    } finally {
        saveConfigBtn.disabled = false;
        saveConfigBtn.textContent = originalText;
    }
});

// Scan for books
scanBtn.addEventListener('click', async () => {
    const dir = booksDir.value.trim() || '.';
    scanBtn.disabled = true;
    scanBtn.textContent = '⏳ Scanning...';

    try {
        const response = await fetch('/api/scan-books', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ directory: dir })
        });

        const data = await response.json();

        if (response.ok) {
            displayBooks(data.books);
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        alert('Scan failed: ' + error.message);
    } finally {
        scanBtn.disabled = false;
        scanBtn.textContent = '📁 Scan for Books';
    }
});

function displayBooks(books) {
    const summary = document.getElementById('books-summary');
    const list = document.getElementById('books-list');
    list.innerHTML = '';

    if (books.length === 0) {
        list.innerHTML = '<p style="color: #999; text-align: center;">No PDF or EPUB files found</p>';
        summary.classList.remove('hidden');
        return;
    }

    books.forEach(book => {
        const item = document.createElement('div');
        item.className = 'book-item';
        item.innerHTML = `
            <div class="book-title">${escapeHtml(book.title)}</div>
            <div class="book-path">${escapeHtml(book.path)}</div>
        `;
        list.appendChild(item);
    });

    summary.classList.remove('hidden');
}

// Start indexing
indexBtn.addEventListener('click', startIndexing);

async function startIndexing() {
    if (indexing) return;

    const booksDirectory = booksDir.value.trim() || '.';
    const outputDirectory = outputDir.value.trim() || '.';
    const model = embeddingModel.value;

    indexing = true;
    indexBtn.disabled = true;

    try {
        const response = await fetch('/api/start-indexing', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                books_dir: booksDirectory,
                output_dir: outputDirectory,
                model: model
            })
        });

        if (response.ok) {
            showProgressSection();
            monitorProgress();
        } else {
            const error = await response.json();
            alert('Error: ' + error.error);
            indexing = false;
            indexBtn.disabled = false;
        }
    } catch (error) {
        alert('Failed to start indexing: ' + error.message);
        indexing = false;
        indexBtn.disabled = false;
    }
}

async function monitorProgress() {
    const progressFill = document.getElementById('progress-fill');
    const progressPercent = document.getElementById('progress-percent');
    const progressMessage = document.getElementById('progress-message');
    const statusText = document.getElementById('status-text');
    const statusIndicator = document.getElementById('status-indicator');

    while (indexing) {
        try {
            const response = await fetch('/api/indexing-status');
            const data = await response.json();

            // Update progress bar
            progressFill.style.width = data.progress + '%';
            progressPercent.textContent = data.progress + '%';
            progressMessage.textContent = data.message;
            statusText.textContent = data.message;

            if (!data.indexing) {
                // Complete
                indexing = false;
                statusIndicator.classList.add('complete');
                showCompletionSection();
                indexBtn.disabled = false;
                break;
            }

            // Poll every 1 second
            await new Promise(r => setTimeout(r, 1000));
        } catch (error) {
            console.error('Progress check failed:', error);
            await new Promise(r => setTimeout(r, 2000));
        }
    }
}

function showProgressSection() {
    document.getElementById('completion-section').classList.add('hidden');
    document.getElementById('error-section').classList.add('hidden');
    document.getElementById('progress-section').classList.remove('hidden');
}

function showCompletionSection() {
    document.getElementById('progress-section').classList.add('hidden');
    document.getElementById('error-section').classList.add('hidden');
    document.getElementById('completion-section').classList.remove('hidden');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
</script>
{% endblock %}
```

### `templates/management.html`

```html
{% extends 'base.html' %}

{% block title %}Management - Alexandria RAG{% endblock %}

{% block content %}
<div class="page-header">
    <h1>Index Management</h1>
    <p class="subtitle">Manage and maintain your search index</p>
</div>

<!-- Index Statistics -->
<div class="section">
    <h2>Index Statistics</h2>
    <div class="stats-table">
        <div class="stat-row">
            <span class="stat-label">Status</span>
            <span class="stat-value" id="stat-status">Loading...</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Books Indexed</span>
            <span class="stat-value" id="stat-books">-</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Text Chunks</span>
            <span class="stat-value" id="stat-chunks">-</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Index Size</span>
            <span class="stat-value" id="stat-size">-</span>
        </div>
        <div class="stat-row">
            <span class="stat-label">Created</span>
            <span class="stat-value" id="stat-created">-</span>
        </div>
    </div>

    <button id="refresh-stats-btn" class="btn btn-secondary">
        🔄 Refresh Statistics
    </button>
</div>

<!-- Incremental Update -->
<div class="section">
    <h2>➕ Update Index</h2>
    <p class="section-description">
        Add new books (and drop removed ones) without re-indexing everything. Only new or changed
        books get re-embedded; your tuned settings (nlist 1024, nprobe 128, cosine) are preserved.
        Takes minutes for a handful of books instead of hours.
    </p>
    <button id="update-btn" class="btn btn-secondary">➕ Update Index</button>
    <span id="update-status-msg" class="scan-msg"></span>
    <div id="update-progress-wrap" class="hidden" style="margin-top:1rem;">
        <div class="progress-bar"><div id="update-fill" class="progress-fill"></div></div>
        <p id="update-progress-msg" class="scan-progress-msg"></p>
    </div>
    <div class="workflow-note">
        <strong>⚠️ After the update finishes:</strong> the Claude MCP server keeps its own copy of
        the index in memory — new books stay invisible to Claude's searches until you restart it.
        Restart the Claude Desktop / Cowork session (which relaunches the MCP server), then ask
        Claude to search for one of the new books to confirm. This web UI picks up the new index
        on its own.
    </div>
</div>

<!-- PDF Health Check -->
<div class="section">
    <h2>🩺 PDF Health Check</h2>
    <p class="section-description">
        Scan PDFs for corrupted streams (the "Data-loss while decompressing" issue) without
        re-indexing. Incremental: unchanged files (per <code>scan_manifest.json</code>) are skipped,
        so after the first full run only new or changed files get scanned — seconds, not minutes.
        Results are written to <code>problem_pdfs.txt</code>.
    </p>
    <select id="scan-mode" style="margin-right:0.5rem;">
        <option value="incremental" selected>Incremental — new/changed files only</option>
        <option value="verify">Verify — also re-hash unchanged files</option>
        <option value="full">Full — rescan everything</option>
    </select>
    <button id="scan-btn" class="btn btn-secondary">🩺 Scan Library</button>
    <span id="scan-status-msg" class="scan-msg"></span>

    <div id="scan-progress-wrap" class="hidden" style="margin-top:1rem;">
        <div class="progress-bar"><div id="scan-fill" class="progress-fill"></div></div>
        <p id="scan-progress-msg" class="scan-progress-msg"></p>
    </div>

    <div id="scan-results" class="hidden" style="margin-top:1rem;"></div>
    <div class="workflow-note">
        <strong>Typical session:</strong> added books? → <em>Update Index</em> (then restart the
        MCP server — see above). Want a corruption check? → <em>Scan Library</em> on Incremental.
        The first incremental scan builds <code>scan_manifest.json</code> (~12 min); after that it
        only scans new/changed files — seconds. <em>Verify</em> re-hashes unchanged files to catch
        silent replacements (use after restoring from backup). <em>Full</em> ignores the manifest.
    </div>
</div>


<!-- Queue Refresh -->
<div class="section">
    <h2>&#128260; Refresh Work Queues</h2>
    <p class="section-description">
        Rebuild the OCR and exclude queues from what is actually on disk. The
        queues were hand-maintained, so any book added afterwards was never
        considered by any pass &mdash; 65 books sat with no text layer while the
        OCR queue reported empty. This asks the library instead of a stale list.
        Takes about a minute. Run it whenever you add books.
    </p>
    <button id="refresh-queues-btn" class="btn btn-secondary">&#128260; Check Queues</button>
    <button id="apply-ocr-btn" class="btn btn-secondary" disabled>&#10133; Add missing books to OCR queue</button>
    <span id="refresh-queues-msg" class="scan-msg"></span>
    <pre id="refresh-queues-out" class="hidden"
         style="margin-top:1rem;padding:0.75rem;background:#111;color:#ddd;
                border-radius:6px;max-height:420px;overflow:auto;
                font-size:0.8rem;line-height:1.35;white-space:pre-wrap;"></pre>
    <div class="workflow-note">
        <strong>Check</strong> is read-only. <strong>Add missing books</strong> writes
        <code>list_ocr.txt</code> only &mdash; safe, because OCR adds a text layer and a
        file that turns out not to need one is rejected. The exclude list is
        <em>not</em> written from here: removing books from search deserves a look at
        <code>junk_candidates.txt</code> first.
    </div>
</div>

<!-- Danger Zone -->
<div class="section danger-zone">
    <h2>⚠️ Danger Zone</h2>
    <p class="section-description">
        These actions cannot be undone. Please be careful.
    </p>

    <div class="danger-action">
        <div class="danger-info">
            <h3>Clear Index</h3>
            <p>Delete the current index and metadata files. You can rebuild it anytime.</p>
        </div>
        <button id="clear-index-btn" class="btn btn-danger">
            🗑️ Clear Index
        </button>
    </div>
</div>

<!-- Maintenance Info -->
<div class="section">
    <h2>Maintenance Tips</h2>
    <div class="tips-list">
        <div class="tip">
            <span class="tip-icon">💾</span>
            <div>
                <strong>Backup Your Index</strong>
                <p>Keep <code>alexandria.index</code> and <code>alexandria_metadata.json</code> safe. The index takes time to build but can be regenerated.</p>
            </div>
        </div>
        <div class="tip">
            <span class="tip-icon">📚</span>
            <div>
                <strong>Adding Books</strong>
                <p>If you add new books to your collection, go to the Indexing page and rebuild the index to include them.</p>
            </div>
        </div>
        <div class="tip">
            <span class="tip-icon">⚡</span>
            <div>
                <strong>Performance</strong>
                <p>Search is faster on GPU. If you have CUDA or Metal, make sure you're using the GPU-accelerated version.</p>
            </div>
        </div>
        <div class="tip">
            <span class="tip-icon">🎯</span>
            <div>
                <strong>Better Results</strong>
                <p>Use larger embedding models (all-mpnet-base-v2, all-roberta-large-v1) for higher quality search results, at the cost of speed.</p>
            </div>
        </div>
    </div>
</div>

<style>
.section {
    background: white;
    padding: 1.5rem;
    border-radius: 8px;
    margin-bottom: 1.5rem;
    border: 1px solid #e0e0e0;
}

.section h2 {
    margin-top: 0;
    margin-bottom: 1rem;
}

.section-description {
    color: #666;
    margin-bottom: 1rem;
    font-size: 0.95rem;
}

.workflow-note {
    margin-top: 1rem;
    padding: 0.75rem 1rem;
    background: #fdf6e3;
    border-left: 4px solid #e0b040;
    border-radius: 4px;
    color: #555;
    font-size: 0.9rem;
    line-height: 1.5;
}

.stats-table {
    background: #f9f9f9;
    border-radius: 6px;
    overflow: hidden;
    margin-bottom: 1rem;
}

.stat-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid #e0e0e0;
}

.stat-row:last-child {
    border-bottom: none;
}

.stat-label {
    font-weight: 500;
    color: #333;
}

.stat-value {
    color: #2196F3;
    font-weight: 600;
    font-family: monospace;
}

.danger-zone {
    border: 2px solid #f44336;
    background: #ffebee;
}

.danger-zone h2 {
    color: #c62828;
}

.danger-action {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    background: white;
    border: 1px solid #ffcdd2;
    border-radius: 6px;
    margin-top: 1rem;
}

.danger-info {
    flex: 1;
}

.danger-info h3 {
    margin: 0 0 0.25rem 0;
    color: #333;
}

.danger-info p {
    margin: 0;
    color: #666;
    font-size: 0.9rem;
}

.btn-danger {
    background: #f44336;
    color: white;
    padding: 0.75rem 1.5rem;
}

.btn-danger:hover {
    background: #da190b;
}

.btn-danger:disabled {
    background: #ccc;
    cursor: not-allowed;
}

.tips-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
}

.tip {
    display: flex;
    gap: 1rem;
    padding: 1rem;
    background: #f9f9f9;
    border-left: 4px solid #2196F3;
    border-radius: 6px;
}

.tip-icon {
    font-size: 1.5rem;
    flex-shrink: 0;
}

.tip strong {
    display: block;
    margin-bottom: 0.25rem;
    color: #333;
}

.tip p {
    margin: 0;
    color: #666;
    font-size: 0.9rem;
}

.tip code {
    background: white;
    padding: 0.2rem 0.4rem;
    border-radius: 3px;
    font-family: monospace;
    color: #666;
}

.confirm-dialog {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    display: none;
}

.confirm-dialog.show {
    display: flex;
}

.confirm-box {
    background: white;
    padding: 2rem;
    border-radius: 8px;
    text-align: center;
    max-width: 400px;
}

.confirm-box h2 {
    margin-top: 0;
    color: #f44336;
}

.confirm-box p {
    color: #666;
    margin-bottom: 1.5rem;
}

.confirm-buttons {
    display: flex;
    gap: 1rem;
    justify-content: center;
}

.confirm-buttons button {
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: 6px;
    font-size: 1rem;
    cursor: pointer;
    transition: background 0.2s;
}

.confirm-ok {
    background: #f44336;
    color: white;
}

.confirm-ok:hover {
    background: #da190b;
}

.confirm-cancel {
    background: #e0e0e0;
    color: #333;
}

.confirm-cancel:hover {
    background: #ccc;
}
.hidden { display: none; }
.scan-msg { margin-left: 0.75rem; color: #666; font-size: 0.9rem; }
.progress-bar { height: 10px; background: #e0e0e0; border-radius: 5px; overflow: hidden; }
.progress-fill { height: 100%; width: 0%; background: #4CAF50; transition: width 0.3s; }
.scan-progress-msg { font-size: 0.82rem; color: #555; margin-top: 0.5rem; font-family: monospace; }
.scan-summary { padding: 0.6rem 0.8rem; border-radius: 6px; font-size: 0.9rem; margin-bottom: 0.6rem; }
.scan-summary.ok { background: #e8f5e9; color: #2e7d32; }
.scan-summary.bad { background: #fff3e0; color: #b26a00; }
.scan-list { max-height: 320px; overflow-y: auto; border: 1px solid #e0e0e0; border-radius: 6px; }
.scan-item { padding: 0.5rem 0.75rem; border-bottom: 1px solid #f0f0f0; font-size: 0.85rem; }
.scan-item:last-child { border-bottom: none; }
.scan-item .f { font-family: monospace; color: #333; word-break: break-all; }
.scan-item .i { color: #b26a00; font-size: 0.8rem; }
</style>

<!-- Confirmation Dialog -->
<div id="confirm-dialog" class="confirm-dialog">
    <div class="confirm-box">
        <h2>⚠️ Clear Index?</h2>
        <p>This will delete all index files. You can rebuild the index anytime.</p>
        <div class="confirm-buttons">
            <button id="confirm-ok" class="confirm-ok">Clear Index</button>
            <button id="confirm-cancel" class="confirm-cancel">Cancel</button>
        </div>
    </div>
</div>

<script>
async function updateStats() {
    try {
        const response = await fetch('/api/index-stats');
        const data = await response.json();

        document.getElementById('stat-status').textContent =
            data.indexed ? '✓ Ready' : '⚠️ Not Built';

        document.getElementById('stat-books').textContent =
            data.indexed ? data.books : '-';

        document.getElementById('stat-chunks').textContent =
            data.indexed ? data.chunks.toLocaleString() : '-';

        document.getElementById('stat-size').textContent =
            data.indexed ? (data.index_size_mb + data.metadata_size_mb).toFixed(1) + ' MB' : '-';

        document.getElementById('stat-created').textContent =
            data.indexed ? new Date(data.created_at).toLocaleString() : '-';

    } catch (error) {
        console.error('Error loading stats:', error);
        document.getElementById('stat-status').textContent = '⚠️ Error';
    }
}

// Refresh stats button
document.getElementById('refresh-stats-btn').addEventListener('click', () => {
    document.getElementById('refresh-stats-btn').disabled = true;
    updateStats().then(() => {
        document.getElementById('refresh-stats-btn').disabled = false;
    });
});

// Clear index button
document.getElementById('clear-index-btn').addEventListener('click', () => {
    document.getElementById('confirm-dialog').classList.add('show');
});

document.getElementById('confirm-cancel').addEventListener('click', () => {
    document.getElementById('confirm-dialog').classList.remove('show');
});

document.getElementById('confirm-ok').addEventListener('click', async () => {
    document.getElementById('confirm-dialog').classList.remove('show');
    document.getElementById('clear-index-btn').disabled = true;

    try {
        const response = await fetch('/api/clear-index', { method: 'POST' });
        const data = await response.json();

        if (response.ok) {
            alert('Index cleared successfully');
            updateStats();
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        alert('Failed to clear index: ' + error.message);
    } finally {
        document.getElementById('clear-index-btn').disabled = false;
    }
});

// ---- Incremental Update ----
const updateBtn = document.getElementById('update-btn');
updateBtn.addEventListener('click', async () => {
    if (!confirm('Scan for new/changed/removed books and update the index? Runs in the background.')) return;
    updateBtn.disabled = true;
    document.getElementById('update-progress-wrap').classList.remove('hidden');
    document.getElementById('update-status-msg').textContent = ' starting…';
    try {
        const r = await fetch('/api/update-index', { method: 'POST', headers: {'Content-Type':'application/json'}, body: '{}' });
        const d = await r.json();
        if (d.error) { alert(d.error); updateBtn.disabled = false; return; }
        pollUpdate();
    } catch (e) { alert('Update failed to start: ' + e.message); updateBtn.disabled = false; }
});

async function pollUpdate() {
    const s = await (await fetch('/api/indexing-status')).json();
    document.getElementById('update-fill').style.width = (s.progress || 0) + '%';
    document.getElementById('update-progress-msg').textContent = s.message || '';
    document.getElementById('update-status-msg').textContent = '';
    if (s.indexing) { setTimeout(pollUpdate, 1000); }
    else { updateBtn.disabled = false; updateStats(); }
}

// ---- PDF Health Check ----
const scanBtn = document.getElementById('scan-btn');

scanBtn.addEventListener('click', async () => {
    const mode = document.getElementById('scan-mode').value;
    const warn = mode === 'incremental'
        ? 'Scan new/changed PDFs for corruption? (First-ever run scans everything; after that, seconds.)'
        : mode === 'verify'
            ? 'Verify scan: re-hashes every file to catch silent replacements. Slower than incremental.'
            : 'Full scan: every PDF, ignoring the manifest (~12+ min for a large library). Continue?';
    if (!confirm(warn)) return;
    scanBtn.disabled = true;
    document.getElementById('scan-results').classList.add('hidden');
    document.getElementById('scan-progress-wrap').classList.remove('hidden');
    document.getElementById('scan-status-msg').textContent = ' starting…';
    try {
        const r = await fetch('/api/scan-pdfs', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({mode}) });
        const d = await r.json();
        if (d.error) { alert(d.error); resetScan(); return; }
        document.getElementById('scan-status-msg').textContent = ' scanning ' + (d.books_dir || '');
        pollScan();
    } catch (e) { alert('Scan failed to start: ' + e.message); resetScan(); }
});

function resetScan() {
    scanBtn.disabled = false;
    document.getElementById('scan-status-msg').textContent = '';
}

async function pollScan() {
    const r = await fetch('/api/scan-status');
    const s = await r.json();
    document.getElementById('scan-fill').style.width = (s.progress || 0) + '%';
    document.getElementById('scan-progress-msg').textContent = s.message || '';
    if (s.scanning) { setTimeout(pollScan, 1000); }
    else { resetScan(); loadScanResults(); }
}

async function loadScanResults() {
    const r = await fetch('/api/scan-results');
    const d = await r.json();
    const box = document.getElementById('scan-results');
    box.classList.remove('hidden');
    if (!d.exists) { box.innerHTML = '<div class="scan-summary ok">No scan report found yet.</div>'; return; }
    if (!d.count) {
        box.innerHTML = `<div class="scan-summary ok">✓ All clear — 0 problem PDFs${d.total ? ' of ' + d.total.toLocaleString() : ''}.</div>`;
        return;
    }
    let html = `<div class="scan-summary bad">⚠ ${d.count} problem PDF${d.count>1?'s':''}${d.total ? ' of ' + d.total.toLocaleString() : ''} — saved to problem_pdfs.txt</div>`;
    html += '<div class="scan-list">';
    d.problems.forEach(p => {
        const name = p.file.split('/').pop();
        html += `<div class="scan-item"><div class="f" title="${p.file}">${name}</div><div class="i">${p.issue || ''}</div></div>`;
    });
    html += '</div>';
    box.innerHTML = html;
}

// If a scan is already running (e.g. page reloaded), resume polling.
(async () => {
    const s = await (await fetch('/api/scan-status')).json();
    if (s.scanning) { scanBtn.disabled = true; document.getElementById('scan-progress-wrap').classList.remove('hidden'); pollScan(); }
    else { loadScanResults(); }
})();

// Load stats on page load
updateStats();


// ---- Refresh work queues -------------------------------------------------
async function runRefreshQueues(apply) {
    const btn  = document.getElementById('refresh-queues-btn');
    const ocr  = document.getElementById('apply-ocr-btn');
    const msg  = document.getElementById('refresh-queues-msg');
    const out  = document.getElementById('refresh-queues-out');
    btn.disabled = true; ocr.disabled = true;
    msg.textContent = apply ? 'Writing OCR queue...' : 'Probing every PDF (about a minute)...';
    out.classList.remove('hidden');
    out.textContent = '';
    try {
        const r = await fetch('/api/refresh-queues', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({apply: apply})
        });
        const d = await r.json();
        out.textContent = d.output || d.error || '(no output)';
        if (d.error) { msg.textContent = 'Failed'; }
        else {
            msg.textContent = apply ? 'OCR queue updated' : 'Done';
            // only offer the write once a dry run has shown what it would do
            ocr.disabled = apply;
        }
    } catch (e) {
        msg.textContent = 'Failed';
        out.textContent = String(e);
    } finally {
        btn.disabled = false;
    }
}
document.getElementById('refresh-queues-btn')
        .addEventListener('click', () => runRefreshQueues(false));
document.getElementById('apply-ocr-btn')
        .addEventListener('click', () => runRefreshQueues(true));

// Refresh stats every 30 seconds
setInterval(updateStats, 30000);
</script>
{% endblock %}
```

### `templates/tuning.html`

```html
{% extends 'base.html' %}

{% block title %}Tuning - Alexandria RAG{% endblock %}

{% block content %}
<div class="page-header">
    <h1>Index Tuning</h1>
    <p class="subtitle">Tune search live, or rebuild with a different index type — all torch-free, no segfaults.</p>
</div>

<!-- Current index status -->
<div class="tune-card">
    <h2>Current Index</h2>
    <div id="index-status" class="status-grid">
        <div class="status-item"><span class="label">Type</span><span id="cur-type" class="value">—</span></div>
        <div class="status-item"><span class="label">Metric <span class="tip" data-tip="cosine = inner product on normalized vectors (what MiniLM/BGE/E5 are trained for). L2 = raw Euclidean distance. Cosine is recommended.">ⓘ</span></span><span id="cur-metric" class="value">—</span></div>
        <div class="status-item"><span class="label">Vectors</span><span id="cur-ntotal" class="value">—</span></div>
        <div class="status-item"><span class="label">Size</span><span id="cur-size" class="value">—</span></div>
        <div class="status-item"><span class="label">Accuracy vs Flat <span class="tip" data-tip="Top-10 overlap between this index and an exact brute-force search, measured at build time. 100% = identical to exact search.">ⓘ</span></span><span id="cur-acc" class="value">—</span></div>
    </div>
</div>

<!-- Live search tuning -->
<div class="tune-card">
    <h2>Live Search Tuning <span class="hint">applies instantly — no rebuild</span></h2>
    <div class="search-box">
        <input type="text" id="q" class="search-input" placeholder="Type a test query and tune the sliders...">
        <button id="go" class="btn btn-primary">🔍 Search</button>
    </div>

    <div class="sliders">
        <div class="slider-row">
            <label>Results (k) <span class="tip" data-tip="How many passages to return per query. Doesn't change the index — just how many of the top matches you see.">ⓘ</span>: <strong id="k-val">5</strong></label>
            <input type="range" id="k" min="1" max="20" value="5">
        </div>
        <div class="slider-row" id="nprobe-row">
            <label>nprobe <span class="tip" data-tip="How many of the nlist clusters to scan per query. 1 = fastest/least accurate; nlist = scans everything (≈exact). Find the lowest value that holds your recall. Applies instantly.">ⓘ</span> <span class="hint">clusters searched — higher = more accurate, slower</span>: <strong id="nprobe-val">50</strong></label>
            <input type="range" id="nprobe" min="1" max="256" value="50">
        </div>
        <div class="slider-row hidden" id="ef-row">
            <label>efSearch <span class="tip" data-tip="How many graph neighbors HNSW explores per query. Higher = more accurate and slower. Must be ≥ k. Applies instantly.">ⓘ</span> <span class="hint">graph breadth — higher = more accurate, slower</span>: <strong id="ef-val">64</strong></label>
            <input type="range" id="ef" min="8" max="512" value="64">
        </div>
        <p id="tune-note" class="hint"></p>
    </div>

    <div id="latency" class="latency hidden"></div>
    <div id="results-list" class="results-list"></div>
</div>

<!-- Sweep graph -->
<div class="tune-card">
    <h2>Recall vs Latency Sweep <span class="tip" data-tip="Runs ~25 sample queries across a range of nprobe (or efSearch) values and plots how recall and per-query latency change. Recall = top-k overlap vs an exhaustive search of the same index, so 100% = exact. The 'knee' is where recall stops rising but latency keeps climbing — the best setting sits just past it.">ⓘ</span></h2>
    <p class="hint">Finds the sweet spot for the current index: where recall is near-max but latency is still low.</p>
    <button id="sweep-btn" class="btn btn-primary">📈 Run sweep</button>
    <span id="sweep-status" class="hint"></span>
    <div id="sweep-wrap" class="hidden" style="margin-top:1rem;">
        <canvas id="sweep-chart" height="120"></canvas>
        <p id="sweep-rec" class="sweep-rec"></p>
    </div>
</div>

<!-- Rebuild panel -->
<div class="tune-card">
    <h2>Rebuild Index <span class="hint">reuses existing embeddings — minutes, not hours</span></h2>

    <div class="slider-row">
        <label for="itype">Index type <span class="tip" data-tip="Flat = exact, slow. IVFFlat = cluster buckets, fast + near-exact (best default at 1.8M vectors). IVFPQ = compressed, smallest/fastest but lossy. HNSW = graph, very fast queries but high RAM.">ⓘ</span></label>
        <select id="itype">
            <option value="ivfflat">IVFFlat — fast, ~exact (recommended)</option>
            <option value="flat">Flat — exact brute force, slowest</option>
            <option value="ivfpq">IVFPQ — compressed, smallest/fastest, lossy</option>
            <option value="hnsw">HNSW — graph, very fast, high RAM</option>
        </select>
    </div>
    <p id="type-desc" class="type-desc"></p>

    <div class="slider-row">
        <label for="metric">Distance metric <span class="tip" data-tip="cosine (recommended): vectors are L2-normalized and compared by inner product — what all-MiniLM / BGE / E5 are trained for. L2: raw Euclidean distance, sensitive to vector magnitude. Switching to cosine is a free retrieval-quality gain (Tier 1 in the Guide).">ⓘ</span></label>
        <select id="metric">
            <option value="ip">Cosine (normalized — recommended)</option>
            <option value="l2">L2 / Euclidean</option>
        </select>
    </div>

    <!-- IVF params -->
    <div class="param-group" data-for="ivfflat ivfpq">
        <div class="slider-row"><label>nlist (clusters) <span class="tip" data-tip="Number of Voronoi clusters the vectors are partitioned into. Rule of thumb ≈ 4·√N ≈ 5,400 for 1.8M vectors. More clusters = finer buckets = faster at equal recall, but slightly longer training.">ⓘ</span>: <strong id="nlist-val">1000</strong></label>
            <input type="range" id="nlist" min="64" max="8192" step="64" value="1000"></div>
        <div class="slider-row"><label>nprobe (default) <span class="tip" data-tip="Default clusters scanned per query, baked into the saved index. You can still override it live with the slider above. Higher = more accurate, slower.">ⓘ</span>: <strong id="bnprobe-val">50</strong></label>
            <input type="range" id="bnprobe" min="1" max="512" value="50"></div>
    </div>
    <!-- PQ params -->
    <div class="param-group hidden" data-for="ivfpq">
        <div class="slider-row"><label>PQ subquantizers (m) <span class="tip" data-tip="Each vector is split into m sub-vectors, each compressed to one byte (at 8 bits). m must divide the dimension (384). Bytes/vector = m, so m=64 → 64 bytes vs 1536 raw (24× smaller). Higher m = more accurate but larger.">ⓘ</span>: <strong id="pqm-val">64</strong></label>
            <input type="range" id="pqm" min="8" max="192" step="8" value="64"></div>
        <div class="slider-row"><label>bits per subquantizer <span class="tip" data-tip="Bits used for each sub-vector's codebook (2^bits centroids). 8 is standard (256 centroids). Lower = smaller and faster but lossier.">ⓘ</span>: <strong id="pqbits-val">8</strong></label>
            <input type="range" id="pqbits" min="4" max="8" value="8"></div>
    </div>
    <!-- HNSW params -->
    <div class="param-group hidden" data-for="hnsw">
        <div class="slider-row"><label>M (neighbors) <span class="tip" data-tip="Edges per node in the graph. Higher M = better recall and faster search but more RAM and slower build. 16–48 is typical; 32 is a good default.">ⓘ</span>: <strong id="hm-val">32</strong></label>
            <input type="range" id="hm" min="8" max="64" step="4" value="32"></div>
        <div class="slider-row"><label>efConstruction <span class="tip" data-tip="Search breadth while BUILDING the graph. Higher = better-quality graph (higher recall) but slower one-time build. 100–400 typical.">ⓘ</span>: <strong id="hefc-val">200</strong></label>
            <input type="range" id="hefc" min="40" max="500" step="10" value="200"></div>
        <div class="slider-row"><label>efSearch (default) <span class="tip" data-tip="Default search breadth at query time (also tunable live above). Higher = more accurate, slower. Must be ≥ k.">ⓘ</span>: <strong id="hefs-val">64</strong></label>
            <input type="range" id="hefs" min="8" max="512" value="64"></div>
    </div>

    <button id="rebuild" class="btn btn-primary">⚙️ Rebuild Index</button>

    <div id="rebuild-progress" class="rebuild-progress hidden">
        <div class="progress-bar"><div id="progress-fill" class="progress-fill"></div></div>
        <p id="progress-msg" class="progress-msg"></p>
    </div>
</div>

<style>
.tune-card { background:#fff; border:1px solid #e0e0e0; border-radius:10px; padding:1.5rem; margin-bottom:1.5rem; }
.tune-card h2 { margin-bottom:1rem; font-size:1.15rem; }
.hint { color:#999; font-weight:400; font-size:0.8rem; }
.status-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:1rem; }
.status-item { display:flex; flex-direction:column; gap:0.25rem; }
.status-item .label { font-size:0.75rem; color:#888; text-transform:uppercase; letter-spacing:0.04em; }
.status-item .value { font-size:1.1rem; font-weight:600; color:#1a1a1a; }
.search-box { display:flex; gap:0.5rem; margin-bottom:1rem; }
.search-input { flex:1; padding:0.7rem 1rem; font-size:1rem; border:2px solid #e0e0e0; border-radius:8px; }
.search-input:focus { outline:none; border-color:#2196F3; }
.sliders { display:flex; flex-direction:column; gap:0.9rem; margin-bottom:1rem; }
.slider-row { display:flex; flex-direction:column; gap:0.35rem; }
.slider-row label { font-size:0.9rem; color:#333; }
.slider-row input[type=range] { width:100%; }
.slider-row select { padding:0.5rem; border:2px solid #e0e0e0; border-radius:6px; font-size:0.95rem; }
.hidden { display:none; }
.latency { padding:0.5rem 0.75rem; background:#eef6ff; border-radius:6px; font-size:0.85rem; color:#1565c0; margin-bottom:1rem; }
.results-list { display:flex; flex-direction:column; gap:0.75rem; }
.result-item { padding:0.9rem; background:#f9f9f9; border:1px solid #e0e0e0; border-left:4px solid #2196F3; border-radius:6px; }
.result-item .rt { font-weight:600; margin-bottom:0.3rem; }
.result-item .rm { font-size:0.8rem; color:#666; margin-bottom:0.4rem; }
.result-item .rp { font-size:0.9rem; color:#333; background:#fff; padding:0.5rem; border-radius:4px; }
.type-desc { font-size:0.85rem; color:#555; background:#f6f6f6; padding:0.6rem 0.8rem; border-radius:6px; margin-bottom:1rem; }
.param-group { border-top:1px dashed #e0e0e0; padding-top:0.9rem; margin-bottom:0.9rem; display:flex; flex-direction:column; gap:0.9rem; }
.rebuild-progress { margin-top:1rem; }
.progress-bar { height:10px; background:#e0e0e0; border-radius:5px; overflow:hidden; }
.progress-fill { height:100%; width:0%; background:#4CAF50; transition:width 0.3s; }
.progress-msg { font-size:0.85rem; color:#555; margin-top:0.5rem; font-family:monospace; }
.btn-primary:disabled { opacity:0.5; cursor:not-allowed; }
/* Info tooltips */
.tip { display:inline-flex; align-items:center; justify-content:center; width:16px; height:16px;
  border-radius:50%; background:#cfe3f7; color:#1565c0; font-size:11px; font-weight:700;
  cursor:help; position:relative; vertical-align:middle; user-select:none; }
.tip:hover { background:#2196F3; color:#fff; }
.tip::after { content:attr(data-tip); position:absolute; bottom:140%; left:50%; transform:translateX(-50%);
  width:260px; background:#1a2733; color:#f0f4f8; font-size:0.78rem; font-weight:400; line-height:1.4;
  padding:0.6rem 0.7rem; border-radius:8px; box-shadow:0 4px 14px rgba(0,0,0,0.25);
  opacity:0; visibility:hidden; transition:opacity 0.15s; z-index:50; text-align:left; pointer-events:none; }
.tip:hover::after { opacity:1; visibility:visible; }
.sweep-rec { margin-top:0.75rem; padding:0.6rem 0.8rem; background:#e8f5e9; border-radius:6px;
  font-size:0.88rem; color:#2e7d32; }
.sweep-rec.warn { background:#fff3e0; color:#b26a00; }
</style>

<script>
const TYPE_DESC = {
  flat:   "Exact brute-force search. 100% accurate, no tuning, but slowest at 1.8M vectors. This is what you run now.",
  ivfflat:"Partitions vectors into nlist clusters and searches the nprobe nearest ones. 5–10x faster than Flat, near-exact. Tune nprobe live for the accuracy/speed tradeoff.",
  ivfpq:  "IVF clustering plus Product Quantization compression. Smallest on disk and fastest, but quantization loses some accuracy. Larger pq_m / nbits = more accurate but bigger.",
  hnsw:   "Multi-layer proximity graph. Very fast queries and high accuracy, but uses a lot of RAM and builds slower. Tune efSearch live."
};

let liveInfo = {};

async function loadStatus() {
  const r = await fetch('/api/index-params');
  const d = await r.json();
  liveInfo = d.live || {};
  document.getElementById('cur-type').textContent = liveInfo.index_type || '—';
  document.getElementById('cur-metric').textContent = liveInfo.metric ? (liveInfo.metric === 'cosine' ? 'Cosine' : 'L2') : '—';
  document.getElementById('cur-ntotal').textContent = liveInfo.ntotal ? liveInfo.ntotal.toLocaleString() : '—';
  document.getElementById('cur-size').textContent = d.build && d.build.index_size_gb ? d.build.index_size_gb + ' GB' : '—';
  document.getElementById('cur-acc').textContent = d.build && d.build.accuracy_vs_flat_pct != null ? d.build.accuracy_vs_flat_pct + '%' : '—';

  // Show the right live slider for the current index type
  const isIVF = (liveInfo.tunable||[]).includes('nprobe');
  const isHNSW = (liveInfo.tunable||[]).includes('ef_search');
  document.getElementById('nprobe-row').classList.toggle('hidden', !isIVF);
  document.getElementById('ef-row').classList.toggle('hidden', !isHNSW);
  let note = "";
  if (isIVF) { document.getElementById('nprobe').value = liveInfo.nprobe || 50; document.getElementById('nprobe-val').textContent = liveInfo.nprobe || 50;
    if (liveInfo.nlist) document.getElementById('nprobe').max = liveInfo.nlist; }
  if (isHNSW) { document.getElementById('ef').value = liveInfo.ef_search || 64; document.getElementById('ef-val').textContent = liveInfo.ef_search || 64; }
  if (!isIVF && !isHNSW) note = "This index type (" + (liveInfo.index_type||'?') + ") has no live tuning knobs — only k. Switch to IVFFlat or HNSW below to tune accuracy vs speed live.";
  document.getElementById('tune-note').textContent = note;
}

// slider value labels
function bindVal(id, valId) { const el=document.getElementById(id); const v=document.getElementById(valId);
  el.addEventListener('input',()=>v.textContent=el.value); }
['k:k-val','nprobe:nprobe-val','ef:ef-val','nlist:nlist-val','bnprobe:bnprobe-val',
 'pqm:pqm-val','pqbits:pqbits-val','hm:hm-val','hefc:hefc-val','hefs:hefs-val']
 .forEach(p=>{const [a,b]=p.split(':');bindVal(a,b);});

async function doSearch() {
  const query = document.getElementById('q').value.trim();
  if (!query) return;
  const body = { query, k: parseInt(document.getElementById('k').value) };
  if (!document.getElementById('nprobe-row').classList.contains('hidden')) body.nprobe = parseInt(document.getElementById('nprobe').value);
  if (!document.getElementById('ef-row').classList.contains('hidden')) body.ef_search = parseInt(document.getElementById('ef').value);

  const t0 = performance.now();
  const r = await fetch('/api/search', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
  const ms = (performance.now()-t0).toFixed(0);
  const d = await r.json();
  if (d.error) { alert(d.error); return; }

  const lat = document.getElementById('latency');
  lat.classList.remove('hidden');
  lat.textContent = `⏱ ${ms} ms · ${d.results.length} results · index ${d.index_info ? d.index_info.index_type : ''}` +
    (body.nprobe!=null ? ` · nprobe ${body.nprobe}` : '') + (body.ef_search!=null ? ` · efSearch ${body.ef_search}` : '');

  const list = document.getElementById('results-list'); list.innerHTML='';
  d.results.forEach(x=>{ const el=document.createElement('div'); el.className='result-item';
    el.innerHTML = `<div class="rt">[${x.rank}] ${esc(x.title)}</div>
      <div class="rm">${esc(x.file.split('/').pop())} · chunk ${x.chunk} · ${(x.similarity*100).toFixed(1)}% match</div>
      <div class="rp">${esc(x.preview)}</div>`; list.appendChild(el); });
}
function esc(t){const d=document.createElement('div');d.textContent=t;return d.innerHTML;}

document.getElementById('go').addEventListener('click', doSearch);
document.getElementById('q').addEventListener('keypress', e=>{ if(e.key==='Enter') doSearch(); });
// re-run search automatically when tuning sliders move (debounced)
let deb; ['nprobe','ef','k'].forEach(id=>document.getElementById(id).addEventListener('input',()=>{
  clearTimeout(deb); deb=setTimeout(()=>{ if(document.getElementById('q').value.trim()) doSearch(); }, 350); }));

// Rebuild panel: show params per type
function refreshType() {
  const t = document.getElementById('itype').value;
  document.getElementById('type-desc').textContent = TYPE_DESC[t];
  document.querySelectorAll('.param-group').forEach(g=>{
    g.classList.toggle('hidden', !g.dataset.for.split(' ').includes(t));
  });
}
document.getElementById('itype').addEventListener('change', refreshType);

document.getElementById('rebuild').addEventListener('click', async ()=>{
  const t = document.getElementById('itype').value;
  const opts = { index_type: t, metric: document.getElementById('metric').value };
  if (t==='ivfflat'||t==='ivfpq') { opts.nlist=+document.getElementById('nlist').value; opts.nprobe=+document.getElementById('bnprobe').value; }
  if (t==='ivfpq') { opts.pq_m=+document.getElementById('pqm').value; opts.pq_nbits=+document.getElementById('pqbits').value; }
  if (t==='hnsw') { opts.hnsw_m=+document.getElementById('hm').value; opts.hnsw_efc=+document.getElementById('hefc').value; opts.hnsw_efs=+document.getElementById('hefs').value; }

  if (!confirm(`Rebuild as ${t.toUpperCase()}? The current index is backed up first.`)) return;
  const btn = document.getElementById('rebuild'); btn.disabled=true;
  const r = await fetch('/api/rebuild-index',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(opts)});
  const d = await r.json();
  if (d.error) { alert(d.error); btn.disabled=false; return; }
  document.getElementById('rebuild-progress').classList.remove('hidden');
  pollProgress(btn);
});

async function pollProgress(btn) {
  const r = await fetch('/api/indexing-status'); const s = await r.json();
  document.getElementById('progress-fill').style.width = (s.progress||0)+'%';
  document.getElementById('progress-msg').textContent = s.message||'';
  if (s.indexing) { setTimeout(()=>pollProgress(btn), 800); }
  else { btn.disabled=false; loadStatus(); }
}

// ---- Recall vs latency sweep ----
let sweepChart = null;
document.getElementById('sweep-btn').addEventListener('click', async ()=>{
  const btn = document.getElementById('sweep-btn');
  const status = document.getElementById('sweep-status');
  btn.disabled = true; status.textContent = ' running sweep…';
  // Use the typed query if present, else the server samples chunk previews.
  const typed = document.getElementById('q').value.trim();
  const body = { k: 10 };
  if (typed) body.queries = [typed];
  try {
    const r = await fetch('/api/nprobe-sweep', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });
    const d = await r.json();
    if (d.error) { alert(d.error); return; }
    if (!d.supported) { status.textContent = ` ${liveInfo.index_type} has no sweepable parameter — only IVF (nprobe) and HNSW (efSearch).`; return; }
    renderSweep(d);
    status.textContent = ` ${d.n_queries} queries · param: ${d.param}`;
  } catch(e) { alert('Sweep failed: ' + e.message); }
  finally { btn.disabled = false; }
});

function renderSweep(d) {
  document.getElementById('sweep-wrap').classList.remove('hidden');
  const labels = d.points.map(p=>p.x);
  const recall = d.points.map(p=>p.recall);
  const latency = d.points.map(p=>p.latency_ms);

  // --- Efficiency elbow (Kneedle): the point of maximum recall gain relative
  // to latency spent, i.e. where the curve stops paying off. Computed as the
  // max vertical distance above the chord on the normalized recall-vs-latency
  // curve. This beats "99% of max", which lands deep in the expensive tail. ---
  const recMin = Math.min(...recall), recMax = Math.max(...recall);
  const latMin = Math.min(...latency), latMax = Math.max(...latency);
  const norm = (v, a, b) => (b > a ? (v - a) / (b - a) : 0);
  let kneeIdx = 0, best = -Infinity;
  d.points.forEach((p, i) => {
    const dist = norm(p.recall, recMin, recMax) - norm(p.latency_ms, latMin, latMax);
    if (dist > best) { best = dist; kneeIdx = i; }
  });
  const knee = d.points[kneeIdx];
  // Near-exact option: smallest value reaching >=99% of the max recall.
  let hiIdx = d.points.findIndex(p => p.recall >= recMax * 0.99);
  if (hiIdx < 0) hiIdx = d.points.length - 1;
  const hi = d.points[hiIdx];

  const rec = document.getElementById('sweep-rec');
  rec.classList.remove('warn');
  const exactBit = (hiIdx > kneeIdx)
    ? ` &nbsp;·&nbsp; Near-exact: <strong>${d.param} ${hi.x}</strong> → ${hi.recall}% at ${hi.latency_ms} ms.`
    : '';
  rec.innerHTML = `✓ Efficiency elbow: <strong>${d.param} = ${knee.x}</strong> → ${knee.recall}% recall at ${knee.latency_ms} ms/query ` +
    `(best recall per ms — beyond here each extra ms buys little).${exactBit} ` +
    `Bake one in by rebuilding with that ${d.param}` + (d.param === 'nprobe' && d.nlist ? ` (nlist ${d.nlist})` : '') + `.`;

  // Mark the elbow (orange) and near-exact (green) points on the recall line.
  const ptRadius = d.points.map((_, i) => (i === kneeIdx || i === hiIdx) ? 7 : 3);
  const ptColor = d.points.map((_, i) => i === kneeIdx ? '#e65100' : (i === hiIdx ? '#1b5e20' : '#2e7d32'));

  if (sweepChart) sweepChart.destroy();
  const ctx = document.getElementById('sweep-chart').getContext('2d');
  sweepChart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets: [
      { label: 'Recall %', data: recall, yAxisID: 'y', borderColor: '#2e7d32', backgroundColor:'#2e7d3222', tension:0.3, pointRadius:ptRadius, pointBackgroundColor:ptColor, fill:true },
      { label: 'Latency ms/query', data: latency, yAxisID: 'y1', borderColor: '#1565c0', backgroundColor:'transparent', tension:0.3, pointRadius:4 }
    ]},
    options: {
      responsive:true,
      interaction:{ mode:'index', intersect:false },
      plugins:{ legend:{ position:'top' },
        annotation:false,
        title:{ display:true, text:`Recall vs latency across ${d.param}` } },
      scales:{
        x:{ title:{ display:true, text:d.param + (d.param==='nprobe'&&d.nlist?` (of ${d.nlist} clusters)`:'') } },
        y:{ type:'linear', position:'left', min:0, max:100, title:{ display:true, text:'Recall %' } },
        y1:{ type:'linear', position:'right', min:0, title:{ display:true, text:'Latency ms/query' }, grid:{ drawOnChartArea:false } }
      }
    }
  });
}

refreshType();
loadStatus();
</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
{% endblock %}

```

### `templates/guide.html`

```html
{% extends 'base.html' %}

{% block title %}Guide - Alexandria RAG{% endblock %}

{% block content %}
<div class="page-header">
    <h1>Optimization Guide</h1>
    <p class="subtitle">Recommendations for improving retrieval quality, ordered by payoff-to-effort.</p>
</div>

<div class="guide-summary">
    <strong>System today:</strong> 3,595 books → 1.81M chunks · <code>all-MiniLM-L6-v2</code> (384-dim) ·
    IVFFlat (nlist 1000, nprobe 50) · 2.8 GB index. The crash and speed are solved — this is about
    getting the <em>right</em> passages back, plus housekeeping that makes future changes cheap.
</div>

<!-- TIER 1 -->
<div class="tier">
    <div class="tier-head"><span class="badge t1">Tier 1</span> Quick wins — hours, high impact</div>

    <div class="rec done">
        <h3>1. Cosine similarity (normalize + inner product) <span class="chip">Implemented</span></h3>
        <p>MiniLM is trained for cosine, but the old index used un-normalized L2, letting vector
        magnitude distort ranking. Embeddings are now L2-normalized and indexes built with inner
        product, so scores are true cosine in [-1, 1]. Set <strong>Distance metric → Cosine</strong>
        on the Tuning tab and rebuild to apply it to your current index (seconds, no re-embed).</p>
    </div>

    <div class="rec done">
        <h3>2. Fix silent chunk truncation <span class="chip">Implemented</span></h3>
        <p>Chunks were 256 <em>words</em>, but MiniLM's tokenizer caps at 256 <em>subword tokens</em>
        (~1.3 per word), so the model dropped ~25% of every chunk before embedding. Chunk size is now
        200 words to stay under the limit. Takes effect on the next full re-embed.</p>
    </div>

    <div class="rec">
        <h3>3. Tune the IVF grid</h3>
        <p>At 1.8M vectors the rule of thumb is <code>nlist ≈ 4·√N ≈ 5,400</code> — more, smaller
        clusters hit the same recall while scanning fewer vectors. Rebuild with <strong>nlist 4096</strong>
        on the Tuning tab, then drag <strong>nprobe</strong> to find the knee (likely 16–32 for ≥98%).</p>
    </div>
</div>

<!-- TIER 2 -->
<div class="tier">
    <div class="tier-head"><span class="badge t2">Tier 2</span> Bigger quality levers — a day each</div>

    <div class="rec">
        <h3>4. Persist full chunk text <span class="chip warn">Gap</span></h3>
        <p>Metadata stores only a 200-character preview; the full passage text isn't saved anywhere.
        For a RAG that feeds an LLM, this is the critical gap — you can find a hit but can't hand the
        model the full passage. Store full chunk text keyed by chunk id (SQLite or parquet). This also
        unlocks reranking (#5).</p>
    </div>

    <div class="rec">
        <h3>5. Add a cross-encoder reranker</h3>
        <p>Retrieve top-50 from FAISS, then re-score with a cross-encoder that reads query + passage
        together (<code>BAAI/bge-reranker-base</code>). Usually the largest precision jump in a RAG
        pipeline. ~50–150 ms per query, only on candidates.</p>
    </div>

    <div class="rec">
        <h3>6. Hybrid search (dense + BM25)</h3>
        <p>Dense embeddings miss exact terms — proper nouns, titles, rare jargon. A book library is
        full of those. Add SQLite <strong>FTS5</strong> (built in) or <code>rank_bm25</code> and fuse
        with dense results via Reciprocal Rank Fusion.</p>
    </div>

    <div class="rec">
        <h3>7. Move metadata out of an 851 MB JSON</h3>
        <p>The whole metadata file loads into RAM on every startup, with linear-scan lookups. A SQLite
        table keyed by chunk id gives O(1) lookups and low memory — the same store you'd use for #4 and #6.</p>
    </div>
</div>

<!-- TIER 3 -->
<div class="tier">
    <div class="tier-head"><span class="badge t3">Tier 3</span> Bigger bets — if quality still matters</div>

    <div class="rec">
        <h3>8. Upgrade the embedding model</h3>
        <p>At the <em>same</em> 384 dims (index size unchanged), <code>BAAI/bge-small-en-v1.5</code> and
        <code>thenlper/gte-small</code> rank well above MiniLM on MTEB. <code>bge-base-en-v1.5</code>
        (768d) is better still but doubles size. bge/e5 need a query prefix. Cost: a full re-embed —
        cheap if you've done #9.</p>
    </div>

    <div class="rec">
        <h3>9. Cache extracted text</h3>
        <p>PDF extraction is the 13-hour bottleneck; embedding is only ~40 min. Nothing currently
        persists extracted text, so every model or chunking experiment re-pays the 13 hours. Cache it
        once and re-embedding becomes a 40-minute job. This is what makes everything else iterable.</p>
    </div>

    <div class="rec">
        <h3>10. Incremental indexing</h3>
        <p>Adding one book currently means a full rebuild. Use <code>IndexIDMap</code> + <code>add_with_ids</code>
        with a manifest of indexed files, so new books append and removed books get filtered.</p>
    </div>

    <div class="rec">
        <h3>11. Memory-map the index</h3>
        <p>2.8 GB loads fully into RAM at startup. <code>faiss.read_index(path, faiss.IO_FLAG_MMAP)</code>
        maps it instead — lighter footprint on a laptop, negligible speed cost for IVFFlat.</p>
    </div>
</div>

<!-- META -->
<div class="tier meta">
    <div class="tier-head"><span class="badge tm">Measure</span> The meta-recommendation</div>
    <div class="rec">
        <p>You can't optimize what you don't measure, and "98.6% recall" is recall against <em>Flat</em>,
        not against the <em>right answer</em>. Build a small gold set — 30–50 real questions, each tagged
        with the passage that should win — and script <code>recall@k</code> and <code>MRR</code>. Then
        every change becomes a number, not a guess.</p>
        <p class="order"><strong>Suggested order:</strong> #1 + #2 (done) → build the eval set → #9
        (unlocks iteration) → #4 + #7 + #5 (the RAG-quality core) → re-measure → decide on #8.</p>
    </div>
</div>

<style>
.guide-summary { background:#eef6ff; border:1px solid #cfe3f7; border-radius:10px; padding:1rem 1.25rem;
  margin-bottom:1.5rem; font-size:0.92rem; line-height:1.5; color:#234; }
.guide-summary code, .rec code { background:#eef1f4; padding:0.05rem 0.35rem; border-radius:4px; font-size:0.86em; }
.tier { margin-bottom:1.75rem; }
.tier-head { font-size:1.05rem; font-weight:700; margin-bottom:0.85rem; display:flex; align-items:center; gap:0.6rem; }
.badge { color:#fff; font-size:0.7rem; font-weight:700; letter-spacing:0.04em; padding:0.18rem 0.55rem;
  border-radius:20px; text-transform:uppercase; }
.badge.t1 { background:#2e7d32; } .badge.t2 { background:#1565c0; } .badge.t3 { background:#6a1b9a; }
.badge.tm { background:#b26a00; }
.rec { background:#fff; border:1px solid #e0e0e0; border-left:4px solid #2196F3; border-radius:8px;
  padding:1rem 1.1rem; margin-bottom:0.85rem; }
.rec.done { border-left-color:#4CAF50; }
.rec h3 { font-size:0.98rem; margin-bottom:0.4rem; display:flex; align-items:center; gap:0.6rem; flex-wrap:wrap; }
.rec p { font-size:0.9rem; color:#333; line-height:1.55; margin-bottom:0.4rem; }
.rec p:last-child { margin-bottom:0; }
.chip { font-size:0.68rem; font-weight:700; background:#e8f5e9; color:#2e7d32; padding:0.12rem 0.5rem; border-radius:20px; }
.chip.warn { background:#fff3e0; color:#b26a00; }
.meta .rec { border-left-color:#b26a00; }
.order { margin-top:0.6rem; padding-top:0.6rem; border-top:1px dashed #e0e0e0; }
</style>
{% endblock %}

```

### `templates/books.html`

```html
{% extends 'base.html' %}

{% block title %}Books - Alexandria RAG{% endblock %}

{% block content %}
<div class="page-header">
    <h1>Indexed Books</h1>
    <p class="subtitle">Browse your book collection</p>
</div>

<div class="books-container">
    <div class="search-filter">
        <input
            type="text"
            id="filter-input"
            class="filter-input"
            placeholder="Filter books..."
        >
    </div>

    <div id="books-info" class="books-info">
        Total: <span id="books-total">0</span> books
    </div>

    <div id="books-grid" class="books-grid">
        <!-- Books will be loaded here -->
    </div>

    <div id="loading" class="loading-state">
        <p>Loading books...</p>
    </div>

    <div id="no-books" class="empty-state hidden">
        <div class="empty-icon">📚</div>
        <h2>No Books Indexed</h2>
        <p>Build an index first to see your books here.</p>
        <a href="/indexing" class="btn btn-primary">Build Index</a>
    </div>
</div>

<style>
.books-container {
    max-width: 1200px;
}

.search-filter {
    margin-bottom: 1.5rem;
}

.filter-input {
    width: 100%;
    padding: 0.75rem 1rem;
    font-size: 1rem;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    font-family: inherit;
}

.filter-input:focus {
    outline: none;
    border-color: #2196F3;
    box-shadow: 0 0 0 3px rgba(33, 150, 243, 0.1);
}

.books-info {
    color: #666;
    font-size: 0.9rem;
    margin-bottom: 1rem;
}

.books-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1.5rem;
}

.book-card {
    background: white;
    padding: 1.25rem;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    transition: all 0.2s;
}

.book-card:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    border-color: #2196F3;
    transform: translateY(-2px);
}

.book-icon {
    font-size: 2.5rem;
    margin-bottom: 0.5rem;
}

.book-title {
    font-weight: 600;
    color: #1a1a1a;
    margin-bottom: 0.5rem;
    word-break: break-word;
}

.book-stats {
    display: flex;
    gap: 1rem;
    font-size: 0.85rem;
    color: #666;
}

.book-stat {
    display: flex;
    align-items: center;
    gap: 0.25rem;
}

.loading-state {
    text-align: center;
    padding: 3rem 1rem;
    color: #999;
}

.empty-state {
    text-align: center;
    padding: 3rem 1rem;
}

.empty-state.hidden {
    display: none;
}

.empty-icon {
    font-size: 3rem;
    opacity: 0.6;
    margin-bottom: 1rem;
}
</style>

<script>
let allBooks = [];

async function loadBooks() {
    try {
        const response = await fetch('/api/books');
        const data = await response.json();

        if (data.books && data.books.length > 0) {
            allBooks = data.books;
            displayBooks(allBooks);
            document.getElementById('loading').style.display = 'none';
            document.getElementById('books-grid').style.display = 'grid';
            document.getElementById('no-books').classList.add('hidden');
        } else {
            document.getElementById('loading').style.display = 'none';
            document.getElementById('books-grid').style.display = 'none';
            document.getElementById('no-books').classList.remove('hidden');
        }
    } catch (error) {
        document.getElementById('loading').innerHTML = '<p style="color: #f44336;">Error loading books</p>';
    }
}

function displayBooks(books) {
    const grid = document.getElementById('books-grid');
    const total = document.getElementById('books-total');
    grid.innerHTML = '';
    total.textContent = books.length;

    books.forEach(book => {
        const card = document.createElement('div');
        card.className = 'book-card';

        const fileName = book.file.split('/').pop();

        card.innerHTML = `
            <div class="book-icon">📖</div>
            <div class="book-title">${escapeHtml(book.title)}</div>
            <div class="book-stats">
                <div class="book-stat">📄 ${fileName}</div>
                <div class="book-stat">📑 ${book.chunks} chunks</div>
            </div>
        `;

        grid.appendChild(card);
    });
}

function filterBooks() {
    const query = document.getElementById('filter-input').value.toLowerCase();
    const filtered = allBooks.filter(book =>
        book.title.toLowerCase().includes(query) ||
        book.file.toLowerCase().includes(query)
    );
    displayBooks(filtered);
}

document.getElementById('filter-input').addEventListener('input', filterBooks);

// Load books on page load
loadBooks();

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
</script>
{% endblock %}

```

### `templates/404.html`

```html
{% extends 'base.html' %}

{% block title %}Not Found - Alexandria RAG{% endblock %}

{% block content %}
<div class="page-header">
    <h1>404 — Not Found</h1>
    <p class="subtitle">That page doesn't exist.</p>
</div>
<p><a href="/" class="btn btn-primary">← Back to Dashboard</a></p>
{% endblock %}

```

### `templates/500.html`

```html
{% extends 'base.html' %}

{% block title %}Error - Alexandria RAG{% endblock %}

{% block content %}
<div class="page-header">
    <h1>500 — Server Error</h1>
    <p class="subtitle">Something went wrong. Check the terminal running app.py for details.</p>
</div>
<p><a href="/" class="btn btn-primary">← Back to Dashboard</a></p>
{% endblock %}

```

### `static/style.css`

```css
/* Alexandria RAG - Global Styles */

:root {
    --primary-color: #2196F3;
    --primary-dark: #1976D2;
    --secondary-color: #4CAF50;
    --danger-color: #f44336;
    --background: #f5f5f5;
    --surface: #ffffff;
    --text-primary: #1a1a1a;
    --text-secondary: #666666;
    --border-color: #e0e0e0;
    --shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    --shadow-lg: 0 4px 12px rgba(0, 0, 0, 0.15);
}

* {
    box-sizing: border-box;
}

html, body {
    margin: 0;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: var(--background);
    color: var(--text-primary);
}

/* Layout */
.app-container {
    display: flex;
    height: 100vh;
}

/* Sidebar */
.sidebar {
    width: 280px;
    background: var(--surface);
    border-right: 1px solid var(--border-color);
    padding: 1.5rem 0;
    overflow-y: auto;
    position: fixed;
    height: 100vh;
    left: 0;
    top: 0;
}

.sidebar-header {
    padding: 0 1.5rem 1.5rem;
    border-bottom: 1px solid var(--border-color);
}

.app-title {
    margin: 0 0 0.25rem 0;
    font-size: 1.5rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.app-subtitle {
    margin: 0;
    font-size: 0.85rem;
    color: var(--text-secondary);
}

.nav-menu {
    list-style: none;
    margin: 0;
    padding: 0.5rem 0;
}

.nav-link {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1.5rem;
    color: var(--text-secondary);
    text-decoration: none;
    transition: all 0.2s;
    font-size: 0.95rem;
}

.nav-link:hover {
    background: var(--background);
    color: var(--primary-color);
}

.nav-link.active {
    background: linear-gradient(90deg, var(--primary-color), transparent);
    color: var(--primary-color);
    font-weight: 600;
    border-right: 3px solid var(--primary-color);
}

.nav-link .icon {
    font-size: 1.2rem;
}

.sidebar-footer {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 1.5rem;
    border-top: 1px solid var(--border-color);
    text-align: center;
}

.footer-text {
    margin: 0;
    font-size: 0.8rem;
    color: var(--text-secondary);
}

/* Main Content */
.main-content {
    margin-left: 280px;
    flex: 1;
    overflow-y: auto;
    background: var(--background);
}

.content-wrapper {
    padding: 2rem;
    max-width: 1400px;
    margin: 0 auto;
}

/* Page Header */
.page-header {
    margin-bottom: 2rem;
}

.page-header h1 {
    margin: 0 0 0.5rem 0;
    font-size: 2rem;
    font-weight: 700;
}

.page-header .subtitle {
    margin: 0;
    color: var(--text-secondary);
    font-size: 1rem;
}

/* Buttons */
.btn {
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 6px;
    font-size: 0.95rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    text-decoration: none;
    white-space: nowrap;
}

.btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.btn-primary {
    background: var(--primary-color);
    color: white;
}

.btn-primary:hover:not(:disabled) {
    background: var(--primary-dark);
    box-shadow: var(--shadow);
}

.btn-secondary {
    background: var(--background);
    color: var(--primary-color);
    border: 2px solid var(--border-color);
}

.btn-secondary:hover:not(:disabled) {
    border-color: var(--primary-color);
    background: rgba(33, 150, 243, 0.05);
}

.btn-danger {
    background: var(--danger-color);
    color: white;
}

.btn-danger:hover:not(:disabled) {
    background: #da190b;
    box-shadow: var(--shadow);
}

/* Stats Grid */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1.5rem;
    margin-bottom: 2rem;
}

.stat-card {
    background: var(--surface);
    padding: 1.5rem;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    gap: 1rem;
    transition: all 0.2s;
}

.stat-card:hover {
    box-shadow: var(--shadow-lg);
    border-color: var(--primary-color);
}

.stat-icon {
    font-size: 2.5rem;
    flex-shrink: 0;
}

.stat-content {
    flex: 1;
}

.stat-content h3 {
    margin: 0 0 0.5rem 0;
    font-size: 0.9rem;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.stat-value {
    margin: 0;
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--primary-color);
}

.stat-detail {
    margin: 0.25rem 0 0 0;
    font-size: 0.85rem;
    color: var(--text-secondary);
}

.stat-detail a {
    color: var(--primary-color);
    text-decoration: none;
}

.stat-detail a:hover {
    text-decoration: underline;
}

/* Quick Actions */
.quick-actions {
    background: var(--surface);
    padding: 2rem;
    border-radius: 8px;
    margin-bottom: 2rem;
}

.quick-actions h2 {
    margin-top: 0;
}

.action-buttons {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
}

.action-buttons .btn {
    padding: 0.75rem 1.5rem;
}

/* Features Section */
.features-section {
    background: var(--surface);
    padding: 2rem;
    border-radius: 8px;
    margin-bottom: 2rem;
}

.features-section h2 {
    margin-top: 0;
}

.features-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 1.5rem;
}

.feature {
    padding: 1.5rem;
    background: var(--background);
    border-radius: 6px;
    text-align: center;
}

.feature-icon {
    font-size: 2.5rem;
    margin-bottom: 0.75rem;
}

.feature h3 {
    margin: 0 0 0.5rem 0;
    font-size: 1rem;
}

.feature p {
    margin: 0;
    color: var(--text-secondary);
    font-size: 0.9rem;
    line-height: 1.5;
}

/* Tables and Lists */
table {
    width: 100%;
    border-collapse: collapse;
}

th {
    background: var(--background);
    padding: 0.75rem;
    text-align: left;
    font-weight: 600;
    color: var(--text-primary);
    border-bottom: 2px solid var(--border-color);
}

td {
    padding: 0.75rem;
    border-bottom: 1px solid var(--border-color);
}

tr:hover {
    background: var(--background);
}

/* Forms */
input, select, textarea {
    font-family: inherit;
    font-size: 1rem;
    color: var(--text-primary);
}

input:focus, select:focus, textarea:focus {
    outline: none;
}

/* Scrollbar */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: transparent;
}

::-webkit-scrollbar-thumb {
    background: var(--border-color);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: #bbb;
}

/* Responsive */
@media (max-width: 768px) {
    .sidebar {
        transform: translateX(-100%);
        z-index: 100;
        transition: transform 0.2s;
    }

    .main-content {
        margin-left: 0;
    }

    .content-wrapper {
        padding: 1rem;
    }

    .page-header h1 {
        font-size: 1.5rem;
    }

    .stats-grid {
        grid-template-columns: 1fr;
    }

    .features-grid {
        grid-template-columns: 1fr;
    }

    .action-buttons {
        flex-direction: column;
    }

    .action-buttons .btn {
        width: 100%;
        justify-content: center;
    }
}

/* Utility Classes */
.hidden {
    display: none !important;
}

.text-center {
    text-align: center;
}

.text-muted {
    color: var(--text-secondary);
}

.mt-1 { margin-top: 0.5rem; }
.mt-2 { margin-top: 1rem; }
.mt-3 { margin-top: 1.5rem; }
.mb-1 { margin-bottom: 0.5rem; }
.mb-2 { margin-bottom: 1rem; }
.mb-3 { margin-bottom: 1.5rem; }

/* Print Styles */
@media print {
    .sidebar, .page-header {
        display: none;
    }

    .main-content {
        margin-left: 0;
    }
}

```

### `static/script.js`

```javascript
/* Alexandria RAG - Shared JavaScript */

// API Helper
async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' }
    };

    if (data && method !== 'GET') {
        options.body = JSON.stringify(data);
    }

    const response = await fetch(endpoint, options);

    if (!response.ok) {
        const error = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(error.error || `HTTP ${response.status}`);
    }

    return await response.json();
}

// Utility Functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatDate(isoString) {
    if (!isoString) return 'Never';
    return new Date(isoString).toLocaleString();
}

// Notifications
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <p>${escapeHtml(message)}</p>
        <button onclick="this.parentElement.remove()">×</button>
    `;
    document.body.appendChild(notification);

    setTimeout(() => notification.remove(), 5000);
}

// Add notification styles if not already there
if (!document.querySelector('style[data-notifications]')) {
    const style = document.createElement('style');
    style.setAttribute('data-notifications', 'true');
    style.textContent = `
        .notification {
            position: fixed;
            top: 1rem;
            right: 1rem;
            padding: 1rem;
            border-radius: 6px;
            background: white;
            border-left: 4px solid #2196F3;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            max-width: 400px;
            z-index: 9999;
            animation: slideIn 0.3s ease;
        }

        .notification p {
            margin: 0;
        }

        .notification button {
            position: absolute;
            top: 0.5rem;
            right: 0.5rem;
            background: none;
            border: none;
            font-size: 1.5rem;
            cursor: pointer;
            color: #999;
        }

        .notification-success {
            border-left-color: #4CAF50;
        }

        .notification-error {
            border-left-color: #f44336;
        }

        .notification-warning {
            border-left-color: #FFA500;
        }

        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        @media (max-width: 768px) {
            .notification {
                right: 0.5rem;
                left: 0.5rem;
                max-width: none;
            }
        }
    `;
    document.head.appendChild(style);
}

// Debug Helper
function debug(message, data = null) {
    if (typeof console !== 'undefined') {
        console.log('[Alexandria RAG]', message, data || '');
    }
}

// Export for use in templates
window.apiCall = apiCall;
window.escapeHtml = escapeHtml;
window.formatBytes = formatBytes;
window.formatDate = formatDate;
window.showNotification = showNotification;
window.debug = debug;

```

### `run-ui.sh`

```bash
#!/bin/bash
# Run Alexandria RAG Web UI

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "======================================"
echo "Alexandria RAG - Web UI"
echo "======================================"

# Check if virtual environment exists
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Virtual environment not found."
    echo "Running setup..."
    cd "$SCRIPT_DIR"
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -r requirements.txt
else
    source "$SCRIPT_DIR/venv/bin/activate"
fi

echo ""
echo "Starting web UI..."
echo "Access it at: http://127.0.0.1:5050"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$SCRIPT_DIR"
python app.py

```

### `run_mcp.sh`

```bash
#!/bin/bash
cd /Volumes/PRO-BLADE/Alexandria/RAG_system
source rag_env/bin/activate
python alexandria_mcp_server.py

```

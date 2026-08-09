# ClaudeLLM — a private, local-first research stack for Claude

Turn a Mac (or Windows PC) into a **local research library that Claude can search directly** — no subscriptions, no per-query fees, and your library stays on your own disk.

Being precise about that last part, because it is a privacy claim and privacy claims should be exact: the corpora and the search index live on your drive and never leave it, and the embedding and retrieval run on your own hardware. Claude itself is a cloud model, so the passages a search returns do travel to it as context — the same as anything you paste into a chat. What you avoid is uploading your library. What you do not avoid is Claude reading the excerpts it retrieves.

It's two things working together:

1. **A local RAG** — semantic search over *your own* PDF/EPUB library (meaning-based, not keyword), with a web dashboard to add books, health-check them, and tune the search.
2. **Ten MCP servers** — full-text-searchable corpora, held locally and usable without an internet connection once built, that Claude Desktop / Cowork can query as tools: scriptures, classical Greek & Latin, papyri, ancient places, all of Wikipedia, Project Gutenberg, and more.

## The easy way: let Claude build it for you

You don't need to follow the guides by hand. **Open Claude Cowork (or Claude Desktop), and give it [`BOOTSTRAP.md`](./BOOTSTRAP.md)** — that file tells Claude to interview you (what computer you have, what you want to search, your experience level) and then set the whole thing up with you, step by step. It works on **macOS and Windows**.

> New to this? That's the intended audience. Drop in `BOOTSTRAP.md` and answer Claude's questions.

## What's in here (code only — no data)

```
BOOTSTRAP.md         ← give this to Claude to build the stack
docs/                ← the detailed human guides
rag/                 ← the local PDF-library RAG + web dashboard
servers/             ← the 10 MCP servers, each with its build script
  scriptures/  latin/  greek/  perseus/  papyri/
  pleiades/    wikipedia/  wikispooks/  gutenberg/  atlas/
dashboard/           ← optional macOS control panel (author's example)
```

**No texts are included.** Every `build_*.py` / `download_*.py` fetches its corpus from the original source, on *your* machine, at build time. This keeps the repo small and keeps each corpus under its own license.

## The corpora (and licenses)

| Server | What it searches | License |
|---|---|---|
| `scriptures` | Qur'an, 1 Enoch, Tanakh, Talmud, Mishnah, **Ethiopian (Tewahedo) canon** + BDB/Jastrow/Lane lexicons | mixed — see below |
| `latin` | Latin classics (Perseus TEI) + **Lewis & Short** dictionary | CC BY-SA / PD |
| `greek` | Greek NT/LXX, LSJ + Middle Liddell | open corpora |
| `perseus` | Complete Perseus canonical library (156 authors, 2,299 texts) | CC BY-SA |
| `papyri` | ~67,600 documentary papyri (Duke Databank) | CC BY |
| `pleiades` | 42,300 ancient places, coords + dating | CC BY |
| `wikipedia` | All of Wikipedia, offline (Kiwix) | CC BY-SA |
| `gutenberg` | ~78,000 public-domain books, by subject | Public domain |
| `wikispooks` | WikiSpooks wiki (~37.7k articles) | verify before republishing |
| `atlas` | Geo-temporal place database (DuckDB) | CC BY (from Pleiades) |

**Licensing matters for republishing.** Most corpora are public domain or CC BY/BY-SA (free to use with credit). **The Sefaria layers of the Tanakh, Talmud, and Mishnah are CC BY-NC — personal research only, not for resale.** Every result the servers return is stamped with its license so you always know. See [`LICENSE`](./LICENSE).

## Requirements

- **macOS or Windows** (Linux works too). Apple Silicon gets GPU-accelerated embedding; other machines use CPU or CUDA.
- **Python 3.10+**.
- **Claude Desktop** with Cowork, to use the servers as tools.
- Disk space for whatever corpora you choose — from ~500 MB (scriptures + places) to 100+ GB (offline Wikipedia). You pick.

## Credit

Built by Peter Duke / The Duke Report, with Claude. Code is MIT-licensed; downloaded texts keep their own licenses.

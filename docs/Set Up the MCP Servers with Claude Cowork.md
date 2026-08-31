# Set Up the MCP Servers with Claude Cowork

A start-to-finish guide for putting this whole research stack on **someone else's**
Mac. It assumes no prior experience with servers, databases, or Python. Every
command is written out. Where something can go wrong, it says so.

By the end, Claude Cowork will be able to search a personal PDF library, ancient
Greek texts, a conspiracy-research wiki, 42,000 ancient places, all of offline
Wikipedia, and five scripture corpora with three lexicons — plus you'll have a
historical map database and an interactive Bible map website.

> **Companion documents**
> - `Build a Local RAG with Claude Cowork.md` — the deep-dive for the PDF-library server
> - `Add an MCP Server.md` — how to build a *new* server of your own
> - `Canonical Paths.md` — where everything lives

---

## 1. What you're building

An **MCP server** is a small program that gives Claude a new ability — a way to
search something on your own computer. Claude Desktop starts these programs for
you; you never run them by hand. Each one is a single Python file sitting next to
its data.

| Server | What Claude can do with it | Disk | Rebuildable by anyone? |
|---|---|---|---|
| `scriptures` | Search/quote Qur'an, 1 Enoch, Tanakh, Talmud, Mishnah, the **Ethiopian (Tewahedo) canon** (36 books, Ge'ez + English) + BDB/Jastrow/Lane lexicons | 239 MB | **Yes** — scripts download everything |
| `pleiades` | Look up 42,300 ancient places, coordinates, dating | 17 MB | **Yes** |
| `gutenberg` | Search ~78,000 public-domain books, by subject | 11.3 GB–207 GB (you choose) | **Yes** — downloader included |
| `wikipedia` | Search all of Wikipedia offline | 115 GB | Yes, but a huge download |
| `wikispooks` | Search 31,865 articles of the WikiSpooks wiki | 259 MB | Needs the site's database dump |
| `greek-resources` | Greek NT/LXX text, LSJ lexicon, Galen | varies | Yes (open corpora) |
| `latin-resources` | Search/quote the Latin classics (Virgil, Horace, Cicero, Ovid, Martial…) by author, work, and line — **plus the Lewis & Short Latin dictionary** (`lewis_short`) | ~350 MB | **Yes** — Perseus TEI XML + L&S from Perseus lexica |
| `perseus` | Search/quote the COMPLETE Perseus canonical library — 156 Greek and Latin authors, 2,299 texts, editions and translations | ~1.5 GB | **Yes** — two GitHub tarball downloads |
| `papyri` | Search/quote ~67,600 documentary papyri (Duke Databank / DDbDP) — letters, contracts, petitions in Greek & Latin, by papyri.info id or Trismegistos (TM) number | ~100 MB | **Yes** — EpiDoc XML from papyri.info |
| `astrology` | Offline natal charts, current/dated sky, and synastry (relationship) comparison — Swiss Ephemeris via **kerykeion** | tiny (code only) | **Yes** — pip install; the one server with a non-stdlib dependency |
| `wordnet` | Define English words: senses, synonyms, antonyms, the broader/narrower (hypernym/hyponym) hierarchy, gloss search — Open English WordNet | ~80 MB | **Yes** — one script, stdlib only |
| `alexandria-rag` | Semantic search over *your own* PDF library | varies | Only with your own PDFs |

Plus two things that aren't servers:

- **Atlas** — a historical geo-temporal database (DuckDB) you can query for
  "what places existed here, in this century?"
- **Bible Map** — an offline website: pick a book, chapter, and verse and see
  every place named there on a map.

**Start with `scriptures` and `pleiades`.** They need no special downloads, build
in minutes, and prove the whole setup works before you tackle the 115 GB one.

---

## 2. Before you start

You need:

1. **A Mac** with Claude Desktop installed, and Cowork enabled.
2. **An external drive** (or plenty of internal space). Everything here lives on
   one drive so it's easy to move. This guide calls it `/Volumes/DRIVE` —
   **substitute your drive's actual name everywhere you see `DRIVE`.**
   (On the original machine it's `PRO-BLADE`.)
3. **Free space:** ~500 MB for the small servers, **~130 GB** if you want offline
   Wikipedia.
4. **The Terminal app.** You'll paste commands into it and press Return. That's
   the whole skill.
5. **Python 3.** Macs ship with it. Check by pasting this and pressing Return:

```
python3 --version
```

If you see something like `Python 3.10.x` or newer, you're fine.

### A note on copying commands

Every block below is one or more commands. Copy the whole block, paste into
Terminal, press Return. If a command seems to hang with no output, that's usually
normal — downloads and builds are quiet. Wait.

---

## 3. Make the folders and the Python environment

A **virtual environment** is a private box of Python add-ons, so this project
can't break anything else on the computer. You make it once.

```
mkdir -p "/Volumes/DRIVE/Scriptures" "/Volumes/DRIVE/Pleiades" "/Volumes/DRIVE/Gutenberg" \
         "/Volumes/DRIVE/Wikipedia" "/Volumes/DRIVE/WikiSpooks" \
         "/Volumes/DRIVE/Atlas"
python3 -m venv "/Volumes/DRIVE/mcp_env"
```

Now install the only two add-ons any of these servers need:

```
"/Volumes/DRIVE/mcp_env/bin/pip" install --upgrade pip
"/Volumes/DRIVE/mcp_env/bin/pip" install libzim duckdb
```

- `libzim` — lets the Wikipedia server read the offline Wikipedia file.
- `duckdb` — powers the Atlas map database.

Everything else in this guide is **stdlib only** — plain Python, no installs.

> **Why one environment?** So a single Python path works for every server in the
> config file. From here on, that path is:
> `/Volumes/DRIVE/mcp_env/bin/python`

---

## 4. The scriptures server (start here)

**What it is:** the Qur'an (Arabic + English), 1 Enoch, the Hebrew Bible, the
Babylonian Talmud, and the Mishnah — 231,000 searchable segments — plus three
public-domain lexicons (BDB for Hebrew, Jastrow for Aramaic, Lane for Arabic).

**Licensing — read this.** Enoch, the Qur'an text, and all three lexicons are
public domain or freely redistributable. The Tanakh/Talmud/Mishnah come from
Sefaria under **CC BY-NC** — free for personal research, **not** for anything you
sell. The server tags every result with its license so you always know.

Copy `build_scriptures.py`, `build_lexicons.py`, and `scriptures_mcp_server.py`
into `/Volumes/DRIVE/Scriptures/`, then:

```
cd "/Volumes/DRIVE/Scriptures"
python3 build_scriptures.py
python3 build_lexicons.py
```

The first script downloads from the internet as it goes. It's **resumable** — if
it stops, run it again and it picks up where it left off. Expect a few minutes.

You should see, at the end:

```
scriptures.sqlite built:
  enoch    en     1,071
  mishnah  en     4,039
  ...
  talmud   he    81,793
```

Then the lexicons print `bdb 11,845 / jastrow 32,512 / lane 1,648`.

**Cleanup:** the `sources/` and `sources_lex/` folders are just download caches.
Delete them to reclaim ~175 MB. Rebuilding re-downloads them.

```
rm -rf "/Volumes/DRIVE/Scriptures/sources" "/Volumes/DRIVE/Scriptures/sources_lex"
```

**Add the Ethiopian (Tewahedo) canon.** One more script adds 36 books of the
broadest biblical canon — Jubilees, 1–3 Meqabyan, Kebra Nagast, 4 Baruch, and the
deuterocanon (Tobit, Judith, Sirach, Wisdom) — in **Ge'ez with word-by-word
transliteration and English** (Charles for Enoch/Jubilees, Brenton's Septuagint
and the KJV side-by-side for the rest). Copy `build_ethiopian.py` into the same
folder and run it:

```
cd "/Volumes/DRIVE/Scriptures"
python3 build_ethiopian.py
```

It clones the open dataset (`LPettay/ethiopian-bible`, ~47 MB), adds an
`ethiopian` corpus of 18,508 verses to `scriptures.sqlite`, and rebuilds the
search index — about a minute. The Ge'ez comes from **Beta Masaheft** (CC BY-SA
4.0); the English translations are **public domain**. Delete the
`ethiopian-bible/` clone afterward if you like — rerunning re-fetches it.

---

## 5. The pleiades server

**What it is:** a gazetteer of 42,300 places from the ancient world, with
coordinates and date ranges. Licensed **CC-BY** — usable commercially with credit.

Copy `build_pleiades_corpus.py` and `pleiades_mcp_server.py` into
`/Volumes/DRIVE/Pleiades/`, then:

```
cd "/Volumes/DRIVE/Pleiades"
python3 build_pleiades_corpus.py
```

It downloads the Pleiades data dumps and builds `pleiades.sqlite` (~17 MB).

---

## 6. The gutenberg server

**What it is:** Project Gutenberg — roughly 78,000 public-domain books —
searchable offline, split by **Library of Congress subject** so you can take only
the shelves you want.

**Read this before you pick a size.** The single-file bundle (`gutenberg_en_all`)
is ~206 GB, because it packs every format for every book: EPUB, MOBI, HTML, cover
art. All 39 subject subsets together come to ~207 GB — *the same corpus*. Subsets
are **not smaller**. What they buy you is: each file resumes on its own (a dropped
download costs one file, not 206 GB), you can search the subjects you have while
the rest arrive, and every search result gets tagged with its subject.

Copy `gutenberg_mcp_server.py` and `download_gutenberg.py` into
`/Volumes/DRIVE/Gutenberg/`, then:

```
cd "/Volumes/DRIVE/Gutenberg"
python3 download_gutenberg.py --list
python3 download_gutenberg.py --set core
```

> **zsh gotcha:** don't paste a `#` comment after a command. Interactive zsh
> doesn't treat `#` as a comment, so `# ~8.6 GB` fails with
> `no such user or named directory: 8.6`. Commands only.

`--set core` is ~11.3 GB (11,315 books): the humanities shelves — Religion & Philosophy,
Classics, Law, Political science, Archaeology, and the language sets. It's the
sensible start.

Then, if you want the rest:

```
python3 download_gutenberg.py --set all
```

Or pick your own shelves by LCC letter:

```
python3 download_gutenberg.py --set b,d,pa
```

| Set | Contents | Size |
|---|---|---|
| `core` | Humanities: Religion/Philosophy, Classics, Law, Politics, languages | ~11.3 GB (11,315 books) |
| `all` | Every subject, 39 files | ~207 GB |
| `b` | Philosophy, Psychology, Religion | 5.9 GB |
| `d` | World history (the big one) | 37 GB |
| `pa` | Classical Greek & Latin | 0.5 GB |

Everything is resumable — re-run and it skips finished files and continues
partial ones. Stop whenever; the server works with whatever is on disk.

The server needs `libzim` (installed in step 3). It opens **every** `.zim` in the
folder, so new subsets are picked up automatically — no restart needed unless the
server code itself changes.

**All of Project Gutenberg is public domain in the US** — no license constraints,
nothing to flag. It's the largest freely-publishable corpus in the set.

---

## 7. The wikipedia server (the big one)

**What it is:** every Wikipedia article, offline, searchable — 18.98 million
articles. No internet required once downloaded.

**This is a 115 GB download.** Budget several hours. It is resumable.

First, pick a size. `maxi` is the full thing with images; `nopic` is half the size
and text-only (the servers only use text, so `nopic` is a perfectly good choice).

```
cd "/Volumes/DRIVE/Wikipedia"
curl -L -C - -O "https://download.kiwix.org/zim/wikipedia/wikipedia_en_all_maxi_2026-02.zim"
```

If the download drops, **re-run the exact same command** — `-C -` resumes it.

For a file this large, `aria2c` (install with `brew install aria2`) is more
reliable because it uses several mirrors at once:

```
aria2c "https://download.kiwix.org/zim/wikipedia/wikipedia_en_all_maxi_2026-02.zim.meta4"
```

Copy `wikipedia_mcp_server.py` into the same folder. It automatically picks up the
newest `.zim` file it finds there — no configuration needed.

> **Smaller option:** swap `maxi` for `nopic` (49 GB) or `mini` (12 GB) in the URL.
> There's also `wikipedia_en_simple_all_nopic` (under 1 GB) if you just want to
> test that the plumbing works.

---

## 8. The wikispooks server

**What it is:** all 31,865 articles of WikiSpooks, a wiki of deep-politics and
intelligence research.

**Provenance.** WikiSpooks is community-edited, outside the mainstream reference
consensus. The server attributes every result to it by article title so citations
carry their source. What you do with that attribution is your methodology's
business, not the tool's.

You need the site's MediaWiki database dump (a `.zip` containing a large `.sql`
file). Put it in `/Volumes/DRIVE/WikiSpooks/`, copy in
`build_wikispooks_corpus.py` and `wikispooks_mcp_server.py`, then:

```
cd "/Volumes/DRIVE/WikiSpooks"
python3 build_wikispooks_corpus.py
```

It reads the SQL straight out of the zip — you don't need to unzip it. Builds
`wikispooks.sqlite` (~259 MB).

> **Gotcha from the original build:** a smaller dump file sitting loose on disk was
> truncated and only contained metadata. The real 4.7 GB dump was *inside* the zip.
> If you end up with 0 articles, that's why — point the script at the zip.

Also check WikiSpooks' own licensing before republishing any of its text.

---

## 9. greek-resources, latin-resources, perseus, and alexandria-rag

These are last because they depend on corpora rather than a single download.

- **`greek-resources`** serves the Greek New Testament and Septuagint, the LSJ and
  Middle Liddell lexicons, and Galen. The texts are open (First1KGreek and
  friends) and arrive as XML. Copy `greek_mcp_server.py` and its data folder.
  When citing in published work, cite **author, work, and edition — never a file
  path.** For the New Testament, the standard used here is the Byzantine textform.

- **`latin-resources`** is the Latin twin of the Greek server: `latin_mcp_server.py`
  plus per-author folders of Perseus TEI XML, each with a small `manifest.json`
  naming its works. Add an author by dropping in the folder, writing the
  manifest, and calling the `latin_reindex` tool. It also carries the **Lewis &
  Short Latin dictionary** (`lewis_short.sqlite`, 51,596 entries, Perseus lexica
  CC BY-SA 4.0) — the Latin counterpart to the Greek LSJ. The `lewis_short` tool
  looks a headword up case-, macron-, u/v- and i/j-insensitively, with a
  stem-trim and full-text fallback. Build the dictionary once — the script
  downloads the Perseus TEI itself and parses it into `lewis_short.sqlite`:

  ```
  cd "/Volumes/DRIVE/Alexandria/Latin-resources"
  python3 build_lewis_short.py
  ```

- **`papyri`** serves ~67,600 documentary papyri from the **Duke Databank of
  Documentary Papyri** (DDbDP) — everyday Greek and Latin writing: letters,
  contracts, petitions, receipts, tax registers. Copy `papyri_mcp_server.py` and
  `build_papyri.py` into `/Volumes/DRIVE/Alexandria/Papyri/`, then:

  ```
  cd "/Volumes/DRIVE/Alexandria/Papyri"
  python3 build_papyri.py
  ```

  It git-sparse-clones just the DDbDP EpiDoc XML (~500 MB) and builds
  `papyri.sqlite` (~100 MB) in about 15 seconds. Tools: `search_papyri`
  (accent-insensitive Greek, prefix `βασιλ*`, AND-terms), `get_papyrus` (by
  papyri.info id like `p.oxy.40.2901` or TM number like `45214`), `papyri_stats`.
  Every result links back to papyri.info. Licensed **CC BY 3.0** — free to quote
  with attribution. (This corpus is the *transcriptions* only; find-spot and date
  live in the separate HGV metadata, not loaded here.)

- **`astrology`** computes charts offline — `natal_chart`, `sky` (now or any
  date), and `synastry` (two-person comparison) — via **kerykeion** and the Swiss
  Ephemeris. It's the **only** server that needs a non-stdlib package, so it gets
  its own environment. Copy `astrology_mcp_server.py`, `setup_astro_env.sh`, and
  `requirements.txt` into `/Volumes/DRIVE/Astrology/`, then:

  ```
  bash "/Volumes/DRIVE/Astrology/setup_astro_env.sh"
  ```

  That builds `astro_env` and installs kerykeion (which bundles the ephemeris —
  no internet needed after install). Birth data is given as **latitude, longitude,
  and an IANA timezone** (e.g. `America/New_York`) — no city lookup. In the config
  block below, note this server's `command` points at **`Astrology/astro_env/bin/python`**,
  not the shared `mcp_env`. Astrology isn't an empirical science: the tools report
  the standard figures (positions, houses, aspects); interpretation is yours.

- **`wordnet`** is an English dictionary/thesaurus engine — `define` (all senses,
  with synonyms + examples), `synonyms`, `antonyms`, `related` (hypernym = broader,
  hyponym = narrower, meronym = parts, holonym = wholes, similar, entails, causes),
  and `search_glosses` (full-text over definitions). Copy `wordnet_mcp_server.py`
  and `build_wordnet.py` into `/Volumes/DRIVE/WordNet/`, then:

  ```
  cd "/Volumes/DRIVE/WordNet"
  python3 build_wordnet.py
  ```

  It downloads Open English WordNet (WN-LMF XML, ~11 MB) and builds
  `wordnet.sqlite` (~80 MB, 107k synsets) in a couple of minutes — stdlib only,
  so it runs under the shared `mcp_env`. Licensed **CC BY 4.0**.

- **`perseus`** is the whole Perseus Digital Library in one server. Download the
  two canonical repositories as tarballs (`canonical-greekLit` and
  `canonical-latinLit` from the PerseusDL GitHub), extract them next to
  `perseus_mcp_server.py` in `Perseus-canonical/`, and run
  `python3 build_resume.py` repeatedly until it prints COMPLETE (the builder
  resumes where it stopped, so interruptions cost nothing). One index covers
  every author, every edition, every translation; `perseus_search` takes
  optional `author` and `lang` (grc/lat/eng) filters. Prose references follow
  each edition's own numbering (Kaibel chapters for Athenaeus, Stephanus
  sections for Plutarch's Moralia) — when a lettered page cite like "11F"
  won't resolve, search a distinctive phrase instead and read the section
  number off the hit.

- **`alexandria-rag`** is the only one that can't be copied wholesale, because its
  value is *your own* PDF library. It uses semantic search (FAISS) rather than
  keyword search. Building it needs extra Python packages and its own careful
  setup — see **`Build a Local RAG with Claude Cowork.md`**, which walks through
  it from scratch.

> **Hard-won rule, don't ignore it:** in the RAG build, never merge the
> embedding step and the index-building step into one program. Both bundle their
> own copy of a library called OpenMP, and loading both in one process crashes on
> macOS. The build scripts deliberately run them separately.

---

## 10. Tell Claude about the servers

Claude Desktop reads one settings file. Open it:

```
open -e "$HOME/Library/Application Support/Claude/claude_desktop_config.json"
```

Replace everything in the `mcpServers` section with the block below — and
**substitute `DRIVE` with your drive's name.** Leave any other settings in the
file (things like `preferences`) exactly as they are.

```json
{
  "mcpServers": {
    "scriptures": {
      "command": "/Volumes/DRIVE/mcp_env/bin/python",
      "args": ["/Volumes/DRIVE/Scriptures/scriptures_mcp_server.py"]
    },
    "pleiades": {
      "command": "/Volumes/DRIVE/mcp_env/bin/python",
      "args": ["/Volumes/DRIVE/Pleiades/pleiades_mcp_server.py"]
    },
    "wikipedia": {
      "command": "/Volumes/DRIVE/mcp_env/bin/python",
      "args": ["/Volumes/DRIVE/Wikipedia/wikipedia_mcp_server.py"]
    },
    "gutenberg": {
      "command": "/Volumes/DRIVE/mcp_env/bin/python",
      "args": ["/Volumes/DRIVE/Gutenberg/gutenberg_mcp_server.py"]
    },
    "wikispooks": {
      "command": "/Volumes/DRIVE/mcp_env/bin/python",
      "args": ["/Volumes/DRIVE/WikiSpooks/wikispooks_mcp_server.py"]
    },
    "greek-resources": {
      "command": "/Volumes/DRIVE/mcp_env/bin/python",
      "args": ["/Volumes/DRIVE/Greek-resources/greek_mcp_server.py"]
    },
    "latin-resources": {
      "command": "/Volumes/DRIVE/mcp_env/bin/python",
      "args": ["/Volumes/DRIVE/Alexandria/Latin-resources/latin_mcp_server.py"]
    },
    "perseus": {
      "command": "/Volumes/DRIVE/mcp_env/bin/python",
      "args": ["/Volumes/DRIVE/Alexandria/Perseus-canonical/perseus_mcp_server.py"]
    },
    "papyri": {
      "command": "/Volumes/DRIVE/mcp_env/bin/python",
      "args": ["/Volumes/DRIVE/Alexandria/Papyri/papyri_mcp_server.py"]
    },
    "astrology": {
      "command": "/Volumes/DRIVE/Astrology/astro_env/bin/python",
      "args": ["/Volumes/DRIVE/Astrology/astrology_mcp_server.py"]
    },
    "wordnet": {
      "command": "/Volumes/DRIVE/mcp_env/bin/python",
      "args": ["/Volumes/DRIVE/WordNet/wordnet_mcp_server.py"]
    },
    "alexandria-rag": {
      "command": "/Volumes/DRIVE/Alexandria/RAG_system/rag_env/bin/python",
      "args": ["/Volumes/DRIVE/Alexandria/RAG_system/alexandria_mcp_server.py"]
    }
  }
}
```

**Only list servers you actually built.** Delete the entries for any you skipped —
a missing file just makes that server fail to start.

Note `alexandria-rag` uses its *own* environment (`rag_env`), because it needs the
heavy machine-learning packages the others don't.

### Check the file isn't broken

JSON is fussy about commas and braces. Before restarting, run:

```
python3 -m json.tool "$HOME/Library/Application Support/Claude/claude_desktop_config.json" > /dev/null && echo "valid JSON"
```

If it prints `valid JSON`, you're good. If it prints an error, it tells you the
line — usually a missing comma between two servers, or one server accidentally
nested inside another.

### Restart Claude

Quit Claude Desktop completely and reopen it. Servers only load at startup.

---

## 11. Check that it worked

In a new Cowork chat, ask Claude things only these servers could answer:

- *"List the corpora in the scriptures server."* → should report five corpora and three lexicons
- *"Look up the word shalom in BDB."* → "completeness, soundness, welfare, peace"
- *"Get me Berakhot 2a:1."* → returns Aramaic **and** English
- *"Search Pleiades for Gadeira."* → ancient Cádiz, with coordinates
- *"Search Wikipedia for the Bretton Woods system."*
- *"List the Gutenberg subjects installed."* → shows each subset and its entry count
- *"Get me Jubilees 1:1 from the Ethiopian canon."* → Ge'ez + transliteration + English together
- *"Cast a natal chart for 15 June 1990, 2:30pm, lat 40.71 lng -74.01, America/New_York."* → planets, houses, aspects
- *"Define 'bank' in WordNet, and give hyponyms of 'dog'."* → all senses; then puppy, cur, lapdog…
- *"Look up virtus in Lewis & Short."* → the full Latin dictionary entry (manliness, virtue, valor…)
- *"Search the papyri for βασιλ*."* → thousands of documentary hits; then *"get p.oxy.40.2901"* returns the Greek transcription

If a server doesn't appear, see Troubleshooting below.

---

## 12. Extras: the Atlas and the Bible Map

### Atlas — a historical geo-temporal database

Places, but with **time** attached: borders, names, and settlements that were
valid only during certain centuries. It's a single DuckDB file, no server to run.
It's seeded from Pleiades, so build that first.

```
cd "/Volumes/DRIVE/Atlas"
"/Volumes/DRIVE/mcp_env/bin/python" build_atlas.py
```

You can then ask it things like *"which settlements existed around the Aegean in
400 BCE?"* — a query that mixes geography and time in one question.

### Bible Map — an offline website

Pick a book, chapter, and verse; see every place named there on a map. Works with
no internet, no server — just a file you double-click.

```
cd "/Volumes/DRIVE/Atlas/bible_map"
python3 process_bible_map.py
open index.html
```

The place data comes from OpenBible.info under **CC-BY** — free for commercial use
with attribution (the attribution is already in the page footer). That makes this
one safe to publish, unlike the CC BY-NC scripture texts.

It also carries a `contested.js` file: a hand-curated list of places where
translations disagree about the actual *location*, not just the spelling. Obadiah
1:20's "Sepharad" is the worked example — Sardis to modern scholars, the Bosphorus
in Jerome's Vulgate, Spain in rabbinic tradition. Use the version buttons to
switch between readings.

---

## 13. Troubleshooting

**A server doesn't show up in Claude.**
Nine times out of ten it's the config file. Run the `json.tool` check above. Then
confirm the two paths in that server's entry both really exist — copy each path
and run `ls "<paste path here>"`. Then fully quit and reopen Claude.

**"No module named libzim" (or duckdb).**
The config is pointing at the wrong Python. The `command` must be
`/Volumes/DRIVE/mcp_env/bin/python`, not plain `python3`.

**The Wikipedia server starts but finds nothing.**
It looks for the newest `.zim` file in its own folder. Confirm one is there and
that the download actually finished (a 115 GB file should read as ~115 GB, not 40).

**The drive isn't plugged in.**
Every server lives on the external drive. If it's unmounted, they all fail. Check
with `ls /Volumes/`.

**A build script died halfway.**
Just run it again. `build_scriptures.py` and the Wikipedia download are both
resumable by design.

**Something crashed the whole Mac during indexing.**
That's the RAG, not these servers — it used too many parallel workers and
exhausted memory. The fix (capping workers) is baked into the current scripts;
see the RAG guide.

---

## 14. What you may and may not republish

| Source | License | Safe to sell / publish? |
|---|---|---|
| 1 Enoch (Charles) | Public domain | **Yes** |
| Qur'an (Tanzil Arabic) | Free redistribution | **Yes** |
| BDB, Jastrow, Lane lexicons | Public domain | **Yes** |
| Pleiades | CC-BY | **Yes**, with credit |
| OpenBible place data | CC-BY | **Yes**, with credit |
| Tanakh / Talmud / Mishnah (Sefaria) | **CC BY-NC** | **No** — personal research only |
| Project Gutenberg | Public domain (US) | **Yes** |
| Ethiopian canon — Ge'ez (Beta Masaheft) | CC BY-SA 4.0 | Yes, with credit + share-alike |
| Ethiopian canon — English (Charles / Brenton LXX / KJV) | Public domain | **Yes** |
| Lewis & Short (Perseus lexica) | CC BY-SA 4.0 | Yes, with credit + share-alike |
| Papyri / DDbDP (papyri.info) | CC BY 3.0 | **Yes**, with credit |
| Wikipedia | CC BY-SA | Yes, with share-alike |
| WikiSpooks | Check the site | Verify before republishing |

Every result the scriptures server returns is stamped with its license, so you
never have to guess which bucket a quotation came from.

---

*Last updated: 2026-08-30 — added the `wordnet` server (Open English WordNet, 107k synsets, CC BY). Earlier: the `astrology` server (kerykeion), the `papyri` server (Duke Databank), the Lewis & Short dictionary on the Latin server, and the **Ethiopian (Tewahedo) canon** in the scriptures server. Full roster is 12 MCP servers.*

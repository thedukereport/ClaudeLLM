# Canonical Paths

One table, one truth. Claude resolves every project path from this registry before running commands or emitting links, and updates this file when a location moves. Path guessing broke skill installs, "Show in folder" links, and folder targeting across multiple sessions.

| Purpose | Canonical path | Status |
|---|---|---|
| Book vault (this vault) | `/Users/peterduke/Documents/Reframing Reality Vault` | active |
| Research vault | `/Users/peterduke/Documents/Research Vault` | active — renamed 2026-07-04, references swept |
| Alexandria RAG system | `/Volumes/PRO-BLADE/Alexandria/RAG_system/` | active |
| Alexandria Web UI | `http://127.0.0.1:5050` — moved off 5000 (AirPlay Receiver owns it) 2026-07-02 | active |
| Alexandria MCP server | `/Volumes/PRO-BLADE/Alexandria/RAG_system/alexandria_mcp_server.py` | active |
| PDF library (RAG corpus) | `/Volumes/PRO-BLADE/Alexandria/` — confirm exact subfolder | confirm |
| G-RAID Dropbox copy | `/Volumes/G-RAID MIRROR/Dropbox/Alexandria/RAG Research/` | mirror — never link to it |
| Old RAG working copy | `/Users/peterduke/Documents/Claude/Projects/Alexandria RAG/` | **STALE (April 2026)** — never edit or launch app.py from here; old wikispooks scripts here are superseded (see next row); archive candidate |
| WikiSpooks archive + MCP | `/Volumes/PRO-BLADE/WikiSpooks/` — corpus builder `build_wikispooks_corpus.py`, MCP server `wikispooks_mcp_server.py`, corpus `wikispooks.sqlite`, source dump in `wikispooks-latest.zip` | active (2026-07-07) — full wiki (~37.7k articles) from the MediaWiki dump, not the 87-file iframeDocs stub |
| Pleiades gazetteer + MCP | `/Volumes/PRO-BLADE/Pleiades/` — `build_pleiades_corpus.py`, `pleiades_mcp_server.py`, `pleiades.sqlite` (42,300 ancient places, CC-BY) | active (2026-07-07) — search_place / get_place with coords, dating, ancient names |
| MCP server template | `/Volumes/PRO-BLADE/Alexandria/mcp_server_template.py` + `How To/Add an MCP Server.md` | active — copy to build new servers |
| Wikipedia (offline) + MCP | `/Volumes/PRO-BLADE/Wikipedia/` — `wikipedia_mcp_server.py` + a Kiwix `*.zim` (drop newest here). Needs `libzim` in rag_env. Server auto-picks newest .zim | active (2026-07-07) — search_wikipedia / get_wikipedia_article via the ZIM's built-in full-text index |
| D3 Viz Kit | `/Volumes/PRO-BLADE/Alexandria/Viz-Kit/` — network-graph / timeline / map templates + vendored D3 in `lib/`; open `index.html` | active (2026-07-07) — local, offline, print-to-PDF figures for reports/decks |
| Project Gutenberg + MCP | `/Volumes/PRO-BLADE/Gutenberg/` — `gutenberg_mcp_server.py` (multi-ZIM), `download_gutenberg.py`, plus Kiwix `gutenberg_en_lcc-*.zim` subsets. Needs `libzim` | active (2026-07-08) — search_gutenberg / get_book / list_subjects. Opens EVERY .zim in the folder and tags hits by LCC subject. All public domain. `--set core` ≈ 11.3 GB / 11,315 books (humanities); `--set all` ≈ 207 GB (same as the single bundle — subsets aren't smaller, just resumable + subject-tagged) |
| Scriptures corpus + MCP | `/Volumes/PRO-BLADE/Scriptures/` — `build_scriptures.py` (texts), `build_lexicons.py` (lexicons), **`build_ethiopian.py`** (Ethiopian canon), `scriptures_mcp_server.py`, `scriptures.sqlite` (239 MB). Texts: Qur'an, 1 Enoch, Tanakh, Talmud Bavli, Mishnah + **Ethiopian (Tewahedo) canon** (36 books, 18,508 verses). Lexicons: BDB, Jastrow, Lane (46k entries, all PD). FTS5, stdlib only | active (2026-07-08; Ethiopian added 2026-08-06) — search_scriptures / get_passage / lookup_word / list_corpora. Enoch PD, Qur'an free, lexicons PD; Sefaria layers CC BY-NC (personal research). Ethiopian: Ge'ez CC BY-SA (Beta Masaheft), English PD (Charles/Brenton-LXX/KJV), from `LPettay/ethiopian-bible`. Download caches (`sources/`, `sources_lex/`, `ethiopian-bible/`) deleted after build; rebuild re-creates them |
| Latin corpus + MCP | `/Volumes/PRO-BLADE/Alexandria/Latin-resources/` — `latin_mcp_server.py`, per-author Perseus TEI dirs with `manifest.json`, index `latin-corpus-index.jsonl` (62,789 segments), **`lewis_short.sqlite`** (Lewis & Short dictionary, 51,596 entries, Perseus lexica CC BY-SA 4.0) | active (2026-07-10; L&S added 2026-08-02) — latin_corpus_search / latin_passage / **lewis_short** / latin_authors / latin_reindex |
| Papyri (DDbDP) + MCP | `/Volumes/PRO-BLADE/Alexandria/Papyri/` — `papyri_mcp_server.py`, `papyri.sqlite` (67,569 documentary papyri, FTS5, stdlib only) | active (2026-08-02) — search_papyri / get_papyrus / papyri_stats. Duke Databank of Documentary Papyri EpiDoc XML from papyri.info (idp.data/DDbDP), CC BY 3.0. Accent-insensitive Greek search; 66k Greek + 2.4k Latin docs. Links to papyri.info |
| Astrology + MCP | `/Volumes/PRO-BLADE/Astrology/` — `astrology_mcp_server.py`, `setup_astro_env.sh`, `requirements.txt`, its own `astro_env` (needs **kerykeion** + pyswisseph — the only MCP server with a non-stdlib dep) | active (2026-08-25) — natal_chart / sky / synastry. Offline Swiss-Ephemeris calc (built-in ephemeris, no internet); birth data by lat/lng/tz (no geonames). Config uses `astro_env/bin/python`, NOT rag_env. Astrology is not empirical — tools report figures; interpretation is the user's |
| WordNet + MCP | `/Volumes/PRO-BLADE/WordNet/` — `wordnet_mcp_server.py`, `build_wordnet.py`, `wordnet.sqlite` (107,519 synsets, 127k words, FTS5, stdlib only) | active (2026-08-30) — define / synonyms / antonyms / related (hypernym/hyponym/meronym/…) / search_glosses. Open English WordNet 2025, WN-LMF XML, **CC BY 4.0**. Runs under rag_env (stdlib) |
| Perseus canonical library + MCP | `/Volumes/PRO-BLADE/Alexandria/Perseus-canonical/` — `perseus_mcp_server.py`, `canonical-greekLit-master/` + `canonical-latinLit-master/` (complete Perseus repos: 156 authors, 2,299 texts, all editions + translations), index `perseus-corpus-index.jsonl` (658 MB), catalog `perseus-authors.json`, resumable builder `build_resume.py` | active (2026-07-12) — perseus_search / perseus_passage / perseus_authors / perseus_reindex. Refresh: re-download the two GitHub tarballs, re-extract, delete `index-done.list`, rerun the builder |
| Skill masters (editable) | `Reframing Reality Vault/Skills/` | active |
| Fact-check ledgers | `Reframing Reality Vault/Fact Check/` | active |
| Logs | `~/Library/Logs/RR/` | active |

## Rename: Reasearch Vault → Research Vault — DONE 2026-07-04

Folder renamed by Mr. Duke; Claude swept the vault the same day: fixed folder-tree diagrams in `README.md` and `Projects/Perkins_and_Company/RESEARCH_WORKFLOW.md`, and repointed two G-RAID mirror paths in `Sources_Index.md` to PRO-BLADE. Zero stale references remain. If Obsidian was pointed at the old path, re-open the vault from the new location once.

## Rules

- Volumes can be unmounted: check `ls /Volumes/` before touching PRO-BLADE or G-RAID paths, and say so if the drive is absent.
- New location → new row here, same commit as the change that created it.

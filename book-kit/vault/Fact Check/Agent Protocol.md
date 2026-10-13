# Fact-Check Agent Protocol

**Owner: the scheduled fact-check agent ("the agent"). Approved by the author.** Systems edits this file on the author's instruction; the agent reads it and never edits it.

The agent is a scheduled task, separate from the role chats named in `Methodology/Roles.md`. It serves the Fact-checker. It audits; it does not author. This file is the agent's complete operating instruction. Each run reads this file first and follows it exactly. The Fact-checker reads this file to know what the agent owns, and receives the agent's output.

**Paths.** The agent reads `book.toml` at the vault folder for the chapter folder, the appendix folder, the fact-check folder, the claims and events folders, the hand-off folder, the library roots and the chapters out of the workflow (`python3 tools/bookconfig.py` prints them). It touches no chapter listed under `[workflow] out_of_workflow`.

---

## The one governing rule: flag, never fix

The agent writes ONLY inside `Fact Check/`, plus its end-of-run section in `Handoffs/Fact-checker.md`. It never edits `Chapters/`, `Appendices/`, `Book Structure.md`, `Punch List.md`, `Project State.md`, `Scratch Notes.md`, or anything else in the vault. It never runs `git`, never pushes, never renders PDFs, never runs `tools/lock.py`. Each finding becomes a row in `Fact Check/Findings Register.md` and an entry in the chapter's ledger; each question for the author becomes an entry in `Fact Check/Asks.md`. The Fact-checker receives the agent's output and passes findings that need a card to the Editor through `Handoffs/Editor.md`; the Editor builds the cards; the author rules on them; Production applies approved cards and owns `Punch List.md` and continuity.

## Files the agent owns (all inside `Fact Check/`)

- `Agent Protocol.md` — this file (read-only to the agent).
- `Findings Register.md` — the agent appends each finding as one row at the foot of the file's **Open** table, in that table's format: `| coordinate | phrase | finding |`. The coordinate is `Ch##/L##` (or the note slug); the phrase is copied from the line, distinctive enough to find it; the finding opens with the check type from the list at the foot of this file (for example `FACT-URGENT:`), then gives the source read, where in it, the words found, and the date read. The same finding goes into the chapter's ledger in the same step.
- `Asks.md` — each question only the author can answer becomes one row in the **Open** table, in that file's format: `| id | kind | ask | blocks | if no answer | asked |`, with kind DECIDE, REVIEW or ONLY YOU CAN. Each ask states what happens if the author says nothing.
- `Agent Run Log.md` — the run history, newest first. Each run writes one section at the top of the log and changes no other run's section. (If the file does not exist, the first run creates it with the heading `# Agent Run Log`.)
- `_Agent State.json` — per-chapter SHA-256, last-audited dates, which checks are complete, and `manuscript_changed`. Machine state; humans need not read it.
- The per-chapter ledgers (`Ch. NN — <short title>.md`) — the agent APPENDS dated sections following `Methodology/Fact-Check Ledger Protocol.md`. Cumulative, never overwritten; prior entries stay.

**ONE LEDGER PER CHAPTER, AND IT IS THE ONE THAT ALREADY EXISTS.** Find it with `bookconfig.ledger_file(NN)` (the glob in `book.toml`, `ledger_glob`) and append to the file that comes back. Never derive a ledger name from the chapter's filename, and never create a second file for a chapter that already has one. The title in a ledger's name is the SHORT title, so deriving the name from the chapter file produces a near-miss that looks plausible and lands beside the real ledger. In the original system that happened to two chapters: runs went into a second file named after the chapter while other runs kept going into the original, each file held audit work the other did not, and the history had to be merged by hand.

**Before writing a row, read the chapter's rows in `Findings Register.md` and its ledger.** A finding already in the register is never written twice, and a finding whose evidence has been applied is never raised again. Open the line in the chapter and read it to decide.

**Run `tools/preflight.sh NN` before auditing a chapter, and read its output.** It prints that chapter's working files, its ledger, its open Punch List items and its open findings. The agent's rule against re-searching a settled question depends on knowing what is already settled, and that knowledge is in those files, never in a summary of them. In the original system a description of a source stood in for the source, and four hours were spent re-deriving what was already written down.

## Write as you go

In the original system one run read this protocol, planned correctly, and launched a wave of audit subagents. The session ended before the wave returned, and the night's work went with it, because the run was holding its findings in memory to write at the end. The previous run's findings waited unrouted for two days afterwards, and a role chat re-ran a sweep the agent had already completed.

1. **Open the run before working it.** Before any audit begins, write a new section at the top of `Agent Run Log.md`, directly under the file's heading and above the newest run: its first line `## RUN NN — STARTED <UTC timestamp>`, its second line the intended backlog. Each progress line and the completion entry of this run go under this run's own heading. Nothing goes at the foot of the log. If the run dies in its first minute, the started line is the only record that it fired.
2. **One chapter, finished, on disk, before the next is picked up.** Ledger section written, Findings Register rows and asks appended, `_Agent State.json` updated. Never hold a finding in memory across a chapter boundary.
3. **Subagents run one chapter at a time**, and the result gets written the moment it returns. Never launch a wave whose output is collected and written later.
4. **Depth beats coverage.** Three chapters audited properly and recorded beat twelve started and none written. When the session is running short, stop taking new chapters, write the completion entry under this run's heading, and record where the next run resumes.

## What a run does

1. **Orient.** Confirm vault access. Read this file, `_Agent State.json`, `Methodology/Standing Rules.md` (the core) and `Methodology/Rules — Fact-checker.md`. Hash each file in the chapter and appendix folders (SHA-256).
2. **Pick work.** A chapter whose hash differs from `_Agent State.json` (or has no entry) is in the backlog, and so is any chapter or appendix never audited. Order the backlog: most recently modified first. **Work the full backlog each run** — the author removed a per-run cap: *"Why is there a cap? … hit everything."* Depth is never traded for breadth: each check still runs per the rules below, and a run that ends mid-backlog records per-chapter check completion in `_Agent State.json` so the next run resumes, never restarts. If the backlog is empty, take the chapter with the oldest `last_audited` for a re-verification pass (recent-developments check on its Tier 2 claims only).
3. **Audit each chapter, the checks below in order** (cheapest first). Count the bold **Check** headings to verify the number; in the original system the line stating the count went stale twice as checks were added.
   - **Check A0 — Banned words.** Run `tools/check-banned-words.sh NN`. It parses the machine-readable list in `Methodology/Word Lists.md` between its machine-list markers — **the single source, which the agent never copies into its own prompt or into this file.** Two copies of a rule drift the moment they exist. The script reports coordinates, never verdicts: **open each line it flags.** In the original system, of 41 hits on one banned word, 21 were violations and 13 were literal uses or quotations the carve-outs allow. Write a `SCAN-banned-word` row only for hits the agent has read and judged to be violations, quoting the clause and naming the carve-out it fails. **Never register a raw count.** Advisory: a banned word never blocks a lock by itself; the lock gate reports it.
   - **Check A1 — Epistemic failures.** Run `tools/check-epistemics.sh NN`. It parses the trigger block in `Methodology/Word Lists.md`; the failure classes are set out under "Borrowed authority and pre-emptive retreat" in `Methodology/Rules — Editor.md`. **The two that matter most have no trigger and will not appear in the output:** a sense substitution (using a word in its headword sense where the passage calls for another) and an unsourced hinge (a load-bearing claim with no note, usually because it reads as common knowledge). Both look like ordinary confident prose. Read for them.

     A hit is a coordinate. On a named scholar, the test is: strip each proper noun from the passage and ask whether anything checkable remains — if nothing does, the passage was resting on the names. On a hedge: a stated limit on the evidence belongs; an apology for having made the claim does not. Rulings go to `Fact Check/Epistemic Rulings.md` through `tools/rulings.py` and are never re-raised.
   - **Check A — Footnotes: the Editor's.** Footnote content belongs to the Editor's card work, built from the author's per-note rulings under `Methodology/Footnote Plan.md`. The agent proposes no footnote trim and no footnote rewrite. A note fault the agent finds — a missing source, page or edition, a quotation the source does not give, self-talk, a broken anchor — becomes a Findings Register row (check type FOOTNOTE) naming the note and the fault, and the Editor decides what the card says. A word count is a trigger to read a note, never a reason to cut one.

     **Two classes from `tools/check-footnotes.sh` fail a lock:** **A ORPHAN** (a continuation paragraph at column zero, which pandoc renders as body text) and **G NO-DEF / NO-ANCHOR** (broken anchor–definition parity). Report them at the top of the run summary.
   - **Check B — Sentence scan.** Sequential single-focus passes over the body prose, one violation type at a time, each pass a separate read of the full chapter: (1) nominalizations — frozen verbs; the proposed fix is always a thaw (restore the actors and the verb), never a deletion, per the author's ruling; (2) abstract nouns — especially abstract nouns given agency; (3) unspecified verbs; (4) sentence completeness — each sentence parses as a complete sentence; then (5+) one pass per remaining principle of the neurolinguistic-prose skill not already covered above. All passes observe the skill's Sweep Scope rules: exclusion zones, mention-vs-use, mechanical carve-outs, and a verdict on each hit. Findings go to the Findings Register with proposed rewrites; the agent does not apply them.
   - **Check C — Claims fact-check.** Run the citation-audit skill's fact-check phases on the chapter: check the chapter's ledger and `Fact Check/Claims/Ch NN.jsonl` FIRST (a prior row short-circuits the search **only if it holds both verdicts — see the short-circuit rule below**), then the library (`tools/have.sh`, the checked shelf, `tools/find-source.sh`), then any local servers, then the web, then direct source reading. Tier 2 claims need three independent sources. Each result — including negative results, with queries and pages listed — is appended to the chapter's ledger as a dated section and logged as a Claims row. Errors found (QUOTE: MISMATCH, CLAIM: OVERSTATED or UNSUPPORTED) also become Findings Register rows marked **FACT-URGENT**.
   - **Check D — Gloss check.** Each inline English gloss of a foreign term — body and footnotes both — is verified against a standard lexicon the author has in the library or on a local server, and recorded in the chapter ledger's Translation Checks table, accurate glosses included, so the next session need not look them up again. A gloss the lexicon does not support becomes a Findings Register row (GLOSS; GLOSS-URGENT where the argument leans on the gloss). A reading the author has ruled on is a term of art; record the ruling and do not re-flag it.
   - **Check E — Working-notes leak scan.** Sweep each chapter and appendix for the workflow talking to itself in publishable text: vault or filesystem paths, the library's folder names, "the vault", references to the fact-check ledger, the Punch List or session process ("verified this session", "an earlier draft", "Correction YYYY-MM-DD", "ruled on YYYY-MM-DD"), open to-dos ("to be confirmed", "not yet verified", TBD, TODO), `[<LANGUAGE>: … FETCH]` placeholders, and any first-person machinery that is the workflow's voice rather than the author's. **Boundary with the Editor:** a leak inside a footnote definition is a note fault; write it as a FOOTNOTE row naming the note, and the Editor's card for that note removes it. This check owns the body and everything else. **Carve-outs:** HTML comments are the sanctioned place for working notes and are never flagged; the author's own first person is the author's voice; method-transparency the author has chosen to print gets a verdict, never an automatic flag. Hits go to the Findings Register as LEAK rows with the proposed relocation (usually: move to the chapter ledger or an HTML comment).
   - **Check F — Attribution drift.** A read. Pair each footnote anchor with its own note and compare the attribution verb in the body sentence with the source language in the note, using the attribution classes in `Methodology/Word Lists.md` (between its ATTRIBUTION-CLASSES markers) and failure 8 in `Methodology/Rules — Editor.md` — *testified* against *summarized in a statute*, *the court held* against *dissenting*, a named person *said* against *quoted in another writer*. Rulings go to `Fact Check/Attribution Rulings.md` through `tools/rulings.py`; a ruled pair is never raised again. **This read misses unsourced claims** — no note, nothing to compare — so the unsourced-hinge read under Check A1 still has to happen. Hits become Findings Register rows (FACT, or FACT-URGENT where the body claims a stronger act than the note supports: sworn testimony, a holding, an admission).

     **The case that produced it.** In the original system a ledger row checked a quotation, found the words identical to the source, recorded in its own comment that the words were a statute's — and passed a body sentence that called them a person's sworn testimony. The check asked whether the quotation was faithful. It never asked whether the sentence characterised the source correctly.
   - Skip continuity (whether a chapter's opening and close fit its neighbours) — Production owns continuity; hand-offs go through `Handoffs/`.

   **The short-circuit rule.** A ledger row stops a re-search only when it answers **both** questions:

   - **QUOTE** — is the quoted matter faithful to the cited source? `VERBATIM` / `PARAPHRASE` / `MISMATCH`
   - **CLAIM** — does the body sentence characterise that source correctly? `SUPPORTED` / `OVERSTATED` / `UNSUPPORTED`

   The attribution case above reads **QUOTE: VERBATIM · CLAIM: OVERSTATED**. Under a single verdict it read VERIFIED, and VERIFIED short-circuited a later full audit, which is how a recorded disproof survived two passes. **A wrong VERIFIED is more durable than an unchecked claim**, because it arrives with a date, a source and a reason to stop looking.

   **A single-verdict row does not short-circuit.** Old rows are never re-read in a batch — that is the "start twelve, finish none" failure. When a chapter comes up in the backlog, its claim rows are re-read under the two-verdict standard as part of Check C, and the ledger's own header records the date that chapter was converted.
4. **Record.** Update `_Agent State.json` (new hash, date, checks completed — a run interrupted mid-chapter records which checks finished so the next run resumes, never restarts). Write the completion entry under this run's own heading in `Agent Run Log.md`. **Never regenerate either file whole.**
5. **Prove you did not touch the manuscript.** Re-hash each file in the chapter and appendix folders (SHA-256) and compare against the hashes taken at orient in step 1. Any file whose hash changed during the run gets reported **loudly** — first line of the summary, and in `_Agent State.json` as `"manuscript_changed": ["Ch07", ...]`. Report it even when the change looks legitimate, and especially when you cannot account for it. An empty list is itself the finding: record `"manuscript_changed": []`, so a run that skipped this step is distinguishable from a run that passed it. `tools/witness.py --json` (report mode only; never `--seal`) lists file changes no event accounts for.

   **This is detection; prevention lives elsewhere.** The agent's write permission may cover the whole vault; the read-only rule lives in this file. A chapter edited while marked finished reports itself as verified to each tool that asks. An unattended agent with write access and no check is that same hazard with nobody in the room.
6. **Report.** End the run with a three-line summary: chapters audited, findings by check (counts, URGENT flagged), backlog remaining. If step 5 found anything, that goes above the three lines.
7. **Hand off.** Append to the **Inbox** of `Handoffs/Fact-checker.md` a section headed `## From the nightly agent — <YYYY-MM-DD>` with the three-line summary, the number of Findings Register rows and asks written, any URGENT finding by coordinate, and where the next run resumes. If the file is missing, create it with `WORKING: nothing` as its first line. The Fact-checker writes the WORKING line; the agent leaves it as it finds it.

## No false economy, and no "You're right"

**Two rules that govern the rest of this file.**

**1. The cheap check locates. The expensive one decides.** Never state a property of a file, a source or a program from anything short of opening it or running it. A summary, a grep window, one failed query, a filename, and reading code instead of executing it are coordinates. None is a finding, and none may be written into a Findings Register row, a ledger or a report as one.

**The economy is false because the cheap answer costs more.** In one day in the original system: queue rows reported open from a summary with no file opened, closed in ninety seconds once opened; source hops recorded unreachable for five days when not one source was missing; a row closed on reasoning about what a script would do, contradicted seconds later by running it. The author: *"I want to make sure that there are no slip-ups because some false sense of token optimization or other false-economy lets things slip through the cracks."*

**The counter-example is the standard.** Asked whether an archive tool preserved what a trim deletes, the answer was tested rather than read. The tool built its filename from the date alone and opened it for overwriting, so the second run of any day destroyed that day's snapshot. A four-line test found in one minute what reading the same nine lines had not. **Run it; do not read it and report.**

**2. Never write "You're right."** The author: *"No more 'You're Right!'"* Nor "correct", "accurate", "good catch", nor the author's own point restated before it is answered. Open with the substance or the correction.

---

## Reading rules

**No illustration by hypothetical — flag each invented person.** A point illustrated with a manufactured example (a plaintiff who sues, a voter who decides, a reader who feels something) is a finding. Register it. The author: *"There was so much flummery in the made-up prose, I couldn't understand when you were making a point, and when you were inventing a fairytale."* When invented illustration and sourced evidence read alike on the page, no reader can audit the chapter without re-sourcing each sentence.

**The test:** can the person be named? A named individual, a documented case, a dated event — or the sentence goes. Watch especially for invented people introduced *as a fix* for an abstraction acting; that trades one violation for two, and it is how this failure survives an edit pass. (Standing Rules §9.)

**State the search surface before the negative.** Whenever a check finds nothing — a source that does not contain what was expected, a claim with no corroboration, a search that came back empty — the Findings Register row gives its **coverage before its conclusion**: which files, how many of how many, which terms, which method, and what was not searched.

The author: *"You need to start being transparent about how deep you're going, and how many keywords you're using."* The worked failure: asked whether a writer covered a subject across several of his books, a chat ran two keyword searches in one of the six titles in the library and reported a flat negative — a conclusion about the whole body of work, drawn from a sixth of it, stated without qualification. The proper search, three methods across all six books, confirmed the negative. The answer was right; the report was not.

**A negative is worth exactly its coverage.** `NOT FOUND` with nothing attached is no finding — it closes a line of inquiry that was never opened, and the next reader cannot tell a thorough search from two greps. The same disclosure applies to a thin search that finds something: say that it was thin.

- **Stop grepping, start reading.** Strip `<!-- -->` comments and backtick code spans before any count; open and read each line a count or grep flags before writing a verdict. A search that cannot find a thing is no evidence the thing is absent.
- **One issue at a time, each separately read.** The author: *"I would much rather that you go over each issue separately; you have more problems when you gang things together and grep instead of reading. I want you to read."* A grep locates; it never adjudicates. Take a single finding to its verdict — line open, whole passage read — before touching the next. No composite verdicts over a list of hits.
- **Reference notation is `Ch##/L##`**, two digits, always. No `§`.
- **Read whole passages, never fragments.** No verdict from a truncated line or a search window alone.
- **Original-language text:** the agent never generates text in another script. Verification is a comparison against a local source where one is reachable; mismatches are flagged in the ledger, never corrected.
- **No invented sources.** UNVERIFIED is a valid and valuable status.
- **Terms of art and the author's framework are claims of a different kind.** Tier 3 items need their underlying evidence checked; they need no citation.

## Coordination with the role chats

**On banned words.** The list has two readers: this agent, on its schedule, and `tools/check-lock-ready.sh`, which runs the sweep against a chapter being locked. Neither owns the list; both parse `Methodology/Word Lists.md`. **To add or amend a banned word, edit that block and nothing else** — never this file, never a script, never a memory note. A rule kept only in a human-readable table no check ever read is how one banned word stood dozens of times across locked chapters in the original system.

The lock gate catches what is about to be sealed; the agent catches what is already sealed. Both defer to the reader, because a hit is a coordinate.

**The division of labour:**

| | Owns | Writes |
|---|---|---|
| **Fact-check agent** (this file, serving the Fact-checker) | claims, sources, prose, glosses, attribution, leaks in the body, note faults reported as rows | Findings Register, Asks, chapter ledgers, Claims rows, Agent Run Log, `_Agent State.json`, the rulings files, `Handoffs/Fact-checker.md` (its section only) |
| **Editor** | footnote content, through cards built from the author's per-note rulings | the Source Rulings page, `Handoffs/Editor.md` |
| **`tools/check-lock-ready.sh`** | the lock boundary | stdout only |

- The author can fire the agent early, pause it, or change its schedule.
- **Collision guard:** if any file in the chapter or appendix folders was modified in the last 30 minutes at run start, the run assumes a live working session, skips those files this run, and says so in its summary.
- The Fact-checker reads the agent's output each session: the run's section in `Agent Run Log.md`, the agent's section in `Handoffs/Fact-checker.md`, and the new Findings Register rows and asks. A finding that needs a card goes to `Handoffs/Editor.md`; the Editor builds the card; Production applies approved cards. A finding the author declines is recorded with one line of reason in the register's **Closed** table; the agent reads those reasons and does not raise the same line again unless the line changes.
- Ledger appends are the shared record; each writer dates its sections. The agent's sections are titled `## YYYY-MM-DD — Agent run`.
- Anything ambiguous goes in `Asks.md` as an ask, never in a chat message to nobody.

## Scripts the agent may run

Report mode only: `tools/preflight.sh`, `tools/check-banned-words.sh`, `tools/check-epistemics.sh`, `tools/check-footnotes.sh`, `tools/check-footnote-length.sh`, `tools/check-anchors.sh`, `tools/check-crossrefs.sh`, `tools/check-glossary.sh`, `tools/check-ellipsis.sh`, `tools/check-note-content.py`, `tools/check-read.sh`, `tools/check-drive-path.sh`, `tools/have.sh`, `tools/find-source.sh`, `tools/find-page.sh`, `tools/show.sh`, `tools/witness.py --json`, and `tools/rulings.py` to record a ruling. Before running any script, read its header and usage. Never pass `--write`, `--seal`, `--fix` or `--apply`, and never run `tools/apply-card.py`, `tools/lock.py`, `tools/blockedit.py`, `tools/publish-pdfs.sh`, `tools/backup-to-github.sh` or `tools/snapshot-vault.sh`.

## Check types

The finding column of each Findings Register row opens with one of these:

FOOTNOTE, SCAN-banned-word, SCAN-epistemic, SCAN-nominalization, SCAN-abstract-noun, SCAN-unspecified-verb, SCAN-completeness, SCAN-<principle>, FACT, FACT-URGENT, GLOSS, GLOSS-URGENT, LEAK. A question goes to `Asks.md`.

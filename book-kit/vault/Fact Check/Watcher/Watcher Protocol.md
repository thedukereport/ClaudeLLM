# Watcher — Protocol

The Watcher is a scheduled task that checks that each role chat does what it was told to do. It serves the Managing editor (`Methodology/Roles.md`). The author edits this file. The Watcher reads it at the start of each run and works from it, never from its own task prompt or from memory.

**Paths.** The Watcher reads `book.toml` at the vault folder for the chapter, appendix, fact-check, claims, events, hand-off and page-snapshot folders and the chapters out of the workflow (`python3 tools/bookconfig.py` prints them). It raises nothing about a chapter listed under `[workflow] out_of_workflow`.

## Who is who

`Methodology/Roles.md` names each role, its chat and the files it writes. The Watcher checks three roles:

- **Production** — applies approved cards to `Chapters/` and `Appendices/`, writes the ledger's apply entry, commits, keeps `Fact Check/Locks.md` (through `tools/lock.py`), `Punch List.md`, `Book Structure.md` and `Project State.md`.
- **Editor** — builds cards on the Source Rulings page and keeps `Fact Check/Ship Triage.md`.
- **Fact-checker** (with the nightly agent) — keeps the chapter ledgers, `Fact Check/Claims/`, `Fact Check/Asks.md`, `Fact Check/Findings Register.md` and `Fact Check/Back-fill Queue.md`.

And three parties outside the checks:

- **The Watcher** — this scheduled task. It reads what each role left on disk, checks it against what the author told that role to do, and writes **directives** to `Directives.md`, each naming the role it is for.
- **Managing editor** — reads `Directives.md` at session open and moves each open directive into the named role's `Handoffs/<Role>.md`, or into `Fact Check/Asks.md` when it needs a new decision from the author.
- **The author** — rules on cards and on asks. The Watcher never waits on the author.

## What the Watcher may write

Only these files, all inside `Fact Check/Watcher/` (the first run creates any that are missing):

- `Directives.md` — the register of directives
- `Watcher Log.md` — one dated line per run, and the run summary
- `_state.json` — where the last run stopped

Everything else in the vault is read-only to the Watcher: chapters, appendices, ledgers, the files in `Handoffs/`, the Punch List, Project State, the rulebook, the Directive Register, Asks, the event log, each script. **No `git add`, no `git commit`.** No messages to any role's chat. A directive reaches a role only when the Managing Editor moves it into that role's hand-off file or into `Asks.md`.

**Scripts.** Before running any vault script, read its header and usage. Run only in report mode. Never pass `--write`, `--seal`, `--fix`, `--apply`, or any flag that writes. Never run `tools/apply-card.py`, `tools/lock.py`, `tools/blockedit.py`, `tools/blockid.py`, `tools/card-log.py`, `tools/dashboard-sync.py`, `tools/publish-pdfs.sh`, `tools/backup-to-github.sh` or `tools/snapshot-vault.sh`. If a script's header does not make plain that it only reads, do not run it.

## Write as you go

1. Before any checking, append a run-started line to `Watcher Log.md` with the timestamp and the window you will examine.
2. Take each finding to its verdict, then write its directive to `Directives.md` before starting the next finding. Never hold findings in memory to write at the end.
3. If the session is running short, stop taking new findings, write `_state.json` and the run summary, and record where the next run resumes.

## The run

### 0. Orient — read, in full, from disk

1. `Methodology/Standing Rules.md` — the whole file; then `Methodology/Rules — Managing Editor.md`, and the role file of each role whose work it checks (`Methodology/Rules — <Role>.md`). The core's first section governs everything here: **a match is a coordinate; only a read decides.** The word lists are in `Methodology/Word Lists.md`.
2. `Methodology/Roles.md` — who does which job, and the author's two queues.
3. Each role file in `Handoffs/`: `Fact-checker.md`, `Editor.md`, `Production.md`, `Managing Editor.md`, `Systems.md`. The first line of each gives that role's `WORKING:` line. A hand-off file that does not exist yet goes in the run summary.
4. `Methodology/Anomalies and Contingencies.md` — the faults already met, and what to do next time.
5. `Fact Check/Asks.md`, `Fact Check/Findings Register.md`, `Fact Check/Directive Register.md` and `Fact Check/Locks.md`.
6. `Fact Check/Watcher/Directives.md` and `Fact Check/Watcher/_state.json`.
7. Any `Methodology/` file changed after the last run — a new rule the author gave any role lands there.

If the vault folder is unreachable, write nothing, end with one line saying so, and stop.

### 1. Establish the window

From `_state.json`: the last run's time, the last commit seen, and the hash of the last event read. On the first run, the window is the previous 24 hours.

Collect what each role did in the window, and record which role did it (Roles.md names the files each role writes):

- `git log --stat` from the last commit seen, and `git status --porcelain` for uncommitted changes
- events in `Fact Check/events/*.jsonl` after the last hash read
- `python3 tools/witness.py --json` — file changes no event accounts for. **Never `--seal`.**
- the first line of each `Handoffs/*.md` role file (the role's `WORKING:` line), and dated entries in the hand-off files and Project State
- dated entries added to `Methodology/`, the Punch List, the Directive Register, `Fact Check/Asks.md`, `Fact Check/Findings Register.md` and `Fact Check/Locks.md`

### 2. Check A — Production: the vault changes against the rulebook

These findings are for Production, which writes `Chapters/` and `Appendices/`. For each chapter or appendix that changed in the window:

- Use the diff to locate. Then open the chapter from disk and read each changed paragraph whole, with the paragraphs either side.
- Read it against the rulebook: banned words, the epistemic rules, the footnote rules, the voice and agency rules.
- Confirm the chapter's lock state in `Fact Check/Locks.md`. A change to a chapter marked 🔒, or one with no unlock in the event log (`file.written` events on `Fact Check/Locks.md`) before the change and no reopening ruling from the author on disk, is a finding for Production.
- Read it for these fault classes: an element edited after the author ruled it (a `decision.recorded` event followed by a later change to the same block); a card applied in part (some of its elements in the chapter, others not); a quotation shortened with no ellipsis — for any quotation added or changed in the window, open the cited source and compare the run of words word for word (`tools/check-ellipsis.sh` prints what an ellipsis took out).

Then run the read-only checkers that bear on what changed (for example `tools/check-banned-words.sh`, `tools/check-epistemics.sh`, `tools/check-footnotes.sh`, `tools/check-footnote-length.sh`, `tools/check-anchors.sh`). Compare against the previous run's results in `_state.json`: a failure present before the window is not Production's work in this window — note it once, do not re-raise it. Open and read each line a checker points at before anything goes in a directive.

### 3. Check B — what each role said against what is on disk

Production's statements live in commit messages, Project State entries and ledger apply entries; each role's statements live in its hand-off file, in `claim.made` events, in rows marked done in the Directive Register, and in its reports under Watcher directives. For each one, open the files and confirm it, and name the role whose statement it is.

Give particular attention to **"ready" reported as progress.** For each `decision.recorded` event in the window, confirm a matching `edit.applied` landed in the chapter. Rules — Production, "A ruling is finished when it is in the chapter and the card says so", governs here. A ruling with no write is a finding for Production.

### 4. Check C — the standing obligations

Each of these leaves a mark on disk. Check the mark.

The Watcher cannot open the Source Rulings page itself. It reads cards from three places on disk:

- **The page snapshot** (`[paths] page_snapshot` in `book.toml`): one file per card in `proposals/<card id>.json` (fields `title`, `chapter`, `where`, `status`, `current`, `proposedPara`, `proposedNote`, `reviewedPara`, `reviewedNote`, `submittedAt`, `reviewedAt`, `approvedAt`, `appliedAt`, `editedAt`), the author's button presses in `presses/`, and the time the page was read in `TAKEN`. State that time in the run summary. A snapshot older than the window covers only part of it; say which part.
- **The card-log entries**: each card's read list, `<card_reads>/<card id>.reads.json` (`[paths] card_reads`); one ledger section per card, headed `## <date> — the sources named on card <card id>: <title>`; and `source.read` events in `Fact Check/events/*.jsonl` that hold the field `card`.
- **The hand-off files and apply entries**: `Handoffs/Editor.md`, `Handoffs/Production.md`, and the ledgers' apply entries.

The event log holds no other card events. Never report a card as missing an event of any other kind.

- **The author's queue is never empty** (Editor). `Handoffs/Editor.md` lists cards built or waiting. A hand-off that lists none while `Fact Check/Ship Triage.md` lists chapters still to card is a finding for the Editor.
- **Ship Triage order** (Editor). The chapter on the Editor's `WORKING:` line is the next one in the Ship Triage register's order, or the hand-off gives a dated reason.
- **Each card shows current and proposed text** (Editor). Where `Handoffs/Production.md` or an event records a card sent back for missing text, and `Handoffs/Editor.md` shows no rebuild, that is a finding for the Editor.
- **Applied as approved** (Production). For each card the snapshot shows as `approved`, a ledger apply entry and a commit follow, or the hand-off records the card sent back unapplied.
- **Lock sequence** (Production). For each chapter changed in the window, the event log shows `tools/lock.py` unlocking it before the change and relocking it after, or the chapter was unlocked throughout.
- **Preflight before research** (Fact-checker). For each chapter whose ledger or claims file changed in the window, confirm a preflight receipt for that chapter (`.preflight/chNN.stamp`, written by `tools/preflight.sh`) dated before the change.
- **Reads logged** (Fact-checker). Each new ledger line names its search surface and has a matching row in `Fact Check/Claims/`. A question for the author found in a ledger or hand-off reached `Asks.md` in the same turn.
- **Scratch Notes routed** (Managing editor). Items in `Scratch Notes.md` with no routing mark go in the run summary for the Managing Editor.
- **Directives honoured** (each role). Read `Fact Check/Directive Register.md` whole: a directive marked done with no evidence named, and a comment of the author's in the window that asks for work and has no row, are findings for the role the directive names.
- **No card served over the author's instruction** (Editor). For each `note.ruled` or `decision.recorded` event in the window, the same item answers the author's instruction in the page snapshot (its card's `reviewedAt` or `editedAt` later than the ruling, and the card's text following the author's words) or in a hand-off entry; one that does not is a finding for the Editor.
- **Card reads logged** (Editor; Fact-checker for the Claims rows). Run `tools/check-card-logged.py --json`; it only reads. NO READ LIST is the Editor's; NO CLAIMS ROW, NO LEDGER and NO EVENT are the role named in the card's hand-off entry, the Editor when none is named. STALE SNAPSHOT or NO SNAPSHOT goes in the run summary for the Editor, as a check that did not run. Compare with `_state.json` and raise only what is new in the window.
- **Closed lines held** (Editor). Run `tools/check-card-closed.py` in report mode: a card open on a line an approved or applied card already changed is a finding for the Editor.
- **Asks** (Fact-checker). A DECIDE ask past due whose recorded outcome is missing.
- **One register.** No new place where open work is written down was created in the window without a line in `Methodology/Roles.md` (Rules — Systems, "One register").
- **Hand-off files current** (each role). The first line of each role's hand-off file reads `WORKING: <task> — <time>` or `WORKING: nothing`. A `WORKING:` line older than 12 hours with no matching activity is a finding for that role.
- **Commits not pushed.** Report the count in the run summary. Pushing is the author's alone, so this never becomes a directive.

Some instructions leave no mark on disk — reading the rulebook at session open, printing the push command in chat. The Watcher cannot see chat. Say so in the summary when it matters; never guess at what happened in a conversation.

### 4a. Check D — each card read against its chapter (Editor and Production)

The author, quoting a chat back to itself as the typical failure: *"Four errors, one root cause, and you've named it four times. I audited each note's text in isolation and never read the card against the chapter."*

For each card the snapshot or a hand-off file shows as built, approved or applied in the window:

1. Open the chapter from disk. Read the paragraph the card names, whole, with the paragraphs either side and each footnote definition those paragraphs anchor.
2. Read the card's proposed text from its snapshot file (`reviewedPara` and `reviewedNote` when set, else `proposedPara` and `proposedNote`) into that place, as the chapter would read once applied. Read the body and its notes together. Where the snapshot has no file for the card, say so in the run summary and check what the chapter shows.
3. Look for what an isolated audit misses:
   - a note whose source does not support the body sentence it is anchored to, or a body quotation whose source the notes no longer cite
   - a note anchored on a marker the proposed body removes, or a body marker with no definition
   - a proposal written against text the chapter no longer holds (the card quotes superseded wording)
   - cruft: working notes, drafting residue, talk about the card itself, or workflow vocabulary left in the proposed text
   - two notes telling one story, or a note repeating the body
   - a card applied in part: some of its elements in the chapter, others still waiting
4. Record which identity the verdict rests on: block id, exact string, or the source page you read.

A card that passes its recorded prose audit and fails this read is a finding: for the Editor when the card is built or approved, for Production when it is applied. The audit record certifies the paperwork; this read checks the card in place.

### 4b. Faults the author has already named

Before writing any directive, search `Methodology/Standing Rules.md`, the role files, `Methodology/Anomalies and Contingencies.md` and earlier entries in `Directives.md` for the same fault.

If the author has named the fault before, the directive says so on its first line, with each earlier date and the author's words quoted from the file. Then the directive asks the role it names for a **gate**: a script or check that refuses the action, named, with the file it lives in. The reason, from the original system's review of its own process: *"Every rule that depends on me remembering has failed, repeatedly."* For a fault the author has already named, a promise to take more care gives the author nothing to approve.

### 5. Before writing a directive

- **Read to a verdict, one finding at a time.** Never a composite verdict across a batch of hits.
- **Check it is not already recorded.** Search `Directives.md` (open, approved, declined), the Punch List, the Directive Register, `Fact Check/Asks.md` and `Fact Check/Findings Register.md`. If it is recorded there and moving, skip it. If it is recorded and stalled, the directive points at the existing record and adds nothing new.
- **A declined directive is never raised again.** The author: *"If it has been checked and I approved it, I don't want to get asked about it again."*
- **Stay inside the Watcher's job.** Claim verification and sentence scans belong to the nightly fact-check agent; footnote content belongs to the Editor, working from the author's per-note rulings. The Watcher checks each role's conduct: what the role did, what it said it did, and what it was told to do.

### 6. Write the directive

Each directive names one role and one route:

- **ROUTE → <role>** — the directive enforces a rule the author has already given. The Managing Editor moves it into `Handoffs/<Role>.md`.
- **ASK** — the directive needs a new decision from the author. The Managing Editor moves it into `Fact Check/Asks.md`.

The Watcher writes the directive to `Directives.md` and moves on. It never waits on the author for either kind.

Append to `Directives.md` in this form, writing the box as a real Markdown checkbox (`- [ ]` at the start of the line):

```
## W-YYYY-MM-DD-NN — <role> did X at <where>

<open box: dash, space, [ ], space> OPEN

**Route:** <ROUTE → Production | ROUTE → Editor | ROUTE → Fact-checker | ROUTE → Systems | ASK>

**Found:** <file and block id, commit hash, or event hash; with the timestamp>

**What I read:** <the passage, diff or event, quoted whole — never cut>

**The instruction it breaks:** <the rule quoted word for word, with its file and heading, and the author's date where the file gives one>

**Directive for <role>:**
> <the instruction the role will act on — specific enough to act on without re-reading this entry, and naming the check that will show it done>

**Routed:**

**<role>'s report:**

**Watcher's check:**
```

The Managing Editor fills **Routed:** with the file it moved the directive to and the date. The author rules only on what reaches the author as a card or an ask; the author's answer to an ASK is recorded in `Asks.md`, and the Watcher reads it there.

The directive's own prose follows the rulebook: actors named, active voice, no banned words, no mind-reading. Describe what is on disk and what the rule says. Never say what any role intended or meant.

### 7. Close the loop on earlier directives

For each directive marked **Routed:**:

- If the role has written a report, under **<role>'s report:** or in its hand-off file, open the evidence it names. Confirmed → change `- [ ] OPEN` to `- [x] VERIFIED <date>` and write what you read under **Watcher's check**. Not confirmed → keep the box open, mark it `REOPENED <date>`, and write what is still missing.
- If the role has not acted within 24 hours of routing, say so in the run summary for the Managing Editor.
- An open directive with an empty **Routed:** line older than 24 hours goes in the run summary for the Managing Editor.
- A report that describes intent ("I will read the card against the chapter") confirms nothing. Verify the action on disk, or the gate in the vault and its refusal on a test case.

For each ASK directive the author declined in `Asks.md`: change the box to `- [x] DECLINED <date>` and leave it in place as the record.

### 8. Finish

- Update `_state.json`: run time, last commit seen, last event hash read, checker results for the next run's comparison, and where to resume.
- Append the run summary to `Watcher Log.md`.
- End the session with three lines: directives written (count, and any that concern the author's words failing to reach the book, first); earlier directives verified or reopened; anything unreachable or unresolved.

## Times

Each time written to any Watcher file comes from the clock at the moment of writing: run `date -u '+%Y-%m-%d %H:%MZ'` and copy its output. Never estimate, round forward, or write a time before it has happened. A run-finished line is written after the last check, from the clock, and nowhere else.

If you find a time in these files that is wrong, leave the line as it stands and append a dated correction beneath it, giving the right time and how you established it.

## Never

- Never fabricate. A source not found, a file not opened, a check not run — say so.
- Never reason over truncated output. `head`, `cut`, width-limited `grep` locate; re-read the whole line or paragraph before judging it.
- Never report a check that did not run.

# Roles — who does what on this book

The author may amend any line of this file, and the author's amendment governs. Claude writes the amendment into this file in the turn the author gives it.

**The rulebook is `Methodology/Standing Rules.md` (the core), plus one file per role, `Methodology/Rules — <Role>.md`.** Each chat reads the core and its own role's file. This file says who does which job. It copies no rule.

The book's title, the author's name, the paths, the library and the review page's address are set in `book.toml` at the vault folder. Every tool reads them from there.

---

## Two queues for the author, and only two

1. **The Source Rulings page** (its address is `[page] url` in `book.toml`): cards, each with the current text and the proposed text in full. The author approves, edits or sends back.
2. **`Fact Check/Asks.md`**: questions only the author can answer, each with what happens if the author says nothing.

Nothing else asks for the author's ruling. The Watcher's directives, the Findings Register, the Ship Triage lanes and the hand-off files feed these two; they never wait on the author directly. A ruling on process (a tool sample, a skill change, deleting a scheduled task) is an ask in `Asks.md` like any other.

## The six roles

| role | chat | writes ONLY to | starts each session by reading | hands off to |
|---|---|---|---|---|
| Author | the author (a person) | the book, through rulings | — | everyone |
| Fact-checker | **Fact-checker**, plus the nightly agent and any reading agents it starts | `Fact Check/` except `Watcher/` and the Ship Triage register: ledgers, `Claims/`, Findings Register, the rulings registers, the agent's run log and state file, the Back-fill Queue; `Handoffs/Fact-checker.md` | Standing Rules · `Methodology/Rules — Fact-checker.md` · `Handoffs/Fact-checker.md` · `Handoffs/Editor.md` · `Fact Check/Asks.md` | Editor |
| Editor | **Editor** | the Source Rulings page (cards), `Fact Check/Ship Triage.md`, `Handoffs/Editor.md` | Standing Rules · `Methodology/Rules — Editor.md` · `Handoffs/Editor.md` · the page's `presses` and `proposals` · the author's note rulings (`note.ruled` events) · the chapter, end to end | Author, then Production |
| Production | **Production** | `Chapters/`, `Appendices/`, `Book Structure.md`, `Punch List.md`, `Project State.md`, `Fact Check/Locks.md` (through `tools/lock.py`), the ledger's apply entry, git commits, PDFs, `Handoffs/Production.md` | Standing Rules · `Methodology/Rules — Production.md` · `Handoffs/Production.md` · approved cards on the page | Managing editor |
| Managing editor | **Managing Editor**, plus the scheduled Watcher | `Fact Check/Watcher/`, `Fact Check/Directive Register.md`, `Scratch Notes.md` (routing marks), `Handoffs/Managing Editor.md` | Standing Rules · `Methodology/Rules — Managing Editor.md` · each file in `Handoffs/` · `Fact Check/Watcher/Directives.md` | the role each item belongs to |
| Systems (IT) | **Systems** | scripts in `tools/`, tests in `tests/`, `Skills/`, the page's code, scheduled-task prompts and protocols (on the author's instruction), `Tools Index.md`, `Methodology/Anomalies and Contingencies.md`, `Handoffs/Systems.md` | Standing Rules · `Methodology/Rules — Systems.md` · `Handoffs/Systems.md` · `Tools Index.md` · `Methodology/Anomalies and Contingencies.md` | the role whose tool it fixed |

Each role writes an anomaly it meets into `Methodology/Anomalies and Contingencies.md` the turn it meets it (Standing Rules §7); Systems keeps the file in order.

## What each discipline does in publishing, and the directive for each chat

Standard practice is drawn from book and magazine publishing (*The Chicago Manual of Style*, chapter 2, on the editorial and production process; the magazine fact-checking desk). Paste the line under **Open with** as the first message of each new session of that chat. Name each chat in your project after its role.

### Author
- **In publishing.** The author owns the words and the claims. Editors and checkers query; the author answers. The text changes only on the author's yes.
- **Here.** The author's ruling on a card or an ask is the only thing that changes the book.

### Fact-checker
- **In publishing.** The checker opens the writer's own source, checks each claim against it, and keeps a record per claim: the claim, the source, where in the source, the words found, the status. A dead end is recorded with the places searched. Questions go to the writer on a query list. The checker reports and never rewrites. The checker never rules one source right and another wrong.
- **Directive.**
  1. Work one chapter per session. Read the chapter, its ledger and its `Claims` file before opening any source.
  2. Log each source read in the turn it is made: a `Claims` row and a ledger line, with the search surface stated.
  3. Each question for the author goes to `Asks.md` in the same turn.
  4. A finding that needs a card goes to `Handoffs/Editor.md` with the claim, the source and the words; the Editor builds the card.
  5. Read the nightly agent's run log and its note in your hand-off file at session start. A change to the agent's protocol goes to `Handoffs/Systems.md` as an inbox item.
  6. End by writing `Handoffs/Fact-checker.md`.
- **Open with:** *You are the Fact-checker. Read `Methodology/Roles.md` (Fact-checker), then `Methodology/Standing Rules.md`, then `Methodology/Rules — Fact-checker.md`, then `Handoffs/Fact-checker.md`, and take the next item there.*

### Editor
- **In publishing.** The editor reads for the argument, the paragraph and the sentence, and queries the author with proposed wording. The author accepts, edits or rejects. One pass has one purpose; a style sheet keeps decisions the same across the book.
- **Directive.**
  1. Read the page's `presses` and `proposals` before each reply (Rules — Editor, "Read the rulings page before every reply").
  2. Work one chapter's cards per session, in the order of `Fact Check/Ship Triage.md`.
  3. A card cites only reads the Fact-checker has logged. A source the log does not show goes to `Handoffs/Fact-checker.md` first.
  4. A footnote card starts from the author's note ruling for that note (`note.ruled`), `Methodology/Footnote Plan.md` and the six directives A–F.
  5. Each card shows the current text and the proposed text in full (`Methodology/How a Card Is Built.md`).
  6. Approved cards go to `Handoffs/Production.md` by title.
  7. End by writing `Handoffs/Editor.md`.
- **Open with:** *You are the Editor. Read `Methodology/Roles.md` (Editor), then `Methodology/Standing Rules.md`, then `Methodology/Rules — Editor.md`, then `Handoffs/Editor.md`, read the Source Rulings page, and take the next chapter there.*

### Production
- **In publishing.** Production applies the approved changes and only those, keeps the versions, sets the pages and runs the proofs. It makes no editorial decision. A change that no longer matches what was approved goes back to the author.
- **Directive.**
  1. State each chapter's lock (`Fact Check/Locks.md`) before touching it; reopening a locked chapter is the author's decision.
  2. Apply approved cards exactly as approved, with `tools/apply-card.py`. If the file has moved and the text no longer fits, send the card back on the page, unapplied.
  3. Mark each card applied on the page and write the ledger's apply entry in the same turn.
  4. Commit after each batch and print the push command; pushing is the author's.
  5. Keep `Punch List.md`, `Book Structure.md` and `Project State.md` current.
  6. End by writing `Handoffs/Production.md`.
- **Open with:** *You are Production. Read `Methodology/Roles.md` (Production), then `Methodology/Standing Rules.md`, then `Methodology/Rules — Production.md`, then `Handoffs/Production.md`, and apply the approved cards listed there.*

### Managing editor
- **In publishing.** The managing editor keeps the schedule and the flow: what is with whom, what is late, what is blocked. The managing editor edits no content.
- **Directive.**
  1. Read each hand-off file and the Watcher's newest directives.
  2. A directive that enforces a rule the author has already given goes to the hand-off file of the role that owns the file in question. A directive that needs a new decision goes to `Asks.md` through the Fact-checker's hand-off.
  3. Route `Scratch Notes.md` items the same way and mark each routed.
  4. Report to the author once per session: the count of cards waiting on the page, the count of open asks in `Asks.md`, the days left to the author's ship date (from `Project State.md`), and what is blocked and on whom.
  5. End by writing `Handoffs/Managing Editor.md`.
- **Open with:** *You are the Managing Editor. Read `Methodology/Roles.md` (Managing editor), then `Methodology/Standing Rules.md`, then `Methodology/Rules — Managing Editor.md`, then each file in `Handoffs/` and `Fact Check/Watcher/Directives.md`, and route what is open.*

### Systems
- **In publishing.** Systems keeps the tools working: one source of truth per kind of record, each change tested before release, a written runbook, and failures reported to a person.
- **Directive.**
  1. Fix what the hand-off files list for Systems.
  2. A tool that writes is shown to the author on a sample first (`tools/uat.py`, `Methodology/UAT Log.md`); Systems runs `tools/smoke-test.sh` before hand-back.
  3. Scheduled tasks: each prompt names its role, defers to its protocol in the vault, and copies no rule.
  4. Retire a script by moving it out of `tools/` and removing its name from each protocol, skill and `Tools Index.md` in the same session.
  5. End by writing `Handoffs/Systems.md`.
- **Open with:** *You are Systems. Read `Methodology/Roles.md` (Systems), then `Methodology/Standing Rules.md`, then `Methodology/Rules — Systems.md`, then `Handoffs/Systems.md` and `Tools Index.md`, and take the first fault there.*

## Practices shared by each role

1. **One rulebook.** Standing Rules and the role files. A directive points to a section and copies none of it.
2. **One writer per file**, as the table names it, with these append-only exceptions:
   - **Hand-off inboxes.** Each `Handoffs/<Role>.md` has an `## Inbox` section. Any role appends an item there for that role; only the owner removes it.
   - **`Fact Check/Asks.md`.** Any role appends a new ask in the file's format; the Fact-checker numbers, chases and closes it.
   - **Field-level shares.** On the page, the Editor writes a card's text and Production sets only its applied fields. In a chapter ledger, Production appends only the apply entry. In `Fact Check/Watcher/Directives.md`, a role appends only its report under its directive.
   - **The event log** (`Fact Check/events/`) is written by the tools on behalf of whichever role acts.
   - **`tools/card-log.py`**, run by the Editor, appends Claims rows, one ledger section per card and `source.read` events, and changes nothing already there.
3. **Work moves through `Handoffs/`.** The author never relays prompts or reports between chats.
4. **One task per session.** A session ends when its task ends, before it is long enough to be compressed. A long source read goes to a reading agent that logs what it read.
5. **Say what you are working on.** The first line of each role's hand-off file reads `WORKING: <chapter or task> — <time>`, or `WORKING: nothing`.
6. **After any compaction**, re-read Standing Rules, the role's `Methodology/Rules — <Role>.md` and the role's hand-off file before the next action.
7. **A finding is written down in the turn it is found**, in the file this table assigns.

## Scheduled tasks

| task | serves | schedule | protocol |
|---|---|---|---|
| Watcher | Managing editor | every 3 hours (set your own) | `Fact Check/Watcher/Watcher Protocol.md` |
| Fact-Check Agent, nightly | Fact-checker | once a night, at an hour no chat is working (set your own) | `Fact Check/Agent Protocol.md` |

Each scheduled task's prompt says only: who it serves, and "Read the protocol named here and follow it exactly." The protocol holds the instructions, so the author can change them by editing one file.

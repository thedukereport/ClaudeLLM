# Rules — Systems

**Read after `Methodology/Standing Rules.md` (the core), at session start and after any compaction.** Where this file and the core differ, the core governs; where the author's newest words differ from both, the author's words govern and go into the core the same turn. The record of things that broke, and what to do next time, is `Methodology/Anomalies and Contingencies.md`.

---

## Nothing writes at scale until the author has accepted a sample

**The rule.** A tool that writes may run on a **sample** freely — it changes nothing and prints the complete before and after of the first few changes. It may **not** write at scale until `Methodology/UAT Log.md` holds a line for that tool recording what the author was shown and that the author accepted it. `tools/uat.py` enforces this. The author: *"You cannot build anything anymore without some kind of user acceptance testing. I don't need to get 300 changes into a process for you to find a bug."*

## Broken is no question. Fix it, then say what you fixed.

The author: *"If it is broken, it is broken. FIX IT."*

**A repair with a mechanical test is not judgment.** A path either opens or it does not. `os.path.exists` answers it for each row, the answer is the same for each reader, and a wrong repair is visible the moment the test runs. **The test IS the sample.** So: run the test on each row, repair only the rows it can verify, name the rows it cannot, and report afterwards.

**The question to ask before asking:** is there a command that decides this? If yes, run it and fix what it finds. If no, it is the author's.

## A path that opens only in the sandbox is a broken path

**The `drive_path` field exists to end a search** — a title invites a second search, a path ends the question. A path that resolves inside Claude's session and nowhere on the author's computer passes any test run from inside the session. `tools/check-drive-path.sh` fails it by name.

## A tool that reports a fault prints Ch##/L##

The author rules by the card title and navigates by the coordinate. **A tool that reports a fault the author cannot open has reported nothing.** `bookconfig.coord(n, line)` is the one implementation; each tool prints coordinates through it. A finding with no coordinate prints `—`, never a guess.

## One register, and a markdown table is never the state

The author: *"When I see serial statements like this, I think the workflow has no mechanism to account for changes as they happen (or to catch errors); it's just bespoke false confidence in whatever the last script you wrote is."*

**Open work lives in the places `Methodology/Roles.md` names** — the Source Rulings page, `Fact Check/Asks.md`, `Fact Check/Findings Register.md`, `Fact Check/Back-fill Queue.md`, `Punch List.md`, the hand-off inboxes — and nowhere else. A new place where open work is written down is declared in Roles.md the day it is made, or it is a place nobody looks. The reason: in the original system the author asked four times for all tasks to be reconciled, and the cause each time was a register that no screen read; one register recorded a fault in a note while a card in another proposed promoting that note into the sentence it failed to support.

### The markdown is a rendering. The state is JSON.

A tool once read its state by parsing a markdown table positionally — column two the item, column five the state. A column was inserted at position three the same day, each later column shifted one right, and the tool began reading the item's TEXT as its STATE. It reported a quarter of the true count and gave no sign of trouble. **A tool keeps its state in JSON (or the event log); a markdown table is written from it and never read back.**

## Scripts go in `tools/`, and `Tools Index.md` is the map

Each script lives in `tools/` under its own file name. **`Tools Index.md`, at the vault folder, is the map** — one line per script, in the script's own words (its first docstring or header line), with its callers and whether it is part of the daily workflow. Add a row when a script is added. A script that cannot describe itself in its own first line shows as "(no description in the file)", which is a gap in the script.

Retire a script by moving it out of `tools/` and removing its name from each protocol, skill and `Tools Index.md` in the same session.

## The glob that reads its own backups

**It happened twice in the original system.** A `.bak` file in a glob gave a verification report six false failures. A week later a count of a field reported hundreds of broken paths where the live files held none — **each figure came from the `.bak` snapshots beside the live files.** The tool was reading the backups of the broken version.

**The number was wrong in the direction that invents work.** Each tool that globs a directory of the author's files excludes backups through one shared function, `bookconfig.is_backup(path)`, never in each tool's own glob.

## Rules from the table "Voice and framing rules"

- **Copy the file before you transform it.** Before any scripted change that rewrites a whole file — a regex sweep, a column repair, a bulk substitution — copy the file first.
- **Run it; do not read it and report.** A tool's behaviour is established by running it on a known input. Reading the code is a coordinate.
- **Each writing tool is run twice in testing.** A tool that cannot be run twice cannot be trusted to have run once.
- **A test writes nothing outside a temporary copy.** A test copies the vault (or the sample vault) to a temporary folder, points `BOOK_VAULT` there, and asserts on output. Nothing under the author's name is written by a test, and no test writes to `Chapters/`.
- **`tools/smoke-test.sh` before hand-back.** A check that did not run is reported as NOT RUN, never as passing.

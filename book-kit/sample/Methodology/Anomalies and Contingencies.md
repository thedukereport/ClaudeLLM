# Anomalies and Contingencies

The author: *"write a contingency for every anomalous case you run into so it does not get lost in compression."*

Each entry here was found by something breaking, usually after it had already reported clean. **The contingency is what to do the next time the signal appears**, written so it survives a compacted conversation and a new session. Any role writes an entry the turn it meets an anomaly (Standing Rules §7); Systems keeps the file in order.

**The three rules under all of them:**

1. **A surface that did not run is not a surface that found nothing.** If a check cannot take its measurement, that is a failure, never a pass.
2. **Hand-check three rows before quoting a total.** In the original system each wrong number was caught that way, and none was caught by reading the code.
3. **Say you are stuck, in those words.** A guess reported as an answer costs more than an admission.

## What an entry holds

```
### <letter><number> · <the anomaly, in a few words>
**Signal.** What you see when it happens: the message, the count, the symptom.
**Case.** What happened, when, and what it cost — in this book, with the date.
**Contingency.** What to do the next time the signal appears.
**Enforced by.** The script, test or gate that now refuses it, or "nothing yet".
```

When something here has no entry, **write one.** An anomaly met twice with no entry is the same failure as a finding held in memory: it survives until the context window fills.

---

## A. Starter entries

These came from the system this kit comes from. Their lessons do not depend on any one book.

### A1 · A backup file is swept into the work
**Signal.** A count or a migration includes a `.bak` file, a file whose name starts with `_`, or one with `backup` in its name.
**Case.** A `.bak` file in a glob gave a verification report six false failures. A week later a count reported hundreds of broken paths where the live files held none: each figure came from backups of the broken version. The number was wrong in the direction that invents work.
**Contingency.** One shared exclusion, `bookconfig.is_backup(path)`, used by each tool that globs the author's files. Never a per-tool glob.
**Enforced by.** `tools/bookconfig.py`.

### A2 · A search that finds nothing
**Signal.** Zero hits, "not found", an empty result.
**Case.** A work was recorded absent after a "whole-library filename search" for its author — and the filename contained the author's name. Separately, a phrase search returned zero on a page that held the phrase, because the scan's text layer had garbled it.
**Contingency.** A zero is a fact about the query. State the surface before the negative: which shelves, how many files, which terms, which method. Then read the page, or search a different way, before writing that anything is missing.
**Enforced by.** Standing Rules §1 and §6; `tools/have.sh` and `tools/find-source.sh` print their coverage.

### A3 · Two processes writing one path
**Signal.** A `disk I/O error` or a corrupted file from inside a rebuild, while everything else keeps working.
**Case.** A dashboard and a shell both rebuilt the same derived file through the same scratch file. One process removed and recreated the file the other had open.
**Contingency.** A scratch file belongs to the process that made it: name it with the process id, take turns with a lock file, and clean up in `finally` so a failed build leaves neither lock nor scratch behind. Two processes writing one path is a bug, never a race to tolerate.
**Enforced by.** Nothing yet in this kit; check any tool that writes a derived file.

### A4 · A guard that has never failed
**Signal.** A check passes on every run, and nothing has ever made it fail.
**Case.** A stray-file guard in a backup script began asking git whether each staged path was ignored. Git calls any path already in the index "not ignored", and each path the guard asked about had just been staged, so for days the guard passed everything. Its test still looked for an older version of the guard and failed for that reason, which hid the real fault behind a stale one.
**Contingency.** A guard is tested by handing it the case it exists to stop, in a scratch copy, and watching it stop it. Then the same test is run against the old code, and it must fail there.
**Enforced by.** The guard's own test in `tests/`.

### A5 · A rule with a measurement and no gate
**Signal.** A rule is written down, a check measures it, and nothing anywhere refuses to proceed.
**Case.** "No citation of a source nobody has opened" was written into the rulebook and a check was built the same day, but the check ran only in a smoke test that asked whether it crashed. Citations of books nobody held were written, reviewed, ruled on and locked.
**Contingency.** A rule that matters is wired to a place that refuses: the lock gate, a card check, `tools/uat.py`. A rule that nothing can refuse is a hope.
**Enforced by.** `tools/check-lock-ready.sh` runs `tools/check-read.sh NN --strict`.

### A6 · An address used as an identity
**Signal.** A mark, a retraction or a reference keyed to a line number, a row or a position now points at something else.
**Case.** Of the open items whose quoted text could be tested, most quoted text that was no longer at the line they named. Separately, a correction written against a row and item number silently discarded each later ruling the author made at that address.
**Contingency.** Store the block id from `<!-- b:xxxxxx -->` and compute the line at read time (`tools/blocks.py`); print `Ch##/L##` for the author and store it nowhere. A retraction names the event it undoes (`vaultlog.retract`), never the place the event happened.
**Enforced by.** `tools/blocks.py`, `tools/vaultlog.py`.

---

## B. This book's entries

<!-- Add entries here as they happen, newest last. Letter them B1, B2, … -->

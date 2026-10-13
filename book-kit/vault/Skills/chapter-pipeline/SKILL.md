---
name: chapter-pipeline
description: >
  The full per-chapter finishing ritual for your book. Use when the user says
  "run the pipeline on chapter X," "full pass on chapter X," "finish chapter
  X," "chapter X is drafted, take it through the process," or issues the
  familiar numbered list (check examples, run the neurolinguistic skill, add
  subheads, run the citation audit). Runs seven ordered steps: citation audit
  (all phases), neurolinguistic pass, example-fit check, subhead check,
  satellite-file sync, cross-reference sweep, PDF cascade. Each step reports
  before the next runs. Ends at a lock gate checked by tools/check-lock-ready.sh.
---

# Chapter Pipeline

The original author issued this sequence by hand for every chapter; satellite files were the step most often missed until he prompted for them. The pipeline exists so nothing gets skipped and every step reports before the next starts.

**Approval protocol throughout:** findings are presented one at a time with full paragraph context, A/B/C options, and a recommendation. The author answers with a letter or supplies exact wording. Batch approval only when the author asks for it.

**Before step 1:** run the session-brief open protocol if it has not run this session, and run `tools/preflight.sh NN` to put the chapter's prior work in front of you. Check `Fact Check/Locks.md`: if the chapter is locked, say so first. Reopening a locked chapter is the author's decision.

## Steps

Run in order for the named chapter. Announce each step's start and report its findings before going on.

### 1. Citation audit
Invoke the **citation-audit** skill — all three phases (continuity, citations, fact-check ledger). The ledger write is part of this step, never deferred.

### 2. Neurolinguistic pass
Invoke the **neurolinguistic-prose** skill: full editorial pass including the mechanical sweeps (openers, redundancy, cross-section sources, tics) and the pre-Edit subject-scan gate for every fix. The mechanical checks in `tools/` (`check-banned-words.sh`, `check-epistemics.sh`, `check-ellipsis.sh`, `check-glossary.sh`) report coordinates; each hit still gets read and ruled.

### 3. Example-fit check
Invoke the **example-fit-check** skill. Three tests: (a) does each example, source, and illustration demonstrate the pattern the chapter labels it with; (b) is each foreign-language or technical term glossed at first-in-chapter use; (c) is each source-jump bridged so the reader sees why the argument moves from one writer to the next. The failures this step was built from: two distinct rhetorical techniques blended into one; a thesis attributed to an older writer when a later writer delivers it; a term of art credited to the writer who quoted it instead of the writers who coined it; paragraphs listing four to six scholars with no bridges between them; a foreign term used with no gloss at its first use in the chapter.

### 4. Subhead check
Sections longer than ~800 words without a subhead get one proposed. Subheads state content plainly — no structural self-announcement (Principle 11 of neurolinguistic-prose applies to subheads too).

### 5. Satellite sync
Diff the chapter against each satellite file and propose updates:
- The chapter map or outline your book keeps (title, number, one-line summary, any claims about the chapter's content). The recorded failure: a chapter map that kept five stale claims about chapter content after the chapters changed.
- Any summary document derived from the chapters (a series outline, a podcast or course outline).
- `Punch List.md` — **explicit checkoff pass, not a summary paragraph.** For every `- [ ]` item in the chapter's section:
  1. Check it against the chapter's current text. If completed, change `- [ ]` → `- [x]` with a DONE / COVERED / CUT annotation and the section anchor.
  2. If the item was routed to another chapter, MOVE the item (cut it here, paste under the target chapter's `### Ch. N —` heading). Do not leave a "routed to Ch. M" note under Ch. N — that still counts as open against Ch. N and blocks its lock.
  3. If the item is still legitimately open, leave it as-is and surface it in the exit report.
  Writing a "closing note" paragraph that describes DONE/COVERED/ROUTED but leaves the checkboxes as `- [ ]` is the recurring failure (five recurrences in the original project). The narrative must APPLY to the checkboxes in the same pass, not just describe them. A lock requires zero open items.
- `Fact Check/` ledger — confirmed current in step 1.

### 6. Cross-reference sweep
Run `tools/check-crossrefs.sh`, then search the full manuscript for: the chapter's number and title, counted items the chapter changed ("nine exchanges" surviving a cut that left eight), and references from other chapters into this one. If chapters have been renumbered, search for the old numbers too, using the key in `Project State.md`. Flag every stale hit, and read each one before ruling on it.

### 7. PDF cascade
Run `tools/publish-pdfs.sh`. Confirm output before declaring the pipeline complete.

## Lock gate

Before declaring the pipeline complete, run `tools/check-lock-ready.sh NN` and read its output. It must show:

- The chapter's Punch List section has **zero** `- [ ]` items.
- The footnote checks it runs (anchors, definitions, orphans) are clean.
- **The mechanical-sweep tables are attached with verdicts.** A lock backed by narrative claims of cleanliness instead of sweep tables is the recorded false-lock failure: in the original project, chapters were locked under a discipline that skipped four principles, never touched footnotes, and never explicitly checked telegraphing.
- **The lock is version-stamped:** the lock entry set with `tools/lock.py` in `Fact Check/Locks.md`, and the exit report, record the skill versions that audited the chapter, e.g. `[nlp-v4 / ca-v3 / ga-v2]`. A lock without a stamp is treated as locked under unknown rules.

`Fact Check/Locks.md` is the one place a chapter's lock state lives. Set it with `tools/lock.py`, never by hand-editing a heading or a marker in another file.

If `tools/check-lock-ready.sh` passes, the chapter may be LOCKED. If `Fact Check/Locks.md` says locked but the Punch List has open items, the state is LOCK-DRIFT — do not report the pipeline as complete. Return to Step 5 and finish the checkoff pass.

## Rule-change re-audit queue

A lock certifies the chapter against the rules that existed on the lock date — nothing later. Whenever a principle, standing rule, or banned word is added:

1. Add a dated row to `Methodology/Standing Rules.md` (single source of truth for rules; a new banned word also goes into `Methodology/Word Lists.md`, where `tools/check-banned-words.sh` reads it).
2. Add a Punch List entry: "Re-sweep locked chapters for [rule] — chapters locked before [date]," listing the affected chapters from their lock stamps in `Fact Check/Locks.md`.
3. The re-sweep targets ONLY the new rule (cheap search per chapter, per Sweep Scope), never a full pipeline re-run.

This queue is the fix for the core finding of the original author's book-wide audit: most of its ~4,000 hits were prose locked under older rules, aging silently because nothing scheduled the re-check.

## Exit report

One compact block: step-by-step outcomes, fixes applied vs. deferred, satellite files touched, ledger rows added, cross-references corrected, PDF status, lock-gate result. Update `Project State.md` and the role's hand-off file (session-brief close protocol).

---
name: session-brief
description: >
  Session open/close protocol for your book project. OPEN: at the start of any
  book-related session — or when the user says "where were we," "status,"
  "brief me," "catch up," "what's next," or begins chapter work without stating
  context — read the vault state files and post a short status before doing
  anything else. CLOSE: when the user says "wrap up," "close out," "done for
  today," or the session's work reaches a natural end, write the session's
  outcomes back to Project State.md and the role's hand-off file. Use this
  skill instead of asking the user to re-explain project context; the answer to
  "what were we doing" lives in the vault, never in a prior chat.
---

# Session Brief

Cross-session context loss is the recorded failure this skill exists to prevent. Sessions die, compaction eats history, and parallel chats hold state the current one can't see. The vault persists. State lives there.

## On open

Read, in order:

0. **`Methodology/Standing Rules.md` — every row, before anything else and before touching prose.** Not optional, not a skim. If this session works in a role (editor, fact-checker, production), read that role's rules file too, for example `Methodology/Rules — Editor.md`. The author: *"Processes that we have been following for months on this project have disappeared like a patient with Alzheimer's."* On the day he said it, a whole session ran on remembered rules: three new rules were written *into* the Standing Rules file during that session, while a different, older rule broke after each one. The rule broken four times in one hour had been in the file for days, already marked as flagged before, and nobody opened it. Writing a rule down is not loading it.
1. `Project State.md` (vault root) — active chapter, open tasks, pending changes, infrastructure state.
2. The role's hand-off file in `Handoffs/` — what the last session in this role finished, left open, and asked the next one to do.
3. `Punch List.md` — outstanding items.
4. `Fact Check/Locks.md` — which chapters are locked.
5. The active chapter's ledger, `Fact Check/Ch. NN — Title.md` — verification state.

If the chapter map has changed (chapters split, merged or renumbered), note the old-to-new number key from `Project State.md` before reading any older record that cites a chapter by number.

Then post a status in chat:

```
Rules: [N rows read from Standing Rules.md (+ role rules file), last dated entry]
Chapter: [active chapter, state and lock — e.g., Ch. 04 audited, unlocked; Ch. 05 not started]
Open: [top 3 tasks by number, from Project State + hand-off + Punch List]
Last decision: [most recent entry in Project State's decision log]
```

The first line is a receipt. A status posted without it means step 0 did not happen.

Ask which item to work on only if the user's opening message didn't already say.

## Re-read triggers

Step 0 runs again, mid-session, whenever any of these happen:

- **After a compaction.** A summary of a conversation is not a copy of the rules. Compaction is the most reliable predictor of rule loss.
- **When the author flags the same class of error twice.** Two flags mean the file is not loaded, whatever memory says.
- **When a session has run long.** In the original author's record, the failures of one bad day clustered entirely in the back half; the early work held to process and the last two hours did not.
- **Before any lock, PDF cascade, or push.**

## On close

Update `Project State.md`:

- Active chapter and its state
- Open tasks (add new, mark done, keep numbering — Task #NN style)
- Decision log: one dated line per decision made this session (standing rules go into `Methodology/Standing Rules.md` as well)
- Pending skill changes awaiting install
- Infrastructure notes (index freshness, tuning values, anything a parallel session would need)

Update the role's hand-off file in `Handoffs/`: what this session finished, what it left open, and the first thing the next session in this role should do.

## Standing rules

- **Search before asking.** Before asking the user a factual question about the book, its sources, or its state, search the library (`tools/find-source.sh`, `tools/have.sh`) and the vault. Ask only after both come up empty, and say what was searched.
- **State outlives the chat.** Anything a future session will need goes in `Project State.md`, the role's hand-off file, or the relevant ledger before the session ends. A decision that lives only in conversation is a decision scheduled for loss.
- **Wrong-chat guard.** When the user references state this session can't see ("the review page," "the 18 open items"), check `Project State.md` and the hand-off files before saying it's unknown.

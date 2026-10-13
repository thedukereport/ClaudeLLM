# Rules — Production

**Read after `Methodology/Standing Rules.md` (the core), at session start and after any compaction.** Where this file and the core differ, the core governs; where the author's newest words differ from both, the author's words govern and go into the core the same turn. The lock sequence is in `Methodology/Chapter Close-Out Procedure.md`.

---

## One chapter per session

A chapter can run many thousands of words, and applying a card means reading the chapter whole. A session that applies cards across several chapters fills its memory and compacts within hours. So: take the cleared cards for one chapter, unlock it, apply them, relock, mark them applied, commit, print the push command, write the hand-off file with the next chapter named, and stop. The next chapter is a new session. Long tool output (git, the lock gate, preflight) goes to a file in a scratch folder; read its last lines, never the whole thing in chat.

## Showing changes — the hard rule

**Each change is shown before it is made: one at a time, with `Ch##/L##` and the surrounding context.** The author: *"I always want to see changes one at a time with context Chapter and Line number, ALWAYS."*

## A ruling is finished when it is in the chapter and the card says so

**The rule.** A card is done when two things are true together: the chapter file holds the text, and the card's status is `applied` with `appliedAt` set and an apply entry in the chapter's ledger. One without the other is unfinished. An edit with no mark is invisible, and a mark with no edit is a lie.

## The workflow, in the author's words

The author: *"Show me the context of the questions you have. Show me the changes you propose. When I agree with the changes, you make the changes. When I find a problem with your proposal, you show me the new version before you apply the changes. … My expectation is that when I approve something, it will get done before you compress your memory and forget … what you are doing."*

**The six steps. Nothing else is the workflow.**

1. **CONTEXT.** The question arrives with the text it is about — the body line, the note, the lines either side — verbatim from disk, under `Ch##/L##`. On the page: the card's `before`, `current[]` and `after`.
2. **PROPOSAL.** The replacement text, in full, under its own heading — never a description of it, never a word count. On the page: `proposedPara` and `proposedNote`.
3. **THE AUTHOR'S RULING.** The author's press on the card, or words in chat.
4. **AGREEMENT → THE EDIT IS MADE.** The same day, by Production: never queued, never staged, never "pending a gate". The chapter file changes (`tools/apply-card.py`) and the card is marked applied.
5. **A PROBLEM → A NEW VERSION IS SHOWN.** The author's objection produces a new version of the card, shown before anything is written. It never produces a silent fix applied on the strength of the objection. An objection is no approval of whatever comes next.
6. **NOTHING IS REVISITED.** The card holds the whole trail (its `removed` list), so nobody re-derives a decision already made.

## The chapter and the card change together, or neither changes

The case in the original system: the author, reading a card, said *"It does not look like you have synced the changes we just made."* The chapter held the paragraph the two had settled together. The card still proposed an earlier draft of it, and was marked applied while doing so — so the card was offering to replace the finished paragraph with a worse version of itself.

**A chapter file and the card that caused the change are written in the same step.** If the card cannot be updated in that step, the chapter is not written either.

**And the author's rulings given in conversation are written to the log as the author's, in the turn they are given**: `decision.recorded`, with the actor from `book.toml` (`author_actor`), the words verbatim. A ruling that exists only in a chat transcript is lost; the log is the record.

## PUSHING IS THE AUTHOR'S; PRODUCTION PRINTS THE COMMAND

The author: *"pushing is mine, and Production prints the command after each commit."* No chat pushes. After each commit Production prints the line the author runs from the vault folder, unprompted:

```
./tools/backup-to-github.sh -m "<commit message>"
```

Unpushed commits are reported in the Watcher's run summary and in the Managing Editor's status, never as an ask.

## Rules from the table "Voice and framing rules"

- **Show context with a command, never from judgment.** `tools/show.sh NN L` runs before any change is proposed, and its output is pasted above the proposal.
- **Show each change before making it.** One at a time, `Ch##/L##` plus context.
- **Preflight before prose.** `tools/preflight.sh NN` runs before Claude writes a word of a chapter, and Claude reads the output.
- **The author edits while we work — address blocks, never match remembered text.** Build each replacement from a read taken in the same turn, and write through `tools/blockedit.py`, which addresses a line by its block id and refuses a stale replacement.
- **grep locates nothing in the manuscript.** `grep` is never used to look at manuscript text. `tools/blocks.py` locates, `tools/show.sh` reads, judgment comes last.
- **Garbage collection is no question.** When a self-addressed comment, a stale hedge, or a correction note turns up in the manuscript, Claude clears it without asking, and logs the change.
- **No renumbering without permission.** Existing footnote and list numbers in any file are frozen.
- **The PDFs after the lock.** `tools/publish-pdfs.sh` after removing the existing PDF, so a failed render cannot leave a stale file looking current.

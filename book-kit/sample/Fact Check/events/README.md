# The event log

`Fact Check/events/YYYY-MM.jsonl` is the append-only, hash-chained record of what happened in the vault. `tools/vaultlog.py` writes it on behalf of whichever role acts; nobody edits it by hand. Each record holds the hash of the one before it, so a hand-edited line, a truncation or a lost write breaks the chain, and `python3 tools/vaultlog.py --verify` says where.

**Never delete a line.** A mistake is undone by appending a later event that retracts it by hash (`vaultlog.retract(event, why)`), so the mistake and its correction are both on the record. A retraction names the event it undoes, never the row or line where the event happened.

**The author's rulings** are recorded with the actor named in `book.toml` (`[book] author_actor`), with the author's words verbatim. Nothing under that actor is written by a test: a test points the log at a temporary folder.

## Kinds

The tools refuse a kind not on this list (`vaultlog.KINDS`).

| kind | when |
|---|---|
| `decision.recorded` | the author ruled: on a card, an ask, or in chat |
| `note.ruled` | the author ruled one footnote (`chapter`, `slug`, `note_kind`, the author's words) |
| `rule.stated` | the author stated a rule; it also goes into `Methodology/Standing Rules.md` |
| `proposal.raised`, `proposal.written` | an item was put to the author; a machine-applicable proposal (block id, old hash, new text) |
| `prose.audited` | the neurolinguistic-prose audit of a proposal, hashed to the exact text it audited |
| `edit.applied`, `edit.reverted`, `edit.refused` | text was written into a chapter, put back, or refused as stale |
| `block.assigned`, `block.changed`, `block.deleted` | block ids stamped; a block's content changed; a block stopped existing |
| `source.read`, `source.absent` | somebody opened a source and read a page; a search found nothing, with its coverage |
| `claim.made`, `claim.corrected` | a number asserted with the method that made it; something Claude told the author that proved false, and the correction |
| `disagreement.opened`, `disagreement.resolved` | two sources or tools answered one question differently; resolved with a verdict and a cause, both required |
| `file.written`, `file.changed.unexplained` | a tool wrote a file; `tools/witness.py` found a change no event accounts for |
| `note.recorded` | a note, including a retraction (`retracts_hash`) |
| `item.superseded`, `submission.repaired` | an item replaced by a newer one; markup restored to the author's submission after a plain-text round trip (the words untouched) |

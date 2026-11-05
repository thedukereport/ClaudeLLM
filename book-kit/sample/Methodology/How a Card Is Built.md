# How a Card Is Built

A card is one proposal on the card desk, built by the Editor (or QA), ruled by the author, applied by Production. Each card holds proposed text: the whole paragraph or the whole footnote as it should read. A card that asks a question without words is unfinished (Standing Rules §5).

## Read first, in full

- `Methodology/Standing Rules.md`, `Methodology/Rules — Editor.md` and `Methodology/Footnote Plan.md`.
- The chapter the card touches, whole, from disk. Each line ends with a block marker `<!-- b:xxxxxx -->`; the block id is how tools find the line after edits move it.
- The chapter's ledger and `Fact Check/Claims/Ch NN.jsonl` (directive A).

## Rules that decide the text

- **Footnotes are citations only**: where the thing is (author, title, publisher and year, page or section, URL). Content belongs in the body. No self-talk, no "verified", no library or vault paths, no workflow vocabulary, no names of the team.
- **Full Chicago citation** at a source's first appearance in the chapter; short form after.
- **No banned word** from `Methodology/Word Lists.md` in proposed text (`tools/check-card-words.py`); no contrast setups; no universal quantifiers unless literally true; no invented people; no chapter as agent.
- **Never write a fact from memory.** Read the source first (the library, then the author's approval for the web). Quote what you read. If you cannot find support, keep the author's sentence and ask the author for the source; never cut, never invent.
- **Record who said what, when and where.** Never judge whether a claim is true, never cut or soften a claim because it seems unsupported or risky, never rule one source right and another wrong.
- **When the body and its own note disagree**, fix the body to say what the note's source says, unless the note is the thing that is wrong.
- **Smallest honest change.** Keep the author's voice and words wherever they are not the fault.
- **Settled is settled.** No card on a line or note the author has approved (`tools/check-card-closed.py --card`).

## The fields of a card

Each card is one JSON record. `tools/cards.py add <card.json> --why "<reason>"` puts it in `Fact Check/Cards/cards.jsonl` as a new version; the record's `id` names the card. The store keeps every version, and the author's presses on a version are events in the log, so a card's status now is the store's newest version with the presses after it (`tools/cards.py show <id>`).

| field | what it holds | who writes it |
|---|---|---|
| `title` | `Ch NN · <short plain title naming the problem>` — the name the author rules by | Editor |
| `chapter` | the chapter number | Editor |
| `where` | the coordinate or coordinates, `Ch##/L##`, and the note slug where one is in play | Editor |
| `job` | one sentence: the paragraph's job in the chapter's argument, taken from the chapter | Editor |
| `jobLabel` | the heading shown over `job`; defaults to "The paragraph's job" | Editor (optional) |
| `before` | the whole paragraph above, verbatim from disk | Editor |
| `current[]` | each piece of text the card changes, as it stands on disk now: `{where, text}`, `text` copied byte for byte without the block marker | Editor |
| `after` | the whole paragraph below, verbatim from disk | Editor |
| `proposedPara` | the replacement text, in full. When the card changes more than one paragraph or note, each piece is a segment and the segments are joined by `"\n\n⁂\n\n"`; a segment that begins `[^slug]:` is a footnote definition | Editor; the author may edit it |
| `segLabels` | one label per segment of `proposedPara`, in order ("Ch05/L112 — the paragraph", "[^slug] — its note") | Editor, when there is more than one segment |
| `proposedNote` | the replacement footnote, when the card has a separate note box | Editor; the author may edit it |
| `noteless` | `true` when the card has no note box (its notes, if any, are segments of `proposedPara`) | Editor |
| `removed[]` | any words a proposal takes out of a note, with the reason (earlier versions of the card stay in the store, and the desk shows them in a fold) | Editor |
| `review` | Claude's check, shown to the author under the proposal: the six directives and the footnote steps below, each answered with evidence | Editor |
| `status` | `yours` (with the author, open), `submitted` (the author sent edits or a directive), `approved` (the author pressed Approve), `applied` (Production wrote it into the chapter), `held` (its owner took it off the desk), `superseded` | the Editor writes `yours`; the author's presses and Production's apply set the rest (`tools/cards.py fold`); `tools/cards.py hold` sets `held` |
| `submittedAt`, `approvedAt`, `appliedAt`, `note`, `notedAt`, `directiveAt` | times and the author's words, folded in from the author's presses | `tools/cards.py fold`, never written by hand |
| `reviewedPara`, `reviewedNote` | the text Claude last checked | Editor |
| `reopenedBy` | the hash of the author's own `decision.recorded` event that reopens a closed line; one way past the closed-line check (the other is the author's "Reopen this line" press on the desk) | Editor, only from the author's words |

The gates are not fields. The card desk runs each one every time it draws a card (the note check, the closed-line check, the banned words, the unread facts, the prose audit by a second session, and whether the card still reads as the chapter does), and holds a card that fails one under "With Claude" with the reason. `tools/cards.py add` runs the word and read gates as the version goes in (`book.toml` `[gates]`).

## The review: six directives

Each card's `review` answers these, in the author's order (Rules — Editor, "The six directives"):

- **A** — the ledger and `Fact Check/Claims/Ch NN.jsonl`, read first: what they already say.
- **B** — the source, read whole, with the search surface stated, including zero results.
- **C** — what belongs in the body, asked before touching the note.
- **D** — redundancy, checked before the proposal and after it.
- **E** — the neurolinguistic-prose skill on each word the author will read, run by a session other than the one that wrote the card, and recorded as a `prose.audited` event by `tools/prose.py --record-card <id> --findings <file> --verdict ok|finding`.
- **F** — each read logged, including what was not found (`tools/card-log.py`).

## The review: seven footnote steps

For any card that touches a footnote, after the directives:

1. **The paragraph's job.** State in one sentence what job the anchoring paragraph does in the chapter's argument (the card's `job`). A note whose source misses that job has a placement fault no trim can fix.
2. **The author's note ruling.** Read the author's last `note.ruled` for that chapter and slug. Put it at the top of the review, quoted whole, and do what it says.
3. **The body first.** Ask whether anything in the note belongs in the body (directive C); promoting beats cutting.
4. **The six piles.** Sort the note sentence by sentence into CITATION, WARNING, RELIED ON, REPEATS, CONTENT and JUDGEMENT (`Methodology/Footnote Plan.md`). Content goes to the body or the ledger; judgement goes; repeats go.
5. **A hand-read verdict governs.** Where a person has read the note and recorded a verdict on it, and that verdict disagrees with `tools/assess-notes.py`, the hand-read verdict governs.
6. **Citation form.** Full Chicago citation at first appearance in the chapter, short form after; no page-mismatch findings; no sentence about the copy in the library; an author gloss at first mention in the body.
7. **The note check.** Run `tools/check-card-notes.py --card <file>`, `tools/check-card-words.py` and `tools/check-card-closed.py --card <file>` before the card goes in. A card that fails any of them does not go to the author; the desk holds it.

## Writing the card

1. Build the card from reads taken in this turn. Faulty lines next to each other in one paragraph go on one card, with the whole paragraph as it will read.
2. Run `tools/card-log.py` for the sources the card names, so each read is on record before the author sees it (`tools/check-card-logged.py` reports any that is not). `tools/card_reads.py --card <id>` lists any name, number, date or quotation in the passage still without an opened read; those go to the Fact-checker first.
3. Put it in the store: `tools/cards.py add <card.json> --why "<reason>"`. A new version of an existing card is a new line in the store; the old version stays there whole and never stands beside the new one on the desk.
4. Ask a second session (QA, or the Editor for QA's cards) to audit its prose and record the audit.
5. Note the card by its title in `Handoffs/Editor.md`. If it is not ready, `tools/cards.py hold <id> --by Editor --reason "<why>"` keeps it off the author's desk until `release`.

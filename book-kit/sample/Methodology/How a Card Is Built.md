# How a Card Is Built

A card is one proposal on the Source Rulings page, built by the Editor, ruled by the author, applied by Production. Each card holds proposed text: the whole paragraph or the whole footnote as it should read. A card that asks a question without words is unfinished (Standing Rules §5).

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

Each card is one document in the page's `proposals` collection, and one file in the page snapshot (`proposals/<card id>.json`).

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
| `removed[]` | earlier versions of this card, newest first, each whole, **its version line first** ("v2 — <date> — what changed and why"), then the words; and any words a proposal takes out of a note, with the reason | Editor |
| `review` | Claude's check, shown to the author under the proposal: the six directives and the footnote steps below, each answered with evidence | Editor |
| `status` | `yours` (with the author, open), `submitted` (the author sent edits for checking), `approved` (the author pressed Approve), `applied` (Production wrote it into the chapter) | the page and the author's presses; Production sets `applied` |
| `submittedAt`, `reviewedAt`, `approvedAt`, `appliedAt`, `editedAt`, `claudeReadAt` | times; `reviewedAt` set after the author's `submittedAt` brings back the Approve button | the page; the Editor sets `reviewedAt` and `claudeReadAt` |
| `reviewedPara`, `reviewedNote` | the text Claude last checked | Editor |
| `noteCheck` | `{ok, at, text, findings}` from `tools/check-card-notes.py --card`; a card whose note failed, or whose text changed after the check, is held off the author's queue | Editor, by merging the tool's output |
| `closedCheck` | the result of `tools/check-card-closed.py --card`: whether the card touches a line or note an approved or applied card already changed | Editor, by merging the tool's output |
| `reopenedBy` | the hash of the author's own `decision.recorded` event that reopens a closed line; the one way past `closedCheck` | Editor, only from the author's words |

## The review: six directives

Each card's `review` answers these, in the author's order (Rules — Editor, "The six directives"):

- **A** — the ledger and `Fact Check/Claims/Ch NN.jsonl`, read first: what they already say.
- **B** — the source, read whole, with the search surface stated, including zero results.
- **C** — what belongs in the body, asked before touching the note.
- **D** — redundancy, checked before the proposal and after it.
- **E** — the neurolinguistic-prose skill on each word the author will read, recorded as a `prose.audited` event.
- **F** — each read logged, including what was not found (`tools/card-log.py`).

## The review: seven footnote steps

For any card that touches a footnote, after the directives:

1. **The paragraph's job.** State in one sentence what job the anchoring paragraph does in the chapter's argument (the card's `job`). A note whose source misses that job has a placement fault no trim can fix.
2. **The author's note ruling.** Read the author's last `note.ruled` for that chapter and slug. Put it at the top of the review, quoted whole, and do what it says.
3. **The body first.** Ask whether anything in the note belongs in the body (directive C); promoting beats cutting.
4. **The six piles.** Sort the note sentence by sentence into CITATION, WARNING, RELIED ON, REPEATS, CONTENT and JUDGEMENT (`Methodology/Footnote Plan.md`). Content goes to the body or the ledger; judgement goes; repeats go.
5. **A hand-read verdict governs.** Where a person has read the note and recorded a verdict on it, and that verdict disagrees with `tools/assess-notes.py`, the hand-read verdict governs.
6. **Citation form.** Full Chicago citation at first appearance in the chapter, short form after; no page-mismatch findings; no sentence about the copy in the library; an author gloss at first mention in the body.
7. **The note check.** Run `tools/check-card-notes.py --card <file>` and merge its `noteCheck` into the card; run `tools/check-card-words.py` and `tools/check-card-closed.py --card <file>`. A card that fails any of them does not go to the author.

## Writing the card

1. Build the card from reads taken in this turn.
2. Run `tools/card-log.py` for the sources the card names, so each read is on record before the author sees it (`tools/check-card-logged.py` reports any that is not).
3. Write it to the page. A new version of an existing card moves the old text into `removed[]`, whole, version line first; the old version never stands beside the new one.
4. Note the card by its title in `Handoffs/Editor.md`.

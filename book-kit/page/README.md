# The Source Rulings page

`source-rulings.html` is the page where you rule on the book's cards. Claude writes a card for each change it proposes: the chapter text as it stands, the proposed text, and Claude's check of it against the source. You read the card, edit the text if you want, and approve it. Production then applies approved cards to the chapters with `tools/apply-card.py`.

The page is a claude.ai artifact with a small database. Your presses are saved in that database, and Claude reads and writes it with the ArtifactData tool. No script in the vault can open the page, so the tools work from a snapshot of the database that Claude copies into the vault (see "Taking the snapshot").

## Views

| View | What it holds |
|---|---|
| Ready for you | Cards you sent for checking that Claude has checked. Each one has an Approve button. |
| With Claude | Cards you sent and Claude has not checked yet, and cards the note check or the prose check is holding. |
| Waiting for you | New cards for your ruling. |
| Approved, going in | Cards you approved that are not in the chapter yet. |
| In the book | Applied cards. Every button still works; "Take a second look" reopens one. |
| Reopen? | A card that changes a line you already approved. The tab shows only when one is waiting. Press "Reopen this line" or "Keep it closed", with your reason if you want to give one. |
| Triage | Items from a triage list, by lane (cut, ships as is, drop), with Agree and No. |
| Asks | Questions Claude needs you to answer, one card at a time. |
| Back-fill | Works the footnotes cite that the library index cannot find, with "I'll get it" and "Approve citing it unread". A work in the library that nobody has read never comes here: it goes to the Fact-checker's reading queue (`tools/dashboard-sync.py queue`). |
| All | Every card. |

A green box at the top lists the cards ready for you and the new ones, and the browser tab shows the count. The page holds one queue for you: no count appears above the cards unless it opens a list you can work through.

## Your typing is kept

Every write to the database, from any chat, redraws the page. So the page keeps each keystroke in every box as a draft in this browser (`localStorage`, key `sr-drafts`, kept 14 days), puts each draft back after a redraw with the cursor where it was, and marks the card "Unsaved draft". A draft clears when the saved text equals it, or when you press "Throw away my edits". Drafts live only in the browser you typed in.

## The gates

- **Note check (`noteHeld`).** A card that proposes a footnote is held under "With Claude", with no Approve button, when its stored `noteCheck` failed, when its text changed after the check, or when Claude checked it after the `noteGateFrom` time with no note check. `tools/check-card-notes.py` writes the `noteCheck`.
- **Prose check (`proseHeld`).** Every card goes through the neurolinguistic-prose skill before it reaches you. A card is held under "With Claude", with no Approve button, until its `proseCheck` says ok for the exact text you would approve (the paragraph box, then the footnote box). `tools/prose.py` records each audit against a hash of that text, so a rewrite makes the audit stale by itself.
- **Closed lines (`closedHeld`).** A card that changes a paragraph or footnote that an approved or applied card already changed goes to the "Reopen?" view as a whole card. So does a card you pressed Approve on that was later rewritten. The page works this out from the cards and presses it already has. `tools/check-card-closed.py` adds your rulings from the event log as `closedCheck`. Two ways past: your own decision in the event log, named in the card's `reopenedBy`, or your "Reopen this line" press on the card (`lineReopenedAt`, for the text you saw). A new version written over the card holds it again.
- **Approve only checked text (`stage`, `readyList`).** Approve is refused when the text in the box differs from the text Claude checked. Edit the text, press "Send my edits for checking", and the card comes back to "Ready for you" once Claude has checked it.

## Publishing the page

Ask Claude in a chat to publish `page/source-rulings.html` as an artifact with the database capability. Claude calls the Artifact tool with:

- `file_path`: the path to `source-rulings.html`
- `capabilities`: `{"db": {}}`
- `icon`: `checklist`

The page is private to you when it is published. Then:

1. Put the artifact's address in `book.toml`, under `[page]`, as `url = "https://claude.ai/artifact/…"`. The tools print it in ledger entries, and the role chats use it.
2. Have Claude write the page's settings document (see "The config document").
3. Ask Claude to read the page back once with ArtifactData `list` on `proposals` to confirm the database answers.

To change the page later, Claude republishes the same file to the same `url`. A republish keeps the database.

## The collections

| Collection | One document per | Who writes it |
|---|---|---|
| `proposals` | card; the document id is the card id | Claude writes the card; your presses update it |
| `presses` | press of a card button, with its result | the page |
| `sources` | source behind a passage, grouped into passage cards by `group` | Claude writes it; your rulings update it |
| `triage` | triage item | Claude writes it; your Agree or No updates it |
| `register` | one document, `summary`: an open-work count. The page no longer shows it | Claude |
| `asks` | open row of `Fact Check/Asks.md` | `tools/dashboard-sync.py build`, loaded by Claude; your answer updates it |
| `backlog` | cited work the library index cannot find | `tools/dashboard-sync.py build`, loaded by Claude; your press updates it |
| `config` | one document, `page`: the page's settings | Claude |

`sources`, `triage`, `asks` and `backlog` are shown in the order of their `order` field, so each document needs one.

## The card fields (`proposals/<id>`)

Text fields hold Markdown as it goes into the chapter, footnote markers included. A card that changes more than one line puts the segments in one text field, separated by a line holding only `⁂` with a blank line either side (`"\n\n⁂\n\n"`).

| Field | What it holds |
|---|---|
| `title` | "Ch 02 · what the card does", in plain words |
| `chapter` | "Ch 02" |
| `where` | the lines the card changes, e.g. `Ch02/L5 (block 3204ff); Ch02/L8 [^fed1_test] (block 244556)` |
| `status` | `yours` (waiting for you), `submitted` (you sent edits), `approved`, `applied` |
| `job`, `jobLabel` | what the paragraph does in the chapter's argument, and its label |
| `before`, `after` | the paragraphs either side, for reading |
| `current` | `[{where, text}]`, one entry per segment: the chapter text now. Name the block in `where` ("(block 3204ff)"). An entry whose `where` says "the new line goes after this one" marks an insertion point |
| `proposedPara` | the proposed text; the page's edit box writes here |
| `reviewedPara` | the text Claude checked; Approve needs `proposedPara` to equal it |
| `submittedPara` | the text you sent for checking |
| `proposedNote`, `reviewedNote`, `submittedNote` | the same three for the separate footnote box |
| `noteless` | `true` hides the footnote box (put a footnote definition in a segment instead) |
| `segLabels` | a label per segment, e.g. `["The paragraph", "Its footnote"]`; `paraLabel`, `noteLabel` label the boxes otherwise |
| `removed`, `removedLabel` | what a trim took out of a note, and why, one line each |
| `review`, `reviewedAt` | Claude's check, in words, and when |
| `submittedAt`, `editedAt`, `approvedAt`, `withdrawnAt`, `reopenedAt` | written by the page when you press |
| `appliedAt`, `appliedNote` | written by Claude after `tools/apply-card.py --write` |
| `claudeReadAt` | when Claude last read your presses on this card; later presses show under "Not yet read by Claude" |
| `noteCheck` | `{ok, at, text, tool, findings}` from `tools/check-card-notes.py` |
| `closedCheck` | `{ok, at, text, tool, reopenedBy, findings}` from `tools/check-card-closed.py` |
| `reopenedBy` | the hash of your `decision.recorded` event reopening a closed line |
| `proseCheck` | `{ok, state, text, sha, audit, at, tool}` from `tools/prose.py` |
| `lineReopenedAt`, `lineReopenText`, `lineReopenWords` | written by the page when you press "Reopen this line": when, the text you saw, your words |
| `lineKeptAt`, `lineKeptText`, `lineKeepWords` | the same for "Keep it closed" |
| `covers` | ids of `sources` rows this card replaces |

## How Claude writes a card

1. Build the card as a JSON file, for example `Handoffs/editor-tools/cards/ch02-reflection-choice.json`, with `status: "yours"` and `reviewedPara` equal to `proposedPara`. Read the chapter on disk for `current`, and give each entry its block id.
2. Read the card's text under `Skills/neurolinguistic-prose`, write the findings for all fourteen principles to a JSON file, and record the audit:

   ```
   tools/prose.py --record-card Handoffs/editor-tools/cards/ch02-reflection-choice.json --findings /tmp/findings.json --patch-dir /tmp/patch
   ```

   An audit that names fewer than fourteen principles is refused. `tools/prose.py` with no arguments lists the open cards on the snapshot with no audit of their current text.
3. Run the other two checks on the file:

   ```
   tools/check-card-notes.py  --card Handoffs/editor-tools/cards/ch02-reflection-choice.json --patch-dir /tmp/patch
   tools/check-card-closed.py --card Handoffs/editor-tools/cards/ch02-reflection-choice.json --patch-dir /tmp/patch
   ```

   A refused note goes back to the Editor to rebuild. A card on a line you closed goes to your "Reopen?" view.
4. Merge each `proseCheck`, `noteCheck` and `closedCheck` from the patch files into the card.
5. Write the card with ArtifactData: `action: "set"`, `collection: "proposals"`, `doc_id: "<card id>"`, `file_path: <the card file>`. Updating an existing card needs `if_version`, the version Claude last read.
6. Put the card's reads on record: `tools/card-log.py Handoffs/editor-tools/cards/<card id>.reads.json`, then again with `--write`.

## Taking the snapshot

The tools read the page from `Handoffs/editor-tools/page-snapshot/` (book.toml `[paths] page_snapshot`).

1. Empty the folder's collection subfolders, so a card deleted on the page does not linger.
2. For each of `proposals`, `presses`, `asks` and `backlog`, call ArtifactData `action: "list"` with the page's `url`, the `collection`, and `out_dir` set to the snapshot folder's full path. Each document lands at `page-snapshot/<collection>/<doc id>.json`. Pass `query.limit: 1000`, and page on with `query.cursor` while a result gives a `next_cursor`.
3. Write the current UTC time to `page-snapshot/TAKEN`, for example `2026-10-13T15:00:00Z`.

`check-card-logged.py` fails a snapshot older than 24 hours, and `apply-card.py --write` refuses one: you may have withdrawn an approval since.

The sample book holds a practice snapshot with four cards: one applied, one whose footnote the note check refuses, one held on the line the applied card changed, and one ready to apply. Its `TAKEN` time is fixed, so before practising `apply-card.py --write` on a copy of the sample, write the current time to that copy's `TAKEN`.

## Applying an approved card

Production runs `tools/apply-card.py <card id>` to see the whole Current and Proposed of every line, then `--write`. It refuses a locked chapter, a chapter out of the workflow, and a card whose `current` text no longer matches the chapter. After the write it prints the patch for the card (`status: applied`, `appliedAt`, `appliedNote`), which Claude writes with ArtifactData `update` on `proposals/<card id>`.

## The config document (`config/page`)

Claude writes it with ArtifactData `set`, collection `config`, doc id `page`. Until it exists, the defaults at the top of the page's script apply (`PAGE_DEFAULTS`).

| Field | What it does | Default |
|---|---|---|
| `bookTitle` | the name above the page title | "Your book" |
| `outOfWorkflow` | chapter numbers no card may reach; the closed-line gate skips them. Keep it equal to `[workflow] out_of_workflow` in book.toml | `[]` |
| `workflowLabel` | how the page names the chapters in the workflow, e.g. "Chapters 2–9" | built from `outOfWorkflow` |
| `noteGateFrom` | UTC time; a card Claude checked after it must have a note check | `1970-01-01T00:00:00Z` (every card) |
| `footer` | a sentence added to the footer, e.g. how the source cards are numbered | empty |

Example:

```json
{"bookTitle": "Two Arguments About Government", "outOfWorkflow": [], "workflowLabel": "Chapters 1–2",
 "noteGateFrom": "1970-01-01T00:00:00Z", "footer": ""}
```

## The other collections' fields

- `presses`: `card`, `title`, `button`, `action` (approve, send, undo, withdraw, reopen, reopenline, keepclosed, ask, backfill, triage …), `at`, `result` (saved, refused, not saved, failed), `reason`.
- `sources`: `order`, `group` (the passage card it belongs to), `gtitle`, `chapter`, `code`, `source`, `kind` (`later`: in the chapter now; `new`: new card today; `prop`: earlier card), `question`, `yourDraft`, `sourceSays`, `proposed`, `card`, `firstWith`, `lastWithout`, `notes`, `before`, `para`, `paraWhere`, `paraNote`, `after`, `dep`; the page writes `ruling` (do, dont, skip, delete), `ruledAt`, `comment`.
- `triage`: `order`, `lane` (cut, ship, drop), `chapter`, `line`, `src`, `text`, `cut`, `cutFound`, `reason`, `finding`; the page writes `ruling` (agree, no) and `ruledAt`.
- `register/summary`: `total`, `asOf`, `byChapter` (`[{ch, open}]`), `note`.
- `asks`: written by `tools/dashboard-sync.py build`: `order`, `aid`, `kind`, `ask`, `blocks`, `silence`, `asked`, `fileLine`, `current`, `before`, `after`; the page writes `answer` (ok, no, words), `words`, `answeredAt`; Claude writes `claudeReadAt` and, after `dashboard-sync.py answers --write`, `writtenAt`.
- `backlog`: written by `tools/dashboard-sync.py build`: `order`, `title`, `lane` (notondrive; works in the library go to `Fact Check/Reading Queue.md` instead), `drivePath`, `chapters`, `cites`, `current`; the page writes `action` (get, exception; older documents may hold backfill or skip), `note`, `actedAt`; Claude writes `writtenAt`.

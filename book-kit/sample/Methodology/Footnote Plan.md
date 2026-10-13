# Footnote Plan — six piles per note

The rubric each footnote card follows. The Editor reads it before building any card that touches a note; `tools/assess-notes.py` and `tools/check-card-notes.py` apply it by machine, and each of their findings is a coordinate to read, never a ruling to obey.

## The rule

**A footnote is a citation, not an essay.** A footnote holds three things and stops:

1. who said it and where — author, title, edition, page or section;
2. the words the body relies on, if the body has not already printed them;
3. one clause where a reader following the citation would otherwise land in the wrong place or read the wrong words — a misprinted title, a stale edition, a variant text, an unclosed chain, a locator the source itself gets wrong.

**Full citation once, short form after.** A source gets its full Chicago citation at its first appearance in a chapter and a shortened form at each appearance after — author surname, short title, locator. Never a bare "Ibid."

A note never says what the copy in the library is (reflowed, unpaginated, an EPUB), never discusses its own making, never says how much to believe a source, and never says what the book is about.

## The six piles

`tools/assess-notes.py` reads each footnote definition in the chapters, finds the body paragraph that anchors it, splits the note into sentences — protecting abbreviations, initials and quotations — and sorts each sentence into one of six piles:

| pile | what it means | what happens to it |
|---|---|---|
| **CITATION** | a pointer to a place in a work: page, chapter, section, volume, edition, archive, the date of a letter, a title | stays |
| **WARNING** | it says another edition or another writer prints something different, which is what keeps a reader off the wrong page | stays |
| **RELIED ON** | a quotation whose words the body rests on and does not itself print | stays |
| **REPEATS** | a sentence whose words are almost all already in the anchor paragraph. **This is the redundancy, and no word count ever sees it.** A quotation the body already prints, or already says in its own words, is a repeat. | goes |
| **CONTENT** | a statement that is neither a pointer nor a warning | goes to the body, or to the chapter's ledger under `Fact Check/` — the author decides which |
| **JUDGEMENT** | it tells a reader how much to believe a source, asserts a source's standing or access, or says what the book is about | goes; the citation stays |

Each note then gets one verdict: CLEAN, CARRIES CONTENT, JUDGING, REDUNDANT, MIXED, or UNANCHORED. One line per note is written to `Fact Check/Note Assessment.jsonl`, rebuilt by one command, so it diffs.

## What the measurement taught

- **The word cap is the wrong instrument.** In the original system most of the notes over the cap were clean citations doing their job, and most of the notes at fault were under the cap, where no length check ever looked. Length is a trigger to read a note, never a reason to cut one.
- **A sentence giving a page or an edition is a citation**, even when it also names an office. An office with dates is biography.
- **A quotation the body already prints is redundant; one the body does not print is content to promote.** One signal, two readings.
- **A sentence holding a citation is never cut by machine.** An early version of the sorter offered to delete a sentence holding two book titles because it ended with a clause about the book's own wording. That cut would have taken a citation out of the book to fix a clause.
- **Test the quotation before the locator.** A clause holding a page AND a quotation the body already says passed as a citation when the sorter tested the locator first. `tools/check-card-notes.py` tests the quotation first.
- **Hand-check before trusting the numbers.** Twelve findings checked by hand against the chapters: ten were real faults, one was a splitting error, one was arguable. Treat the counts as right to about one in ten.

## How the work ships

1. **Per-note rulings first.** The author rules each note at least once (`note.ruled` events: `apply`, `promote`, `citations_only`, `no_change`, `instruct` with the author's words, or `skip`). A card that touches a note does what the author's last ruling on that note says. The author: *"the interface needs to be modified to allow me to make an individual ruling on each if there are discrepancies."*
2. **Pass A — JUDGING and REDUNDANT notes, cuts only.** No new prose, so no new claims; the fastest pass. Only a cut that removes no citation is safe to propose by machine; the rest need a sentence drafted, which is Claude's to write and the author's to rule.
3. **Pass B — CARRIES CONTENT and MIXED notes, chapter by chapter.** Each card says, per note, what the body would gain and in which sentence (directive C: ask what belongs in the body first).
4. **Pass C — UNANCHORED notes.** Either the body sentence they belong to is missing, or they should be cut; the author decides.

## What stops it regressing

- `tools/check-card-notes.py` holds any card whose proposed note has a REPEATS or JUDGEMENT clause, CONTENT with no body paragraph changed, or a proposal that contradicts the author's last `note.ruled` for that note. The result is stored on the card as `noteCheck`; the page shows a held card under "With Claude" with no Approve button.
- `tools/check-note-content.py` reports any new note in a chapter that holds body content.
- `tools/check-footnotes.sh` and `tools/check-anchors.sh` report orphaned continuation paragraphs and broken anchor–definition parity, which `tools/check-lock-ready.sh` refuses.

# From finding to book: the life of one change

1. **Found.** The Fact-checker, the Editor, the nightly agent or the Watcher finds something: a quotation that differs from its source, a note that holds an argument, a banned word, a cited work nobody opened.
2. **Fact-checked first.** A suspected error is checked by reading the source, starting in your own library (`tools/have.sh`, `tools/find-source.sh`, `tools/find-page.sh`, the local source servers), and logged before it reaches you: a Claims row, a ledger section, a `source.read` event. A search that finds nothing is logged too, with what was searched.
3. **Recorded, not judged.** The finding says what was read, where, and what it says: "the source says X; the body says Y". It never says a claim is true or false.
4. **A card.** The Editor builds it (`Methodology/How a Card Is Built.md`): the paragraph's job, the paragraph above and below, the Current text and the Proposed text in full, what changes and why, and the check against the rules. Before writing it to the page: `tools/card-log.py --write` for its reads, `tools/check-card-notes.py --card` and `tools/check-card-closed.py --card`.
5. **Your ruling.** On the page: Approve, edit and send back for checking, or leave it. Your words on a card are kept as you wrote them.
6. **Applied.** Production runs `tools/apply-card.py <card> --write` (dry run first), which refuses if the chapter is locked or the text on disk has moved, writes through `blockedit` so block ids survive, writes the ledger entry, and prints the page update. Production then commits and prints the push line for you.
7. **Closed.** The line is settled. A later finding on it goes to the chapter's ledger and the back-fill list, never to a new card, unless you reopen the line yourself.

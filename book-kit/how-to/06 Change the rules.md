# Change the rules

The rulebook is yours. It came from another author's book, and each rule in it exists because something went wrong without it; keep what fits your book and change what does not.

- **The core** is `Methodology/Standing Rules.md`. Each chat reads it at the start of every session. Keep it short enough to read every time.
- **Each role's rules** are in `Methodology/Rules — <Role>.md`. A rule that concerns one role goes there and nowhere else.
- **A rule you state** in any chat is written into the core or the one role file it concerns, the same day, quoted in your words, with the date. Tell the chat to do it.
- **Banned and watch words** are in `Methodology/Word Lists.md`, whose top section says how to add or remove one. `tools/check-banned-words.sh` and `tools/check-card-words.py` read the machine list there and nowhere else.
- **A word you keep on purpose** in one sentence is a ruling: a row in `Fact Check/Banned-Word Rulings.md`, so the check stops asking.
- **Terms of art** your book defines go in `Methodology/Glossary Terms.md`; `tools/check-glossary.sh` checks that each is glossed where a reader first meets it.
- **The footnote plan** (a footnote is a citation, not an essay; six piles for each note's sentences) is `Methodology/Footnote Plan.md`.
- **Skills** in `Skills/` (the citation audit, the prose lens, the footnote pass, the chapter pipeline and others) follow the same rules; install them in Claude so the chats can call them.

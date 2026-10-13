# The sample book

A two-chapter practice book for learning the system before you point it at your own manuscript. Its library is the folder `library/PDF/`, which holds two public-domain texts from Project Gutenberg: Thomas Paine's *Common Sense* and *The Federalist Papers*. Each file is the first 60 KB of the Project Gutenberg text, enough for the passages the chapters cite.

## Four faults are planted on purpose

Find them with the tools and the role chats; the how-to guides walk through each one.

1. **A quotation that differs from its source.** Chapter 2 quotes Hamilton as writing "from reflection and design"; *Federalist* No. 1 reads "from reflection and choice". The fact-checker reads the source and logs the difference; the editor builds a card.
2. **A footnote that holds an argument.** `[^fed1_test]` in Chapter 2 adds a sentence of interpretation after the citation. The note check (`tools/check-card-notes.py`) and the footnote rules send it back.
3. **A banned word.** Chapter 1 says the sentence "carries" the frame. `tools/check-banned-words.sh` reports it against the starter word list.
4. **A read nobody logged.** Neither chapter's sources have a Claims row yet. `tools/check-read.sh` lists both works as cited and unread.

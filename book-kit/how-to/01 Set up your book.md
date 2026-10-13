# Set up your book

You can have Claude do all of this with you: give it `../BOOTSTRAP-BOOK.md`. These are the same steps, by hand.

1. **Copy the template.** Copy `book-kit/vault/` to where you keep your book and rename it (for example `My Book Vault`). This folder is your "vault": chapters, fact-check records, rules, hand-offs and tools live together in it.
2. **Settings.** Copy `book.toml.example` to `book.toml`. Fill in `[book] title`, `[library] roots` (the folder that holds the books and articles you cite) and, if you have a subfolder you have checked by hand, `checked_shelf`. Leave `[page] url` empty for now. Run:
   ```
   python3 tools/bookconfig.py
   ```
   It prints the vault, the chapters it found, and the library it will search.
3. **Chapters.** One Markdown file per chapter in `Chapters/`: `Chapter 01 - Title.md`. Footnotes are `[^slug]` in the text and `[^slug]: Author, *Title*, page.` at the end of the chapter. `pandoc` converts Word files: `pandoc ch1.docx -t gfm -o "Chapters/Chapter 01 - Title.md"`.
4. **Block ids.** Each paragraph and footnote gets an id that stays with it when text moves:
   ```
   python3 tools/blockid.py            # shows what it would do
   python3 tools/blockid.py --write
   ```
   From now on chapter text changes through `tools/blockedit.py` or `tools/apply-card.py`, which keep the ids and log each change.
5. **Baseline and check.**
   ```
   python3 tools/witness.py --seal     # any later change with no logged reason is reported
   python3 tools/smoke-test.sh         # every tool in its safe mode, then every test
   ```
6. **Fill in** `Book Structure.md` (one line per chapter) and `Project State.md`.

Next: publish the review page (`../page/README.md`), then open the role chats (`02 Open the role chats.md`).

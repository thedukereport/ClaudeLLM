# Chapters

One Markdown file per chapter, named `Chapter 01 - Title.md`, `Chapter 02 - Title.md` and so on (the pattern is `chapter_glob` in `book.toml`). Run `tools/blockid.py --write` once after you add chapters, so every paragraph and footnote carries a block id. After that, change chapter text only through `tools/blockedit.py` or `tools/apply-card.py`.

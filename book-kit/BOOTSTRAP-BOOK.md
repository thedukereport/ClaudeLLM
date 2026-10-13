# BOOTSTRAP-BOOK — set up the book kit with an author

**Claude: this file is addressed to you.** An author gave it to you to set up the book kit in `book-kit/` of this repository for their own book. Work through the steps below with them, one at a time. Ask before you move or write anything in their files, show them what each command printed, and do not go on past a step that failed.

## 0. Learn the kit before you touch their book

Read, whole: `book-kit/README.md`, `book-kit/vault/Methodology/Roles.md`, `book-kit/vault/Methodology/Standing Rules.md`, `book-kit/vault/Tools Index.md`, and `book-kit/page/README.md`. Then run the tests, which use only a copy of the practice book:

```
cd book-kit/vault
python3 tools/smoke-test.sh --tests
```

Every test should say `ok`. If one does not, stop and tell the author what failed.

## 1. Interview the author (one message, short)

Ask:

1. Their book's working title, and how many chapters are drafted.
2. Where the chapters are now (Word files, Google Docs, Markdown, Scrivener) and where they want the book's folder (the "vault") to live.
3. Where the books and articles they cite live on their computer (a folder of PDFs, EPUBs, text files), if anywhere.
4. Whether they use GitHub (for backups), and whether they have Python 3.10+ (`python3 --version`).
5. Whether any chapters are unfinished and should stay out of the workflow for now.

## 2. Make the vault

1. Copy `book-kit/vault/` to the folder they chose, and rename it for the book.
2. Copy `book.toml.example` to `book.toml` and fill in, with them: `[book] title`, `[library] roots` (their sources folder) and `checked_shelf` (a subfolder they have checked by hand, if any), `[workflow] out_of_workflow`, `[output] pdf_dir` and `snapshot_dir`.
3. Run `python3 tools/bookconfig.py` from the vault and read its output back to them.

## 3. Bring in the chapters

Each chapter becomes one Markdown file in `Chapters/`, named `Chapter 01 - Title.md`, with footnotes as `[^slug]` in the text and `[^slug]: …` at the end of the chapter. Convert with `pandoc` where it helps (`pandoc chapter.docx -t gfm -o "Chapters/Chapter 01 - Title.md"`), and show the author the first chapter before converting the rest; their words must come through unchanged. Then:

```
python3 tools/blockid.py --write        # a block id on each paragraph and note
python3 tools/witness.py --seal         # the baseline for "changed with no reason"
python3 tools/smoke-test.sh             # the tools against their book, then the tests
```

Fill in `Book Structure.md` (one line per chapter) and `Project State.md` with them.

## 4. Library index and first reads

If they have a library folder: `python3 tools/have.sh "<a title they cite>"` builds the library index on its first run. Then `python3 tools/check-read.sh` lists each cited work and whether anyone has opened it. On a new book every work is UNREAD: that list is the Fact-checker's first back-fill.

## 5. Publish the review page

Follow `book-kit/page/README.md`: publish `page/source-rulings.html` as an artifact with the database capability, put its URL in `book.toml` under `[page] url`, and write the page's `config/page` document with their title and their out-of-workflow chapters.

## 6. The chats

Help them make one Claude project for the book, with the vault folder attached, and one chat per role, each named for its role. Give them each role's "Open with" line from `Methodology/Roles.md` to paste as that chat's first message. Explain the two queues: the review page (cards) and `Fact Check/Asks.md` (questions only they can answer). They never copy messages between chats; the chats pass work through `Handoffs/`.

## 7. Scheduled tasks (optional, later)

Two scheduled tasks keep the system honest once the chats are running: the **Watcher** (`Fact Check/Watcher/Watcher Protocol.md`, every few hours: checks each role's work against the rules and writes directives) and the **nightly fact-check agent** (`Fact Check/Agent Protocol.md`). Each task's prompt names its role and tells it to follow its protocol in the vault; the prompt copies no rule.

## 8. Backups

If they use GitHub: `git init` in the vault, add their own private repository as `origin`, and run `tools/backup-to-github.sh --dry-run`, then `tools/backup-to-github.sh -m "First backup"`. Pushing is theirs to run. The `.gitignore` keeps PDFs, images and their library out of the repository.

## 9. Practise on the sample

Before the first real card, walk them through `book-kit/how-to/03 Practise on the sample book.md`. The sample has four faults planted on purpose, and each role finds one.

## Rules for you while you set this up

- Read a file whole before you change it. A search locates; only reading decides.
- Nothing in their chapters is removed or reworded without their approval.
- Show a sample before any change to more than five things.
- Use their words for their rules: a rule they state goes into `Methodology/Standing Rules.md` (or the one role file it concerns) the same day, quoted.

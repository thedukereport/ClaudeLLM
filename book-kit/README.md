# The book kit — a fact-checked book, built with six Claude chats

This folder holds a working system for writing a nonfiction book with Claude: six role chats that each do one job, a review page where you rule on every proposed change, a fact-check record for every source the book cites, and about forty scripts that check the chapters before anything is locked or published. It was built on a real book over several months, and the book's own content is not in it.

The rest of this repository (the local library search and the source servers) is optional here, and it makes the fact-checking much faster: the Fact-checker reads your sources from your own disk.

> **The quick way:** open Claude (Cowork, or Claude Desktop with a folder connected) and give it [`BOOTSTRAP-BOOK.md`](./BOOTSTRAP-BOOK.md). Claude asks you about your book and sets the whole thing up with you.

## How the work moves

```
            you rule in one place only
     ┌──────────────────────────────────────┐
     │  Source Rulings page                  │
     │  cards: Current and     Asks tab:     │
     │  Proposed text          questions     │
     └───────▲──────────────────────▲───────┘
             │ cards                │ asks
   ┌─────────┴─────┐        ┌───────┴────────┐
   │    Editor     │◀───────│  Fact-checker  │  reads each source, logs each read
   └─────────┬─────┘ finds  └────────────────┘
             │ approved cards
   ┌─────────▼─────┐        ┌────────────────┐
   │  Production   │        │ Managing editor│  routes the Watcher's findings,
   │ applies, locks│        │                │  reports the schedule
   └───────────────┘        └────────────────┘
        Systems keeps the tools working.   The Watcher (a scheduled task) checks each role.
```

- **You** own the words and the claims. The text changes only when you approve a card.
- **The Fact-checker** opens your own source for each claim, records what it says (`Fact Check/Claims/`, the chapter's ledger, the event log), and reports what it read. It never rules one source right and another wrong.
- **The Editor** turns findings into cards: the paragraph's job, the paragraph above and below, the current text and the proposed text, in full.
- **Production** applies the cards you approved, exactly as approved, and locks each finished chapter.
- **The Managing editor** routes the Watcher's directives and tells you what is blocked and on whom.
- **Systems** keeps the scripts, the page and the scheduled tasks working.

Each chat reads its rules at the start of every session, and hands its work to the next chat through a file in `Handoffs/`. You never copy messages between chats.

## What is in this folder

```
book-kit/
  README.md            this file
  BOOTSTRAP-BOOK.md    give this to Claude to set the kit up with you
  vault/               the template: copy this folder to start your book
    book.toml.example  your settings (copy to book.toml)
    tools/             the scripts (Tools Index.md lists each one)
    tests/             their tests; each runs on a copy of the sample book
    Methodology/       the rulebook, the six roles, each role's rules, word lists,
                       the footnote plan, the close-out procedure
    Skills/            seven Claude skills (citation audit, prose lens, footnote pass, …)
    Fact Check/        the asks queue, triage list, locks, claims, event log, protocols
    Handoffs/          one hand-off file per role chat
    Chapters/ Appendices/ Punch List.md Project State.md Book Structure.md …
  sample/              a two-chapter practice book with four faults planted on purpose
  page/                the Source Rulings page and how to publish it
  how-to/              step-by-step guides
```

## Requirements

- macOS, Windows or Linux, with **Python 3.10 or newer**. The scripts use the standard library.
- **Claude** with access to your vault folder (Cowork, or Claude Desktop with the folder connected). The review page is a claude.ai artifact, so the account needs artifacts with the database capability.
- **Optional programs**, each named by the tool that needs it, which says so plainly when it is missing:
  - `pandoc` — `blockid.py` checks that adding block ids changes nothing in the rendered text; `publish-pdfs.sh` makes PDFs (with `xelatex`).
  - `pdfplumber` (Python) or `pdftotext` — `find-page.sh` reads page numbers from PDFs.
  - `pypdf` (Python) — `check-ellipsis.sh` reads a PDF source.
  - `git` and a GitHub account — `backup-to-github.sh`.

## Start in ten minutes

1. Copy `vault/` to where you keep your book, and rename it. Copy `book.toml.example` to `book.toml` and fill in the title, your library folder, and the two output folders.
2. Put your chapters in `Chapters/` as `Chapter 01 - Title.md`, `Chapter 02 - Title.md` and so on, with footnotes in Markdown (`[^slug]` in the text, `[^slug]: …` at the end of the chapter).
3. Run `python3 tools/bookconfig.py` (it prints what it found), then `python3 tools/blockid.py --write` (block ids on each paragraph and note), then `python3 tools/smoke-test.sh`.
4. Publish the review page: [`page/README.md`](./page/README.md). Put its URL in `book.toml`.
5. Make one Claude project for the book, and one chat per role, each opened with its **Start** prompt from `Chat Prompts.md`. When a chat compresses, use its **Recover** prompt; when it goes wrong, **Close** it and open a new one ([`how-to/07`](./how-to/07%20When%20a%20chat%20gets%20long%20or%20compresses.md)).
6. Practise first on the sample. From the `book-kit` folder: `BOOK_VAULT=sample python3 vault/tools/check-read.sh`. The guides in [`how-to/`](./how-to/) walk through each planted fault.

## The rules travel with the tools

The rulebook in `vault/Methodology/` comes from the original author's working rules, with his reasons and his words where they state the rule. Edit it for your book: a rule you state goes into `Standing Rules.md` (or the one role file it concerns) the same day, in your words. Some of the rules you will keep, because each one exists to prevent a mistake that happened:

- **Read the text. A search locates; only reading decides.**
- **Nothing is removed from the book without your approval.** A claim with no logged read goes on the back-fill list; it is never cut for want of a source.
- **Closed is closed.** A line you approved does not come back to you; the page holds any card on it.
- **A card shows the words.** Current and Proposed, in full, every time.
- **A sample before any bulk write.**

## Credit and license

Built by Peter Duke / The Duke Report, with Claude. Code is MIT-licensed (see the repository's `LICENSE`). The two texts in `sample/library/` are public domain, from Project Gutenberg.

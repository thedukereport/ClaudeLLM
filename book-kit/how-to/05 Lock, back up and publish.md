# Lock, back up and publish

## Locks

`Fact Check/Locks.md` is the only record of whether a chapter is locked, and `tools/lock.py` is its only writer.

```
python3 tools/lock.py status
python3 tools/lock.py unlock 5 --by production --note "the author approved card <title>"
python3 tools/lock.py lock 5 --by production     # refuses until check-lock-ready passes
```

`tools/check-lock-ready.sh 5` blocks a lock on: open Punch List items naming the chapter, open cards for it on the page, a cited work nobody has opened (`check-read.sh --strict`), unruled banned words or epistemic flags, footnotes over the cap or structurally broken, wrong cross-references, and a missing or stale preflight (`tools/preflight.sh 5`). A sub-check that crashes is a failure, never a pass. The full sequence is in `Methodology/Chapter Close-Out Procedure.md`: unlock, edit, relock, push.

## Back up to GitHub

Make a private repository on GitHub, then in the vault:

```
git init
git remote add origin https://github.com/<you>/<your-book>.git
tools/backup-to-github.sh --dry-run
tools/backup-to-github.sh -m "First backup"
```

The `.gitignore` keeps PDFs, images, the library and scratch folders out; the script refuses binaries and data files that slip past it. Pushing is yours: the chats commit and print the line, and you run it.

## A copy on another disk

Set `[output] snapshot_dir` in `book.toml`, then `tools/snapshot-vault.sh`. It copies the vault and checks every file against the original.

## PDFs

Set `[output] pdf_dir`, then `tools/publish-pdfs.sh`. It needs `pandoc` and `xelatex`, and says how to install them if they are missing.

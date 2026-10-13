# Banned-Word Rulings

Every banned-word hit the author has ruled on. `tools/check-banned-words.sh` reads this file through `tools/rulings.py` and hides a ruled hit, so a sweep never asks the same question twice. Pass `--all` to see ruled hits again.

How a row is keyed: the first column is the fingerprint of the word in its sentence (30 characters either side), from `rulings.context_fingerprint`. Print one with `tools/rulings.py --word "the whole line" word`. The fingerprint breaks when the sentence is rewritten, and a rewritten sentence needs ruling again. A row whose first cell is `—` records a hit that was changed rather than kept; the tools ignore it.

Columns:

- **fingerprint** — ten hex characters in backticks
- **where** — the coordinate when ruled, e.g. `Ch01/L5` (for people; lines move)
- **word** — the hit as matched
- **ruling** — `keep` (literal or quoted use) or `changed`
- **date** — the day the author ruled
- **note** — the author's reason, in his words where he gave them

| fingerprint | where | word | ruling | date | note |
|---|---|---|---|---|---|

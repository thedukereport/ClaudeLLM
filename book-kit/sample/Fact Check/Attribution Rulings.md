# Attribution Rulings

Every attribution pair the author has ruled on: the verb a body sentence uses for its source (*wrote*, *testified*, *held*, *said*) against the source language in the sentence's own footnote (*quoted in*, *summarized in*, *dissenting*). A ruled pair is never raised again. Tools read this file through `tools/rulings.py`.

How a row is keyed: the first column is the fingerprint of the body sentence, from `rulings.fingerprint`. Print one with `tools/rulings.py "the whole sentence"`. The fingerprint breaks when the sentence is rewritten, and a rewritten sentence needs ruling again. A row whose first cell is `—` records a pair that was changed rather than kept; the tools ignore it.

Columns:

- **fingerprint** — ten hex characters in backticks
- **where** — the coordinate when ruled, e.g. `Ch02/L5` (for people; lines move)
- **anchor** — the footnote label, e.g. `[^fed1_test]`
- **body verb** — the attribution verb in the sentence
- **note says** — the source language in the footnote
- **ruling** — `keep` or `changed`
- **date** — the day the author ruled
- **note** — the author's reason, in his words where he gave them

| fingerprint | where | anchor | body verb | note says | ruling | date | note |
|---|---|---|---|---|---|---|---|

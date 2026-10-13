# Back-fill Queue

Works the book cites with no logged read. `tools/check-read.sh` lists them: **UNREAD** (in the library, nobody has logged a read) and **NOT ON DRIVE** (not found in the library). Nothing in the book is removed from here (Standing Rules §6). The author's presses on the page's Back-fill view are written here by `tools/dashboard-sync.py`; the Fact-checker works the rows — read the source, then log it in `Fact Check/Claims/` and the chapter ledger — and marks the last column done. A fact found after a passage was approved also comes here, and reaches the author only if the author reopens the line.

**Columns:** `pressed` (date) · `work` (*title*) · `cited in` (chapters) · `lane` (unread or notondrive) · `the author's ruling` (Back-fill: read it and log it · I'll get it · Approve citing it unread · Skip for now) · `the author's note` · `state` (open, or done with the date and the Claims row).

| pressed | work | cited in | lane | the author's ruling | the author's note | state |
|---|---|---|---|---|---|---|

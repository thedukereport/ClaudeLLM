# Asks — questions only the author can answer

One of the author's two queues (the other is the Source Rulings page). Any role appends a new ask to the **Open** table in this format; the Fact-checker numbers, chases and closes it. Asks are batched and put to the author at a checkpoint, and asked once.

**Kinds, and what silence means:**

| kind | if the author does not answer |
|---|---|
| **DECIDE** | Claude takes its own recommendation, stated in the ask, and records that it did |
| **REVIEW** | Claude does not proceed. Silence is never acceptance |
| **ONLY YOU CAN** | it stays open: pushing, connecting a folder, getting a source, approving an outside fetch |

**Columns:**

- **id** — `` `A1` ``, `` `A2` ``, … in backticks, never reused (the tools find a row by its opening `` | `A ``).
- **kind** — DECIDE, REVIEW or ONLY YOU CAN.
- **ask** — the question in one or two plain sentences, with `Ch##/L##` where a place in the book is in question. For a source: the author, the title, the URL where one exists, and whether it is in the author's draft or new.
- **blocks** — what waits on the answer (a card title, a chapter, a tool).
- **if no answer** — what happens on silence, by the kind's rule; for DECIDE, the recommendation Claude will take.
- **asked** — the date the ask was first put.

When the author answers, the row moves to **Answered** with the author's words verbatim and the date, and the answer goes to the event log as `decision.recorded`.

## Open

| id | kind | ask | blocks | if no answer | asked |
|---|---|---|---|---|---|

## Answered

| id | kind | ask | the author's answer, verbatim | answered |
|---|---|---|---|---|

# Claims — one JSONL file per chapter

`Fact Check/Claims/Ch NN.jsonl` holds one row per source read for chapter NN: each read, each zero, each correction, in the turn it is made (Standing Rules §6, directive F). Before any search, open this file first and repeat no search it records. Each row is one JSON object on one line; append, never edit a row in place. An overturned row stays, and a later row says what overturned it.

`tools/card-log.py` appends rows for the sources a card names; the Fact-checker and the nightly agent append the rest. `tools/check-read.sh` reads these files to say which cited works nobody has opened, and `tools/check-drive-path.sh` fails any `drive_path` that does not open.

## Fields

| field | what it holds |
|---|---|
| `reader` | who opened the source: the role (Fact-checker, Editor, the nightly agent) or the author |
| `date_read` | the date of the read, `YYYY-MM-DD` |
| `author` | the source's author |
| `title` | the source's title, as on its title page |
| `drive_path` | the file that was opened, as a path under a library root in `book.toml` — the file, never the title or the folder |
| `where_read` | instead of `drive_path`, for a source that is not a library file: a URL with the date fetched, or "print copy held by the author" |
| `location` | where in the source: page, chapter, section, heading, timestamp |
| `states` | the words found, quoted exactly; for a negative, the coverage — which files, how many of how many, which terms, which method, and what was not searched |
| `ref` | the place in the book the read serves: `Ch##/L##` or the note slug |
| `card` | the card's id, when the read was made for a card |

Example (the sample book):

```json
{"reader": "Fact-checker", "date_read": "YYYY-MM-DD", "author": "Alexander Hamilton", "title": "The Federalist No. 1, \"General Introduction\"", "drive_path": "PDF/Hamilton Madison Jay - The Federalist Papers.txt", "location": "No. 1, first paragraph", "states": "<the words found, quoted exactly>", "ref": "Ch02/L5", "card": ""}
```

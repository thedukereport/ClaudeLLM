# Glossary Terms — the terms of art the glossary check reads

`tools/check-glossary.sh` reads this file. It checks that each term below is glossed where the reader first meets it in the book: an em-dash, colon or parenthesis followed by explanation, or a "which means" / "that is" / "defined as" construction, in the same sentence or the next.

## How to add a term

Write one entry per line, a bold term at the start of the line, then a colon (or a dash) and the gloss:

```
**Term of art**: what the book means by it, in one sentence.
**Second Name / Other Name**: two names for one entry are split on the slash.
```

- A one-word term is matched only where it is capitalised, and is skipped when the book also uses the word in the ordinary way three or more times. Multi-word and hyphenated terms match in any case.
- A term that appears in no chapter yet is not a fault. `tools/check-glossary.sh --terms` lists it as defined and unused.
- If your book prints its own glossary as an appendix, point the check at it instead of copying entries here. Add a line like this (a path relative to the vault), and the check reads the entries in that file too:

```
glossary-file: Appendices/Appendix A - Glossary.md
```

The examples above are inside code fences, so the check does not read them as entries. Remove nothing above this line; add your entries below it.

## Terms


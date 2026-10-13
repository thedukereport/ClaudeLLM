# Fact-Check Ledger Protocol

**Purpose:** each chapter has one persistent fact-check ledger in `Fact Check/`. The ledger is cumulative — it preserves all verification work, including negative results, so that context compression across sessions does not destroy what was learned about the sources.

**Location:** `Fact Check/Ch. NN — <Short Title>.md`. The pattern is `ledger_glob` in `book.toml`; tools find the ledger with `bookconfig.ledger_file(NN)`. One file per chapter: append to the one that exists, and never create a second.

**When to write:** during every citation audit, as each read is made, and as the final step before an audit is declared complete. Each read also gets a row in `Fact Check/Claims/Ch NN.jsonl` (`Fact Check/Claims/README.md`) and a `source.read` event.

---

## Ledger structure

Each ledger file uses this template:

```markdown
# Fact-Check Ledger: Chapter NN — <Title>

**Last updated:** <date>
**Two-verdict conversion:** <date this chapter's claim rows were re-read under QUOTE and CLAIM, or "not yet">

---

## 1. Claims Register

| Ref | Claim | Tier | QUOTE | CLAIM | Source | Note slug | Comment | Date |
|---|---|---|---|---|---|---|---|---|
| Ch05/L112 | <specific claim> | 1/2/3 | VERBATIM / PARAPHRASE / MISMATCH | SUPPORTED / OVERSTATED / UNSUPPORTED | <source with page or section> | [^slug] or "none" | <notes> | <date> |

Include each disputable claim, including those that never reached a footnote. The register is the master record of what was checked and what was found.

---

## 2. Source Pages Consulted

| Source | Format | Anchor | Result | Date |
|---|---|---|---|---|
| Paine, *Common Sense* | Web | "Of the Origin and Design of Government in General" | <what was found, with the verdict; for a negative, the coverage> | <date> |

---

## 3. Original-Language Verification Log

| Passage | Word claimed | Actually in text? | Notes |
|---|---|---|---|

---

## 4. Translation Checks

| English in text | Original | Gloss accurate? | Standard lexicon sense | Notes |
|---|---|---|---|---|

---

## 5. Editorial Decisions

| Date | Change | Reason |
|---|---|---|

---

## 6. Open Questions

- [ ] <question> (an ask for the author goes to `Fact Check/Asks.md` the same turn)
```

**Tier** — Tiers 1 and 2 are claims checked against sources; a Tier 2 claim needs three independent sources. Tier 3 is a term of art or the author's own framework: its underlying evidence is checked, and it needs no citation. The citation-audit skill (`Skills/`) assigns the tiers.

**Format tag** — one of:
- `PDF-scan` — a PDF that preserves the print edition's pagination (running heads or footers show print pages)
- `EPUB-to-PDF` — a PDF generated from an EPUB; pagination is reflowed and does NOT match print
- `EPUB` — an original EPUB; no page concept
- `Web` — an HTML or online source
- `Print` — a physical copy read directly
- `Audio` — an audiobook or recorded lecture (cite by timestamp)

**Anchor** — what locates the content. For `PDF-scan` and `Print` sources, use print pages. For `EPUB`, `EPUB-to-PDF` and `Web` sources, anchor by **chapter, section or appendix** plus, where useful, a quoted phrase that can be searched. Never cite a page number from an EPUB or EPUB-to-PDF copy in a chapter footnote — the number is not stable across reading apps or print editions. The ledger records both the local-copy anchor (where the read was made) and the structural anchor the footnote uses.

---

## Working rules

**Cumulative, never overwritten.** Each audit session ADDS to the ledger. Never delete previous entries — update their status, mark an overturned row as overturned, and add a dated note.

**Negative results are mandatory.** "Read pp. 145–152, found no relevant content" is a finding. Record it, with its coverage: which files, which terms, what went unsearched. The next session will not have to look again.

**One file per chapter.** The file grows over the life of the project. It is the single source of truth for what has been verified in that chapter.

**Original-language verification is required.** Any chapter that claims a word appears in a passage of a text in another language has that claim checked against the text and recorded in section 3.

**Format-aware anchoring is required.** When the local copy is an EPUB, an EPUB-to-PDF conversion or an audio file, the chapter footnote cites by structural anchor. Page numbers derived from a converted PDF exist only in the converted file.

**Apply entries.** Production appends one dated entry per applied card — the card's title, what changed, the commit — and changes nothing else in the ledger.

---

## Two verdicts per claim row

**Each claim row answers two questions, and neither closes it alone.**

| | question | values |
|---|---|---|
| **QUOTE** | Is the quoted matter faithful to the cited source? | `VERBATIM` · `PARAPHRASE` · `MISMATCH` |
| **CLAIM** | Does the body sentence characterise that source correctly? | `SUPPORTED` · `OVERSTATED` · `UNSUPPORTED` |

**The case that forced it, in the original system.** A ledger row read VERIFIED: the checker went to the right source, compared the words, found them identical, and wrote down that they were a statute's words. The body sentence said a person had testified them under oath. The check asked whether the quotation was faithful; it never asked whether the sentence characterised the source correctly, and one verdict cannot hold both answers. Under two verdicts the row reads **QUOTE: VERBATIM · CLAIM: OVERSTATED**, and the contradiction is on its face.

**Why this matters more than the instance.** A prior VERIFIED row short-circuits later searching. So the wrong verdict did more than fail to catch the error; it **protected** the error from a later full audit, which read "VERIFIED" and moved past. **A wrong VERIFIED is more durable than an unchecked claim**, because it arrives with a date, a source and a reason to stop looking.

**Single-verdict rows.** A row with one verdict does not short-circuit a re-search. Rows convert when their chapter next comes up, never in a batch — a batch is the "start twelve, finish none" failure — and the ledger's header records the conversion date.

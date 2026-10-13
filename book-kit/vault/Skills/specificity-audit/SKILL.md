---
name: specificity-audit
description: >
  A hostile pass over your book's body prose for fabricated atomic specifics —
  middle initials, birth years, edition details, named example sets, round
  numbers, exact dates — smuggled into otherwise-correct sentences. Use after
  citation-audit and neurolinguistic-prose have run on a chapter, or when the
  user asks to "check the specifics," "find fabricated details," "run the
  specificity audit," or doubts a name, number or date in the prose. Every
  specific is guilty until traced; returns TRACED / PUBLIC RECORD / UNTRACED.
---

# Specificity Audit

A hostile pass over prose that has already passed citation-audit and neurolinguistic-prose. This skill assumes the footnotes are honest and the style is clean. It looks for one specific failure mode: **fabricated atomic specifics smuggled into otherwise-correct sentences.**

## The failure mode

When an LLM writes prose, it produces text that *reads* like the work of someone who knows the subject. To make the text read that way, the LLM inserts confident-sounding atomic specifics — middle initials, birth years, edition numbers, named examples, round-number quantities, parenthetical biographical details. None of these are required by the surrounding argument. They are inserted because they make the prose feel concrete and authoritative.

Most of these specifics are correct or close enough. Some are fabrications that read exactly like the correct ones. The LLM that wrote them cannot reliably tell the two apart, because both "look right" by the same training signal that produced them.

The specificity audit assumes every specific is **guilty until traced.**

## What counts as a specific

A specific is any atomic fact a reader could in principle check against a source — and could in principle find wrong. The audit scans for five patterns:

### 1. Parenthetical biographical details

Patterns: `Name (Middle Initial) Surname`, `Name (PhD, Institution)`, `Name ("Nickname")`, `Name (born YEAR)`, `Name, the [adjective] author of...`

**The recorded failure:** a body sentence gave a living scholar two middle initials and a nickname in parentheses. The initials were fabricated; his real given names were different. The parenthetical added details that went beyond what any source supported, and the footnote repeated the same fabricated name, so the footnote looked like confirmation.

**Test:** Does the footnote attached to this sentence contain the same biographical details, and does the source the footnote cites contain them? If not, where do they come from? If you cannot answer, flag.

### 2. Category-with-named-examples

Patterns: `particularly older X and Y titles`, `including A, B, and C`, `among them: D, E, F`, `several X, in particular Y`.

**The recorded failure:** a sentence said that several of the book's citations — "particularly" titles from two named kinds of publisher — had come into the library through a scanning workflow. The named category was invented because the prose needed concrete examples. No inventory of what had been scanned existed anywhere.

**Test:** Is the named set documented anywhere — a list in a footnote, a checked inventory, a public-record source? If the named set is invented to make the category feel concrete, flag.

### 3. Quantified specifics

Patterns: `approximately N`, `roughly N`, `around N`, `N-many sources`, `over N years`, `N percent`, dollar figures.

**Example pattern:** "approximately 6,000 books," "twelve different sources," "three articles." The number sounds checked; often it is a round estimate that has no underlying count.

**Test:** Where does the number come from? Is it counted, measured, sourced, or rounded for verisimilitude? Round numbers (5, 10, 50, 100, 1,000) and exact-looking-but-conveniently-round numbers (6,000; 12,000) are higher-suspicion.

### 4. Adjectives that imply an unstated set

Patterns: `the standard edition`, `the canonical text`, `older X`, `the typical X`, `the usual X`, `the established Y`.

**Example pattern:** "the standard scholarly edition" presupposes a known standard. If there is no documented standard, the adjective is doing work the evidence does not support.

**Test:** Is there a named, citable referent for the implied set? Or is the adjective making the sentence feel grounded without grounding it?

### 5. Initials, full middle names, publisher addresses, exact dates

Patterns that look like rigor: `W. and T. Bradford`, `Philadelphia: W. and T. Bradford, 1776`, `February 14, 1776`, `pp. 132–135`.

**Test:** Does the footnote contain the same initials, middle names, dates, page numbers — and does the source? Or are they additions to the body prose that exceed what the footnote anchors?

**Worked example from the sample book.** Chapter 1 says the Bradford printing of *Common Sense* "is dated February 14, 1776," and its note cites the title page. The title page in the library copy reads "Printed and sold by W. & T. Bradford, February 14, 1776." The printer's initials and the date both appear in the source in the form claimed: TRACED.

## The three verdicts

For every specific the audit identifies, return one of three verdicts:

- **TRACED** — The specific appears in a footnote in this document, or in a source the chapter cites, in the form claimed.
- **PUBLIC RECORD** — The specific is a widely-known public fact (e.g., a constitutional date, the name of a head of state, an internationally famous title). Be conservative here — when in doubt, treat as UNTRACED.
- **UNTRACED** — The specific cannot be located in the document's footnotes or in widely-known public record. Treat as a fabrication candidate. Flag for checking or removal.

## Output format

For each chapter, return:

```
SPECIFICITY AUDIT — [Chapter file path]

UNTRACED (review/check/cut):
  L[line] | [specific quoted from prose] | [brief note on why untraced]
  L[line] | ...

TRACED:
  [count summary, no per-line detail unless requested]

PUBLIC RECORD:
  [count summary, no per-line detail unless requested]

NOTES:
  [any pattern observations, edge cases, or specifics that needed judgment]
```

The skill prioritizes UNTRACED with full detail. TRACED and PUBLIC RECORD get only counts — the author does not need to review what was already checked.

## What the skill is not

The skill does not certify a specific as correct merely because it cannot detect a problem. Checking is a separate step that requires opening the actual source (`tools/find-source.sh`, `tools/find-page.sh`, then reading the passage). The skill's job is to surface candidates; the author's job is to check or cut.

The skill assumes the LLM running it can hallucinate the checking too. When in doubt, the verdict is UNTRACED. Better to over-flag than under-flag.

## What the skill is for

This is the third member of the fact-checking bundle:

- **citation-audit** — checks every disputable claim in a chapter against the named primary source
- **neurolinguistic-prose** — audits prose for the linguistic violations that skill names
- **specificity-audit** *(this skill)* — scans the body prose for atomic fabrications the citation-audit doesn't catch because they live outside the footnotes

The three skills run in sequence. Citation-audit certifies the footnotes. Neurolinguistic-prose certifies the form. Specificity-audit certifies the small embedded facts. Together they catch phantom quotes, fabricated initials, invented categories, and made-up biographical details.

## The shape of every catch

Both recorded failures above have the same shape: an atomic specific that read like rigor and was fabrication. The skill's value is that it runs as a separate pass — after the body prose is otherwise clean — looking only for this one failure mode. A footnote that repeats the body's specific is no defence on its own: the same writer may have written both, so trace the specific to the cited source itself.

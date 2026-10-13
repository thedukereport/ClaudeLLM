---
name: example-fit-check
description: >
  Chapter-pipeline Step 3 for your book — check that every example, dialogue,
  citation, and illustration in the chapter does the work the surrounding
  prose says it does. Three tests: (a) does the example demonstrate the
  pattern the chapter labels it with; (b) is each foreign-language or technical
  term glossed at first use in the chapter; (c) is each source-jump bridged so
  the reader sees why the chapter moves from one authority to the next. Flag
  conflations, mismatches, missing glosses, and name-list stretches without
  bridges. Use when the user says "run the example-fit check," "do the
  examples fit," "check the illustrations in chapter X," "check glosses,"
  "check the source jumps," or when running the chapter-pipeline skill (Step
  3). Also invoke when the user reports that "this example doesn't fit," "this
  quote doesn't match the claim," or "these scholars read like a name-list."
---

# Example-Fit Check

You are checking whether the chapter's examples, quoted sources, and foreign or technical terms support what the surrounding prose says they support. The failure mode this skill guards against: an example labeled as showing X that shows Y, a citation attributed to the wrong writer, a foreign term used without an English gloss, or a paragraph of five scholars in a row without bridges between them.

The pattern this skill exists to prevent: **plausible source-name → plausible topic → the reader's brain fills in "the source must support the claim"** — and half the time the source supports a related-but-distinct claim, and the reader never notices because the citation looks scholarly. The prose gets credit for authority that the underlying source does not give it.

---

## Three Tests, One at a Time

### Test 1 — Does the example demonstrate what the paragraph says it demonstrates?

For each named source, quote, illustration, dialogue, or worked case in the chapter, extract two things:

1. **What the paragraph claims the example shows** (the labeled pattern)
2. **What the source says or demonstrates** (the source's own thesis, read directly)

Compare. Three failure types:

- **Mismatch:** The source says X, the paragraph implies Y. The recorded shape: a paragraph put an older, famous writer in the citation slot for a multi-part framework, when the older writer names a single drive and a later writer is the one who builds the multi-part framework the chapter's argument needs. The chapter credited the later writer's thesis to the older one.
- **Conflation:** Two distinct patterns collapsed into one. The recorded shape: two different rhetorical techniques presented as if they were the same technique.
- **Wrong-scholar attribution:** A term or claim attributed to the writer who quotes it instead of the writer who originated it. The recorded shape: a term of art credited to the scholar the chapter was reading, when that scholar's own sentence says "what [two other scholars] call" the term.

**A sample-book case of the same shape.** *Federalist* No. 1 asks "whether societies of men are really capable or not of establishing good government from reflection and choice, or whether they are forever destined to depend for their political constitutions on accident and force." Hamilton introduces the question with "It has been frequently remarked that it seems to have been reserved to the people of this country…" and follows it with "If there be any truth in the remark." A paragraph saying Hamilton *coined* the question, or *asserted* it flat, fails Test 1: Hamilton reports it as a remark other people made, and conditions it.

**How to check:** open the source directly (`tools/find-source.sh` to locate, then read the passage in the library copy, starting with the `checked_shelf` folder). Do not check from a search excerpt alone — the excerpt often shows a paragraph that appears to confirm the claim and is followed by a qualification that reverses it. Read enough context around the passage to see what the source's own argument is, then compare to what the chapter attributes to the source.

**Repair pattern:** When a mismatch is caught, rewrite the paragraph so the source that delivers the claim gets the load-bearing citation. If a secondary source cites a primary source for the framework, put the secondary source's thesis first (as its own contribution) and cite the primary source as the framework the secondary source draws from. Do not silently move the citation while leaving the same claim structure — the argument itself may need to change.

### Test 2 — Is each foreign-language or technical term glossed at first use?

Extract every non-English term in the chapter body. For each occurrence, check:

- Is this the term's **first use in the chapter body**? (Not first-in-the-book — first-in-*this*-chapter. A reader may enter the book at a specific chapter or return to it out of sequence.)
- If first-in-chapter, is there an inline English gloss next to the term?

**Acceptable gloss patterns** (examples use Paine's own Latin, "the whole affair is a *felo de se*"):
- Parenthetical translation: "*felo de se* (self-murder)"
- Em-dash appositive: "*felo de se* — the old legal term for self-murder"
- Quote followed by translation: a quoted foreign-language sentence followed directly by its English rendering
- Implicit-through-content: acceptable when the surrounding sentence supplies the meaning by naming the referent explicitly ("Paine calls the English constitution a *felo de se*, a body that destroys itself")

**Not acceptable:**
- A bare foreign term without English (the recorded failure: a book-wide term of art used with no gloss at its first use in a later chapter)
- Gloss that arrives 3+ sentences later (reader has moved on)
- Gloss that only appears in the footnote (body has to stand on its own)

**Repair pattern:** add a compact inline gloss. Prefer parenthetical or em-dash appositive. Do not push glosses into footnotes unless the surrounding sentence already supplies the meaning.

**Applies also to Latin, technical vocabulary (legal, medical, philosophical), foreign-language quotations, acronyms on first use.** `tools/check-glossary.sh` checks the narrow mechanical half — whether a term the book's glossary defines gets a gloss where the reader first meets it. The rest is read.

### Test 3 — Are source-jumps bridged?

A source-jump happens when the chapter moves from citing one authority to citing another, either within the same paragraph or across paragraph boundaries. Read the transitions between named sources.

- If Scholar A and Scholar B are cited in the same paragraph, is there a bridging clause explaining why the chapter moves from A to B?
- Is the bridge grounded in what each scholar contributes distinctly? Or does the paragraph read as a name-list?

**Bridge quality gradient:**

1. **Strong bridge:** names each writer's distinct contribution and how each extends, refines, confirms, or complicates the prior. ("Paine separated society from government in 1776. In 1787 Hamilton asked whether a people could establish government 'from reflection and choice.'")
2. **Adequate bridge:** signals continuity with a light connective ("Later, Hamilton wrote…").
3. **Thin bridge:** just juxtaposes names ("Paine writes… Hamilton writes…" with no connective explaining WHY the paragraph moves from one to the other).
4. **Name-list:** four or more scholars in sequence, each with a brief description of their book, no bridges. Reads as a citation dump.

**Recorded failures, in shape:** a paragraph citing five scholars where only the last transition was bridged; a paragraph citing six scholars where one synthesized the first three and the last two arrived with no framing clause.

**Repair pattern:** Add bridging clauses that name what each writer adds. Temporal framing works well ("extends the argument backward," "extends the argument forward," "confirms the pattern in a different setting"). Structural framing works for scale claims ("At that scale," "The pattern held in..."). Do not just insert "additionally" or "furthermore" — those are connective filler, not real bridges.

---

## When to Run

1. **Chapter-pipeline Step 3.** The pipeline invokes this skill after citation-audit (Step 1) and neurolinguistic-prose (Step 2). Run when the previous two are green.
2. **Any time the user says the example doesn't fit.** Skip to Test 1 for the specific example flagged.
3. **Any time the user reports the reader can't tell why scholar B follows scholar A.** Skip to Test 3.
4. **Any time the user adds new foreign or technical vocabulary in a chapter.** Skip to Test 2 for the new term.

## What the Output Should Contain

For each finding:

- **Location** (`ChNN/LNNN`, line number in the chapter file; paste `tools/show.sh NN L` output)
- **Test that flagged it** (1, 2, or 3)
- **What the chapter currently says** (short verbatim excerpt)
- **What the source says / what the reader needs and doesn't get** (the mismatch or gap)
- **Two or three repair options** (A/B/C) with the load-bearing tradeoff of each stated plainly
- **Recommendation** with reasoning

Findings surface **one at a time** for approval (per chapter-pipeline protocol), unless the user asks for the batch view.

---

## Recorded Failures (case library)

The skill keeps a growing case library of failures caught, so the check learns from prior misses. Add each new catch here in this form:

```
### ChNN/LNNN — [one-line name of the failure]
- What the paragraph claimed: [verbatim]
- What the source says: [verbatim, with locator]
- The failure pattern: [which of the shapes below, or a new one]
- Repair applied: [the new wording]
```

The shapes the original project recorded, which recur:

- **Attribution slide** — the paragraph puts one writer in the load-bearing citation slot for a thesis another writer delivers. A reader who chased the footnote would find the cited writer saying something narrower.
- **Citer for coiner** — a term of art credited to the source you happen to be reading, when that source names who coined it.
- **Gloss assumed from an earlier chapter** — a book-established term treated as if it does not need re-glossing in each chapter. The reader may open the book at this chapter.
- **Name-list with thin bridges** — compressed apparatus reads as a citation dump. The reader gets names and no framework for why the argument moves from A to B to C.
- **Tail-end sources** — two sources arriving at the end of a scholarship paragraph without a clause telling the reader what each adds.
- **Conflation** — two distinct techniques presented as one.

---

## Working Principles

**Read the source directly, not the search excerpt.** The excerpt often shows a passage that appears to confirm the claim, and a page later the source qualifies or reverses it. Confirm the claim in context.

**Attribution errors are the most common finding.** People confuse the citer with the coiner, the primary source with the secondary source, the framework's originator with the framework's extender. This is Test 1's highest-yield check.

**Book-established terms still need first-in-chapter glosses.** A reader may enter the book at any chapter. Do not rely on prior chapters to have taught the term.

**A name-list is a failure of framing, not of research.** Four or more scholars in one paragraph without bridges tells the reader "I have citations" and does not tell them "here is the shape of the argument." Add bridges that name each contribution, or split the paragraph.

**When in doubt about a fit, ask what a skeptical reader would say.** A skeptical reader who chased a footnote to the cited writer and found another writer's thesis would say the paragraph was misleading. A skeptical reader who found the cited writer quoting someone else for the term would say the term was misattributed. If the skeptical reader has a legitimate complaint, the fit needs work.

**Do not check example-fit from the same session that drafted the example.** The drafter's memory of what they meant will fill in for what the prose delivers. The check runs against the prose as it currently reads, not against the drafter's intent.

---

## Interaction with Adjacent Pipeline Steps

- **Depends on citation-audit (Step 1):** citation-audit checks that the cited source contains the passage; example-fit-check checks that the passage supports the specific claim the paragraph attaches to it. If citation-audit is green, example-fit-check is the natural next pass.
- **Interacts with neurolinguistic-prose (Step 2):** the repair patterns (source restructuring, bridge additions) introduce new prose. Every fix goes through the pre-Edit subject-scan gate before it is applied.
- **Feeds subhead-check (Step 4):** paragraphs that need splitting because of name-list issues may also need subheads. Flag suspected split candidates for Step 4.

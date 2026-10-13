# Word Lists — the lists the tools read

The tools that check words read their lists here, and only here: `tools/check-banned-words.sh` reads the banned-word list, `tools/check-epistemics.sh` reads the epistemic triggers, and `tools/check-card-words.py` reads the banned-word list through `check-banned-words.sh`. All of them go through one loader, `tools/wordlists.py`. **Edit a list here and nowhere else.** Two copies of a rule drift the moment they exist; in the system this kit comes from, that happened twice in one day.

## How to add or remove a word

1. Find the block for the list you want to change. Each machine list is written between two HTML comment markers, for example `<!-- BANNED-WORDS-MACHINE-LIST:BEGIN -->` and `<!-- BANNED-WORDS-MACHINE-LIST:END -->`. The tools read only what is between the markers. Never rename or delete a marker.
2. **To add a word**, add one line inside the block:

   ```
   \bleverage(s|d)?\b ;; financial leverage; quoted
   ```

   The part before the first `;;` is a regular expression, matched without regard to case against the body prose (HTML comments and backtick code spans are stripped first, and line numbers are kept). Use `\b` at each end so the pattern matches whole words. The part after the first `;;` is the carve-out note: the uses that are allowed, printed under every hit so whoever reads the hit knows what to check.
3. **To make a carve-out fire by itself**, add a second `;;` and a regular expression. When that expression matches the words around a hit (forty characters either side), the hit is counted as carved and is not shown as work:

   ```
   \bprint(s|ed|ing)?\b ;; a printer or publisher as subject ;; (out of print|printing press)
   ```

   A carve-out that only prints a note under the hit still raises the hit every run. If you can describe the allowed use as a pattern, write it as the third field.
4. **To remove a word**, delete its line. To pause one without losing it, put `#` at the start of the line; lines starting with `#` are comments.
5. The separator is `;;` because regular expressions use `|` for alternation. Splitting on `|` cut every alternation short the first time the original system ran.
6. Run `python3 tools/check-banned-words.sh` after an edit. A pattern that is not a valid regular expression is reported and skipped, never silently dropped.

The table under "Banned and watch words" is for people. It records why a word is on the list and since when. When you add a word to the machine list, add a row to the table too, with the reason in one sentence.

---

## Banned and watch words

"Banned" means: replace it in drafted prose, and every hit needs a reading. A hit is a coordinate, never a verdict.

| Word | Allowed uses (carve-out) | Why |
|---|---|---|
| carry / carries / carried / carrying | literal physical carrying; quoted; glossing a foreign verb | It treats meaning as an object being moved from place to place. Say who said what. |
| run / runs / running / ran | literal running; checked idioms; quoted | It gives agency to an abstraction ("the argument runs") or is a dead metaphor. |
| apparatus | quoted | A vague abstraction standing in for the thing itself. |
| hold / holds / holding / held | physical grip; financial holdings; holding an infant; holding an office or an academic chair | "The view holds" gives a view agency. Name the person who holds it. |
| at scale | none, a hard ban | Jargon that hides how many and where. |
| operate / operation(s) | a named operation; surgical or military literal | It turns a process into a thing and hides the people doing it. |
| practitioner | none | A label in place of the person and what that person did. |
| impact / impacted | the author's own use | Vague: say what changed and who changed it. |
| precise / precisely | quoted | It claims an exact match without showing one. |
| empirical / empirically | quoted | Standardise on "scientific". |
| sit / sits / sat | literal seating of a person or a statue | "The claim sits in the note" places a thing with no actor. Name the actor and the relation. |
| stand / stands / stood | literal standing of a physical object or person | Same fault as "sits": a dead metaphor that gives a thing a posture. |
| inhabit / inhabits | none | Same family as "sits" and "stands". |
| emerge / emerged / emergence / emergent | quoted | It poses as a cause and names none. Say who did what, and how, from the source. If no document can say, the sentence is a story. |
| evolve / evolved | quoted | Same fault as "emerge". |
| register / registers / registry | literal registers and lists | A metaphor for tone or level that says less than the plain word. |
| script | literal scripts and screenplays | A metaphor that hides who wrote or ordered what. |
| grammar | the literal grammar of a language | A metaphor for "structure" or "rules". |
| print / prints / printed, with a writer or a text as the subject | a printer, a press or a publisher as the subject; the literal act (printing money); the physical object or medium (out of print, print edition, printed page, printing press); quoted | **Only a printer, a press or a publisher prints.** Writers write, publish, report, document. A document does not print any more than an author does. The fix is the accurate verb: *quotes* when the words are reproduced, *publishes* when the house issued it, *reports*, *documents*, *records*, *gives*, *spells*, *has* when one of those is what happened. In an edition comparison, *reads* is usually the word. |
| reads X as Y | a manuscript, inscription or edition literally reading a word; the author's own "we read X as Y" about the author's own book | A person who interprets a thing interprets it. Say so. |
| diagnostic, as a noun (the diagnostic, a diagnostic, diagnostics, run a diagnostic) | the adjective ("diagnostic test"); quoted titles | Name the act: the test, the question, what the reader checks. |

Watch words (no machine pattern; read them when you meet them): move (as a noun for an argument), land (metaphorical), name (as a verb for "identify"), pattern, worked example, artifact, performs, template, reading (as a noun), reach for.

### A footnote never says what a book is about

A note that gives an account of what a source argues, or of what kind of book it is, comes out, in every chapter. This is a different fault from evaluation. A note that says how much to believe a source is caught by `tools/check-epistemics.sh` and by class J of `tools/check-footnotes.sh`. This one contains no verdict language at all: it reads as a helpful summary, so nothing flags it until class K of `check-footnotes.sh` looks for it. These notes survive because they are short: footnote passes that trim the long notes never open them.

**The test:** cover the citation and read the rest of the note. If what remains is a sentence about the work rather than a pointer to a page, chapter or section, it goes. A locator that happens to use one of these verbs ("Paine gives the argument in the section on monarchy," "Hamilton states the question at No. 1, paragraph 1") routes a reader to a place and stays.

### Machine-readable list — the single source for every sweep

One word per line: `pattern ;; carve-out note ;; optional automatic carve-out regex`. The pattern is a regular expression, matched without regard to case against body prose with HTML comments and backtick code spans already stripped.

<!-- BANNED-WORDS-MACHINE-LIST:BEGIN -->
```
# pattern ;; carve-out          — the separator is ';;' because regex alternation uses '|'
\bcarr(y|ies|ied|ying)\b ;; literal physical carrying; quoted; glossing a foreign verb
\b(run|runs|running|ran)\b ;; literal running; checked idioms; quoted
\bapparatus\b ;; quoted
\b(hold|holds|holding|held)\b ;; physical grip; financial holdings; "holding an infant"; holding an office or an academic chair
\bat scale\b ;; hard ban, no carve-out
\boperat(e|es|ed|ing|ion|ions)\b ;; a named operation; surgical or military literal
\bpractitioner\b ;; none
\bimpact(ed|s)?\b ;; the author's own use
\bprecise(ly)?\b ;; quoted
\bempirical(ly)?\b ;; quoted; standardise on "scientific"
\b(sit|sits|sat)\b ;; literal seating of a person or a statue
\b(stand|stands|stood)\b ;; literal standing of a physical object or person
\binhabits?\b ;; none
\bemerg(e|es|ed|ence|ent|ing)\b ;; quoted
\bevolv(e|es|ed|ing)\b ;; quoted
\bregist(?:er|ers|ry|ries)\b ;; literal registers and lists
\bscript\b ;; literal scripts and screenplays
\bgrammar\b ;; literal grammar of a language
\bprint(s|ed|ing)?\b ;; a press, printer or publisher as subject; the literal act (printing paper money, printing notes); the physical object or the medium (out of print, print edition, print advertisements, printed page, printing press); quoted ;; (out of print|print(ed)? (advertisement|edition|page|pagination|quarto|run|shop|media)|printing press|printing \(|printing (paper )?money|printing (the )?notes|\b(edition|copy|copies|issue|pamphlet|book)s? printed by)
\breads?\s+(?:the|this|that|them|it|his|her|their|him)\b[^.\n]{0,80}\bas\b ;; a manuscript, inscription or edition literally reading a word or phrase; the author's own "we read X as Y" framing of the author's own book. A person who INTERPRETS a thing interprets it.
```
<!-- BANNED-WORDS-MACHINE-LIST:END -->

**A hit is a coordinate, not a verdict.** Every sweep that uses this list reports hits for reading. The lock gate, `tools/check-lock-ready.sh`, refuses to lock a chapter while it has an unruled hit: fix the line, or rule the hit as a keep in `Fact Check/Banned-Word Rulings.md` (keyed by fingerprint, see `tools/rulings.py`), and the hit stops blocking. In the system this kit comes from, a sweep of four chapters found 41 hits on `carry` alone: 21 were violations, 13 were literal or quoted and correct, and the rest were in working files. Deciding which is which needs the line open.

---

## Epistemic triggers — borrowed authority and pre-emptive retreat

Read by `tools/check-epistemics.sh`. The number after `;;` is the failure class the trigger points at; the script prints the question to ask for each class. Each line is a trigger to READ the line, never a verdict. As with banned words, an unruled hit blocks the chapter's lock until the line is fixed or the hit is ruled in `Fact Check/Epistemic Rulings.md`.

1. **Borrowed authority** — settling a question by naming interpreters. Test: strip every proper noun from the passage and ask whether anything checkable is left.
2. **Pre-emptive retreat** — telling the reader the book's own evidence settles nothing.
3. *(no trigger)* **Sense substitution** — a word glossed in one sense where the source defines another. Caught only by reading, with the dictionary open.
4. **Over-reach** — a claim broader than the source's own scope.
5. **True-when-written** — "the current President": date it rather than tense it.
6. **Draft history on the page** — the reader has no earlier drafts.
7. *(no trigger)* **Unsourced hinge** — a load-bearing claim with no note, usually because it reads as common knowledge. Caught only by reading.
8. **Invented person** — "a reader", "imagine a voter". Name a real person or cut the sentence.
9. **"A man who"** — banned: the indefinite article means nobody. Name the person or state the property.
10. **Telegraphing** — the prose announces its own structure ("we will see", "as shown in Chapter 3", "to recap") instead of doing the work.

<!-- EPISTEMIC-TRIGGERS-MACHINE-LIST:BEGIN -->
# pattern ;; which failure — a trigger to READ the line, never a verdict
\b(?:most|many|some|the majority of) (?:scholars|historians|experts|researchers) \w* ?(?:agree|hold|believe|reject|accept|maintain) ;; 1 borrowed authority
\b(?:mainstream|consensus|accepted|orthodox|established) (?:scholarship|opinion|view|history|academia) ;; 1 borrowed authority
\b(?:widely|generally|universally) (?:accepted|regarded|acknowledged|considered|held) ;; 1 borrowed authority
\bit is (?:well[- ]known|widely known|generally agreed|accepted) ;; 1 borrowed authority
\b(?:experts|authorities|specialists) (?:say|agree|tell us|have shown) ;; 1 borrowed authority
\b(?:none|nothing) of (?:this|it|which) (?:settles|proves|establishes|demonstrates) ;; 2 pre-emptive retreat
\bdoes not (?:need|require) (?:it|this|that) settled ;; 2 pre-emptive retreat
(?:^|(?<=[.;:]\s))(?:Of course|To be fair|Needless to say|It must be (?:said|admitted|conceded))\b ;; 2 pre-emptive retreat
(?:^|(?<=[.;:]\s))(?:Granted|Admittedly)\s*, ;; 2 pre-emptive retreat
\bthis (?:is not|isn't) (?:to say|meant to|intended to) ;; 2 pre-emptive retreat
\bI (?:do not|don't) (?:claim|argue|suggest) that ;; 2 pre-emptive retreat
\b(?:one for each|all of (?:them|which)|throughout its|in every case) ;; 4 over-reach — check the source's actual scope
\bsitting (?:President|Vice[- ]President|Director|Secretary|Senator|Congress\w+|Representative|Justice|Judge|Governor|Chair(?:man|woman)?|Mayor|Attorney General|Prime Minister|Pope|monarch|king|queen) ;; 5 true-when-written
(?<!what )\bis (?:currently|now|presently) the ;; 5 true-when-written
\b(?:the )?(?:current|incumbent) (?:President|Director|Secretary|Chairman|CEO) ;; 5 true-when-written
\b(?:earlier|previous|prior) drafts? ;; 6 draft history on the page
\b(?:corrected|fixed|revised|amended) (?:on|against|per) (?:direct read|the source|\d{4}-\d{2}-\d{2}) ;; 6 draft history on the page
\bthe chapter (?:previously|originally|formerly) (?:stated|said|read|had) ;; 6 draft history on the page
\b(?:an earlier|a previous) (?:draft|version) of this ;; 6 draft history on the page
\b(?:a|an|one) (?:reader|voter|citizen|plaintiff|defendant|creditor|employee|manager|officer|shareholder|juror|taxpayer|patient|student|customer)\b ;; 8 invented person — name him or cut him
\b(?:imagine|suppose|consider) (?:a|an|that a|what happens when) ;; 8 invented person — hypothetical illustration
\b(?:say you|suppose you|if you were to) ;; 8 invented person — hypothetical illustration
\b(?:a|an) (?:man|woman|person|reader|voter|citizen|official|judge|juror|witness|bureaucrat|shareholder|owner|handler|worker|employee|manager|taxpayer|plaintiff|creditor|debtor|student|patient|customer|prisoner) who\b ;; 9 BANNED "a man who" — indefinite article means nobody; name him or state the property
# Telegraphing. The original author named this the most often missed fault in
# the book, and no scan looked for it until these lines were added.
(?i)\b(?:we|I)\s+(?:will|'ll|shall)\s+(?:see|document|examine|show|explore|develop|return|take up|come back|meet)\b|\blater in this (?:chapter|book)\b|\bin a later chapter\b|\bthat comes later\b|\b(?:see|as shown in)\s+Chapter\s+\d+\b ;; 10 telegraphing — the prose announces its own structure instead of performing it
(?i)\b(?:we|I)\s+(?:documented|introduced|defined|saw|established|met|described|traced|showed)\b[^.]{0,40}\bChapter\s+\d+\b|\bwhat\s+(?:we|I)\s+(?:defined|called|introduced|named)\b[^.]{0,40}\bChapter\s+\d+\b|\bas\s+(?:we\s+saw|noted|discussed|established)\b[^.]{0,40}\bChapter\s+\d+\b|\bearlier in this (?:chapter|book)\b ;; 10 telegraphing — the prose announces its own structure instead of performing it
(?i)(?:^|[.!?]\s+|\n)(?:What follows|Here is what|Here's what|Below,? we|In the next section|In what follows|The next section|We turn now|We now turn|This section (?:examines|turns|takes up|looks at)|Consider first|Three things follow|The argument (?:proceeds|runs) as follows) ;; 10 telegraphing — the prose announces its own structure instead of performing it
(?i)\b(?:what this (?:chapter|section|book) has (?:shown|argued|established|traced)|closes a circle|completes the circle|as (?:this|the) chapter has (?:shown|argued|traced|documented)|to recap|to summari[sz]e|in summary|in short|having (?:shown|established|traced|documented)|the foregoing|taken together, (?:these|the))\b ;; 10 telegraphing — the prose announces its own structure instead of performing it
(?i)\b(?:this|the present)\s+(?:chapter|section)\b|\b(?:this|the present)\s+book\s+(?:will|documents?|documented|argues?|shows?|showed|traces?|traced|examines?|is about|sets out)\b|\bthe (?:first|last|next)\s+\w+\s+(?:parts?|chapters?)\s+of this book\b|\bthe pages that follow\b ;; 10 telegraphing — the prose announces its own structure instead of performing it
<!-- EPISTEMIC-TRIGGERS-MACHINE-LIST:END -->

---

## Attribution classes — attribution drift

No script reads this list today. A fact-checker reads it by hand: pair each footnote anchor with its own note, and compare the attribution verb in the body sentence with the source language in the note. When the body's verb and the note's language fall in different classes, and the pair is listed below, read both.

<!-- ATTRIBUTION-CLASSES-MACHINE-LIST:BEGIN -->
```
# CLASS <name> ;; regex        — how that class shows up in text
# PAIR <body-class> <note-class> ;; what the disagreement means
# The separator is ';;' because the regexes use '|' for alternation.

CLASS sworn ;; \b(testif(y|ies|ied|ying)|testimony|sworn|swore|under oath|depos(ed|ition))\b
CLASS concession ;; \b(admitt(ed|ing)|admits|conced(ed|es|ing)|acknowledg(ed|es|ing)|confess(ed|es))\b
CLASS majority ;; \b(the Court (held|ruled|found|decided)|Supreme Court (held|ruled)|the majority (held|ruled)|court held)\b
CLASS dissent ;; \b(dissent(ing|s|ed)?|J\., dissenting|in dissent)\b
CLASS speech ;; \b(said|says|told|declar(ed|es)|announc(ed|es)|remark(ed|s)|stated|spoke)\b
CLASS authored ;; \b(wrote|writes|publish(ed|es)|records|argues|in his book|in her book)\b
CLASS institutional ;; \b(statute|public law|P\.L\.|enact(ed|ment)|act of|resolution|ordinance|regulation|codified|summariz(ed|es|ing))\b
CLASS secondary ;; \b(?:quoted|cited|reproduced|printed)\s+(?:here\s+)?(?:in|from|by)\s+(?!the body|this chapter|the text|the same|full\b|so many words)(?:[A-Z]|\*)

PAIR sworn institutional ;; body claims sworn testimony; the note cites an enactment or a summary of a position
PAIR majority dissent ;; body reports a holding; the note cites a dissenting opinion
PAIR speech secondary ;; body puts words in a named person's mouth; the note reaches them through another writer
PAIR authored secondary ;; body says the author wrote it; the note quotes it from someone else's book
PAIR sworn secondary ;; body claims sworn testimony; the note reaches it through a secondary
PAIR concession secondary ;; body reports an admission; the note reaches it through a secondary
```
<!-- ATTRIBUTION-CLASSES-MACHINE-LIST:END -->

---

## Stored-thing names — name the file

When a message or a working note refers to a stored thing ("the register", "the log"), give its path, so the reader can open it. A hit on this pattern with no path after it is the fault.

<!-- ARTIFACT-NAMING-MACHINE-LIST:BEGIN -->
\bthe (?:register|ledger|the record|index|store|log|system) \b ;; only when followed by no path
<!-- ARTIFACT-NAMING-MACHINE-LIST:END -->

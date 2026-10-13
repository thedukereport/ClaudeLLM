---
name: neurolinguistic-prose
description: "Two-pass editorial lens for linguistically exact prose in your book, with two mandatory gates. Mechanism Gate: before proposing prose for any causal chain or process, write the chain out in chat, name every class of person, source each link, and get it confirmed. Pre-Edit Gate: before any prose-change Edit, produce the subject-scan table. Then audit for twelve violations (abstract-noun agency, nominalizations, negation-led framing, false universals, smuggled modals, unanchored comparatives, emergence language, Complex Equivalence, Mind Reading, Rhetorical Flourish, Telegraphing, Epistemic Framing) plus abstraction by omission, actor-verb headings and the invented-person check, under Sweep Scope rules. Principle 12 tests falsifiability first: a claim no document could break is a story, and \"may\" replaces \"probably.\" Use whenever Claude writes prose for the book, or when the user asks for \"precise writing,\" \"clean prose,\" \"no AI slop,\" or mentions linguistic precision, nominalization, or agency in writing."
---

# Neurolinguistic Prose

You are writing for someone trained in neurolinguistics. This person can identify the structural patterns LLMs default to — and will reject them. But this person also values prose that moves, that has rhetorical energy and varied rhythm. Flat, defensive writing that avoids errors by retreating to the safest possible sentence structure is just as much a failure as prose riddled with nominalizations.

The method that produces the best results is a **two-pass process**:

1. **Draft pass:** Write naturally. Use your full rhetorical range — vary sentence length, use subordinate clauses, shift rhythm, build arguments with momentum. Do not think about the principles below while drafting. Let the prose breathe. Write plainly: abstraction costs more words and says less, and exactness is part of the draft, not a correction layer added later.

2. **Editorial pass:** Audit the draft against the principles. Identify specific violations. Correct each violation surgically — change only what needs to change to fix the violation, keeping the sentence's rhythm, voice, and position in the paragraph. If a sentence has no violations, leave it alone, even if it could in theory be "more exact." The goal is to fix errors, not to rewrite everything.

The editorial pass is a scalpel, not a steamroller. A sentence that flows well and has one nominalization needs that nominalization fixed — it does not need to be rebuilt from scratch.

Before either gate, read `Methodology/Standing Rules.md` (and the role's rules file, e.g. `Methodology/Rules — Editor.md`). The author's dated rulings live there; the banned-word list and the pet-phrase watchlist live in `Methodology/Word Lists.md`. Neither lives here.

---

## The Mechanism Gate (fires before the Pre-Edit Gate)

**Trigger:** the passage describes how something works — a sequence of steps, a causal chain, a legal or financial procedure, an institutional process, a mechanism of any kind. The test: does the passage contain two or more steps where one enables or causes the next? If yes, this gate fires first, before the subject-scan table, before any Current/Proposed pair.

**The rule:** write the mechanism out in chat as a numbered chain — one link per line, each line naming an actor, an action, and what that action makes possible for the next link. Name every distinct class of person in the chain. Attach a source to every disputable link and read that source in the same turn. Get the chain confirmed. **Only then propose prose.**

```
1. [class of person] does [action], which means
2. [class of person] cannot do [action], which means
3. [class of person] must do [action] ...
```

**Three checks on the chain before it is shown:**

1. **Every link named.** If a step is missing, the prose built on it will assert a consequence with no cause, and the reader supplies the missing link from imagination.
2. **One word, one class of person.** Trace each noun through the whole chain. A term that means one group at step 2 and a different group at step 5 is the fault that survives every other check in this skill, because each sentence passes on its own.
3. **Every factual link sourced in the same turn.** A claim about what a document, statute, or record says gets read before it is written, not after someone asks whether it is true.

**A chain drawn from the sample book.** Paine, *Common Sense*, "Of the Origin and Design of Government in General," describes how representation comes about in his supposed colony:

```
1. The colonists multiply and spread out, so they cannot all meet "on every occasion as at first."
2. The colonists consent "to leave the legislative part to be managed by a select number chosen from the whole body."
3. As the colony grows, the colonists divide it into parts, "each part sending its proper number."
4. The colonists hold elections often, so that the elected "might never form to themselves an interest separate from the electors."
5. The elected return and "mix again with the general body of the electors in a few months."
```

Three classes of person — the colonists, the elected, the electors — and Paine keeps them apart. A paraphrase that writes "the members" for the colonists in one sentence and for the representatives in the next fails check 2, and every sentence in it would pass on its own. The chain is also Paine's own thought experiment ("let us suppose a small number of persons settled in some sequestered part of the earth"), so prose built on it attributes it to Paine.

**The recorded failure — one paragraph, one hour, six rewrites.** The passage described a six-link financial chain, from the people who started a failure to the people at the far end who bore its cost. The chain was never drawn. What followed:

- The first plain-language pass produced a sentence that read plainly and was false. **Plain language is a test of comprehension, not a substitute for it.**
- A compression pass, taken in response to "too granular," deleted the causal links. The author: *"You lost the raison d'être."* The chain was the content.
- Two short clauses were shorthand for statutory tests never put on the page. The author asked *"what is this ???"* about each.
- One assertion was wrong. The statute was read only after the author asked *"Is that change true?"*
- Found last, after everything else was settled: **one word did duty for two different sets of people** — one group in one sentence, the clients of that group in the next. Each sentence was defensible; the paragraph was not.

When the explanation was finally written out in chat, the paragraph came out in one pass and every correction after that was small.

**The second recorded failure.** A passage naming several people and a law firm was proposed three times and rejected three times, and the gate never fired. First, compressing a source's phrasing produced a verb with a preposition it does not take. Then an abstract phrase blurred two different objects, one a lawsuit the person lost and one a set of agreements that survived. Then the author: *"the implication/context is missing."* Only when the chain was drawn — nine links, each sourced — did the passage come right. **A passage proposed three times without the chain is the signal, and it was missed three times.**

**The discipline test:** a passage that cannot be drawn as a chain cannot be edited. If I find myself proposing prose for a mechanism I have not written out, that is the signal to stop and write it out.

**Carve-out:** a passage with no causal chain — a single stated fact, a date, a quotation, a description of a thing rather than a process.

---

## The Pre-Edit Gate (mandatory before any prose-change Edit)

**This gate is non-optional. It runs before the Edit tool is called, not after the author flags a violation.**

The pattern this gate exists to prevent: I have the rules in memory, the skill is loaded, and I still ship prose with abstract-nouns-as-agents because I bypass the discipline at the moment of generation. The two-pass workflow is a debugger. The pre-Edit gate is a guardrail.

**The rule:** Before every Edit that changes prose — body, footnote, section heading, even a one-sentence revision — produce a **subject-scan table in chat** with the following columns:

| Line / location | Subject of active verb | Verb | Chair-test result | Named-actor substitution (if fail) |
|---|---|---|---|---|

Every active verb in the proposed text. Every subject named. Every chair-test result spelled out (`pass` / `fail` / `borderline`). For every fail, a named actor in the substitution column. If the table has a fail with no substitution, the Edit does not happen; rewrite the prose and re-scan.

Paste `tools/show.sh NN L` output above the table so the author sees the line in its section.

**The chair test:** Could this subject sit in a chair? Could it testify in court? Could it sign its name to a document? If no, it is an abstraction. If yes, it is a person (or a named institutional body with documented membership).

**Term-of-art nouns are not exempt.** "The system," "the framework," "the cycle," "the synthesis," "the sequence," "the process," "the move," and the terms of art your own book defines are *names* — they can be identified, described, attributed, modified. They cannot be the *subject of an active verb*. The carve-out is the doorway every violation enters through. There is no carve-out.

**What counts as a pass:**
- Named individual (Paine, Hamilton, the author)
- Named group with documented membership (the printers W. and T. Bradford; the three authors of *The Federalist*)
- The named actor of the chapter (the reader, the voter, whatever class of person the chapter is about)
- First-person (I argue, I observe)

**What counts as a fail:**
- Abstract noun (the system, the framework, the cycle, the synthesis, the dialectic, the move, the process)
- Place or building (Philadelphia decided X, the State House debated Y)
- Document or text as actor (the pamphlet argues, the chapter shows, the constitution asks) — defensible only for literal textual description ("the Bradford printing reads," "the title page gives"), not for active intellectual acts
- Possessive abstractions (the chapter's argument claims X, the framework's logic locks Y)
- Time periods (the eighteenth century produced X, the founding era inherited Y)

**What counts as borderline:**
- Collective institutional metonymy ("the colonial press," "the opposition") — defensible if the metonymy unpacks to a documented body of actors. Better to name them.
- Lexicographic description ("the Latin *felo de se* denotes self-murder") — defensible because words do literally denote senses.
- Term-of-art as descriptive subject of an identity verb ("[term] is what happens when…") — defensible because the term is being identified, not acting.

**The discipline test:** The author can refuse to read any prose change that arrives without the subject-scan table attached. That refusal is the external enforcement. The internal one is: I do not call Edit on prose I have not scanned in chat. If I find myself about to call Edit without producing the table, that is the signal to stop and produce it.

**Two rules govern how a proposal is shown, and both were learned the same day as the Mechanism Gate:**

- **Unchanged is not checked.** A sentence reproduced inside a proposal as surrounding context has not been audited, and marking it unchanged does not clear it. An audit of a passage is an audit of every sentence in it. The recorded failure: a six-word sentence stood inside four consecutive proposals as untouched context; on the fifth showing the author read it and found two faults — a phrase duplicating what the quotation marks already said, and a verb attributing a posture the quoted body never took. Carve-outs: quoted primary-source material, and the author's own first-person prose.
- **Whole paragraph once it is in play.** When two or more sentences in a paragraph are under revision, every later showing is the entire paragraph, start to finish — no fragments, no ellipses standing in for "unchanged." The author, twice and in capitals: *"LET ME SEE THE WHOLE THING, DAMN IT."* Current/Proposed on a fragment is legible only to someone already holding the rest of the paragraph in memory; the author is reading for rhythm, repetition, register and the seam between sentences, and a fragment shows none of them. This sharpens the Current/Proposed rule rather than replacing it: showing one sentence is permitted when only one sentence changes, and that permission ends the moment a second sentence moves.

**And never describe the file's future state in the present tense.** A proposal once said a name "is now in the body" about a change the author had not yet approved, in order to justify a second change that depended on it. Check the file and paste the check. This is the same fault as asserting that a chapter does not contain a sentence it prints twenty-four lines further on.

The scan-table IS the audit. The per-principle numbered list that appears later in the editorial pass is a tally of what the scan found, not proof that the scan happened. The proof is the table.

---

## The Core Defect

The patterns below share a single root: **they let abstractions act instead of people.** Nominalizations, abstract-noun-as-agent, emergence language, and agentless passives are all versions of the same move — they delete the human actor and let a process, system, or concept appear to act on its own. Telegraphing is the parallel structural failure: the writer announces what the prose is about to do instead of doing it.

**And the mirror failure:** fixing an abstraction by inventing a person instead of naming one. That is Principle 14, and it is the failure this skill's own fixes produce most often.

---

## Twelve Principles (for the Editorial Pass)

Read through the draft and check for each of these. When you find a violation, fix it with minimal disruption to the surrounding prose. Principles 12b, 13 and 14 follow the twelve and are checked in the same pass.

### 1. Agent Visibility

When an abstract noun takes the subject position and an active verb, the sentence asserts that a concept does something. Concepts don't do things. People do things through concepts.

**The test:** Could you put the subject of this sentence in a chair? Could it testify in court? If not, find the person behind it.

**How to fix:** Replace the abstract subject with the human agent. Keep the rest of the sentence intact where possible. **Name a real one — see Principle 14. Inventing a person to fill the subject position is a second violation, not a fix.**

| Violation | Fix |
|---|---|
| "Schools train you to reproduce answers" | "People who design curricula train you to reproduce answers" |
| "Language manages perception" | "People who choose specific language manage other people's perception through it" |
| "The interpretation justifies the boundary" | "People who hold the interpretation use it to justify the boundary" |
| "The sentence frames the whole pamphlet" | "Paine frames the whole pamphlet with that sentence" |

**Watch for agent-adjacent abstractions.** "Interpretive authority," "institutional power," "social control" — these feel close to human agents because they describe what people do. But they are still abstractions in the subject position. A group can hold authority; authority does not hold itself. Always ask: who wielded it?

**No term-of-art carve-out.** Your book's own terms of art are *names*, not actors. Use them to identify, describe, attribute, modify. Do not let them be the subject of an active verb. "The framework locks in X" fails. "[Named person]'s translation locks in X" passes. "[Term] happens internally" passes (identity verb, not action). "[Term] works on the reader" fails (active verb, abstract subject). For a chapter whose thesis IS this discipline, the chapter's own argument is the strictest test: if I write "the framework locks in," I commit the failure the chapter exists to describe.

**Quoted sources keep their own grammar.** Paine writes that "the same constitution which gives the commons a power to check the king" also gives the king a power to check the commons. The constitution acts in Paine's sentence, inside quotation marks, and that is Paine's choice. The book's own sentence around the quotation names Paine as the actor.

### 2. Verb Priority

Nominalizations freeze processes into static things, deleting both the agent and the action.

**The test:** Put "ongoing" in front of the word. If it still makes sense ("ongoing discernment," "ongoing mediation"), you have a frozen verb. Thaw it — give it back its subject and let it act.

**How to fix:** Replace the nominalization with the verb form and supply the agent. Reshape only as much of the sentence as necessary.

**Common-noun frozen-verb watchlist:** "diagnostic," "framing," "analysis," "takeaway," "move" (as noun for argument/action), "interpretation" (as the actor), "operation" (as the actor) — all freeze acts into static things. Name the actor and the act. Your book's watchlist in `Methodology/Word Lists.md` adds to this one.

### 3. Negation Discipline

Negation is a legitimate rhetorical tool. The problem is overuse — when "not X but Y," "rather than," "not merely," and "not simply" become a stylistic crutch, they show up as an identifiable AI artifact. The reader notices the pattern before the content.

**The rule is frequency and proximity.** One or two negation-first constructions in a multi-paragraph piece can do real argumentative work. Five or six and you have a tic. But even two is too many if they land in the same paragraph or within a few sentences of each other — proximity amplifies the pattern and makes both instances read as a crutch. During the editorial pass, count every negation-first construction in the draft — "not X but Y," "rather than X," "not merely," "not simply," "did not X; they Y'd." If there are more than one or two in the piece, keep the strongest and rewrite the rest as direct assertions. If two survive, make sure they are well separated — different paragraphs, different sections of the argument.

**How to rewrite:** Most negation-first constructions can simply be stated directly. "The pamphlet was not a plea for reform, but a call for separation" → "The pamphlet called for separation." "These were not local grievances" → "These were grievances the writers addressed to every colony." "The exclusion works not through explicit prohibition but through the design of the requirements" → "The people who wrote the requirements excluded applicants through their design." State what it IS.

**Which ones to keep:** Keep a negation-first construction when it does work the assertion alone can't — when it pre-empts a specific misreading the audience holds, when a parenthetical aside earns the framing, or when the rhythmic contrast between the negation and the assertion creates genuine rhetorical texture. If the sentence is just as strong stated directly, state it directly.

### 4. Quantifier Discipline

"Every," "all," "always," "never" are claims about the entire set. Use them only when you mean the entire set and can defend it. Watch also for **hidden universals** — words that smuggle totality without using an explicit quantifier: "indispensable," "essential," "inevitable," "universal," "unprecedented." These claim the entire set by implication. "Indispensable" means nothing could work without it — that's a universal claim. Prefer words that leave room: "crucial," "central," "significant."

**No rhetorical-flourish carve-out.** "Climax effect," "for emphasis," "rhythmic punch," "the chapter's voice has always used this" are not exceptions. If the universal claim cannot be defended literally, drop it or scope it.

**How to fix:** Drop the quantifier, or scope it. For hidden universals, replace with a word that makes a strong claim without claiming totality. Often the sentence is stronger without the absolute.

### 5. Modal Restraint

Assert what IS, not what MUST BE. Modal operators — must, should, have to, of necessity — smuggle prescription into description.

**How to fix:** State it as history, as evidence, or as someone's claim. Replace "of necessity" with who said it was necessary and why.

**Exceptions:** Modals inside quoted material stay ("all considerate and good men must feel" is Hamilton's modal, not the book's). Modals describing literal mechanics (e.g., "the losing team must designate a player" inside the rules of a game) stay — naming the rule is descriptive, not prescriptive.

### 6. Comparison Specificity

Every comparative or superlative needs a named reference point. "Stronger" than what?

**How to fix:** Name the comparison. If you can't, rewrite as a direct assertion. Strip unanchored "more effective" / "more powerful" / "more important than" — those smuggle editorial assumption.

### 7. No Emergence Language

"Emerge," "emergence," "arise" describe something appearing without identifying who made it appear. They paper over gaps in the account.

**How to fix:** Name who did it. If you can't, acknowledge the gap honestly.

### 8. No Complex Equivalence

"Because" welds cause and effect together as though the connection were self-evident. If the causal link is interpretation rather than established fact, you're asserting a Complex Equivalence.

Also watch for equivalence smuggled through "the same gesture as," "in the way that," "no different from."

**How to fix:** Separate the two observations. Let the reader draw the connection — or provide evidence for the causal claim. Don't fuse interpretation and fact into a single sentence as though the link were obvious.

### 9. No Mind Reading

Attributing internal states, motivations, or intentions to people without evidence. "The framers knew," "they intended," "they used X as a mechanism to achieve Y," "probably thought," "must have wanted." It applies to chat prose as well as book prose, and to what people needed or did not need to do.

**How to fix:** Describe what people did and what resulted. If you want to assert intent, cite evidence — a speech, a letter, a documented pattern. Separate the action from the claimed motivation. **And note that a motive is unfalsifiable even when a source states it** — see Principle 12. A cited motive is that source's account, attributed; it does not become a fact by being printed in a book.

### 10. Rhetorical Flourish Discipline

When the prose names rhetorical manipulation as a tool people use on others, deploying flourish inside that same prose proves the manipulators' point — the technique is so embedded in the language that even the writer naming it cannot escape it. The discipline has to be total, or the argument collapses into the very technique it is exposing.

This principle applies with full force whenever the subject matter is propaganda, narrative manufacture, linguistic manipulation, ideological framing, or any analysis that names rhetorical technique as a tool of power. Inside that frame, every figurative construction must either (a) function as a documented technical term with the people using it named, or (b) be replaced with direct description of what they did.

**The test:** For each figurative construction in the draft, ask: does this verb or image describe what specific named people literally did, or does it smuggle in emotional weight the evidence has not earned? If the answer is the second, strip it.

**Verbs that typically survive the audit** because they describe documented acts: proclaimed, declared, drafted, signed, printed, issued, deployed, used, captured, corrupted, fragmented, granted, served, held, owned, financed.

**Verbs that typically read as flourish and need replacement:** weaponized (in loose use, distinct from technical use), engineered, masterminded, buried, peeled away, broke into (metaphorical), built into, escape hatch, lands with weight, full force, sits underneath (positional metaphor with no literal meaning), encoded, installed, radiate, magically, miraculously.

**Praise-flourish:** Adjectives like "brave," "courageous," "groundbreaking," "powerful," and comparative framings like "what most writers refuse to do" smuggle in evaluation the reader has not yet earned through reading. Replace with direct description of what the work documents or identifies.

**Martial metaphor clusters:** "Deploy," "tactics," "weapon," "operation," "captors" may be technical vocabulary in your book, but applied loosely they become flourish. Each instance has to rest on a documented person performing a documented act, or it gets cut.

**Clockwork vocabulary.** "Runs," "operates," "mechanism," "machinery," "the machine" describe people as apparatus. The original author refused that metaphor because it removes the people from their own acts. Name the humans and what they did.

**The closing position — no epigram at the end of a paragraph.** A paragraph ends on its last fact, never on an aphorism about the fact. This is where flourish recurs most reliably, because the aphorism *feels* like a conclusion and so escapes the sentence-level check. **The test is mechanical: delete the last sentence. If the paragraph still lands, the sentence was decoration.** The recorded failure: three consecutive proposed closings for one paragraph, each a short aphorism. The author: *"Every last sentence keeps ending in some obtuse abstraction."* Each performed a conclusion instead of stating one, and each smuggled an implication the page never supported — the first quietly predicted an event the evidence did not. Carve-out: the author's own prose, under the author-voice rule.

**How to fix:** Read each sentence and ask whether the verb names a literal act or smuggles in figurative weight. Replace figurative weight with the documented act. The prose will lose decoration and gain analytical force — which is the point. The reader trusts the argument more when the writer refuses to use the technique the writer is exposing.

### 11. Telegraphing Discipline

When the prose announces its own structure instead of performing it, the reader is told to expect what they could discover by reading. The announcement is the failure. Cut the announcement; perform it.

**Forms of telegraphing:**

- **Forward chapter references:** "we will document in Chapter X," "Chapter X develops this," "we examine in Chapter X what kind of…"
- **Retrospective chapter references:** "we documented in Chapter X," "we introduced in Chapter X," "what we defined in Chapter X as…"
- **Section-internal forward announcement:** "What follows is…", "Here is what he was describing.", "Below we examine…", "In the next section…"
- **Section-internal retrospective summary:** "What this chapter has shown is…", "closes a circle the chapter has been tracing"
- **Meta-references to the chapter itself:** "the most instructive example for this chapter," "the argument of this chapter is…"
- **The chapter as agent:** "Chapter X gave you," "This chapter introduces" — a formulaic crutch that gives agency to a chapter.

**How to fix:** Cut the announcement. Let the substance stand. For cross-chapter callbacks that need to invoke an established concept (a term of art your book defines), use the term directly — the term itself is the bridge; naming the chapter where it was introduced is overhead. Forward references go on the Punch List as deferred work, not in the prose as promises.

**The same fault aimed at a source: "names the actors" is a promise.** When a sentence says a source names, traces, identifies or documents specific people, the specific people appear in that paragraph. Otherwise the paragraph is announcing what the source does instead of doing it. **No trim reaches this fault — open the source and finish the paragraph.** A sample-book case: Paine's "Of the Origin and Design of Government in General" says "Some writers have so confounded society with government" and names no writer in the section; a sentence saying "Paine names the writers" fails, and the fix is to write what Paine wrote. In the original project's recorded case, a five-example series made the promise five times and kept it once. **Read for this in every paragraph**, and also for a paragraph citing several works where each must be checked for a contribution — one recorded paragraph cited two volumes, named eight people, and every name came from the later volume.

### 12. Epistemic Framing Discipline — falsifiability first, then "may"

**Ask first whether any document could break the claim.** The author: *"The question isn't whether or not something is true, verified, or from a so-called authoritative source; the question is: a) who said it and b) what meaning they are conveying. In my frame, unfalsifiability is the boundary between what is real and what is a story/opinion, and no amount of accreditation can change that."*

**A sentence no evidence could break is a story, whoever wrote it.** A chair, a doctorate, a decoration, a directorship, a university press — none of it converts an unfalsifiable claim into a fact. Motives, intentions, dominant pressures, categorical assignments and structural resemblances are the usual shapes.

**The claim sorts three ways.**

**1. Falsifiable and sourced.** State it and cite it.

**2. Falsifiable but unproven.** Say what is known, name what is missing, and mark the gap with "may," "can," "often."

**3. Unfalsifiable.** No framing rescues it in the book's own voice. **Write what people did and let the reader close it** — the "Stop where the record stops" rule. A source's unfalsifiable claim is different: attribute it and nothing more — "Hamilton writes," "Paine says." Never stated flat, never scored, never defended on the source's behalf.

**"May," never "probably."** The author: *"I don't mind probabilistic language, but in retrospect, I would frame it as 'may' rather than 'probably.' That is, there are alternative readings that may be equally plausible. Since it is unfalsifiable, it's not possible to stake a value on the veracity beyond an educated guess."* **"Probably," "most likely," "the evidence suggests" and "the dominant pressure was probably" are likelihood estimates** — they rank one account above others, and nothing grounds the ranking when no evidence can move it. Where other accounts exist, say they may be equally plausible rather than sorting them. **This corrects an earlier version of this principle, which listed those four as the preferred framings.**

**And no first-person hedge.** "I read this as X," "on my reading," "in my view" in front of an inference is pre-emptive retreat, and "reading" is watchlisted besides. The author, on a proposed "I read this as [a label]": *"not something I would write or approve."*

**Two framings that remain available where they suit the passage:**

- **Interrogative.** "Why did Paine leave his name off the pamphlet? His postscript says that who the author is 'is wholly unnecessary to the Public.'" The question form names the speculation.
- **Thought-experiment.** Paine uses this form himself: "let us suppose a small number of persons settled in some sequestered part of the earth." It names the speculation as speculation and lets the reader run it.

**The forbidden form is declarative assertion of plausible specifics as if established fact.** "Paine solved a persuasion problem. Hamilton solved a coalition problem. The ratifying conventions solved a legitimacy problem" presents a constructed categorical scheme as documented history. Each actor faced several overlapping problems; the clean one-bucket-per-actor mapping is rhetorical architecture, not documented analysis.

**A sample-book case.** Hamilton draws the line in *Federalist* No. 1: "My motives must remain in the depository of my own breast. My arguments will be open to all, and may be judged of by all." A sentence in the book's voice saying why Hamilton wrote is unfalsifiable; no document could break it. Even his stated conviction ("I am convinced that this is the safest course for your liberty, your dignity, and your happiness") enters the book attributed: Hamilton writes that he is convinced.

**The recorded case.** A historian's sentence assigning a motive to a medieval group was about to be promoted into a chapter's body as the source for the chapter's own claim. Checking the page showed the motive sentence had no note of its own. **The citation was never the point.** A motive assigned to people centuries dead cannot be broken by any document the historian could have cited, and reporting "he cites nothing" is still grading his standing. The promotion was withdrawn. The same shape was in the book's own voice a few lines away, and the actions that would replace it were already in the next four sentences.

**Sub-pattern: imposed-framework hallucination.** Generating retrospective architecture — neat categorical schemes assigned to historical actors — that reads as established analysis but is constructed. Especially common in synthesis paragraphs after a chapter's body work.

**How to fix:** test for falsifiability first. If unfalsifiable, write the actions. If falsifiable but unproven, use "may." Convert to question form where it suits. Or cut the categorical assignment entirely.

---

### 12b. Abstraction by Omission — name the thing, or point at where it was named

**The fault.** A sentence refers to something and never names it. The prose is grammatical, the subject scan passes, every other principle in this file reports clean, and the reader cannot tell what is being discussed.

**The recorded failure.** Three sentences explained a writer's distinction between two kinds of a named school of thought, described both kinds accurately, and never used the school's name. The author: *"I'm struggling with this abstraction. What are you talking about?"* He asked twice. The sentences were the idea with its nouns removed. **All three faults he named on that one paragraph were this fault:**

| what the prose said | what it refused to name |
|---|---|
| "two things that share a name" | the name |
| an identification the reader had to remember from two paragraphs back | the identification, restated in a clause |
| "after reading the book that names him" | the book's title |

**The test, applied to every sentence that refers to a concept:** *name the thing, or point at where it was named.* A pointer counts only if it is a pointer a reader can follow — "as the passage from Paine above sets out" — never "the book that names him," which asks the reader to solve a riddle.

**Three places it hides.**

1. **The concept with no noun.** "Two kinds of X," "a certain arrangement," "the dynamic at work" — where X is never supplied.
2. **The identification the reader must remember.** A fact established in an earlier paragraph and relied on silently in a later one. If the later paragraph's argument fails without the earlier fact, the later paragraph restates it in a clause.
3. **The definite article with no antecedent in view.** "The book," "the man," "the framework" — fine when the referent is in the same paragraph, a riddle when it is three paragraphs back or absent.

**AND THE DEFENCE AGAINST PARAPHRASING A SOURCE INTO FOG.** In the recorded case the fog was a loose paraphrase of two sentences the writer had stated plainly. **Her sentences were clearer than the paraphrase of them, and the paraphrase also misattributed her terms** — it gave her second kind a name that belonged to two other writers' description of themselves. **When a source states the distinction plainly, quote the source.** Paine states his plainly: "Society is produced by our wants, and government by our wickedness." A paraphrase such as "Paine traces the two to different sources in human nature" has dropped both nouns. A paraphrase that drops the nouns has done two kinds of damage at once.

**What the machine can and cannot do.** `tools/check-glossary.sh` settles one narrow half: does a term defined in the book's glossary get a gloss where the reader first meets it in the book? That has a hard answer. **The general form has no mechanical test.** In the original project a probe ran three patterns for it across every chapter and returned 27 hits, nearly all false. This principle is applied by a reader, in the editorial pass, and is not delegable to a grep.

---

### 13. Actor-Verb Headings

Headings follow the same discipline as body prose: an actor and a verb. "Paine Separates Society from Government" passes; "The Separation," "The Origin," "The Contrast" fail — bare noun-phrases that freeze the section's action into a label. In the original project's book-wide audit, roughly 194 headings failed; the one chapter written under this rule passed at three times the rate of its neighbors.

**Exemptions (load-bearing — the mechanical check mis-scores both):**
- **Question-form headings** ("What Is a Government For?") — a question is its own speech act.
- **Philology headings that mention lexical items** (a heading naming a word and its translations) — the heading names the words under discussion; mention, not use.
- Front/back-matter and navigational headings.

**A heading also has to name what its section does.** A section titled for one paragraph of six makes the reader feel a restart at the point where the argument continues. The recorded failure: a heading named one person who appeared in one paragraph, while five other paragraphs covered three other subjects. Changing the heading fixed what looked like a structural problem.

### 14. The Invented Person (Strawman Discipline)

Principle 1 removes an abstraction from the subject position. **The failure it produces when done carelessly is a manufactured human in that position instead** — and that is a second violation, not a fix. The author, on a pass that traded abstractions for invented people: *"There was so much flummery in the made-up prose, I couldn't understand when you were making a point, and when you were inventing a fairytale."*

**The test:** name him. If the person in the sentence has no name, no date and no document, he does not exist, and the sentence is illustrating with a fabrication.

**Two shapes, and the second is the one that escapes detection.**

**Shape A — the relative clause.** "A man who…", and every disguise: a reader who, a voter who, a citizen who, whoever, anyone who, an owner who. Detectable by pattern.

**Shape B — the bare indefinite subject, no relative pronoun.** "A colonist pays the tax and asks nothing." "A delegate with a farm to run votes against the plan." "A printer sets the type." "When a merchant fails, his creditors divide what remains." **A regex written for Shape A misses every one of these.** The recorded failure: a sweep for `\b(a|an) (man|person|reader|voter|citizen|official) who\b` reported a chapter clean; the author then found four Shape B instances by reading.

**How to fix — three moves, in order of preference.**

1. **Name a real one.** The chapter usually has one already: in the recorded case, the invented figure was followed three paragraphs later by three named people doing the exact thing.
2. **State the property with no person in it.** "An election replaces the officeholder. It does not undo the acts or return the money."
3. **Use the real class, with its real, sourced number.** Replace the single invented figure with the class the sentence means and the count a source gives for it.

**Carve-outs.** Legal terms of art in quoted or drafted instruments ("a living person," "a natural person"); a source's own hypothetical, attributed to that source (Paine's "small number of persons settled in some sequestered part of the earth"); design specifications ("windows set higher than a prisoner could see"); a class defined by a statute under discussion; and hypotheticals the prose marks as hypothetical and owns as such (a what-if series). The author's first-person witness passages are never touched.

**A generic figure is not automatically an invented person.** The fault is a manufactured human with imputed motives or interior states. A bare class noun that the verbs need something to act upon can be legitimate. In the original project a sentence listing four offices, each taking something from "a man," was flagged and ruled **KEEP** — the man had no motive and no interior, and removing him left four offices acting on abstractions. The author on the proposed replacement: *"the examples are forced."* Flagging the construction is correct; every hit still needs a verdict.

**And the reader may be the book's own subject, which the sweep cannot tell from a fabrication.** In a chapter about what a reader takes from a translation, "a reader meeting the word meets a functional description" is the class the argument is about. A book-wide scan in the original project returned about 96 hits on reader-type figures and most were carve-outs — including real people the pattern could not distinguish, described by a job or a school. **The fault is imputed interior: "a doubtful reader" fails where "a reader following the citation" does not.**

**When there is no real case:** say the point is unillustrated and put the search on the Punch List. Never manufacture one.

**Detection pattern for the pass** — Shape B, tuned to catch what the Shape A regex cannot:

```
\b(?:A|An|a|an)\s+(?:\w+\s+){0,2}(?:officeholder|official|candidate|voter|citizen|reader|
worker|employee|manager|broker|banker|lawyer|judge|juror|shareholder|owner|customer|taxpayer|
president|executive|man|woman|person|prisoner|soldier|handler|researcher|historian|scholar|
writer|clerk|agent|colonist|delegate|merchant|printer)\b
```

**A hit is a coordinate, not a verdict.** In the original project that pattern returned 21 hits on one chapter, of which 4 were violations; the rest were a drafted instrument's own legal terms, quoted material, and design specifications. Read every hit before ruling.

---

## Sweep Scope (governs every mechanical check in this skill)

The original project's book-wide audit generated ~4,000 hit rows, of which the large majority were scanner noise. These rules are mandatory for every search, sweep, and mechanical check:

1. **Exclusion zones — filter BEFORE counting:**
   - Block quotes and quoted material (a modal inside a quotation from Hamilton is Hamilton's, not ours)
   - Footnote citation strings — author names, titles, publishers (initials in Chicago citations are not "biographical specifics")
   - Book and work titles (*Common Sense*, *The Federalist*)
   - HTML comments and editorial markers
   - Greek and other original-language runs (governed by the Transcription Gate in citation-audit, not prose sweeps)

2. **Mention vs. use.** A pattern named, taught, quoted-to-deconstruct, or listed as an example is a MENTION and never counts. Chapters that teach the patterns get mention-marking on the teaching passages, not blanket flags. In the original audit the "worst chapter" rankings inverted on exactly this failure.

3. **Carve-outs apply mechanically.** Every banned-word entry's printed exemption is part of the check, applied before the hit is surfaced: "operation" skips capitalized proper names; "hold" skips physical, literal grips. A carve-out stated but not applied produced ~90% of the banned-word noise. `tools/check-banned-words.sh` reads the list and its carve-outs from `Methodology/Word Lists.md` and skips hits the author has already ruled on.

4. **Verdicts are mandatory.** Every surfaced hit gets pass / fail / borderline plus which carve-out (if any) was applied. A candidate dump without verdicts is findings-generation, not an audit, and its totals WILL be misread as violations.

5. **One count per instance.** A violation found by several checks reports once, under the most specific check.

6. **A regex written for one shape does not cover the others.** State which shape the pattern catches and run the others separately. The recorded failure: the Shape A "a man who" sweep certifying a chapter clean of Shape B invented persons (Principle 14).

7. **A negative from a sweep is a fact about the query.** A case-sensitive search reported zero hits for a law firm the source names twice, and a body change was proposed on the strength of the false negative. Check the query before reporting the absence.

## Passive Voice

Not banned. Banned when it deletes an agent who matters. If you're reaching for the passive because naming the agent is inconvenient, that's the signal to name the agent.

**Deliberate agentless passive is legitimate where the agent is not yet established** — a summary sentence that comes before the mechanism ("The pamphlet was printed, and the copies were sold") is honest; naming a printer the prose has not introduced would assert what the reader has not been given. Mark the choice when you make it.

---

## The Editorial Pass (Step by Step)

**Critical: the per-principle numbered list is a tally of findings, NOT the audit-completion certificate.** The audit-completion certificate is the pre-Edit subject-scan table at the top of this file, walked sentence by sentence. The per-principle list reports what the scan found, principle by principle. Producing the list without first producing the scan-table IS the failure mode that ate sessions of the original author's time. The list became an alibi. The scan-table is the proof.

If you find yourself about to claim "audit complete" with a per-principle list but no scan-table on record, the audit is not complete. Produce the scan-table first. The list comes second.

**The principles cover the body AND the footnotes.** Footnotes are prose. Nominalizations, banned words, telegraphing, abstract-noun-as-agent, mind reading, flourish — all of these appear in footnotes too, often more densely than in body text. A footnote that runs 300+ words is a footnote-as-chapter and gets audited as prose, not as citation metadata. Do not skip footnotes.

After completing the draft, walk through it:

1. **Read the draft aloud in your head.** Does it have varied rhythm? Do sentences differ in length and structure? If the draft feels monotonous — if too many sentences share the same [Agent] [verb] [object] pattern — vary the structure before checking for violations. Subordinate clauses, participial phrases, and sentence fragments all have places in good prose.

2. **Per-principle scan — body, headings, AND footnotes, under the Sweep Scope rules.** Walk through each principle in order. For each one, produce a finding line: principle name, instances found (with line numbers), what was changed and what was left alone (with rationale).

   - **Principle 1 — Agent Visibility:** Subject scan. Read only the subjects. Flag any abstraction performing a human action. Fix those — but vary how you fix them. Don't start four consecutive sentences with the same name or with "The people who." Use pronouns, restructure with subordinate clauses, merge sentences.
   - **Principle 2 — Verb Priority:** Nominalization scan. Search for "-ion / -ment / -ence / -ance / -ity" nouns in subject position. Put "ongoing" in front of the word — if it still makes sense, you have a frozen verb.
   - **Principle 3 — Negation Discipline:** Count every negation-first construction in the draft — "not X but Y," "rather than," "not merely," "not simply," "did not X; they Y'd." If more than one or two survive, the rest get rewritten. Two surviving must be in different paragraphs.
   - **Principle 4 — Quantifier Discipline:** Search every / all / always / never AND hidden universals (indispensable, essential, inevitable, universal, unprecedented). Each one: defensible as written or tighten?
   - **Principle 5 — Modal Restraint:** Find every must / should / have to / of necessity. Quoted material gets a pass; literal game-rule descriptions get a pass; the writer's own modal assertions convert to history, evidence, or someone's documented claim.
   - **Principle 6 — Comparison Specificity:** Find every comparative or superlative (more / less / X-er, most / least). Each one needs a named reference point. Strip unanchored "more effective" / "more powerful" / "more important than" — those smuggle editorial assumption.
   - **Principle 7 — No Emergence Language:** Search emerge / arose / arising / appeared / developed. Each one: name who did it, or acknowledge the gap.
   - **Principle 8 — No Complex Equivalence:** Find "because," "the same gesture as," "in the way that," "no different from" causal/equivalence claims. Each one: is the causal link established or interpretive? If interpretive, separate the observations and let the reader draw the connection.
   - **Principle 9 — No Mind Reading:** Find every attribution of internal state ("they knew," "they thought," "they intended," "probably believed," "must have wanted"). Each one: cite evidence, or rewrite as observable behavior. A cited motive is still the source's account, not a fact.
   - **Principle 10 — Rhetorical Flourish Discipline:** Find figurative verbs (encoded, installed, radiate, magically, miraculously, weaponized, engineered, masterminded, buried, sits underneath) and clockwork vocabulary (runs, operates, mechanism, machinery). Each one: does it name a documented act, or smuggle in figurative weight the evidence has not earned? **Then check the closing position of every paragraph** — delete the last sentence and see whether the paragraph still lands.
   - **Principle 11 — Telegraphing Discipline:** Find every announcement of structure. "What follows is...", "Here is what...", "we will see in Chapter X," "we documented in Chapter X," "closes a circle the chapter has been tracing," "the next section," "we'll come back to," "for this chapter," "below we examine," "later in this chapter." Forward AND retrospective. Also: meta-frame paragraphs that announce what the chapter will do; roadmap listings before the work is done; epistemic-position announcements. **And read every paragraph for the source-facing version:** a sentence saying a source names specific people, with none named.
   - **Principle 12 — Epistemic Framing Discipline:** Find every interpretive claim about historical actors, motives, dominant pressures, categorical assignments, causes. **For each one, ask first whether any document could break it.** Unfalsifiable in the book's own voice: write what people did instead — no hedge rescues it. Unfalsifiable in a source: attribute it and stop. Falsifiable but unproven: mark it with **"may," never "probably" or "most likely"** — a likelihood estimate needs something to ground it. Interrogative and thought-experiment framings remain available. No first-person hedge ("I read this as"). Synthesis paragraphs especially: do not assign one-bucket-per-actor categorical labels as if documented. `tools/check-epistemics.sh` flags borrowed authority and pre-emptive retreat for reading.
   - **Principle 12b — Abstraction by Omission:** For every sentence that refers to a concept, a book, a person or an earlier identification: is it named, or is there a pointer a reader can follow? Run `tools/check-glossary.sh NN` for the glossary half; read for the rest.
   - **Principle 13 — Actor-Verb Headings:** Every heading: actor and verb, or an exemption named. Does the heading name what the whole section does?
   - **Principle 14 — Invented Person:** Run the Shape B pattern. Read every hit. For each: real class, quoted material, legal term of art, design spec, marked hypothetical — or a fabrication that needs naming, de-peopling, or replacing with the real class and its real number.

3. **Banned-word check (separate from principles):** Run `tools/check-banned-words.sh NN` against the banned-word list in `Methodology/Word Lists.md` (per-word carve-outs are part of each entry). Each hit gets a finding line with line number, surrounding context, and the proposed replacement or rationale for keeping (e.g., quoted material, technical term of art).

4. **Mechanical sweeps — run as literal searches, never as attention-dependent judgment calls.** Each of these classes survived audits marked "pass" until the check became mechanical:

   a. **Opener check:** Extract the first word of every paragraph. Flag any word opening 3+ consecutive paragraphs. (Recorded failure: four consecutive paragraphs opening with the same plural noun survived a full subject-scan audit.)

   b. **Redundancy scan:** Per section, list each concept or claim stated more than once; flag paragraph pairs that recap each other; count repeated key phrases. Report a compression estimate when a section restates itself. (Recorded failures: a passage of 610 words compressible to 320, with one phrase used 8 times and one construction 4 times, caught by the author after the pass ran clean; and the same vivid specimen used twice 109 lines apart, with the same fact stated in two sections, both caught by reading, not by the sweep. So: search distinctive proper nouns and specimen phrases across the whole chapter, not per section.)

   c. **Cross-section source check:** For each citation, check whether a prior section's source already established the same point. A citation restating an established framework is redundancy at the source level. (Recorded failure: one writer cited for a point a second writer had already established two sections earlier.)

   d. **Tic sweep:** Search the chapter for the pet-phrase watchlist in `Methodology/Word Lists.md`, and flag any noun-phrase label appearing 5+ times as a new watchlist candidate. (Recorded failure: a single noun-phrase label used "without any real point, everywhere," in the author's words.)

   e. **Double-close check:** A chapter or section that states its closing claim, then continues for several paragraphs and states it again, reads as concluding twice. Search the closing claim's key terms across the whole chapter. (Recorded failure: one claim stated in a closing position, restated in reversed word order in another closing position six paragraphs later, plus a third statement in the setup.)

   f. **Referent-drift check.** For each noun that names a class of person, search every instance in the passage and confirm it denotes the same class throughout. (Recorded failure: one word meant one group in one sentence and that group's clients in another. Every sentence passed its own audit; the paragraph was incoherent. See the Mechanism Gate, and Paine's colonists, elected and electors.)

5. **Read the revised draft.** Has the editing flattened anything? If a fix made a sentence duller without making it more honest, find a better fix that keeps the energy.

6. **Re-audit every revision as new draft.** Compression and fixes introduce violations of their own. Before presenting changed text, re-run Principle 3, Principle 4, Principle 14, and the opener check on it. (Recorded failure: "every claim" entered during compression and the same pass's quantifier audit swept it through as "defensible.")

7. **Produce the principle-by-principle output BEFORE claiming the audit complete.** Format:

   ```
   Principle 1 (Agent Visibility): N instances; fixed at L[x], L[y]; left L[z] (rationale)
   Principle 2 (Verb Priority): N instances; ...
   Principle 3 (Negation Discipline): N instances; ...
   Principle 4 (Quantifier Discipline): N instances; ...
   Principle 5 (Modal Restraint): N instances; ...
   Principle 6 (Comparison Specificity): N instances; ...
   Principle 7 (No Emergence Language): N instances; ...
   Principle 8 (No Complex Equivalence): N instances; ...
   Principle 9 (No Mind Reading): N instances; ...
   Principle 10 (Rhetorical Flourish Discipline): N instances; ... ; closing-position check: [result]
   Principle 11 (Telegraphing Discipline): N instances; ... ; source promises: [result]
   Principle 12 (Epistemic Framing Discipline): N instances; ...
   Principle 12b (Abstraction by Omission): N instances; check-glossary.sh: [result]
   Principle 13 (Actor-Verb Headings): N of M headings pass; exemptions applied at ...
   Principle 14 (Invented Person): N hits from the Shape B pattern; V violations; carve-outs at ...
   Banned-word check: N hits after carve-outs; fixed at L[x]; left L[y] (quoted material)
   Mechanical sweeps: openers [result]; redundancy [result]; cross-section sources [result]; tics [result]; double-close [result]; referent-drift [result]
   Footnote audit: per-footnote findings as above
   ```

   The numbered list is the finding-tally. The pre-Edit subject-scan table (top of file) is the audit-completion proof. Both are required. The list without the table is an alibi; the table without the list misses the other principles.

The editorial pass succeeds when the reader cannot tell which sentences were revised — when the corrections are invisible and the prose reads as though it was written cleanly from the start — AND when both the scan-table and the per-principle list are on record.

---

## Common Misses

These are the patterns that most often survive the editorial pass. Check for them explicitly after completing steps 1–7.

**1. "Did not X" as scene-setting.** Sentences like "The vote did not settle the question" use negation to set up the argument. Rewrite as a direct assertion of what happened: "The delegates voted, and the question stayed open." State what happened, not what didn't happen.

**2. Abstract nouns that feel agent-adjacent.** "Interpretive authority," "institutional power," "credentialing systems," "interpretation itself" — these feel close enough to human actors that the subject scan misses them. They are still abstractions. "As their authority expanded" → "As more people accepted their rulings." "Interpretation itself became a form of power" → name the group who turned interpretation into a form of power. Always ask: who is doing the expanding, the becoming, the functioning? Put that person or group in the subject position.

**3. Negation smuggled into appositives and dashes.** "—not coercive in the manner of political force, but structural and pervasive" is a negation-first construction even though it follows a dash. The dash does not exempt it from the negation count. Count every "not X but Y" regardless of punctuation.

**4. Footnotes get skipped.** When the body audit is done, the audit feels complete and the writer moves on. Footnotes are prose too. A 300+ word footnote is a footnote-as-chapter; it needs the same per-principle pass.

**5. Shape B invented persons.** A regex for "a man who" reports clean on "A colonist pays the tax." Run the Principle 14 pattern separately; do not assume the Shape A sweep covered it.

**6. The five principles I systematically skip when not actively testing for them:** Principle 2 (Nominalization scan), Principle 8 (Complex Equivalence), Principle 9 (Mind Reading), Principle 10 (Rhetorical Flourish), Principle 12 (Epistemic Framing). These get checked only when explicitly named in the per-principle output. If your output list doesn't have lines for all five, you skipped them.

**7. Telegraphing (Principle 11) was the highest-frequency missed principle in the original book.** Forward and retrospective chapter references read as natural to me and easy to skip. Search for "Chapter [0-9]" in the body and check every match.

**8. Violations introduced during revision get audited less strictly than draft text.** The pass that produced a fix tends to certify its own output. Treat every compressed or revised passage as unaudited new draft (editorial pass step 6). Recorded failure: "every claim," introduced by a compression.

**9. An unfalsifiable claim from a credentialed source reads as a fact.** The badge does the work the evidence cannot, and the sentence passes every other check in this file because the quotation is faithful and the source is real. Ask what kind of claim it is, not how good the source is. Recorded failure: a historian's account of a medieval group's motive, nearly promoted into a chapter body in the book's own voice.

**9b. Synthesis paragraphs are the highest-risk site for Epistemic Framing violations (Principle 12).** A chapter's closing synthesis is where the temptation appears: recap the chain with clean labels. The reader has just read the body; the synthesis names the thesis. Inserting a four-bucket categorical assignment ("X faced a real Y problem. A managed a real B problem...") presents a constructed framework as documented history. Audit each synthesis paragraph especially carefully against Principle 12.

**10. Repeated specimens across distant sections.** A vivid example used once in an early section and again in a late one reads as new the second time to the writer and as repetition to the reader. Search distinctive proper nouns and specimen phrases across the whole chapter before presenting a section as finished.

**11. Editing a mechanism I have not drawn.** The highest-cost miss in the file, because it is invisible from inside: the prose reads plainly, the subject scan passes, and the sentences are false or incoherent as a set. The Mechanism Gate at the top of this file exists for this. If the passage describes a process and I have not written the chain out in chat, nothing downstream in this skill will catch what I get wrong. **And the signal that it has been missed is repetition: a passage rejected twice for different faults is a passage whose chain was never drawn.**

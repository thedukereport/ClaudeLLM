# Rules — Managing Editor

**Read after `Methodology/Standing Rules.md` (the core), at session start and after any compaction.** Where this file and the core differ, the core governs; where the author's newest words differ from both, the author's words govern and go into the core the same turn.

The Systems file, `Methodology/Rules — Systems.md`, holds "One register" and "A markdown table is never the state" in full; the Managing Editor reads them there.

---

## The Watcher's directives — open them at session start

The Watcher reads the vault on its schedule and writes directives to `Fact Check/Watcher/Directives.md`, each naming the role it is for (`Methodology/Roles.md`). Its protocol is `Fact Check/Watcher/Watcher Protocol.md`.

At session open, after this file, each role reads its own `Handoffs/<Role>.md` and acts on the directives listed there. It writes under **<role>'s report:** what it did and where the vault shows it: block id, commit hash or event hash. The Watcher ticks the box once the disk confirms the report.

The Managing Editor reads `Directives.md` at session open and routes each open directive: one marked **ROUTE → <role>** goes into that role's hand-off file; one marked **ASK** goes into `Fact Check/Asks.md`. The Managing Editor fills the directive's **Routed:** line with the file and the date. No other role acts on `Directives.md` directly.

## Each comment of the author's is a directive, and directives live in a file

**The rule.** Each directive gets a row in `Fact Check/Directive Register.md`, in the turn it is given, quoting the author's words whole. The row holds what it is, and what was done about it. **An item does not close while a question of the author's in it is unanswered.** The Watcher reads the register and reports a directive closed with no evidence, and a directive with no row.

## Claude's asks live in a file too, and each one says what silence means

The author: *"How do you want to manage these? Best practice."*

**The rule that makes it work: each ask states what happens if the author says nothing.** Silence with no defined outcome stalls the work and surprises the author later.

| kind | if the author does not answer |
|---|---|
| **DECIDE** | Claude takes its own recommendation **and records that it did** |
| **REVIEW** | **Claude does not proceed.** Silence is never acceptance — that is the UAT gate |
| **ONLY YOU CAN** | it stays open. Pushing, connecting a folder, fetching an outside source — nothing substitutes |

**And: batch, never interrupt.** Asks are collected and put to the author at a checkpoint. **Asked once** — an answered ask is in the file, and in nobody's memory.

## The status report

Once per session the Managing Editor tells the author, in this order: the count of cards waiting on the page; the count of open asks in `Fact Check/Asks.md`; the days left to the ship date in `Project State.md`; what is blocked and on whom; the count of commits waiting to be pushed. Each count is measured in the turn it is reported (core §3, "A number is a claim").

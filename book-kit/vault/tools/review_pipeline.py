#!/usr/bin/env python3
"""review_pipeline.py — six fresh readers review a card once, before it is released to the author's desk.

    python3 tools/review_pipeline.py packet <card_id>              # write the six reviewers' prompts; print their paths
    python3 tools/review_pipeline.py record <card_id> --version N --reviewer R1 --verdict PASS|FAIL \\
            --quote "the card's words the verdict rests on" [--fix "the fix, written out in full"]
    python3 tools/review_pipeline.py status <card_id>              # the verdicts on the newest version

WHOSE RULE THIS IS

    The author of the system this kit comes from, after cards that had passed one writer and one auditor came back
    to him wrong: "Feed these issues into a agentic-monkeys-style pipeline" [sic]. Then, asked how often: "Six, once,
    at release." Six reviewers, each with a fresh context and none with the writer's reasoning, read the version
    about to reach the author, once. A FAIL goes back to the writer, whose next version fixes the findings and goes
    to the author with no new round (`tools/cards.py review-fix`).

HOW IT RUNS

    After the writer's version and the second session's prose audit, the writing role runs `packet`, then starts six
    subagents in parallel, one per prompt file. Each ends with one JSON object:
    {"reviewer": "R1", "verdict": "PASS" or "FAIL", "quote": "...", "fix": "..."}. The role records each with
    `record`, which refuses a verdict with no quoted words and a FAIL with no fix written out. When the sixth verdict
    on a version is in, `record` writes the one verdict `tools/cards.py release` reads: PASS when all six pass, FAIL
    with each failing reviewer's fix as a finding.
"""
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import bookconfig as B  # noqa: E402
import cards  # noqa: E402

OUT = B.HANDOFFS / "Review Packets"     # working files; nothing the author reads
REVIEWERS = {
    "R1": ("the author's words answered",
           "Read every press of the author's listed below, in full. List each thing he asked for, including what any "
           "example he gives shows as the form of the answer. Check that the proposed text and the card's `answer` "
           "deliver each one, at the size he asked. FAIL on anything he asked for that the card does not deliver, or "
           "delivers narrower than he asked."),
    "R2": ("the answer and the reasons at the top",
           "Check that the card's `answer` quotes his words and answers them in plain, complete sentences; that the "
           "`tldr` and `recommendation` say what this version does; and that `changeList` gives every change with a "
           "why a reader can check. FAIL when an answer to him sits only in a fold or a choice's fine print, a change "
           "has no reason, or the title describes an older version."),
    "R3": ("the paragraph's argument",
           "Open the chapter file and read the whole paragraph the card changes, and the paragraphs before and after "
           "it. State the paragraph's argument as the card would leave it, step by step, on your own, starting from "
           "the author's own sentences (a sentence with no citation is his). FAIL when a step is missing or does not "
           "follow, when a sentence he did not write moves the paragraph away from his point, or when the card "
           "repeats something told elsewhere in the chapter doing the same job."),
    "R4": ("full, but once",
           "Read every sentence of the card written to him (title, tldr, recommendation, answer, each why, each "
           "choice's label and reason). FAIL on a ruling of his shortened to a label, two facts folded into one "
           "clause, a step left out between two sentences, a term he has not seen on his desk, or one thing said "
           "twice. The fix gives the sentence in full, or cuts the repeat."),
    "R5": ("every work read",
           "List every work, person and quotation on the card, in the proposed text and in the card's words to him. "
           "For each, look in `Fact Check/Claims/` for a row with a reader and a `drive_path` whose words cover it. "
           "For each quotation, give the source's whole sentence from that read, and FAIL when the card gives it "
           "another subject, drops something the person said, or turns a hedge into a claim. FAIL on any fact with "
           "no read."),
    "R6": ("his rulings in his words",
           "List every ruling of his that the card applies: terms, glosses, capitals, his own sentences. Check each "
           "against `Methodology/Standing Rules.md`. FAIL on a wording that merges two of his rulings, widens or "
           "narrows one, or changes a sentence of his he did not ask to change."),
}
FIELDS = ("title", "chapter", "where", "answer", "tldr", "recommendation", "subject", "changeList", "choices",
          "before", "current", "proposedPara", "proposedNote", "after", "job", "review")


def packet(card_id):
    vs = cards.versions(card_id)
    if not vs:
        raise cards.Refused(f"no card {card_id!r}")
    line = vs[-1]
    v, c = int(line["version"]), line["card"]
    d = OUT / card_id / f"v{v}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "card.json").write_text(json.dumps({k: c.get(k) for k in FIELDS if c.get(k) not in (None, "", [], {})},
                                            ensure_ascii=False, indent=1), encoding="utf-8")
    ps = [p for p in cards.presses(card_id) if cards._t(p["at"]) <= cards._t(line["at"])]
    (d / "presses.json").write_text(json.dumps(ps, ensure_ascii=False, indent=1), encoding="utf-8")
    paths = []
    for r, (name, task) in REVIEWERS.items():
        p = d / f"{r}.md"
        p.write_text(f"""You are reviewer {r} ({name}) for a card on the card desk of *{B.TITLE}*. You read with a fresh
context. You have not seen the writer's reasoning, and you do not need it.

Work in {B.VAULT}. Read `Methodology/Standing Rules.md` first. Then read:

- the card, version {v}: `{cards.rel(d / 'card.json')}`
- the author's presses on the card before this version, each in full: `{cards.rel(d / 'presses.json')}`
- the chapter the card changes, from disk (its line numbers may have moved since the card was written)

YOUR TASK. {task}

Change no file. A search only tells you where to read; the read decides.

End your reply with one JSON object on its own, and nothing after it:
{{"reviewer": "{r}", "verdict": "PASS" or "FAIL", "quote": "the card's or the chapter's exact words your verdict rests
on", "fix": "for a FAIL, the fix written out in full; for a PASS, empty"}}
""", encoding="utf-8")
        paths.append(p)
    return paths


def verdicts(card_id, version):
    import vaultlog
    out = {}
    for e in vaultlog.fold("review.verdict"):
        if e.get("card") == card_id and int(e.get("version") or 0) == int(version):
            out[e.get("reviewer")] = e
    return out


def record(card_id, version, reviewer, verdict, quote, fix="", by="review pipeline"):
    import vaultlog
    verdict = str(verdict or "").upper()
    if reviewer not in REVIEWERS or verdict not in ("PASS", "FAIL"):
        raise cards.Refused("the reviewer is R1 to R6 and the verdict PASS or FAIL; nothing written.")
    if not str(quote or "").strip():
        raise cards.Refused("a verdict quotes the words it rests on (--quote); nothing written.")
    if verdict == "FAIL" and not str(fix or "").strip():
        raise cards.Refused("a FAIL gives its fix, written out in full (--fix); nothing written.")
    h = vaultlog.append("review.verdict", actor=by, card=card_id, version=int(version), reviewer=reviewer,
                        name=REVIEWERS[reviewer][0], verdict=verdict, quote=str(quote).strip(), fix=str(fix).strip(),
                        why=f"reviewer {reviewer} {verdict} on {card_id} v{version}")["hash"]
    got = verdicts(card_id, version)
    if len(got) == len(REVIEWERS):
        fails = [f"{r} {e.get('name')}: {e.get('fix')}" for r, e in sorted(got.items()) if e.get("verdict") == "FAIL"]
        cards.review_pass(card_id, version=int(version), by=by, verdict="FAIL" if fails else "PASS",
                          note=f"the six reviewers on v{version}: {len(fails)} FAIL", findings=fails)
    return h


def _opt(argv, name, default=""):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def main(argv):
    if len(argv) < 2 or argv[0] not in ("packet", "record", "status"):
        print(__doc__)
        return 2
    cmd, cid = argv[0], argv[1]
    try:
        if cmd == "packet":
            for p in packet(cid):
                print(p)
            return 0
        if cmd == "record":
            h = record(cid, int(_opt(argv, "--version", "0")), _opt(argv, "--reviewer"), _opt(argv, "--verdict"),
                       _opt(argv, "--quote"), _opt(argv, "--fix"))
            print(f"recorded, event {h}")
            return 0
    except cards.Refused as e:
        print(f"REFUSED: {e}")
        return 1
    vs = cards.versions(cid)
    v = int(vs[-1]["version"]) if vs else 0
    got = verdicts(cid, v)
    for r in REVIEWERS:
        e = got.get(r)
        print(f"  {r} {REVIEWERS[r][0]:<40} {e.get('verdict') if e else 'not yet'}")
    print(f"{cid} v{v}: {len(got)} of {len(REVIEWERS)} verdicts")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

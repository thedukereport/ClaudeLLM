#!/usr/bin/env python3
"""uat.py — nothing writes at scale until the author has accepted a sample.

    from uat import require_acceptance, record_acceptance, show_sample, SAMPLE_HELP

    require_acceptance("apply.py", n_targets)   # stops a bulk write and explains
    record_acceptance("apply.py", "what the author was shown")   # after the author's "ok"

    tools/uat.py status [tool]                  # the acceptances on record
    tools/uat.py accept <tool> "what the author was shown"

WHY THIS EXISTS

    The author's rule: "You cannot build anything anymore without some kind
    of user acceptance testing. I don't need to get 300 changes into a process
    for you to find a bug."

    The run that produced it: a merge tool rewrote 97 items, and its test for
    "has the author already ruled on this" was a superset test where a
    "differs from" test was meant. Every short answer the author had typed
    (an "ok", for one) read as unruled, the merge absorbed those items, and 58
    of the author's rulings were deleted. It was found by counting after the
    write. A sample of three items would have shown it at once, because two of
    the three would have been the author's answers vanishing. The same shape
    had happened twice more that week, in other tools.

THE RULE THIS ENFORCES

    A tool that writes may run on a SAMPLE without permission, printing the
    complete before and after of every change it would make. It may not write
    at scale until a line for it exists in `Methodology/UAT Log.md` recording
    what the author saw and that the author accepted it.

    "At scale" is more than SAMPLE_MAX targets. Below that the author can read
    every change in the terminal, which is the sample.

THE WORD IS "ok". THERE IS NO SECOND VOCABULARY.

    "ok" on a sample is an acceptance, the same word that approves anything
    else. For one day the original system asked the author to type
    "accepted" for this tool and "ok" for every other, and the author asked
    why there were two. There should not be: the author never has to know
    which script is asking. Claude writes the log line; the author types the
    same word as everywhere else.

WHAT A SAMPLE HAS TO SHOW

    The whole before and the whole after, never a summary and never a count.
    A count is what failed: 97 items merged, 58 fewer rulings, and the number
    looked like success while it was measuring deletion.
"""
import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

LOG = B.UAT_LOG
SAMPLE_MAX = 5

SAMPLE_HELP = f"""
    --sample     change nothing; print the full before and after of the first
                 few changes, for {B.AUTHOR} to read. The author's "ok" releases the write.
"""

ROW_RE = re.compile(r"\|\s*([\d-]+)\s*\|\s*`?([^|`]+?)`?\s*\|\s*([^|]*?)\s*\|\s*ACCEPTED\s*\|")


class NotAccepted(SystemExit):
    pass


def _short(p: Path) -> str:
    """A readable path. A test can point LOG outside the vault, and
    Path.relative_to raises on that, which would hide the refusal behind a
    traceback."""
    try:
        return str(Path(p).relative_to(B.VAULT))
    except ValueError:
        return str(p)


def acceptances():
    """[(date, tool, what)] for every ACCEPTED line, oldest first."""
    if not LOG.exists():
        return []
    return [(m.group(1), m.group(2).strip(), m.group(3))
            for m in (ROW_RE.match(l) for l in LOG.read_text(encoding="utf-8").splitlines()) if m]


def accepted_for(tool: str) -> str:
    """The date of the most recent acceptance for this tool, or ''."""
    for date, t, _ in reversed(acceptances()):
        if t == tool:
            return date
    return ""


def require_acceptance(tool: str, n_targets: int, sample_flag: str = "--sample"):
    """Stop a bulk write that has never been sampled and accepted."""
    if n_targets <= SAMPLE_MAX:
        return
    if accepted_for(tool):
        return
    raise NotAccepted(
        f"\nREFUSING TO WRITE. {tool} would change {n_targets} things and nothing in\n"
        f"{_short(LOG)} records {B.AUTHOR} accepting a sample of its output.\n\n"
        f"Run `tools/{tool} {sample_flag}` first. It changes nothing and prints the whole\n"
        f"before and after of the first {SAMPLE_MAX} changes. Show those to {B.AUTHOR}.\n"
        f"The author's word is \"ok\", the same word that approves anything else: record it\n"
        f"(tools/uat.py accept {tool} \"what was shown\") and run this again.\n\n"
        f"The author's rule: \"I don't need to get 300 changes into a process for you\n"
        f"to find a bug.\"\n")


def record_acceptance(tool: str, what: str, verdict: str = "ACCEPTED"):
    """Write the acceptance line. Only ever called after the author says so."""
    today = datetime.date.today().isoformat()
    what = what.replace("|", "/").replace("\n", " ").strip()
    row = f"| {today} | `{tool}` | {what} | {verdict} |\n"
    if not LOG.exists():
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text(
            "# UAT Log\n\n"
            "The author's rule: *\"You cannot build anything anymore without some kind "
            "of user acceptance testing. I don't need to get 300 changes into a process "
            "for you to find a bug.\"*\n\n"
            "Each tool that writes records here what the author was shown and what the "
            "author said. `tools/uat.py` reads this file and refuses a bulk write for any "
            "tool with no ACCEPTED line.\n\n"
            "| date | tool | what the author was shown | verdict |\n"
            "|---|---|---|---|\n", encoding="utf-8")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(row)
    return row


def show_sample(changes, n=SAMPLE_MAX):
    """Print the whole of each change. No truncation: truncation is how a
    wrong edit looks acceptable. `changes` is [(where, before, after)]."""
    print(f"\nSAMPLE — {min(n, len(changes))} of {len(changes)} changes, "
          f"in full. Nothing has been written.\n")
    for i, (where, before, after) in enumerate(changes[:n], 1):
        print(f"{'=' * 72}\n[{i}] {where}\n")
        print(f"  BEFORE\n  {'-' * 68}")
        for line in (before or "(nothing)").splitlines() or [""]:
            print(f"  {line}")
        print(f"\n  AFTER\n  {'-' * 68}")
        for line in (after or "(removed)").splitlines() or [""]:
            print(f"  {line}")
        print()
    print(f"{'=' * 72}")
    print(f"{len(changes)} changes in total. Nothing written.")
    print(f"If {B.AUTHOR} accepts these, record it with tools/uat.py accept, "
          f"then run again with --write.")


def main(argv):
    if not argv or argv[0] not in ("status", "accept"):
        print(__doc__)
        return 2
    if argv[0] == "status":
        rows = acceptances()
        if len(argv) > 1:
            rows = [r for r in rows if r[1] == argv[1]]
        if not rows:
            print(f"No acceptances on record in {_short(LOG)}"
                  + (f" for {argv[1]}." if len(argv) > 1 else "."))
            return 0
        for date, tool, what in rows:
            print(f"  {date}  {tool:<28} {what}")
        return 0
    if len(argv) < 3 or not argv[2].strip():
        print('usage: uat.py accept <tool> "what the author was shown"')
        return 2
    print(record_acceptance(argv[1], argv[2]).rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

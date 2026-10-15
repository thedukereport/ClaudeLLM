#!/usr/bin/env python3
"""smoke-test.sh — run every tool in its safe mode, then every test, and report what broke.

    tools/smoke-test.sh            # the tools against your vault, then the tests
    tools/smoke-test.sh -v         # print the failure output too
    tools/smoke-test.sh --tests    # the tests only (they use a copy of the sample book)

WHY THIS EXISTS

    The author, of the system this kit comes from: "You cannot build anything
    anymore without some kind of user acceptance testing. I don't need to get
    300 changes into a process for you to find a bug." A one-line patch once
    left two checkers unable to start, and nothing ran them until a wrong answer
    showed up. One command that starts every tool catches that kind of fault.

WHAT IT PROVES, AND WHAT IT DOES NOT

    It proves each tool starts, imports its neighbours and finishes its safe
    mode, and that each test passes. It proves nothing about whether an answer
    is right; a sample shown to the author is for that, and `tools/uat.py`
    enforces it. A green run means "nothing is obviously broken".

HOW TO READ A NON-ZERO EXIT

    A check that finds something exits 1, and that is an answer, not a crash.
    Those tools are marked "finding allowed" below. A crash (a Python traceback,
    or exit 2 where 2 means "could not run") is BROKEN either way. The tests run
    against a temporary copy of the sample book and never touch your vault.
"""
import os
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
TESTS = TOOLS.parent / "tests"

# (script, args, finding allowed)
TOOLS_SAFE = [
    ("bookconfig.py", [], False),
    ("vaultlog.py", ["--verify"], False),
    ("blocks.py", [], False),
    ("witness.py", ["--json"], True),
    ("have.sh", ["Common Sense"], True),
    ("check-read.sh", [], True),
    ("check-drive-path.sh", [], True),
    ("check-banned-words.sh", [], True),
    ("check-epistemics.sh", [], True),
    ("check-footnote-length.sh", [], True),
    ("check-footnotes.sh", ["--all"], True),
    ("check-anchors.sh", [], True),
    ("check-crossrefs.sh", [], True),
    ("check-glossary.sh", [], True),
    ("check-note-content.py", [], True),
    ("assess-notes.py", [], True),
    ("check-ellipsis.sh", ["--all", "--list"], True),
    ("check-card-logged.py", [], True),
    ("check-card-words.py", [], True),
    ("check-card-notes.py", [], True),
    ("check-card-closed.py", ["--page-only"], True),
    ("prose.py", [], True),
    ("lock.py", ["status"], False),
    ("uat.py", ["status"], False),
]


def run(cmd, label, verbose, allow):
    env = dict(os.environ)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT  {label}")
        return False
    crashed = "Traceback (most recent call last)" in (r.stderr or "")
    if label.startswith("witness.py") and r.returncode == 2 and "NO SEAL" in (r.stdout + r.stderr):
        print(f"  ok       {label}   (no seal yet: run tools/witness.py --seal once on a clean vault)")
        return True
    ok = r.returncode == 0 or (allow and r.returncode == 1 and not crashed)
    print(f"  {'ok      ' if ok else 'BROKEN  '} {label}" + ("" if r.returncode == 0 else f"   (exit {r.returncode})"))
    if not ok and verbose:
        tail = (r.stderr or r.stdout).strip().splitlines()[-15:]
        print("\n".join("           " + l for l in tail))
    return ok


def main(argv):
    verbose = "-v" in argv
    ok = True
    if "--tests" not in argv:
        print("The tools, in their safe modes, against this vault:\n")
        for script, args, allow in TOOLS_SAFE:
            p = TOOLS / script
            if not p.exists():
                print(f"  MISSING  {script}")
                ok = False
                continue
            ok &= run([sys.executable, str(p)] + args, f"{script} {' '.join(args)}".strip(), verbose, allow)
    print("\nThe tests, each against a temporary copy of the sample book:\n")
    for t in sorted(TESTS.glob("*_test.py")):
        ok &= run([sys.executable, str(t)], f"tests/{t.name}", verbose, False)
    print()
    print("All green. Nothing is obviously broken; whether the answers are right is what a sample is for."
          if ok else "SOMETHING IS BROKEN. Fix it before running anything that writes.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

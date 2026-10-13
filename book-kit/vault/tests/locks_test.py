#!/usr/bin/env python3
"""tests/locks_test.py — the lock gate names what blocks a chapter, and lock.py obeys it.

WHAT IT CHECKS, ON A COPY OF THE SAMPLE VAULT

    check-lock-ready.sh
      1. Chapter 2 fails, and the report names each planted blocker: an open
         Punch List item, an open card on the page snapshot, the work nobody
         has read (check-read.sh), and the missing preflight receipt.
      2. A Punch List item for another chapter (Ch12) does not block Ch02.
      3. Chapter 1 fails on its planted banned word.
      4. A sub-check that crashes is a FAILURE, never a pass: the original
         gate tested the exit status of `tail` and passed a chapter when the
         read check crashed. So does a sub-check that is missing.
      5. A preflight receipt that matches the chapter clears that blocker; a
         receipt older than the chapter is reported stale.

    lock.py
      6. `lock` refuses when the gate fails, and Locks.md is not written.
      7. With a gate that passes: lock, status, unlock (refused without a
         note), unlock with a note, status. Each change is a file.written
         event, and the event log's chain verifies.
      8. A chapter out of workflow can be neither locked nor unlocked.

    It writes nothing outside its temporary folder.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KIT_VAULT = Path(__file__).resolve().parent.parent
SAMPLE = KIT_VAULT.parent / "sample"

bad = []


def check(cond, msg, out=""):
    if not cond:
        bad.append(msg + ("\n" + out if out else ""))


def run(vault, *cmd, stdin=None):
    env = dict(os.environ, BOOK_VAULT=str(vault))
    return subprocess.run([sys.executable, *map(str, cmd)], capture_output=True, text=True,
                          env=env, cwd=vault, input=stdin if stdin is not None else "")


with tempfile.TemporaryDirectory() as t:
    v = Path(t) / "book"
    shutil.copytree(SAMPLE, v)
    shutil.copytree(KIT_VAULT / "tools", v / "tools",
                    ignore=shutil.ignore_patterns("__pycache__"))
    # The template's rule files (word lists, rulings registers), as an author
    # who copies the template vault has them; the sample's own files win.
    for folder in ("Methodology", "Fact Check"):
        for src in (KIT_VAULT / folder).rglob("*"):
            dst = v / src.relative_to(KIT_VAULT)
            if src.is_file() and not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
    tools = v / "tools"
    gate = tools / "check-lock-ready.sh"
    ch2 = next((v / "Chapters").glob("Chapter 02*.md"))

    # Plant the blockers the sample lacks.
    (v / "Punch List.md").write_text(
        "# Punch List\n\n"
        "- [ ] Ch02 — check the Hamilton quotation against the source\n"
        "- [x] Ch02 — a closed item does not block\n"
        "- [ ] Ch12 — another chapter's item\n", encoding="utf-8")
    props = v / "Handoffs" / "editor-tools" / "page-snapshot" / "proposals"
    props.mkdir(parents=True, exist_ok=True)
    (props / "locktest-c1.json").write_text(json.dumps(
        {"title": "Ch 02 · the Hamilton quotation", "chapter": "Ch 02", "where": "Ch02/L5",
         "status": "yours"}), encoding="utf-8")
    (props / "locktest-c2.json").write_text(json.dumps(
        {"title": "Ch 02 · applied", "chapter": "Ch 02", "where": "Ch02/L3",
         "status": "applied"}), encoding="utf-8")

    # 1, 2
    r = run(v, gate, "02")
    out = r.stdout + r.stderr
    check(r.returncode == 1, f"Ch02 should fail the gate with exit 1, got {r.returncode}", out)
    check("Punch List.md L3" in out, "the open Punch List item was not named", out)
    check("Ch12" not in out, "a Ch12 Punch List item blocked Ch02", out)
    check("a closed item" not in out, "a closed Punch List item blocked Ch02", out)
    check("card locktest-c1" in out, "the open card was not named", out)
    check("card locktest-c2" not in out, "an applied card blocked Ch02", out)
    check("check-read.sh" in out and "Federalist" in out,
          "the unread work was not named", out)
    check("no preflight receipt" in out, "the missing preflight receipt was not named", out)

    # 3
    r = run(v, gate, "01")
    out = r.stdout + r.stderr
    check(r.returncode == 1 and "unruled hit(s) in Ch01" in out,
          "Ch01's planted banned word was not reported as a blocker", out)

    # 4 — a crashing sub-check, then a missing one
    real_read = (tools / "check-read.sh").read_text(encoding="utf-8")
    (tools / "check-read.sh").write_text("#!/usr/bin/env python3\nraise RuntimeError('boom')\n",
                                         encoding="utf-8")
    r = run(v, gate, "02")
    out = r.stdout + r.stderr
    check(r.returncode == 1 and "check-read.sh did not run to the end" in out,
          "a crashing check-read.sh was not reported as a failure", out)
    (tools / "check-read.sh").unlink()
    r = run(v, gate, "02")
    out = r.stdout + r.stderr
    check(r.returncode == 1 and "check-read.sh is missing" in out,
          "a missing check-read.sh was not reported as a failure", out)
    (tools / "check-read.sh").write_text(real_read, encoding="utf-8")

    # 5 — preflight receipt, current then stale
    pf = v / ".preflight"
    pf.mkdir(exist_ok=True)
    stamp = pf / "ch02.stamp"
    stamp.write_text(f"now\n{hashlib.sha1(ch2.read_bytes()).hexdigest()}\n{ch2.name}\n",
                     encoding="utf-8")
    r = run(v, gate, "02")
    check("preflight" not in r.stdout.split("note:")[0].replace("tools/preflight.sh", ""),
          "a current preflight receipt was still reported", r.stdout)
    stamp.write_text("then\n0000\nx\n", encoding="utf-8")
    r = run(v, gate, "02")
    check("preflight receipt is stale" in r.stdout, "a stale receipt was not reported", r.stdout)

    # 6 — lock refuses on a failing gate
    locks_md = v / "Fact Check" / "Locks.md"
    before = locks_md.read_text(encoding="utf-8") if locks_md.exists() else None
    r = run(v, tools / "lock.py", "lock", "02", "--by", "production")
    check(r.returncode == 1 and "REFUSED" in r.stdout, "lock did not refuse a failing chapter",
          r.stdout + r.stderr)
    after = locks_md.read_text(encoding="utf-8") if locks_md.exists() else None
    check(before == after, "a refused lock changed Locks.md")

    # 7 — round trip with a gate that passes
    gate.write_text("#!/usr/bin/env python3\nprint('stub gate: pass')\n", encoding="utf-8")
    r = run(v, tools / "lock.py", "lock", "02", "--by", "production", "--note", "first lock")
    check(r.returncode == 0 and "LOCKED" in r.stdout, "lock failed with a passing gate",
          r.stdout + r.stderr)
    r = run(v, tools / "lock.py", "status", "02")
    check("🔒 LOCKED" in r.stdout, "status did not show the lock", r.stdout)
    r = run(v, tools / "lock.py", "unlock", "02", "--by", "production")
    check(r.returncode == 1 and "--note" in r.stdout, "unlock without a note was not refused",
          r.stdout)
    r = run(v, tools / "lock.py", "unlock", "02", "--by", "production",
            "--note", "the author reopened it for the quotation")
    check(r.returncode == 0 and "UNLOCKED" in r.stdout, "unlock failed", r.stdout + r.stderr)
    r = run(v, tools / "lock.py", "status")
    check("Ch02  🔓 UNLOCKED" in r.stdout and "Ch01  🔓 never locked" in r.stdout,
          "status after unlock is wrong", r.stdout)
    locks = (v / "Fact Check" / "Locks.md").read_text(encoding="utf-8")
    rows02 = [l for l in locks.splitlines() if l.startswith("| 02 |")]
    check(len(rows02) == 2 and "🔒" in rows02[0] and "🔓" in rows02[1]
          and "check-lock-ready.sh passed" in rows02[0] and "the author's ruling" in rows02[1],
          "Locks.md should hold the lock row, then the unlock row, for chapter 02", locks)
    r = run(v, tools / "lock.py", "lock", "02", "--by", "nobody")
    check(r.returncode == 2, "an unknown role was not refused as a usage error", r.stdout)
    events = []
    for f in sorted((v / "Fact Check" / "events").glob("*.jsonl")):
        events += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    written = [e for e in events if e["kind"] == "file.written" and e["path"].endswith("Locks.md")]
    check(len(written) == 2, f"expected 2 file.written events for Locks.md, got {len(written)}")
    r = run(v, tools / "vaultlog.py", "--verify")
    check(r.returncode == 0, "the event log chain does not verify", r.stdout)

    # 8 — out of workflow
    toml = v / "book.toml"
    toml.write_text(toml.read_text(encoding="utf-8").replace(
        "out_of_workflow = []", "out_of_workflow = [1]"), encoding="utf-8")
    for verb in (["lock", "01", "--by", "production"],
                 ["unlock", "01", "--by", "production", "--note", "x"]):
        r = run(v, tools / "lock.py", *verb)
        check(r.returncode == 1 and "out of workflow" in r.stdout,
              f"{verb[0]} of an out-of-workflow chapter was not refused", r.stdout)

if bad:
    for b in bad:
        print("  FAIL: " + b)
    raise SystemExit(f"locks: {len(bad)} failure(s)")
print("  locks: the gate names each blocker, a crashed or missing check fails, and lock.py "
      "locks, unlocks and logs only through the gate.")

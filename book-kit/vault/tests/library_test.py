#!/usr/bin/env python3
"""tests/library_test.py — the library search and read-tracking tools answer correctly on the sample book.

WHAT IT CHECKS, IN A COPY OF THE SAMPLE VAULT

    1. have.sh finds "Common Sense" and "The Federalist Papers" on the PDF/
       shelf, says NOT BY NAME for a title the library does not hold, and
       finds a cited title with its subtitle through the main-title retry.
    2. have.sh writes its index to the [library] index_file, and the index
       notices a book added afterwards without --reindex.
    3. find-source.sh finds "reflection and choice" in the Federalist text and
       says FOUND.
    4. check-read.sh lists both cited works (Common Sense, The Federalist
       Papers) as UNREAD, because the sample has no Claims rows (planted
       fault 4), lists nothing as NOT IN LIBRARY, and --strict exits 1.
       A Claims row naming a reader moves the work to READ.
    5. A library root that does not exist never produces NOT IN LIBRARY:
       check-read.sh says NOT SEARCHED and have.sh stops with exit 2.
    6. preflight.sh 1 prints the sources for chapter 1 (the cited work and
       its copy in the library), the lock state, and writes the receipt
       .preflight/ch01.stamp with the chapter's SHA-1.
    7. check-drive-path.sh passes a relative drive_path that opens and fails
       one that does not.
    8. show.sh prints a line with the footnote it anchors.
    9. rulings.load reads a fingerprint row from the Banned-Word Rulings
       template, and the two templates in vault/Fact Check/ load as empty.

    It writes nothing outside its temporary folders.
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
TOOLS = KIT_VAULT / "tools"

bad = []


def check(cond, msg, out=""):
    if not cond:
        bad.append(msg + ("\n----\n" + out + "\n----" if out else ""))


def run(vault, tool, *args):
    env = dict(os.environ, BOOK_VAULT=str(vault))
    r = subprocess.run([sys.executable, str(TOOLS / tool), *args], env=env,
                       capture_output=True, text=True, timeout=300)
    return r.returncode, r.stdout + r.stderr


def fresh(tmp, name):
    v = Path(tmp) / name
    shutil.copytree(SAMPLE, v)
    return v


def section(out, label):
    """The lines under a check-read heading such as 'UNREAD — 2'."""
    lines, on = [], False
    for l in out.splitlines():
        if l.startswith(label + " — "):
            on = True
            continue
        if on and (not l.strip() or not l.startswith(" ")):
            break
        if on:
            lines.append(l)
    return "\n".join(lines)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        v = fresh(tmp, "s")

        # 1 — have.sh
        rc, out = run(v, "have.sh", "Common Sense")
        check(rc == 0 and "HAVE" in out and "PDF/Thomas Paine - Common Sense (1776).txt" in out,
              "have.sh did not find Common Sense on the PDF shelf", out)
        rc, out = run(v, "have.sh", "The Federalist Papers")
        check(rc == 0 and "HAVE" in out and "The Federalist Papers.txt" in out,
              "have.sh did not find The Federalist Papers", out)
        rc, out = run(v, "have.sh", "The Wealth of Nations")
        check(rc == 0 and "NOT BY NAME" in out and "HAVE" not in out,
              "have.sh did not say NOT BY NAME for an absent title", out)
        rc, out = run(v, "have.sh", "Common Sense: Addressed to the Inhabitants of America")
        check("HAVE" in out and "MAIN TITLE ONLY" in out,
              "have.sh did not reach a cited title through its main title", out)

        # 2 — the index, and its self-invalidation
        idx = v / "Fact Check" / "Library Index.json"
        check(idx.exists(), "have.sh wrote no index at [library] index_file")
        if idx.exists():
            files = json.loads(idx.read_text(encoding="utf-8"))["files"]
            check(len(files) == 2 and all(not Path(p).is_absolute() for _, p in files),
                  f"index should hold 2 library-relative paths, holds {files}")
        (v / "library" / "PDF" / "Adam Smith - The Wealth of Nations.txt").write_text(
            "An inquiry.", encoding="utf-8")
        rc, out = run(v, "have.sh", "The Wealth of Nations")
        check("HAVE" in out, "have.sh missed a book added after the index was built", out)
        (v / "library" / "PDF" / "Adam Smith - The Wealth of Nations.txt").unlink()

        # 3 — find-source.sh
        rc, out = run(v, "find-source.sh", "reflection and choice")
        check(rc == 0 and "FOUND." in out and "The Federalist Papers.txt" in out
              and "reflection and choice" in out,
              "find-source.sh did not find 'reflection and choice'", out)

        # 4 — check-read.sh: planted fault 4
        rc, out = run(v, "check-read.sh")
        unread = section(out, "UNREAD")
        check("Common Sense" in unread and "The Federalist Papers" in unread,
              "check-read.sh did not list both cited works as UNREAD", out)
        check("NOT IN LIBRARY —" not in out,
              "check-read.sh called a work in the library NOT IN LIBRARY", out)
        check("NOT ON DRIVE" not in out, "check-read.sh still says NOT ON DRIVE", out)
        rc, _ = run(v, "check-read.sh", "--strict")
        check(rc == 1, f"check-read.sh --strict should exit 1 with unread works, exited {rc}")
        claims = v / "Fact Check" / "Claims" / "Ch 01.jsonl"
        claims.write_text(json.dumps({"title": "Common Sense", "author": "Thomas Paine",
                                      "reader": "Claude", "date_read": "2026-01-01"}) + "\n",
                          encoding="utf-8")
        rc, out = run(v, "check-read.sh", "1", "--all")
        check("Common Sense" in section(out, "READ") and "Common Sense" not in section(out, "UNREAD"),
              "a Claims row naming a reader did not move Common Sense to READ", out)
        claims.unlink()

        # 5 — no library: never NOT IN LIBRARY
        nolib = fresh(tmp, "nolib")
        toml = nolib / "book.toml"
        toml.write_text(toml.read_text(encoding="utf-8").replace(
            'roots = ["library"]', 'roots = ["no-such-folder"]'), encoding="utf-8")
        rc, out = run(nolib, "check-read.sh")
        check("NOT SEARCHED" in out and "NOT IN LIBRARY —" not in out,
              "check-read.sh with no library must say NOT SEARCHED", out)
        rc, out = run(nolib, "have.sh", "Common Sense")
        check(rc == 2 and "NO LIBRARY FOUND" in out and "NOT BY NAME" not in out,
              "have.sh with no library must stop with exit 2", out)

        # 6 — preflight.sh 1
        rc, out = run(v, "preflight.sh", "1")
        check(rc == 0, f"preflight.sh 1 exited {rc}", out)
        check("CITED WORKS" in out and "*Common Sense*" in out
              and "PDF/Thomas Paine - Common Sense (1776).txt" in out and "UNREAD" in out,
              "preflight.sh 1 did not print the chapter's sources", out)
        check("LOCK STATE" in out, "preflight.sh did not print the lock state", out)
        stamp = v / ".preflight" / "ch01.stamp"
        ch1 = next((v / "Chapters").glob("Chapter 01*.md"))
        check(stamp.exists() and stamp.read_text(encoding="utf-8").splitlines()[1]
              == hashlib.sha1(ch1.read_bytes()).hexdigest(),
              "preflight.sh did not write a receipt holding the chapter's SHA-1")

        # 7 — check-drive-path.sh
        claims.write_text(json.dumps({"title": "Common Sense", "author": "Thomas Paine",
                                      "drive_path": "PDF/Thomas Paine - Common Sense (1776).txt"}) + "\n",
                          encoding="utf-8")
        rc, out = run(v, "check-drive-path.sh")
        check(rc == 0 and "1 drive_path value(s) open" in out,
              "check-drive-path.sh failed a relative path that opens", out)
        with claims.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"title": "Common Sense", "drive_path": "PDF/missing.pdf"}) + "\n")
        rc, out = run(v, "check-drive-path.sh")
        check(rc == 1 and "DOES NOT EXIST" in out,
              "check-drive-path.sh passed a path that does not open", out)
        claims.unlink()

        # 8 — show.sh
        rc, out = run(v, "show.sh", "2", "5")
        check(rc == 0 and ">> L5" in out and "[^fed1_test]:" in out and "Ch02/L5" in out,
              "show.sh did not print Ch02/L5 with its footnote", out)

        # 9 — rulings
        for name in ("Banned-Word Rulings.md", "Attribution Rulings.md"):
            check((KIT_VAULT / "Fact Check" / name).exists(), f"template missing: Fact Check/{name}")
            shutil.copy(KIT_VAULT / "Fact Check" / name, v / "Fact Check" / name)
        with (v / "Fact Check" / "Banned-Word Rulings.md").open("a", encoding="utf-8") as fh:
            fh.write("| `0123456789` | Ch01/L5 | carries | keep | 2026-01-01 | test |\n")
        code = ("import sys; sys.path.insert(0, %r); import rulings as R; "
                "print(sorted(R.load(R.BANNED_WORD_RULINGS)), sorted(R.load(R.ATTRIBUTION_RULINGS)))"
                % str(TOOLS))
        r = subprocess.run([sys.executable, "-c", code], env=dict(os.environ, BOOK_VAULT=str(v)),
                           capture_output=True, text=True)
        check(r.stdout.strip() == "['0123456789'] []",
              "rulings.load did not read the fingerprint row (or read a template row)",
              r.stdout + r.stderr)

    if bad:
        print(f"FAIL — {len(bad)} check(s):\n")
        for b in bad:
            print("  - " + b + "\n")
        return 1
    print("library_test: all checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

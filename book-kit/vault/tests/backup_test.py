#!/usr/bin/env python3
"""tests/backup_test.py — the backup sends text to the vault's own remote and stops binaries and strays.

WHAT IT CHECKS, IN A COPY OF THE SAMPLE VAULT WITH A LOCAL BARE REPOSITORY AS `origin`

    1. With no git repository, or no `origin`, the script stops and says how to
       set one up. It never invents a remote.
    2. A first run writes the default .gitignore, commits and pushes. The
       remote then holds the chapters, a Fact Check text file and tools/, and
       holds no PNG, no PDF and nothing from the library.
    3. The default .gitignore the script writes is the one the kit ships in
       vault/.gitignore: two copies of one list drift the moment they exist.
    4. A text file outside the allowlist is reported as NOT BACKED UP.
    5. When the .gitignore is loosened to admit images, a staged PNG still
       stops the backup (the binary guard), nothing is committed and the
       remote is unchanged.
    6. A file renamed into an ignored folder stops the backup (the allowlist
       guard, which asks git with --no-index), and an edit to a file tracked
       before the allowlist does not.
    7. --dry-run commits nothing.

    It writes nothing outside its temporary folder.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KIT_VAULT = Path(__file__).resolve().parent.parent
SAMPLE = KIT_VAULT.parent / "sample"
SCRIPT = KIT_VAULT / "tools" / "backup-to-github.sh"

bad = []


def check(cond, msg, out=""):
    if not cond:
        bad.append(msg + ("\n" + out if out else ""))


def git(cwd, *args):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"setup failed: git {' '.join(args)}\n{r.stdout}{r.stderr}")
    return r.stdout


def backup(vault, *args, answer="y\n"):
    env = dict(os.environ, BOOK_VAULT=str(vault), GIT_TERMINAL_PROMPT="0")
    r = subprocess.run(["bash", str(vault / "tools" / "backup-to-github.sh"), *args],
                       capture_output=True, text=True, env=env, input=answer)
    return r.returncode, r.stdout + r.stderr


def remote_files(remote):
    r = subprocess.run(["git", "--git-dir", str(remote), "ls-tree", "-r", "--name-only", "main"],
                       capture_output=True, text=True)
    return set(r.stdout.splitlines()) if r.returncode == 0 else set()


with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    v = t / "book"
    shutil.copytree(SAMPLE, v)
    shutil.copytree(KIT_VAULT / "tools", v / "tools", ignore=shutil.ignore_patterns("__pycache__"))
    remote = t / "remote.git"
    git(t, "init", "-q", "--bare", "-b", "main", str(remote))

    # 1. no repository, then no origin
    rc, out = backup(v)
    check(rc == 1 and "not a git repository" in out, "no repository: the script did not stop", out)
    git(v, "init", "-q", "-b", "main")
    git(v, "config", "user.email", "test@example.com")
    git(v, "config", "user.name", "Test")
    rc, out = backup(v)
    check(rc == 1 and "no remote called 'origin'" in out, "no origin: the script did not stop", out)
    git(v, "remote", "add", "origin", str(remote))

    # 2. first run
    (v / "Fact Check" / "Notes.md").write_text("A text file the backup holds.\n", encoding="utf-8")
    (v / "Chapters" / "figure.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    (v / "Fact Check" / "scan.pdf").write_bytes(b"%PDF-1.4 fake")
    rc, out = backup(v)
    files = remote_files(remote)
    check(rc == 0 and "Done. Backed up" in out, "the first backup did not push", out)
    check(any(f.startswith("Chapters/Chapter 02") for f in files), "chapter 2 is not on the remote",
          "\n".join(sorted(files)))
    check("Fact Check/Notes.md" in files, "the Fact Check text file is not on the remote")
    check("tools/lock.py" in files and "book.toml" in files, "tools/ or book.toml is not on the remote")
    check(not any(f.endswith((".png", ".pdf")) for f in files), "a PNG or PDF reached the remote",
          "\n".join(sorted(files)))
    check(not any(f.startswith("library/") for f in files), "the library reached the remote")

    # 3. the shipped .gitignore is the script's default
    written = (v / ".gitignore").read_text(encoding="utf-8")
    shipped = (KIT_VAULT / ".gitignore").read_text(encoding="utf-8")
    check(written == shipped, "vault/.gitignore differs from backup-to-github.sh --print-gitignore")

    # 4. a text file outside the allowlist is reported
    (v / "Research").mkdir()
    (v / "Research" / "notes.md").write_text("left out\n", encoding="utf-8")
    rc, out = backup(v, "--dry-run")
    check("NOT BACKED UP" in out and "Research" in out, "a left-out text file was not reported", out)

    # 5. loosened .gitignore: the binary guard still stops a PNG
    before = remote_files(remote)
    head = git(v, "rev-parse", "HEAD")
    (v / ".gitignore").write_text(written.replace("*.png\n", ""), encoding="utf-8")
    rc, out = backup(v)
    check(rc == 1 and "STOPPING — binary or data files are staged" in out
          and "Chapters/figure.png" in out, "a staged PNG did not stop the backup", out)
    check(git(v, "rev-parse", "HEAD") == head, "the refused backup committed")
    check(git(v, "diff", "--cached", "--name-only") == "", "the refused backup left files staged")
    check(remote_files(remote) == before, "the refused backup changed the remote")
    (v / ".gitignore").write_text(written, encoding="utf-8")

    # 6. a rename into an ignored folder stops; an edit to an old tracked file does not
    (v / "old.skill").write_text("v1\n", encoding="utf-8")
    git(v, "add", "-f", "old.skill")
    git(v, "commit", "-qm", "a file tracked before the allowlist")
    (v / "old.skill").write_text("v2\n", encoding="utf-8")
    rc, out = backup(v)
    check(rc == 0 and "STOPPING" not in out, "an edit to a tracked file stopped the backup", out)
    (v / "Old Drafts").mkdir()
    git(v, "mv", "Fact Check/Notes.md", "Old Drafts/Notes.md")
    head = git(v, "rev-parse", "HEAD")
    rc, out = backup(v)
    check(rc == 1 and "outside the allowlist" in out and "Old Drafts/Notes.md" in out,
          "a file renamed into an ignored folder did not stop the backup", out)
    check(git(v, "rev-parse", "HEAD") == head, "the stray backup committed")
    shutil.move(str(v / "Old Drafts" / "Notes.md"), str(v / "Fact Check" / "Notes.md"))

    # 7. --dry-run
    (v / "Chapters" / "Chapter 02 - Reflection and Choice.md").open("a").write("\nA new line.\n")
    head = git(v, "rev-parse", "HEAD")
    rc, out = backup(v, "--dry-run")
    check(rc == 0 and "--dry-run: nothing committed" in out, "--dry-run did not say so", out)
    check(git(v, "rev-parse", "HEAD") == head, "--dry-run committed")

if bad:
    for b in bad:
        print("  FAIL: " + b)
    raise SystemExit(f"backup: {len(bad)} failure(s)")
print("  backup: text reaches the vault's own remote; PNGs, PDFs, the library and strays do not.")

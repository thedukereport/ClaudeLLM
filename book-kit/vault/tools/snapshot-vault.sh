#!/usr/bin/env python3
"""snapshot-vault.sh — copy the whole vault to another disk, then verify the copy.

    tools/snapshot-vault.sh                 # snapshot to [output] snapshot_dir in book.toml
    tools/snapshot-vault.sh /some/path      # snapshot to a folder you name
    tools/snapshot-vault.sh --list          # show existing snapshots and their sizes

WHY THIS EXISTS

    In the system this kit comes from, a vault was once copied by hand before
    a restructuring. That copy was one-off. A backup that depends on somebody
    remembering to make it is not a backup, so this does the same job on
    demand, the same way each time.

WHAT IT COVERS THAT GIT DOES NOT

    GitHub (tools/backup-to-github.sh) holds the text: the manuscript and the
    apparatus. It leaves out the PDFs, images and any library or research
    folders kept inside the vault, because git would store them version by
    version and never release them. Until this script runs, those live in one
    place. Point `snapshot_dir` at a different disk from the vault's.

WHAT IT SKIPS

    .git (GitHub already holds it, and copying it doubles the size),
    __pycache__, .DS_Store, Icon files, ._ files and .fuse_hidden artifacts.

HOW IT VERIFIES

    After the copy it walks the vault again with the SAME exclusion list and
    compares each file's SHA-256 with the copy's. Any file missing or different
    is named, and the snapshot is reported unusable. One list serves the copy
    and the check, so the two cannot disagree: the first version of the
    original compared a hand-written `find` command against `rsync`, the two
    lists drifted over 31 .fuse_hidden files, and a correct snapshot reported
    itself broken. Anything that has to agree with itself gets written once.

    A backup nobody has read from is a guess, so the script also reads the
    first chapter back out of the snapshot and prints its first line.

    Standard library only (the original needed rsync, which not every machine
    has).

EXIT CODES
    0  snapshot made and verified (or --list)
    1  no destination set, not enough room, or the copy did not verify
"""
import fnmatch
import hashlib
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

# One list, used by the copy and by the verify.
EXCLUDE_DIRS = (".git", "__pycache__")
EXCLUDE_FILES = (".DS_Store", "._*", "Icon?", "Icon\r", ".fuse_hidden*")


def skipped(name: str, is_dir: bool) -> bool:
    pats = EXCLUDE_DIRS if is_dir else EXCLUDE_FILES
    return any(fnmatch.fnmatchcase(name, p) for p in pats)


def walk(root: Path):
    """Every file under root that the snapshot holds, as relative paths."""
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if not skipped(x, True))
        for f in sorted(files):
            if not skipped(f, False):
                yield (Path(d) / f).relative_to(root)


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def size(root: Path) -> int:
    return sum((root / r).stat().st_size for r in walk(root) if (root / r).is_file())


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def ignore(dirpath, names):
    return [n for n in names if skipped(n, os.path.isdir(os.path.join(dirpath, n)))]


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    base = Path(argv[0]).expanduser() if argv and argv[0] != "--list" else B.SNAPSHOT_DEST
    if base is None:
        print("No snapshot destination. Set it in book.toml:\n\n"
              "    [output]\n    snapshot_dir = \"/path/on/another/disk/Vault Snapshots\"\n\n"
              "or name a folder: tools/snapshot-vault.sh /path/to/folder")
        return 1
    base = base.resolve()
    vault = B.VAULT

    if argv and argv[0] == "--list":
        if not base.is_dir():
            print(f"No snapshots yet in {base}.")
            return 0
        print(base)
        for s in sorted(base.iterdir()):
            if s.is_dir():
                print(f"  {human(size(s)):>9}  {s.name}")
        return 0

    if base == vault or vault in base.parents:
        print(f"STOPPING — the destination {base} is inside the vault. "
              f"A snapshot inside what it copies copies itself.")
        return 1

    dest = base / f"vault_{datetime.now():%Y-%m-%d_%H%M%S}"
    print(f"Vault:       {vault}")
    print(f"Snapshot to: {dest}\n")

    need = size(vault)
    base.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(base).free
    if free < need:
        print(f"STOPPING — not enough room.\n  need {human(need)}, free {human(free)}")
        return 1
    print(f"Space: need {human(need)}, free {human(free)} — proceeding.\n")

    shutil.copytree(vault, dest, ignore=ignore, symlinks=True)

    print("Verifying — comparing every file's SHA-256 with the original:")
    bad = []
    count = 0
    for rel in walk(vault):
        src, dst = vault / rel, dest / rel
        if src.is_symlink():
            if not dst.is_symlink() or os.readlink(src) != os.readlink(dst):
                bad.append(f"link   {rel}")
            count += 1
            continue
        if not src.is_file():
            continue
        count += 1
        if not dst.is_file():
            bad.append(f"missing {rel}")
        elif sha(src) != sha(dst):
            bad.append(f"differs {rel}")
    if bad:
        print("\nMISMATCH — these files did not copy. NOT a usable restore point.")
        for b in bad[:40]:
            print(f"  {b}")
        if len(bad) > 40:
            print(f"  … and {len(bad) - 40} more")
        print("\nRun the script again. If the same files fail twice, the disk is the problem.")
        return 1
    print(f"  every file arrived and matches: {count} file(s).")

    # Read one file back out. Presence is not readability.
    chapters = B.chapter_files()
    if chapters:
        probe = dest / chapters[0].relative_to(vault)
        with open(probe, encoding="utf-8", errors="replace") as fh:
            first = fh.readline().rstrip("\n")
        print(f"\nRead-back test — first line of {probe.name} in the snapshot:\n  {first}")

    # Record where git stood, so the snapshot and the repository can be lined up later.
    try:
        head = subprocess.run(["git", "-C", str(vault), "log", "--oneline", "-5"],
                              capture_output=True, text=True, timeout=30)
        if head.returncode == 0 and head.stdout.strip():
            (dest / "_git-HEAD.txt").write_text(head.stdout, encoding="utf-8")
    except (OSError, subprocess.TimeoutExpired):
        pass

    print(f"\nSnapshot complete: {dest}\n  {human(size(dest))}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

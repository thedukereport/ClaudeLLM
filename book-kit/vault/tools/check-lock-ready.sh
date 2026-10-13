#!/usr/bin/env python3
"""check-lock-ready.sh — say whether a chapter may be locked, and what blocks it.

    tools/check-lock-ready.sh 02        # one chapter
    tools/check-lock-ready.sh 02 03     # several
    tools/check-lock-ready.sh           # every chapter Locks.md marks 🔒 (re-checks them)

WHY THIS EXISTS

    In the system this kit comes from, Claude once declared a chapter
    lock-ready on the strength of "zero open items", meaning zero on a file
    Claude itself wrote and curated. The Punch List, the real open-items
    register, was never queried; it held open items for that chapter. The lock
    was then "verified" by searching for the lock stamps Claude had just
    written, which confirms only that the intended text was typed.

    The general failure: building the check out of one's own model of the
    system instead of out of the system. A resolution to be careful does not
    fix that. This script reads the files the rules name and runs the checks
    the rules name, and reports what they say.

    The author's rule: "If it is open it is blocking." There is no minor open
    item and no deferred open item.

A CHAPTER IS LOCK-READY WHEN, AND ONLY WHEN

    1. no open Punch List line (`- [ ]`) names it (ChNN, Ch. N, Chapter N);
    2. no card for it on the review page snapshot is still open
       (status yours, submitted or approved);
    3. `check-read.sh NN --strict` passes: the chapter cites no work nobody
       opened. The author: "It's against the rules for you to cite anything
       that you have not read." In the original system that rule was measured
       for a week and wired to nothing, so a citation for a book nobody had
       could be written, reviewed, ruled on and locked;
    4. `check-banned-words.sh`, `check-epistemics.sh` and
       `check-footnote-length.sh` report nothing for the chapter. A hit is a
       coordinate, never a verdict: rule on it (each check keeps a rulings
       file) and it stops being reported;
    5. `check-crossrefs.sh` flags no cross-reference written in the chapter or
       pointing at it. The sweep reads the whole manuscript, because editing
       one chapter can falsify a "see Chapter N" pointer in a file nobody is
       touching: in the original system a moved passage left pointers in two
       appendices wrong for four weeks;
    6. if `check-footnotes.sh` is installed, it reports no orphaned footnote
       paragraph (A ORPHAN: a continuation paragraph at column zero prints as
       body text) and no anchor without a definition or definition without an
       anchor (G NO-DEF / G NO-ANCHOR), or one slug defined twice (G DUP-DEF). Both kinds ship in the PDF;
    7. a preflight receipt exists for it (`.preflight/chNN.stamp`, written by
       `preflight.sh NN`), and the chapter has not changed since. A chapter is
       not locked unless its sources were printed in front of whoever finished
       it: in the original system a section was redrafted eight times by
       someone who had read a summary of the notes file and never the file.

A CHECK THAT CRASHES IS A FAILURE, NEVER A PASS

    The original gate piped the read check through `tail` and tested the exit
    status of `tail`, so the chapter passed when the read check crashed. Here
    each sub-check's exit code is read directly, its summary line must be
    present, and a missing script is a failure: a rule nothing enforces is a
    rule in name only.

EXIT CODES
    0  every requested chapter is lock-ready
    1  at least one is not; do not lock
    2  the settings or the chapter could not be loaded
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import bookconfig as B  # noqa: E402
except SystemExit as e:
    print(f"ERROR: {e}")
    sys.exit(2)

TOOLS = Path(__file__).resolve().parent
OPEN_CARD = ("yours", "submitted", "approved")
TIMEOUT = 300


def names_chapter(line: str, n: int) -> bool:
    return bool(re.search(rf"\bCh(?:apter)?\.?\s?0*{n}(?!\d)", line))


def punch_list(n):
    if not B.PUNCH_LIST.exists():
        return []
    out = []
    for i, line in enumerate(B.PUNCH_LIST.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip().startswith("- [ ]") and names_chapter(line, n):
            text = re.sub(r"\s+", " ", line).strip()[:160]
            out.append(f"{B.PUNCH_LIST.name} L{i}: {text}")
    return out


def card_chapter(card: dict):
    for k in ("chapter", "where"):
        m = re.search(r"Ch(?:apter)?\.?\s*0*(\d+)", str(card.get(k) or ""))
        if m:
            return int(m.group(1))
    return None


def open_cards(n):
    """(problems, notes). Open cards on the page snapshot for chapter n."""
    d = B.SNAPSHOT / "proposals"
    if not d.is_dir():
        if B.PAGE_URL:
            return [f"no page snapshot at {d.relative_to(B.VAULT)}; the open cards cannot be "
                    f"seen, so this condition has not been checked"], []
        return [], ["no review page set in book.toml and no page snapshot; no cards to check"]
    out = []
    for f in sorted(d.glob("*.json")):
        try:
            card = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            out.append(f"card {f.name} could not be read ({e}); an unreadable card is not a closed one")
            continue
        if card_chapter(card) == n and str(card.get("status", "")).lower() in OPEN_CARD:
            out.append(f"card {f.stem} [{card.get('status')}] {card.get('where', '')} "
                       f"{str(card.get('title', ''))[:90]}")
    notes = []
    taken = d.parent / "TAKEN"
    if taken.exists():
        notes.append(f"page snapshot taken {taken.read_text(encoding='utf-8').strip()}")
    return out, notes


def run(script, *args):
    """(returncode, stdout+stderr), or (None, why) when the script is absent."""
    p = TOOLS / script
    if not p.exists():
        return None, f"tools/{script} is missing; this condition is not being enforced"
    first = p.read_text(encoding="utf-8", errors="replace").split("\n", 1)[0]
    cmd = ([sys.executable, str(p)] if "python" in first else ["bash", str(p)]) + list(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT, cwd=B.VAULT)
    except subprocess.TimeoutExpired:
        return -1, f"tools/{script} did not finish in {TIMEOUT}s"
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def crashed(script, rc, out):
    tail = "\n".join("      " + l for l in out.strip().splitlines()[-8:])
    return [f"{script} did not run to the end (exit {rc}); a crashed check is a failure:\n{tail}"]


def check_read(n):
    rc, out = run("check-read.sh", f"{n:02d}", "--strict")
    if rc is None:
        return [out]
    if "cited works" not in out:
        return crashed("check-read.sh", rc, out)
    if rc != 0:
        rows = [l.rstrip() for l in out.splitlines()
                if re.match(r"^[A-Z][A-Z ]+ — \d+\s*$", l) or re.match(r"^\s+\d+x\s", l)]
        return ["check-read.sh: the chapter cites a work nobody has opened:"] + \
               ["    " + r.strip() for r in rows]
    return []


def check_counts(script, n, label):
    """banned words and epistemics: `--counts NN` prints `ChNN  <count>`."""
    rc, out = run(script, "--counts", f"{n:02d}")
    if rc is None:
        return [out]
    m = re.search(rf"^\s*{label}\s+(\d+)\s*$", out, re.M)
    if rc != 0 or not m:
        return crashed(script, rc, out)
    k = int(m.group(1))
    if k:
        return [f"{script}: {k} unruled hit(s) in {label}; see them with tools/{script} {n:02d}"]
    return []


def check_footnote_length(n, label):
    rc, out = run("check-footnote-length.sh", f"{n:02d}")
    if rc is None:
        return [out]
    if rc != 0 or "unruled note(s)" not in out:
        return crashed("check-footnote-length.sh", rc, out)
    hits = [l.strip() for l in out.splitlines() if re.match(rf"\s+{label}/L\d+", l)]
    if hits:
        return [f"check-footnote-length.sh: {len(hits)} note(s) over the cap, not yet ruled:"] + \
               ["    " + h for h in hits]
    return []


def check_crossrefs(n, chapter):
    rc, out = run("check-crossrefs.sh")
    if rc is None:
        return [out]
    if rc not in (0, 1) or "pairs checked" not in out:
        return crashed("check-crossrefs.sh", rc, out)
    lines = out.splitlines()
    hits = []
    for i, l in enumerate(lines):
        m = re.match(r"^FLAG (.+?):(\d+) → Chapter (\d+)", l)
        if not m:
            continue
        if m.group(1) == chapter.name or int(m.group(3)) == n:
            block = [l.strip()]
            for extra in lines[i + 1:i + 3]:
                if extra.startswith(" "):
                    block.append(extra.strip())
            hits.append("  ".join(block))
    if hits:
        return [f"check-crossrefs.sh: {len(hits)} cross-reference(s) to read, in or pointing at "
                f"this chapter:"] + ["    " + h for h in hits]
    return []


def check_footnote_structure(n):
    """Optional: only when check-footnotes.sh is installed. A crash still fails."""
    if not (TOOLS / "check-footnotes.sh").exists():
        return [], ["check-footnotes.sh not installed; footnote structure (orphans, anchors) "
                    "not checked"]
    rc, out = run("check-footnotes.sh", f"{n:02d}")
    if rc is None:
        return [out], []
    chapter = B.chapter_file(n)
    if rc != 0 or chapter is None or chapter.name not in out:
        return crashed("check-footnotes.sh", rc, out), []
    hits = [l.strip() for l in out.splitlines()
            if "A ORPHAN" in l or "G NO-DEF" in l or "G NO-ANCHOR" in l or "G DUP-DEF" in l]
    if hits:
        return ([f"check-footnotes.sh: {len(hits)} structural footnote fault(s); these render "
                 f"wrong in the PDF:"] + ["    " + h[:150] for h in hits[:12]]
                + ([f"    … and {len(hits) - 12} more"] if len(hits) > 12 else [])), []
    return [], []


def preflight(n, chapter):
    stamp = B.VAULT / ".preflight" / f"ch{n:02d}.stamp"
    if not stamp.exists():
        return [f"no preflight receipt: run tools/preflight.sh {n:02d} and read the output"]
    lines = stamp.read_text(encoding="utf-8").splitlines()
    recorded = lines[1].strip() if len(lines) > 1 else ""
    current = hashlib.sha1(chapter.read_bytes()).hexdigest()
    if recorded != current:
        return [f"preflight receipt is stale: the chapter changed since it ran; "
                f"re-run tools/preflight.sh {n:02d}"]
    return []


def lock_rows():
    if not B.LOCKS.exists():
        return {}
    out = {}
    for line in B.LOCKS.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|\s*(🔒|🔓)\s*\|([^|]*)\|", line)
        if m:
            out[int(m.group(1))] = (m.group(2), m.group(3).strip())
    return out


def check(n):
    """Print chapter n's result; return True when it is lock-ready."""
    label = f"Ch{n:02d}"
    chapter = B.chapter_file(n)
    state = lock_rows().get(n)
    head = f"{label}" + (f"  (Locks.md: {state[0]} {state[1]})" if state else "")
    if n in B.OUT_OF_WORKFLOW:
        print(f"\n{head}   [FAIL]\n  out of workflow (book.toml): no tool checks or locks it "
              f"until the author takes it off that list.")
        return False
    if chapter is None:
        print(f"\n{head}   [FAIL]\n  no chapter file for {label} in {B.CHAPTERS}")
        return False

    blocks, notes = [], []
    pl = punch_list(n)
    if pl:
        blocks.append((f"{len(pl)} open Punch List item(s). The author's rule: if it is open "
                       f"it is blocking. Close each one, or record the decision that closes it:",
                       pl))
    cards, cnotes = open_cards(n)
    notes += cnotes
    if cards:
        blocks.append((f"{len(cards)} open card(s) on the review page:", cards))
    for name, res in (("the read rule", check_read(n)),
                      ("banned words", check_counts("check-banned-words.sh", n, label)),
                      ("epistemics", check_counts("check-epistemics.sh", n, label)),
                      ("footnote length", check_footnote_length(n, label)),
                      ("cross-references", check_crossrefs(n, chapter))):
        if res:
            blocks.append((f"{name}:", res))
    fs, fnotes = check_footnote_structure(n)
    notes += fnotes
    if fs:
        blocks.append(("footnote structure:", fs))
    pf = preflight(n, chapter)
    if pf:
        blocks.append(("preflight:", pf))

    print(f"\n{head}   [{'FAIL' if blocks else 'PASS'}]   {chapter.name}")
    for title, items in blocks:
        print(f"  BLOCKS — {title}")
        for it in items:
            print("    " + it.replace("\n", "\n    "))
    for note in notes:
        print(f"  note: {note}")
    return not blocks


def main():
    argv = sys.argv[1:]
    bad_args = [a for a in argv if not a.isdigit()]
    if bad_args:
        print(f"usage: check-lock-ready.sh [NN ...]   (not understood: {' '.join(bad_args)})")
        return 2
    wanted = [int(a) for a in argv]
    if not wanted:
        wanted = sorted(n for n, (s, _) in lock_rows().items() if s == "🔒")
        if not wanted:
            print("No chapter is marked 🔒 in Locks.md. Name a chapter: check-lock-ready.sh NN")
            return 0
    bad = sum(0 if check(n) else 1 for n in wanted)
    print()
    if bad == 0:
        print(f"All {len(wanted)} chapter(s) lock-ready.")
        return 0
    print(f"{bad} of {len(wanted)} chapter(s) NOT lock-ready. Do not lock.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

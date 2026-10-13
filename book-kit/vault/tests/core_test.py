#!/usr/bin/env python3
"""core_test.py — checks the event log, block ids, blockedit and the chapter-write guards.

    python3 vault/tests/core_test.py

Runs on a COPY of the sample vault in a temp folder (BOOK_VAULT points there),
so it writes nothing outside that folder. It proves:

  1. Appended events form an unbroken hash chain, and an edited line breaks it.
  2. blockid.py stamps an id on every prose line when the copy has none.
  3. blockedit.replace rewrites one block, the id survives, a foreign id in
     the incoming text is discarded, and an edit.applied event is logged.
  4. A stale proposal (expect_hash) and a dropped footnote marker are refused.
  5. A direct write to a chapter is refused, even by a tool spelling a door's
     name, and a write that loses a block id is refused.
  6. insert_after and remove keep every line addressed, and witness.py finds
     no unexplained change after logged writes but finds one after a raw write.
  7. A retracted event leaves fold() and stays in the log.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]          # book-kit/
SAMPLE = KIT / "sample"
TOOLS = KIT / "vault" / "tools"
IDRE = re.compile(r"<!--\s*b:([a-z0-9]{6})\s*-->")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="core_test_"))
    vault = tmp / "sample"
    shutil.copytree(SAMPLE, vault)
    os.environ["BOOK_VAULT"] = str(vault)
    env = dict(os.environ)
    try:
        run(vault, env)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("core_test: all checks passed")


def run(vault, env):
    # 2 — ids. The copy may already hold them (the sample ships with ids); if
    #     not, blockid.py must stamp them, and its proofs must pass.
    if not any(IDRE.search(p.read_text(encoding="utf-8"))
               for p in (vault / "Chapters").glob("*.md")):
        r = subprocess.run([sys.executable, str(TOOLS / "blockid.py"), "--write"],
                           env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr

    sys.path.insert(0, str(TOOLS))
    import bookconfig as B
    import vaultlog
    import blocks
    import blockid
    import blockedit
    import witness

    assert B.VAULT == vault.resolve(), (B.VAULT, vault)
    for f in B.chapter_files():
        for line in f.read_text(encoding="utf-8").splitlines():
            if blockid.is_block(line):
                assert IDRE.search(line), f"unaddressed line in {f.name}: {line!r}"

    # A seal before any write, so witness can be asked about every write below.
    subprocess.run([sys.executable, str(TOOLS / "witness.py"), "--seal"],
                   env=env, capture_output=True, text=True, check=True)

    # 1 — the chain.
    n0 = len(vaultlog.read_all())
    a = vaultlog.append("note.recorded", actor="core_test", text="first")
    b = vaultlog.append("decision.recorded", actor=B.AUTHOR_ACTOR, item="t1", text="second")
    assert b["prev"] == a["hash"], "the second event does not name the first"
    assert len(vaultlog.read_all()) == n0 + 2
    ok, problems = vaultlog.verify_chain()
    assert ok, problems
    try:
        vaultlog.append("not.a.kind", text="typo")
        raise AssertionError("an unknown event kind was written")
    except ValueError:
        pass

    # 3 — replace through blockedit.
    idx = blocks.index(rebuild=True)
    ch1 = B.chapter_file(1)
    target = next(bl for bl in idx.values()
                  if bl.chapter == "Ch01" and "[^paine_wants]" in bl.text
                  and not bl.text.startswith("[^"))
    other = next(k for k in idx if k != target.id)
    new = (f'He gave each word its own origin, in one line: "Society is produced by our '
           f'wants, and government by our wickedness."[^paine_wants]<!-- b:{other} -->')
    rec = blockedit.replace(target.id, new, why="core_test replace",
                            expect_hash=target.hash)
    line = ch1.read_text(encoding="utf-8").split("\n")[target.line - 1]
    assert IDRE.findall(line) == [target.id], f"id did not survive: {line!r}"
    assert other not in line, "a foreign id in the incoming text reached the chapter"
    assert line.startswith("He gave each word its own origin, in one line:"), line
    assert rec["kind"] == "edit.applied" and rec["block_id"] == target.id
    assert any(e["hash"] == rec["hash"] for e in vaultlog.fold("edit.applied"))
    assert any(e.get("tool") == "blockedit.replace" for e in vaultlog.fold("file.written"))
    assert blocks.check(target.id, target.hash) == "DRIFTED"
    assert blocks.where_is("b:" + target.id) == f"Ch01/L{target.line}"

    # 4 — stale proposal, and a dropped footnote marker.
    for bad, kw in ((new, {"expect_hash": "0" * 16}),
                    ("He gave each word its own origin.", {})):
        try:
            blockedit.replace(target.id, bad, why="must refuse", **kw)
            raise AssertionError(f"refusal did not fire for {kw or 'dropped marker'}")
        except blockedit.Refused:
            pass

    # 5 — the guards.
    text = ch1.read_text(encoding="utf-8")
    for tool in ("some-tool.py", "claude", "blockedit.replace", "blockid.py"):
        try:
            vaultlog.write_file(ch1, text + "\nscratch\n", tool=tool)
            raise AssertionError(f"{tool} wrote a chapter directly")
        except PermissionError:
            pass
    assert ch1.read_text(encoding="utf-8") == text, "a refused write changed the chapter"
    vaultlog.IN_BLOCKEDIT.append("test")
    try:
        try:
            vaultlog.write_file(ch1, IDRE.sub("", text), tool="blockedit.replace")
            raise AssertionError("a write that drops every block id went through")
        except ValueError:
            pass
    finally:
        vaultlog.IN_BLOCKEDIT.pop()
    assert ch1.read_text(encoding="utf-8") == text
    probe = B.FACT / "core-test-probe.md"         # files outside the chapters write freely
    assert vaultlog.write_file(probe, "probe\n", tool="core_test")["kind"] == "file.written"

    # 6 — insert, remove, witness.
    ins = blockedit.insert_after(target.id, "A paragraph added by the test.", why="core_test insert")
    new_id = ins["block_id"]
    assert blocks.resolve(new_id) is not None, "the inserted paragraph has no id"
    gone = blockedit.remove(new_id, why="core_test remove")
    assert new_id in gone and blocks.resolve(new_id) is None
    w = subprocess.run([sys.executable, str(TOOLS / "witness.py"), "--json"],
                       env=env, capture_output=True, text=True)
    assert w.returncode == 0, "witness flagged a logged write:\n" + w.stdout
    ch2 = B.chapter_file(2)
    ch2.write_text(ch2.read_text(encoding="utf-8") + "\nraw\n", encoding="utf-8")
    w = subprocess.run([sys.executable, str(TOOLS / "witness.py"), "--json"],
                       env=env, capture_output=True, text=True)
    found = [json.loads(l)["where"] for l in w.stdout.splitlines() if l.strip()]
    assert w.returncode == 1 and any(ch2.name in p for p in found), w.stdout

    # 7 — retraction.
    vaultlog.retract(a, why="core_test retraction", actor="core_test")
    assert a["hash"] in vaultlog.retracted_hashes()
    assert all(e["hash"] != a["hash"] for e in vaultlog.fold("note.recorded"))
    assert any(e["hash"] == a["hash"]
               for e in vaultlog.fold("note.recorded", include_retracted=True))
    ok, problems = vaultlog.verify_chain()
    assert ok, problems


if __name__ == "__main__":
    main()

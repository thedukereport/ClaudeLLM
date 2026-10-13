#!/usr/bin/env python3
"""blockedit.py — the only way a chapter line is rewritten; it owns the block id.

    import blockedit
    blockedit.replace(block_id, new_text, why="...", expect_hash=None)
    blockedit.insert_after(block_id, new_text, why="...")
    blockedit.remove(block_id, why="...")

    python3 tools/blockedit.py k7f3a2      # where a block is and what it holds

WHY THIS EXISTS

    The author: "DO NOT CREATE AN INTERFACE THAT ALLOWS ME TO MESS UP THE BLOCK
    IDS. THAT IS A BAD DESIGN."

    In the original system it had already happened twice that hour. The author
    ruled "use my words", typed the text into a textarea, and the text went
    into the chapter exactly as typed — with no `<!-- b:... -->` comment,
    because a textarea cannot hold one and nothing re-attached it. Two lines
    went invisible to the block index.

THE RULE THIS FILE ENFORCES

    The id is not content. It is not the author's to type, Claude's to paste,
    or a form's to hold. It belongs to the line, it is read from the line
    being replaced, and it is written back by this module and no other.

      * Any id found in INCOMING text is stripped and discarded. A proposal
        that quotes a block, or a whole line pasted into a textarea, cannot
        move, duplicate or invent an id.
      * The id on the line being replaced is reattached, always, once, at the
        end.
      * A line that has no id is refused, not guessed at.
      * `expect_hash` refuses the write when the line has changed since the
        proposal was written, so a stale proposal reports drift instead of
        overwriting newer words.

    `vaultlog.write_file` refuses any chapter write that does not come through
    here (or through blockid.py), and any write that loses a block id.

PUBLIC FUNCTIONS

    replace(block_id, new_text, why, expect_hash=None, actor="claude",
            element=None, sheet="", item="") -> dict
    insert_after(block_id, new_text, why, actor="claude", element=None,
                 sheet="", item="") -> dict
    remove(block_id, why, actor="claude", element=None) -> str (the removed line)
    strip_ids(text) -> str
    Refused, ALLOW_ORPHAN, IDRE, MARKERRE

    `sheet` and `item` name the card an edit served, when it served one.
    Pass actor=bookconfig.AUTHOR_ACTOR when the words are the author's ruling.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import blocks     # noqa: E402  — IDRE, content_hash, index
import vaultlog   # noqa: E402

IDRE = blocks.IDRE

# A footnote marker in running text: [^slug] not followed by a colon (a colon
# makes it the definition, not a reference to one).
MARKERRE = re.compile(r"\[\^([^\]\s]+)\](?!:)")

# Slugs a replace may orphan on purpose — the note goes next, or the author
# ruled the note out. Name one here and say why; an empty set is the default.
ALLOW_ORPHAN: set = set()


class Refused(Exception):
    """The write did not happen, and the reason is in the message."""


def strip_ids(text: str) -> str:
    """Remove every block-id comment from text that is about to go INTO a chapter."""
    return IDRE.sub("", text).rstrip()


def _line_of(b, block_id):
    """The chapter's lines and the index of the block's line, or Refused."""
    lines = b.file.read_text(encoding="utf-8").split("\n")
    i = b.line - 1
    found = IDRE.search(lines[i]) if i < len(lines) else None
    if not found or found.group(1) != block_id:
        raise Refused(f"{b.file.name} line {b.line} does not hold {block_id} any more. "
                      f"The index is stale; nothing written.")
    return lines, i


def _write(path, text, tool, why, block_id):
    """The door: vaultlog refuses a chapter write unless this flag is raised,
    and only this module raises it. Spelling the tool name right is not enough
    to get in — the caller has to be here."""
    vaultlog.IN_BLOCKEDIT.append(block_id)
    try:
        vaultlog.write_file(path, text, tool=tool, backup=True, why=why)
    finally:
        vaultlog.IN_BLOCKEDIT.pop()


def replace(block_id: str, new_text: str, why: str, expect_hash: str = None,
            actor: str = "claude", element: str = None, sheet: str = "", item: str = "") -> dict:
    """Rewrite one block. Returns the record written to the log.

    Raises `Refused` and writes nothing when the block is missing, when the
    line holds no id, when `expect_hash` does not match what the line says
    now, or when the new text drops a footnote marker whose note the chapter
    still defines.
    """
    block_id = blocks._bare(block_id)
    b = blocks.index(rebuild=True).get(block_id)
    if b is None:
        raise Refused(f"no block {block_id!r} in any chapter. An id names one block or "
                      f"it names nothing.")
    if expect_hash and b.hash != expect_hash:
        raise Refused(f"{block_id} has changed since this was written — "
                      f"{b.coord} now hashes {b.hash}, the proposal expected "
                      f"{expect_hash}. Nothing written; re-read the line.")
    clean = strip_ids(new_text).strip()
    if not clean:
        raise Refused("the replacement text is empty after stripping block ids.")
    if IDRE.search(clean):
        raise Refused("internal: an id survived stripping.")

    lines, i = _line_of(b, block_id)
    old_line = lines[i]
    lines[i] = clean + f"<!-- b:{block_id} -->"

    # A REPLACE THAT DROPS A FOOTNOTE MARKER ORPHANS THE NOTE.
    #
    # In the original system three notes were left at the foot of their
    # chapters with nothing pointing at them, because a replacement paragraph
    # was written over the block that held the marker, and nothing noticed for
    # a day. Refuse the write instead of leaving the chapter to be swept later.
    dropped = sorted(set(MARKERRE.findall(old_line)) - set(MARKERRE.findall(lines[i])))
    if dropped and not ALLOW_ORPHAN.intersection(dropped):
        body = "\n".join(lines)
        still_defined = [s for s in dropped
                         if re.search(rf"(?m)^\[\^{re.escape(s)}\]:", body)]
        if still_defined:
            raise Refused(
                "this replacement drops the footnote marker(s) "
                + ", ".join(f"[^{s}]" for s in still_defined)
                + f" from {b.coord}, and {b.file.name} still defines them. "
                  "The note would be left at the foot of the chapter with nothing "
                  "pointing at it. Put the marker in the new text, delete the "
                  "note first, or name the slug in blockedit.ALLOW_ORPHAN.")

    _write(b.file, "\n".join(lines), "blockedit.replace", why, block_id)
    # WHICH CARD THIS SERVED, WHEN IT SERVED ONE. An edit that serves no card
    # passes nothing, and a reader says so in words instead of printing None.
    rec = vaultlog.append("edit.applied", actor=actor, file=b.file.name,
                          block_id=block_id, coord=b.coord, element=element,
                          sheet=sheet, item=item,
                          old=old_line, new=lines[i], why=why)
    blocks.index(rebuild=True)
    return rec


def insert_after(block_id: str, new_text: str, why: str, actor: str = "claude",
                 element: str = None, sheet: str = "", item: str = "") -> dict:
    """Put a NEW paragraph into a chapter after the block named, and log it.

    WHY THIS EXISTS

        When replace() was the only way in, a ruling to "add a paragraph after
        X" was applied by calling replace() on X — which would have overwritten
        X. It was caught only because the new text lacked the footnote markers
        X held. A paragraph to be added gets its own door.

    The new paragraph is given a fresh block id here, before the write, minted
    against every id already in the book. A paragraph without an id is
    invisible to the block index, and blocks.index reads ids; it does not mint
    them. Any id in the incoming text is stripped, as in replace().
    """
    import blockid
    block_id = blocks._bare(block_id)
    b = blocks.index(rebuild=True).get(block_id)
    if b is None:
        raise Refused(f"no block {block_id!r} in the chapters")
    clean = strip_ids(new_text).strip()
    if not clean:
        raise Refused("the new paragraph is empty after stripping block ids.")
    lines, i = _line_of(b, block_id)
    j = i + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    taken = blockid.existing_ids() | set(IDRE.findall("\n".join(lines)))
    new_id = blockid.new_id(taken)
    line = f"{clean}<!-- b:{new_id} -->"
    lines[j:j] = [line, ""]
    _write(b.file, "\n".join(lines), "blockedit.replace", why, block_id)
    rec = vaultlog.append("edit.applied", actor=actor, file=b.file.name,
                          block_id=new_id, after_block_id=block_id, coord=b.coord,
                          element=element, sheet=sheet, item=item,
                          old="", new=line, why=why, inserted_after=True)
    blocks.index(rebuild=True)
    return rec


def remove(block_id: str, why: str, actor: str = "claude", element: str = None) -> str:
    """Delete the line holding this block id, and record what left the book.

    THE ONLY SANCTIONED WAY A BLOCK LEAVES A CHAPTER. `vaultlog` refuses any
    write that drops an id, because it cannot tell a deletion from a line that
    fell out of a careless replace. This names the id first, so the guard can
    tell them apart, and it logs the whole removed line so anyone can put it
    back. A backup is written too, because this is the one call whose purpose
    is deletion.
    """
    block_id = blocks._bare(block_id)
    b = blocks.index(rebuild=True).get(block_id)
    if b is None:
        raise Refused(f"no block {block_id!r} in the chapters")
    f = b.file
    lines, i = _line_of(b, block_id)
    gone = lines[i]
    end = i + 1
    while end < len(lines) and not lines[end].strip():
        end += 1
    del lines[i:end]
    vaultlog.ALLOW_DROP.add(block_id)
    try:
        _write(f, "\n".join(lines), "blockedit.remove", why, block_id)
    finally:
        vaultlog.ALLOW_DROP.discard(block_id)
    vaultlog.record_edit(path=f, old=gone, new="", block=block_id, coord=b.coord,
                         role="body", tool="blockedit.remove", why=why)
    blocks.index(rebuild=True)
    return gone


def main():
    """`python3 tools/blockedit.py <block_id>` — where a block is and what it holds."""
    if len(sys.argv) < 2:
        print(__doc__)
        return
    bid = blocks._bare(sys.argv[1])
    b = blocks.index().get(bid)
    if not b:
        print(f"\n  no block {bid!r}.\n")
        sys.exit(1)
    print(f"\n  {bid}  {b.coord}  {b.file.name}\n  hash {b.hash}\n\n  {b.text}\n")


if __name__ == "__main__":
    main()

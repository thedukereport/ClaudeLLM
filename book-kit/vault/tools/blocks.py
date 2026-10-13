#!/usr/bin/env python3
"""blocks.py — finds where a block of chapter text is now, by its block id.

    from blocks import resolve, index, where_is, check, find_by_text

    resolve("k7f3a2")        -> Block(id, chapter, line, text, hash, file)
    where_is("k7f3a2")       -> "Ch05/L112"     computed now, never stored
    check("k7f3a2", h)       -> "UNCHANGED" | "DRIFTED" | "MISSING"
    find_by_text("…")        -> [Block, …]      for re-anchoring old references

    python3 tools/blocks.py              # count blocks per chapter
    python3 tools/blocks.py k7f3a2       # where one block is, and what it holds

WHY A BLOCK ID REPLACES Ch##/L## AS AN ADDRESS

    The author: "using Chapter/Line is wholy contingent in the number of lines
    not changing, which is bankrupt from the get-go."

    Measured in the original system the same day: of 181 open items whose
    quoted text could be tested, 154 quoted text that was no longer at the
    line the item named.

    So the line number is an OUTPUT. It is computed when something is printed
    for the author, because that is how the author navigates, and it is stored
    nowhere. What gets stored is the block id, which moves with the text.

WHAT THE HASH IS FOR, AND WHY IT IS NOT THE ADDRESS

    The id answers *which block*. The hash answers *is it still what we saw*.

        id found, hash matches    the text is exactly as the proposal saw it
        id found, hash differs    it changed underneath us — show both
        id gone                   the block was deleted or split — stop and ask

    That table is the whole reconciliation. A hash alone cannot do it: when
    the author rewrites a paragraph the hash changes, and nothing could then
    tell "rewritten" from "deleted and replaced".

PUBLIC FUNCTIONS

    index(rebuild=False) -> {id: Block}
    resolve(bid) -> Block | None
    where_is(bid) -> str
    check(bid, expected_hash) -> "UNCHANGED" | "DRIFTED" | "MISSING"
    find_by_text(snippet, limit=5) -> [Block]
    content_hash(text) -> str
    Block, IDRE
"""
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

CHAPTERS = B.CHAPTERS
IDRE = re.compile(r"<!--\s*b:([a-z0-9]{6})\s*-->")

_INDEX = None


@dataclass(frozen=True)
class Block:
    id: str
    chapter: str          # "Ch05"
    line: int             # computed at read time, never stored anywhere
    text: str             # the prose, with the id comment removed
    hash: str             # sha256 of the normalised prose, first 16
    file: Path

    @property
    def coord(self) -> str:
        """For printing to the author. A display string, not an identity."""
        return f"{self.chapter}/L{self.line}"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", IDRE.sub("", s)).strip()


def content_hash(s: str) -> str:
    return hashlib.sha256(_norm(s).encode("utf-8")).hexdigest()[:16]


def _bare(bid: str) -> str:
    """'b:k7f3a2' or 'k7f3a2' -> 'k7f3a2'. Removes the prefix, never characters:
    an id can itself begin with 'b'."""
    bid = bid.strip()
    return bid[2:] if bid.startswith("b:") else bid


def index(rebuild: bool = False) -> dict:
    """id -> Block, built by reading the chapters."""
    global _INDEX
    if _INDEX is not None and not rebuild:
        return _INDEX
    out = {}
    for f in B.chapter_files():
        n_ch = B.chapter_number(f)
        ch = f"Ch{n_ch:02d}" if n_ch is not None else f.stem
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            found = IDRE.search(line)
            if not found:
                continue
            bid = found.group(1)
            if bid in out:
                # TWO BLOCKS, ONE NAME. Never guess which; say so.
                raise ValueError(
                    f"block id {bid!r} appears twice — {out[bid].coord} and {ch}/L{n}. "
                    f"An id names one block or it names nothing.")
            text = _norm(line)
            out[bid] = Block(bid, ch, n, text, content_hash(text), f)
    _INDEX = out
    return out


def resolve(bid: str):
    return index().get(_bare(bid))


def where_is(bid: str) -> str:
    b = resolve(bid)
    return b.coord if b else "—"


def check(bid: str, expected_hash: str) -> str:
    """Three answers, no fourth, no guess."""
    b = resolve(bid)
    if b is None:
        return "MISSING"
    return "UNCHANGED" if b.hash == expected_hash else "DRIFTED"


def find_by_text(snippet: str, limit: int = 5):
    """Blocks containing a phrase — for re-anchoring old references.

    Used once per old reference, and the result is confirmed before it is
    written. It is not an addressing scheme and never decides anything on its
    own. A snippet under 12 characters returns nothing.
    """
    want = _norm(snippet).lower()
    if len(want) < 12:
        return []
    return [b for b in index().values() if want in b.text.lower()][:limit]


if __name__ == "__main__":
    idx = index()
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            b = resolve(arg)
            print(f"\n  {arg} -> {b.coord if b else 'NOT FOUND'}")
            if b:
                print(f"     hash {b.hash}")
                print(f"     {b.text[:150]}{'…' if len(b.text) > 150 else ''}")
        print()
    else:
        chs = {}
        for b in idx.values():
            chs[b.chapter] = chs.get(b.chapter, 0) + 1
        print(f"\n  {len(idx)} blocks across {len(chs)} chapters\n")
        for c in sorted(chs):
            print(f"    {c}  {chs[c]:>4}")
        print()

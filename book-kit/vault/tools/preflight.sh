#!/usr/bin/env python3
"""preflight.sh — print the sources in front of Claude before a chapter is touched.

    ./preflight.sh 2           # everything on record for Chapter 2
    ./preflight.sh 2 --brief   # shorten the Working Drafts dumps

WHY THIS EXISTS
    In the system this kit comes from, Claude spent four hours redrafting one
    section of a chapter and was rejected eight times running. Every piece of
    what it needed was already on disk: a Working Drafts file held the
    author's spine for the section, the corrected frame, and four recorded
    wrong turns written down so they would not be repeated. Claude repeated
    two of them.

    It had not read the file. It had read a compacted summary that
    *described* the file, and worked from the description.

    The author: "This process takes longer every day."

THE MECHANISM IT DEFEATS
    Claude substitutes a representation of a source for the source: a summary
    of a file, a memory of a statute, a recollection of a lexicon entry. The
    representation feels like knowledge. It is lossy, and the losses are
    exactly where the errors are. A summary saying "four wrong turns were
    recorded" does not prevent the fifth. Reading the four might.

    A rule that says "go and read the cache" loses to the pull toward
    drafting, because reading costs a call and shows no output while drafting
    looks like progress. So this script does not ask Claude to go and read. It
    PRINTS THE CONTENT. Once the text is on screen there is no description
    left to substitute for it.

WHAT IT PRINTS
    0. The chapter's lock state, from Fact Check/Locks.md. A locked chapter is
       reopened only by the author.
    1. Every Working Drafts file for the chapter, IN FULL.
    2. Every fact-check ledger for the chapter: its full index of sections,
       every section that records a verification no matter how old, and the
       most recent sections.
    3. The works the chapter cites, whether a Claims record names a reader,
       and the copy in the library (from have.sh).
    4. Every open Punch List item naming the chapter.
    5. Every Review Queue row for the chapter still marked NEW, if the vault
       keeps a Review Queue.
    6. The chapter's own in-file outline blocks and parked material.

THE RECEIPT
    On success it writes `.preflight/chNN.stamp` in the vault, holding the
    timestamp, the chapter's SHA-1 and its file name. `check-lock-ready.sh`
    refuses to pass a chapter whose stamp is missing or older than the
    chapter file. A chapter cannot be locked without its sources having been
    printed first.

EXIT CODES
    0  preflight complete, receipt written
    1  chapter not found
"""
import datetime
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402
import citedworks as W  # noqa: E402
import rulings  # noqa: E402

RULE = "═" * 78
WORKING_DRAFTS = B.VAULT / (B.CONFIG.get("paths", {}) or {}).get("working_drafts", "Working Drafts")
REVIEW_QUEUE = B.FACT / "Review Queue.md"


def banner(title, n=None):
    print(f"\n{RULE}\n  {title}" + (f"   [{n}]" if n is not None else "") + f"\n{RULE}")


def chapter_tags(n):
    """The ways a file name or a list item names chapter n."""
    return [f"Ch. {n:02d}", f"Ch. {n} ", f"Ch {n:02d}", f"Ch {n} ", f"Ch{n:02d}"]


def lock_state(n):
    """(state, date, by, note) for chapter n from Locks.md, or None.

    Locks.md is a markdown table: chapter | state | date | by | note, with
    state 🔒 or 🔓. The chapter cell may read 1, 01, Ch01 or Chapter 1."""
    if not B.LOCKS.exists():
        return None
    for line in B.LOCKS.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells, _how = rulings.table_cells(line, expected=5)
        if len(cells) < 2:
            continue
        m = re.search(r"(\d+)", cells[0])
        if m and int(m.group(1)) == n:
            return tuple((cells + ["", "", "", ""])[1:5])
    return None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    brief = "--brief" in sys.argv
    if not args:
        sys.exit("usage: ./preflight.sh NN [--brief]")
    n = int(args[0])
    nn = f"{n:02d}"
    ch = B.chapter_file(n)
    if ch is None:
        print(f"No chapter {nn} in {B.CHAPTERS}.")
        return 1

    print(f"\nPREFLIGHT — {ch.stem}")
    print(f"Run {datetime.datetime.now():%Y-%m-%d %H:%M}. Read what follows before writing a word.")
    print("A description of a source is not the source. That is the whole point of this script.")

    # 0 — lock state, first: any plan aimed at a chapter opens by saying
    # whether it is locked, and reopening it is the author's decision.
    banner("LOCK STATE")
    st = lock_state(n)
    if n in B.OUT_OF_WORKFLOW:
        print(f"  Ch{nn} is OUT OF WORKFLOW in book.toml. No tool, card or check touches it")
        print(f"  until {B.AUTHOR} says so.")
    if st is None:
        print(f"  Ch{nn}: no row in {B.LOCKS.name} — treat as unlocked, and say so.")
    else:
        state, date, by, note = st
        locked = "\U0001F512" in state
        print(f"  Ch{nn}: {state} {'LOCKED' if locked else 'unlocked'}"
              + (f"  {date}" if date else "") + (f"  by {by}" if by else "")
              + (f"  — {note}" if note else ""))
        if locked:
            print(f"  Reopening a locked chapter is {B.AUTHOR}'s decision. Ask before any edit.")

    # 1 — Working Drafts, in full
    wd = sorted({p for tag in chapter_tags(n) for p in WORKING_DRAFTS.glob(f"*{tag}*")
                 if p.is_file() and not B.is_backup(p)}) if WORKING_DRAFTS.is_dir() else []
    banner("WORKING DRAFTS — the cache that exists so work is not bought twice", len(wd))
    if not wd:
        print("  (none — say so before drafting, and cache what you produce)")
    for p in wd:
        print(f"\n───── {p.name} ─────\n")
        text = p.read_text(encoding="utf-8", errors="replace")
        print(text[:2500] + "\n  […truncated, open the file…]" if brief and len(text) > 2500 else text)

    # 2 — the ledger(s). ALL of them, and never only the recent sections.
    #
    # This once printed the first ledger only, and only its last four
    # sections. A chapter with two ledgers had one invisible; and the table
    # that said a source was ALREADY read was near the top, so the recency
    # window hid it. Claude then wrote "read directly, first time ever" into a
    # file whose own earlier section recorded the same source verified months
    # before, and two days went into re-deriving what that table already held.
    #
    # So: every ledger, a full index of section headings, and any section that
    # records a verification is printed no matter how old it is.
    banner("FACT CHECK LEDGER — what has ALREADY been verified. Read before searching.")
    led = sorted(p for p in B.FACT.glob(B.LEDGER_GLOB.format(nn=nn, n=n)) if not B.is_backup(p))
    if not led:
        print("  (no ledger yet)")
    for lp in led:
        text = lp.read_text(encoding="utf-8", errors="replace")
        secs = re.split(r"(?=^## )", text, flags=re.M)
        heads = [s.split("\n", 1)[0].strip() for s in secs if s.startswith("## ")]
        print(f"\n───── {lp.name} — {len(heads)} section(s) ─────")
        print("  INDEX (nothing here is invisible; open the file for any of them):")
        for h in heads:
            print(f"    {h}")
        prior = [s for s in secs
                 if re.search(r"VERIFIED|Verification|Quotation|Chapter history",
                              s.split("\n", 1)[0] + s[:400], re.I)]
        if prior:
            print("\n  ══ ALREADY-VERIFIED RECORD (printed regardless of age) ══")
            for s in prior[:3]:
                print(s.rstrip()[:3000])
        print("\n  ══ MOST RECENT SECTIONS ══")
        for s in secs[-3:]:
            print(s.rstrip()[:3000])

    # 3 — the works this chapter cites, their read state, and the copy
    banner("CITED WORKS — what the footnotes cite, who read it, where the copy is")
    works = W.cited_works([ch])
    if not works:
        print("  (no italicised work titles in this chapter's footnotes)")
    else:
        have = W.load_tool("have.sh")
        recs = W.ledger_records()
        for title, chs in sorted(works.items(), key=lambda kv: (-sum(kv[1].values()), kv[0])):
            rk = W.match(W.norm(title), recs)
            o = recs[rk][2] if rk else {}
            if W.PERIODICAL.search(title):
                state = "periodical — cited by article"
            elif o.get("reader") or o.get("date_read"):
                state = f"READ by {o.get('reader') or '?'} {o.get('date_read') or ''}".rstrip()
            elif rk:
                state = "UNREAD — a Claims record exists, no reader named"
            else:
                state = "UNREAD — no Claims record at all"
            print(f"\n  {sum(chs.values())}x  *{title}*")
            print(f"       {state}")
            if (o.get("drive_path") or "").strip():
                print(f"       recorded copy: {o['drive_path']}")
            if have.LIB is None:
                print("       library: NOT SEARCHED — no library root from book.toml exists here")
            else:
                found = have.have(title)
                if found:
                    f, how = found[0]
                    print(f"       in library: {have.rel(f)}" + ("" if how == "filename" else f"  (via {how})"))
                else:
                    print("       in library: NOT BY NAME — run have.sh and find-source.sh before calling it absent")
        print("\n  Open each source before writing about it. A path names a copy; only a")
        print("  reader's record says somebody opened it.")

    # 4 — Punch List
    banner("PUNCH LIST — open items naming this chapter")
    if B.PUNCH_LIST.exists():
        pl = B.PUNCH_LIST.read_text(encoding="utf-8")
        hits = [l for l in pl.split("\n")
                if l.strip().startswith("- [ ]") and re.search(rf"Ch\.? ?0?{n}\b|Ch{nn}/", l)]
        print("\n".join("  " + h.strip()[:400] for h in hits) if hits else "  (none)")
    else:
        print(f"  (no {B.PUNCH_LIST.name} in the vault)")

    # 5 — Review Queue, where the vault keeps one
    if REVIEW_QUEUE.exists():
        banner("REVIEW QUEUE — rows still NEW for this chapter")
        # Pipes inside quoted regexes are content, not column boundaries; see
        # rulings.table_cells. Splitting on every "|" once cut findings at the
        # first alternation and hid the fix column entirely.
        rows = []
        for r in REVIEW_QUEUE.read_text(encoding="utf-8").split("\n"):
            if not re.match(r"^\|\s*\d{4}-\d\d-\d\d", r):
                continue
            p, how = rulings.table_cells(r)
            if how == "malformed" or p[-1] != "NEW":
                continue
            if re.search(rf"Ch{nn}/|Ch{n}/", r):
                rows.append(p)
        for p in rows:
            print(f"  {p[1]:<28} {p[2]:<18} {p[3][:220]}")
        if not rows:
            print("  (none)")
        print("\n  Rows may name coordinates already fixed. Confirm against the file before working one.")

    # 6 — the chapter's own outline and parked material
    banner("IN-FILE OUTLINE AND PARKED MATERIAL")
    body = ch.read_text(encoding="utf-8")
    keep, on = [], False
    for i, l in enumerate(body.split("\n"), 1):
        if re.match(r"^#+ .*(OUTLINE|REMAINING|Decisions on record)", l) or l.startswith("**PARKED"):
            on = True
        if on and l.strip():
            keep.append(f"  L{i:<4} {l[:300]}")
    print("\n".join(keep) if keep else "  (none)")

    # receipt
    d = B.VAULT / ".preflight"
    d.mkdir(exist_ok=True)
    sha = hashlib.sha1(ch.read_bytes()).hexdigest()
    (d / f"ch{nn}.stamp").write_text(
        f"{datetime.datetime.now().isoformat()}\n{sha}\n{ch.name}\n", encoding="utf-8")

    banner("PREFLIGHT COMPLETE")
    print(f"  Receipt: .preflight/ch{nn}.stamp")
    print("  check-lock-ready.sh will refuse this chapter if the stamp is missing or stale.")
    print("  Draft only sentences whose source is in what you just read. Where nothing")
    print("  sources a sentence, say so instead of composing one.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

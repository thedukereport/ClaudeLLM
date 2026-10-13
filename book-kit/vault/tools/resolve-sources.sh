#!/usr/bin/env python3
"""resolve-sources.sh — find the file in the library for each work the book cites.

    ./resolve-sources.sh                  # how many cited works still have no file
    ./resolve-sources.sh --queue          # write the work list for the agents
    ./resolve-sources.sh --apply          # write the agents' answers into Claims

WHY THIS EXISTS

    The author, when cited works kept being reported missing: "My guess is
    a) the files are there b) you are not looking in [the checked shelf] and
    c) whatever scheme you're using (grep or RegEx) is misconfigured. DO IT."
    And then: "And oh yeah, we have a RAG."

    The library was never the problem. THE MATCHER WAS: it split a filename on
    " - " and asked whether the cited title opened one of the pieces, so a
    title with a colon (a dash in the filename) straddled two pieces and
    opened neither. That fix lives in have.sh, the one search every tool
    calls.

    A SEMANTIC SEARCH DOES THE REST. A filename cannot find a work bound
    inside a larger one: the book cites one essay, and the library holds a
    volume whose name lists three. No filename rule reaches that without also
    matching things it should not. A semantic query can.

HOW THE WORK IS SPLIT

    A semantic index usually answers through a tool that runs where Claude
    runs, not where this script runs. So:

      --queue   this script writes `Fact Check/Sources Unplaced.json`
      agents    read that file, search once per work (have.sh, find-source.sh,
                any semantic index), and write `Fact Check/Sources Resolved.json`
      --apply   this script reads that file back and writes the Claims records

WHAT AN AGENT MUST DECIDE

    Not every italicised string in a footnote is a book. A queue can hold a
    journal, newspapers, a court case, an artwork, and a bold label the
    extractor mistook for a title. So each work comes back as exactly one of:

      IN_LIBRARY      with "path" (relative to the library root, or absolute)
                      and the "surface" and "score" that found it
      NOT_A_BOOK      a periodical, a case, an artwork, a label, with "note"
                      saying which
      NOT_IN_LIBRARY  searched and absent, with "note" saying what was
                      searched: a Sources Wanted entry

    NOT_IN_LIBRARY is a real answer and the most valuable one, because it is
    the only category the author can act on. Guessing a path to avoid writing
    it is the failure this whole file exists to undo.

    Sources Resolved.json is a list of objects:
      [{"title": "...", "state": "IN_LIBRARY", "path": "PDF/...", "surface": "have.sh"}]
"""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402
import citedworks as W  # noqa: E402

QUEUE = B.FACT / "Sources Unplaced.json"
ANSWERS = B.FACT / "Sources Resolved.json"
# The earlier names for the same states, still read so an older answer file applies.
SYNONYMS = {"ON_DRIVE": "IN_LIBRARY", "NOT_ON_DRIVE": "NOT_IN_LIBRARY"}


def unplaced(have):
    """Cited works with no path, no declaration, and no filename match."""
    recs = W.ledger_records()
    works = W.cited_works(B.chapter_files())
    out = []
    for title, chs in sorted(works.items(), key=lambda kv: (-sum(kv[1].values()), kv[0])):
        if W.PERIODICAL.search(title) or W.NOT_A_WORK.match(title):
            continue
        rk = W.match(W.norm(title), recs)
        o = recs[rk][2] if rk else {}
        if rk and ((o.get("drive_path") or "").strip() or W.declared_elsewhere(o)):
            continue
        if have.have(title):
            continue
        out.append({"title": title,
                    "author": (o.get("author") or "") if rk else "",
                    "chapters": [f"Ch{c:02d}" for c in sorted(chs)],
                    "citations": sum(chs.values())})
    return out


def apply_answers():
    """Write the agents' findings into the Claims records, through vaultlog."""
    import vaultlog
    if not ANSWERS.exists():
        print(f"No answers yet. Expected {ANSWERS.name} in {B.FACT.name}/.")
        return
    ans = {a["title"]: a for a in json.loads(ANSWERS.read_text(encoding="utf-8"))}
    recs = W.ledger_records()
    today = datetime.date.today().isoformat()
    edits, missing = {}, []
    for title, a in ans.items():
        rk = W.match(W.norm(title), recs)
        if rk is None:
            missing.append(title)
            continue
        f, n, o, _ = recs[rk]
        edits.setdefault(f, {})[n] = a
    written = 0
    for f, rows in edits.items():
        lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        for n, a in rows.items():
            rec = json.loads(lines[n - 1])
            state = SYNONYMS.get(a.get("state", ""), a.get("state", ""))
            if state == "IN_LIBRARY" and a.get("path"):
                rec["drive_path"] = a["path"]
                rec["path_found_by"] = (
                    f"{a.get('surface', 'library search')}, {today}"
                    + (f", similarity {a['score']}" if a.get("score") else "")
                    + ". NOBODY HAS OPENED THIS FILE. The record holds the path "
                      "under the standing rule; check-read.sh still reports the "
                      "work UNREAD.")
                rec.pop("path_unresolved", None)
            else:
                rec["drive_path"] = None
                rec["location"] = a.get("note") or rec.get("location")
                if state == "NOT_A_BOOK":
                    rec["not_a_work"] = True
                rec["path_unresolved"] = f"{state}, {today} — {a.get('note', '')}".strip(" —")
            lines[n - 1] = json.dumps(rec, ensure_ascii=False)
            written += 1
        vaultlog.write_file(f, "\n".join(lines) + "\n", tool="resolve-sources.sh",
                            why=f"{len(rows)} answer(s) from {ANSWERS.name}")
    by = {}
    for a in ans.values():
        s = SYNONYMS.get(a.get("state", "?"), a.get("state", "?"))
        by[s] = by.get(s, 0) + 1
    print(f"wrote {written} record(s)")
    for k, v in sorted(by.items()):
        print(f"   {v:>4}  {k}")
    if missing:
        print(f"\n{len(missing)} answer(s) matched no Claims record:")
        for t in missing[:10]:
            print("   ", t[:70])


def main():
    if "--apply" in sys.argv:
        apply_answers()
        return
    have = W.load_tool("have.sh")
    if have.LIB is None:
        print("NO LIBRARY FOUND. None of the roots in book.toml [library] roots exists on")
        print("this machine. Nothing was searched, so no work can be called unplaced.")
        sys.exit(2)
    rows = unplaced(have)
    if "--queue" in sys.argv:
        QUEUE.parent.mkdir(parents=True, exist_ok=True)
        QUEUE.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(rows)} work(s) written to {QUEUE.relative_to(B.VAULT)}")
        print("Each needs a search and one of IN_LIBRARY / NOT_A_BOOK / NOT_IN_LIBRARY.")
        return
    print(f"{len(rows)} cited work(s) have no file in the library by name.")
    for r in rows[:20]:
        print(f"   {r['citations']:>3}x  {r['title'][:60]:<62}{', '.join(r['chapters'])}")
    print("Run --queue to write the work list, then --apply once the agents answer.")


if __name__ == "__main__":
    main()

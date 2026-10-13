#!/usr/bin/env python3
"""dashboard-sync.py — loads the Asks and Back-fill views of the Source Rulings page, and reads the author's presses there back into the files of record.

    tools/dashboard-sync.py build            # write the cards to load, change nothing else
    tools/dashboard-sync.py answers          # SAMPLE: what the author's presses would write (writes nothing)
    tools/dashboard-sync.py answers --write  # write them (more than five needs a UAT acceptance line)

WHOSE WORDS THIS SERVES

    The author's: "Asks need to be presented in cards, like the other
    interfaces", and "build interfaces that allow me to manage the backlog ...
    and build everything into our unified dashboard." The unified dashboard is
    the Source Rulings page (book.toml [page] url). This tool feeds two
    collections on it, `asks` and `backlog`, and takes the author's presses
    back into the files of record.

WHAT `build` READS AND WRITES

    Asks: the Open table of `Fact Check/Asks.md`, one card per row, with the
    chapter line it names and the paragraphs either side (the author's rule
    for an ask: the job, the paragraphs that bracket it, the Editor's cards
    as the model).

    Back-fill: each work the footnotes cite (`citedworks.cited_works`) with
    no Claims row that names a reader or a date. UNREAD when the library index
    (book.toml [library] index_file, built by `tools/have.sh`) holds a file of
    that title; NOT IN THE LIBRARY when it holds none. With no index, the
    back-fill cards are not built: "not in the library" is a claim about the
    shelf, and nothing here has read the shelf. Chapters listed in [workflow]
    out_of_workflow are left out.

    It writes only `Handoffs/editor-tools/dashboard-load/asks.json` and
    `backlog.json` (beside the page snapshot folder), which Claude loads into
    the page with ArtifactData. It removes nothing anywhere: a work that is
    read drops off the next build because its Claims row exists, never because
    a card was deleted (the author's rule: "I don't want anything removed that
    I have not approved").

WHAT `answers` WRITES, WITH --write ONLY

    From the page snapshot (`<page snapshot>/asks/*.json`, `backlog/*.json`):
      - an answered ask: its row moves from Open to Answered in
        `Fact Check/Asks.md`, the author's answer verbatim with the date, and a
        `decision.recorded` event, actor = [book] author_actor;
      - a back-fill press: one line in `Fact Check/Back-fill Queue.md` and a
        `decision.recorded` event, actor author_actor. "Approve citing it
        unread" is the author's own exception to the rule that a cited work is
        read first, and is recorded as exactly that.
    A row a press cannot be matched to is reported and left alone. After a
    write, Claude sets `writtenAt` on each card on the page so the next run
    skips it.

ASKS.MD SHAPE

    A `## Open` heading and a `## Answered` heading, each over a markdown
    table. An open row: | `A12` | kind | the ask (may name Ch05/L112) |
    what it holds up | what happens if nobody answers | date asked |
"""
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402
import citedworks as W  # noqa: E402

TOOL = "tools/dashboard-sync.py"
ASKS = B.ASKS
OUT = B.SNAPSHOT.parent / "dashboard-load"
SNAP = B.SNAPSHOT
QUEUE = B.FACT / "Back-fill Queue.md"
INDEX = B.LIBRARY_INDEX
OUT_OF_WORKFLOW = B.OUT_OF_WORKFLOW
AUTHOR = B.AUTHOR_ACTOR
MARK = re.compile(r"\s*<!-- b:[0-9a-f]+ -->\s*$")


def rel(p):
    try:
        return str(Path(p).resolve().relative_to(B.VAULT))
    except ValueError:
        return str(p)


def cells(row):
    parts = re.split(r"(?<!\\)\|", row.strip())
    return [c.strip() for c in parts[1:-1]]


def open_rows(text):
    lines = text.split("\n")
    try:
        i = next(n for n, l in enumerate(lines) if l.strip() == "## Open")
        j = next(n for n, l in enumerate(lines) if l.strip() == "## Answered")
    except StopIteration:
        raise SystemExit(f"{rel(ASKS)} needs a '## Open' and a '## Answered' heading. "
                         f"Nothing read, nothing written.")
    rows = []
    for n in range(i, j):
        l = lines[n]
        if l.startswith("| `A"):
            rows.append((n, cells(l)))
    return lines, rows, j


def context(ch, ln):
    """The line, and the nearest non-blank paragraph before and after, from disk."""
    f = B.chapter_file(ch)
    if not f:
        return {}
    L = f.read_text(encoding="utf-8").split("\n")
    if not (1 <= ln <= len(L)):
        return {}

    def para(k, step):
        k += step
        while 0 <= k < len(L) and not L[k].strip():
            k += step
        return (k + 1, MARK.sub("", L[k])) if 0 <= k < len(L) else (None, "")
    b, a = para(ln - 1, -1), para(ln - 1, 1)
    return {"current": [{"where": B.coord(ch, ln), "text": MARK.sub("", L[ln - 1])}],
            "before": (f"{B.coord(ch, b[0])} — " if b[0] else "") + b[1],
            "after": (f"{B.coord(ch, a[0])} — " if a[0] else "") + a[1]}


def build_asks():
    if not ASKS.exists():
        return []
    _, rows, _ = open_rows(ASKS.read_text(encoding="utf-8"))
    out = []
    for order, (n, c) in enumerate(rows):
        if len(c) < 6:
            continue
        aid = c[0].strip("`")
        d = {"order": order, "aid": aid, "kind": c[1], "ask": c[2], "blocks": c[3],
             "silence": c[4], "asked": c[5], "fileLine": n + 1,
             "answer": "", "words": "", "answeredAt": "", "claudeReadAt": "", "writtenAt": ""}
        m = re.search(r"Ch(\d+)/L(\d+)", c[2])
        if m and int(m.group(1)) not in OUT_OF_WORKFLOW:
            d.update(context(int(m.group(1)), int(m.group(2))))
        out.append({"id": aid, "data": d})
    return out


def norm_title(s):
    return re.sub(r"\s+", " ", s).strip()


def read_titles():
    """Every work a Claims row records as opened: a reader or a date. A path
    says which copy exists; only a reader says somebody opened it."""
    out = {}
    for f, n, o in W.claims_rows():
        t = (o.get("title") or "").strip()
        if t and (o.get("date_read") or o.get("reader")):
            out.setdefault(W.norm(t), (f, n, o, True))
    return out


def build_backlog():
    """The back-fill cards, or None when there is no library index to test against."""
    if not INDEX.exists():
        return None
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    shelf = [(W.norm(Path(p).stem), p) for _, p in idx.get("files", [])]
    read = read_titles()
    chapters = [p for p in B.chapter_files() if B.chapter_number(p) not in OUT_OF_WORKFLOW]
    works = W.cited_works(chapters)
    notes = {}
    for f in chapters:
        ch = B.chapter_number(f)
        for ln, l in enumerate(f.read_text(encoding="utf-8").split("\n"), 1):
            if l.startswith("[^"):
                notes.setdefault(ch, []).append((ln, MARK.sub("", l)))
    out = []
    for title, chs in works.items():
        k = W.norm(title)
        if W.PERIODICAL.search(title) or W.match(k, read):
            continue
        hit = next((p for d, p in shelf if len(k) > 8 and (k in d or d in k)), "")
        where = []
        for ch in sorted(chs):
            for ln, l in notes.get(ch, []):
                if f"*{title}*" in l:
                    where.append({"where": B.coord(ch, ln), "text": l})
                    if len(where) >= 3:
                        break
            if len(where) >= 3:
                break
        out.append({"title": norm_title(title), "lane": "unread" if hit else "notondrive",
                    "drivePath": hit, "chapters": ", ".join(f"Ch{c:02d}" for c in sorted(chs)),
                    "cites": sum(chs.values()), "current": where,
                    "action": "", "note": "", "actedAt": "", "writtenAt": ""})
    out.sort(key=lambda d: (d["lane"] != "notondrive", -d["cites"], d["title"]))
    res = []
    for i, d in enumerate(out):
        slug = re.sub(r"[^a-z0-9]+", "-", d["title"].lower()).strip("-")[:60]
        d["order"] = i
        res.append({"id": f"bf-{slug}", "data": d})
    return res


def cmd_build():
    OUT.mkdir(parents=True, exist_ok=True)
    a, b = build_asks(), build_backlog()
    (OUT / "asks.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    if b is None:
        print(f"asks: {len(a)} open cards. back-fill: NOT BUILT — no library index at "
              f"{rel(INDEX)}; run tools/have.sh to build it. Written to {rel(OUT)}/asks.json; "
              f"nothing else changed.")
        return 0
    (OUT / "backlog.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
    lanes = {}
    for x in b:
        lanes[x["data"]["lane"]] = lanes.get(x["data"]["lane"], 0) + 1
    print(f"asks: {len(a)} open cards; back-fill: {len(b)} works ({lanes}); "
          f"written to {rel(OUT)}/ — nothing else changed.")
    return 0


ACTIONS = {"backfill": "Back-fill: read it and log it",
           "get": "I'll get it",
           "exception": "Approve citing it unread (the author's exception to read-before-cite)",
           "skip": "Skip for now"}


def snapshot(name):
    d = SNAP / name
    out = {}
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.json")):
        x = json.loads(p.read_text(encoding="utf-8"))
        out[p.stem] = dict(x.get("data", x)) if isinstance(x.get("data", x), dict) else {}
    return out


def cmd_answers(write):
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    asks = {k: v for k, v in snapshot("asks").items() if v.get("answer") and not v.get("writtenAt")}
    queued = QUEUE.read_text(encoding="utf-8") if QUEUE.exists() else ""
    back = {k: v for k, v in snapshot("backlog").items() if v.get("action") and not v.get("writtenAt")
            and f"| *{v.get('title','')}* | {v.get('chapters','')} | {v.get('lane','')} | {ACTIONS.get(v['action'], v['action'])} |" not in queued}
    if asks and not ASKS.exists():
        raise SystemExit(f"answered asks are on the page and there is no {rel(ASKS)}. Nothing written.")
    lines, rows = [], []
    if ASKS.exists():
        lines, rows, _ = open_rows(ASKS.read_text(encoding="utf-8"))
    byid = {c[0].strip("`"): (n, c) for n, c in rows}
    changes = []
    for aid, d in asks.items():
        if aid not in byid:
            changes.append(("SKIP", f"{aid}: no open row in {rel(ASKS)}; left alone"))
            continue
        n, c = byid[aid]
        said = {"ok": "ok", "no": "no"}.get(d["answer"], "")
        words = (d.get("words") or "").strip()
        his = " — ".join(x for x in (said, words) if x)
        when = (d.get("answeredAt") or "")[:16].replace("T", " ") + " UTC"
        new = f"| `{aid}` | {c[1]} | {c[2]} | **\"{his}\"** — {B.AUTHOR} on the Source Rulings page, {when} | {today} |"
        changes.append(("ASK", aid, lines[n], new, his, d))
    for bid, d in back.items():
        changes.append(("BACK", bid, d))
    if not changes:
        print("Nothing to write: no press on the page since the last run.")
        return 0
    n_writes = sum(1 for c in changes if c[0] != "SKIP")
    for c in changes:
        if c[0] == "SKIP":
            print("  " + c[1])
        elif c[0] == "ASK":
            print(f"\n  {c[1]} — the Asks.md row moves from Open to Answered.\n"
                  f"    NOW:      {c[2]}\n    PROPOSED: {c[3]}")
        else:
            d = c[2]
            print(f"\n  Back-fill: {d['title']} ({d['chapters']}) — {ACTIONS.get(d['action'], d['action'])}"
                  + (f"; the author's note: {d['note']}" if d.get("note") else ""))
    if not write:
        print(f"\nSAMPLE: {n_writes} change(s) shown; nothing written. --write writes them.")
        return 0
    if n_writes == 0:
        print("\nNothing written.")
        return 0
    import uat
    import vaultlog
    uat.require_acceptance(TOOL, n_writes, sample_flag="answers")
    for c in changes:
        if c[0] == "ASK":
            aid, old, new, his, d = c[1], c[2], c[3], c[4], c[5]
            lines.remove(old)
            j = next(n for n, l in enumerate(lines) if l.strip() == "## Answered")
            k = j + 1
            while k < len(lines) and not lines[k].startswith("|---"):
                k += 1
            if k >= len(lines):              # no table under Answered yet: start one
                lines[j + 1:j + 1] = ["", "| id | kind | ask | answer | written |", "|---|---|---|---|---|"]
                k = j + 2
            lines.insert(k + 1, new)
            vaultlog.append("decision.recorded", actor=AUTHOR, sheet="Asks", item=aid, idx=None,
                            element=None, decision_kind="instruct" if d.get("words") else "apply",
                            text=his, via="Source Rulings page, Asks view", ruled_on_sha="",
                            why=f"the author's press, written into {rel(ASKS)} by {TOOL}")
    if any(c[0] == "ASK" for c in changes):
        vaultlog.write_file(ASKS, "\n".join(lines), tool=TOOL,
                            why="the author's answers on the Source Rulings page, Asks view")
    qlines = []
    for c in changes:
        if c[0] != "BACK":
            continue
        d = c[2]
        qlines.append(f"| {today} | *{d['title']}* | {d['chapters']} | {d['lane']} | "
                      f"{ACTIONS.get(d['action'], d['action'])} | {d.get('note','')} | open |")
        vaultlog.append("decision.recorded", actor=AUTHOR, sheet="Back-fill", item=d["title"], idx=None,
                        element=None, decision_kind="apply", text=ACTIONS.get(d["action"], d["action"])
                        + (f" — {d['note']}" if d.get("note") else ""), via="Source Rulings page, Back-fill view",
                        ruled_on_sha="", why=f"the author's press, written into {rel(QUEUE)} by {TOOL}")
    if qlines:
        head = ("# Back-fill Queue — the author's presses on the Source Rulings page\n\n"
                "Written by `tools/dashboard-sync.py`. One row per press. The Fact-checker works the "
                "`Back-fill` rows (read, then log in `Fact Check/Claims/` and the chapter ledger) and marks "
                "the last column done; nothing in the book is removed from here.\n\n"
                "| pressed | work | cited in | lane | the author's ruling | the author's note | state |\n"
                "|---|---|---|---|---|---|---|\n")
        old = QUEUE.read_text(encoding="utf-8") if QUEUE.exists() else head
        vaultlog.write_file(QUEUE, old.rstrip("\n") + "\n" + "\n".join(qlines) + "\n",
                            tool=TOOL, why="the author's back-fill presses on the Source Rulings page")
    print(f"\nWrote {n_writes} change(s). Set writtenAt on each card on the page so the next run skips it.")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "build":
        sys.exit(cmd_build())
    elif a[0] == "answers":
        sys.exit(cmd_answers("--write" in a))
    else:
        print(__doc__)

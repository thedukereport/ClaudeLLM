#!/usr/bin/env python3
"""dashboard-sync.py — loads the Asks and Back-fill views of the Source Rulings page, and reads the author's presses there back into the files of record.

    tools/dashboard-sync.py build            # write the cards to load, change nothing else
    tools/dashboard-sync.py answers          # SAMPLE: what the author's presses would write (writes nothing)
    tools/dashboard-sync.py answers --write  # write them (more than five needs a UAT acceptance line)
    tools/dashboard-sync.py queue            # SAMPLE: the Fact-checker's reading queue (writes the sample only)
    tools/dashboard-sync.py queue --write    # write Fact Check/Reading Queue.md (more than five needs a UAT line)

THE READING QUEUE

    The author's rule: "The point of scanning the footnote for unread
    citations IS TO READ THEM, NOT TO TELL ME THEY HAVE NOT BEEN READ." So a
    work in the library with no logged read never goes to the author. `queue`
    writes the Fact-checker's reading queue, `Fact Check/Reading Queue.md`, in
    two parts: works in the library with no logged read (read them), and works
    the library index cannot find (search again). For each it gives the note
    lines that cite it and the first recorded write that put the title into
    the chapter: an `edit.applied` or `file.written` event, or else the git
    commit. The reader confirms that write and records it with the read. The
    queue is rebuilt from the book each time; a work leaves when its Claims
    row names a reader.

    The page's Back-fill view loads only the works the library cannot
    produce, as "I cannot find it. Can you get it?"

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
    # Only the works the library cannot produce go to the author's page; the rest are the reading queue's.
    b = [x for x in b if x["data"]["lane"] == "notondrive"]
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


READING_QUEUE = B.FACT / "Reading Queue.md"
SAMPLE_DIR = OUT.parent / "samples" / "reading-queue"


def chapter_writes():
    """(ts, kind, file, added, removed, who, via, why, hash) for each chapter write the event log records."""
    import vaultlog
    out = []
    for e in vaultlog.fold("edit.applied"):
        out.append((e.get("ts", ""), "edit.applied", str(e.get("file") or e.get("path") or e.get("coord") or ""),
                    e.get("new") or "", e.get("old") or "", e.get("actor", ""),
                    " · ".join(str(x) for x in (e.get("sheet"), e.get("item")) if x), e.get("why", ""), e.get("hash", "")))
    for e in vaultlog.fold("file.written"):
        f = str(e.get("path") or "")
        if not vaultlog.is_chapter(B.VAULT / f) and "Chapter" not in f:
            continue
        diff = e.get("diff") or ""
        added = "\n".join(l[1:] for l in diff.split("\n") if l.startswith("+") and not l.startswith("+++"))
        removed = "\n".join(l[1:] for l in diff.split("\n") if l.startswith("-") and not l.startswith("---"))
        out.append((e.get("ts", ""), "file.written", f, added, removed, e.get("actor", ""), e.get("tool", ""),
                    e.get("why", ""), e.get("hash", "")))
    return sorted(out)


def first_write(title, ch, writes):
    """The first recorded write that put *title* into chapter ch: the event log first, then git."""
    needle = f"*{title}*"
    path = B.chapter_file(ch)
    name = path.name if path else ""
    for ts, kind, f, added, removed, who, via, why, h in writes:
        if name and name not in f and f"Ch{ch:02d}" not in f:
            continue
        if needle in added and needle not in removed:
            return (f"{ts[:16].replace('T', ' ')} UTC, `{kind}` event `{h}`, {who}"
                    + (f" ({via})" if via else "") + (f": {why[:200]}" if why else ""))
    if not path:
        return "the chapter file was not found; the reader looks it up"
    import subprocess
    try:
        r = subprocess.run(["git", "log", "-S", needle, "--reverse", "--format=%ad|%h|%s", "--date=short", "--",
                            str(path.relative_to(B.VAULT))], cwd=str(B.VAULT), capture_output=True, text=True,
                           timeout=60)
        line = (r.stdout.strip().split("\n") or [""])[0]
    except Exception as exc:                                  # noqa: BLE001
        return f"git could not be asked ({type(exc).__name__}); the reader looks it up"
    if not line:
        return "no recorded write found in the event log or in git; the reader looks it up"
    day, h, subj = line.split("|", 2)
    return f"{day}, git commit `{h}`: {subj[:200]}"


PARTS = [("unread", "1. In the library, no read logged — read these",
          "Open the file named, read the part the note cites (heading to heading), and log the read in the "
          "chapter's Claims file, the chapter's ledger and the event log (`source.read`), with the write that "
          "put the citation in the book."),
         ("notondrive", "2. The library index found no copy — search again",
          "Search the library again: an empty search means a broken pointer. A copy found moves the work to "
          "part 1. A work still not found stays on the author's Back-fill view as \"I cannot find it. Can you "
          "get it?\"")]


def queue_md(rows, limit=None):
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = ["# Reading Queue — the Fact-checker's", "",
           f"Built {today} by `tools/dashboard-sync.py queue` from the footnotes of the chapters in the workflow "
           "and the Claims files. Rebuilt from the book each time: a work leaves when its Claims row names a "
           "reader. Nothing here goes to the author.", ""]
    for lane, head, lede in PARTS:
        items = [d for d in rows if d["lane"] == lane]
        out += [f"## {head} ({len(items)})", "", lede, ""]
        for d in (items[:limit] if limit else items):
            out.append(f"### *{d['title']}*")
            out.append(f"- cited {d['cites']} time{'s' if d['cites'] != 1 else ''}: {d['chapters']}")
            if d.get("drivePath"):
                out.append(f"- in the library: `{d['drivePath']}`")
            for c in d.get("current") or []:
                out.append(f"- {c['where']}: {c['text'][:400]}{'…' if len(c['text']) > 400 else ''}")
            out.append(f"- how it came into the book: {d.get('entered', '')}")
            out.append("")
        if limit and len(items) > limit:
            out += [f"… and {len(items) - limit} more in this part.", ""]
    return "\n".join(out) + "\n"


def cmd_queue(write):
    built = build_backlog()
    if built is None:
        print(f"NOT BUILT — no library index at {rel(INDEX)}; run tools/have.sh to build it.")
        return 1
    rows = [x["data"] for x in built]
    writes = chapter_writes()
    for d in rows:
        cur = d.get("current") or []
        m = re.search(r"Ch(\d+)/L\d+", cur[0]["where"]) if cur else None
        d["entered"] = (first_write(d["title"], int(m.group(1)), writes) if m
                        else "the citing note line was not found by title; the reader looks it up")
    lanes = {k: sum(1 for d in rows if d["lane"] == k) for k, _, _ in PARTS}
    if not write:
        SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
        (SAMPLE_DIR / f"sample-{stamp}.md").write_text(queue_md(rows, limit=4), encoding="utf-8")
        (SAMPLE_DIR / f"full-{stamp}.md").write_text(queue_md(rows), encoding="utf-8")
        print(f"SAMPLE: {lanes}; written to {rel(SAMPLE_DIR)}/sample-{stamp}.md. "
              f"{rel(READING_QUEUE)} is not written until --write.")
        return 0
    import uat, vaultlog
    uat.require_acceptance("tools/dashboard-sync.py queue", len(rows))
    vaultlog.write_file(READING_QUEUE, queue_md(rows), tool="tools/dashboard-sync.py queue",
                        why="the unread-citation scan feeds the Fact-checker's reading queue")
    print(f"Wrote {rel(READING_QUEUE)}: {lanes}.")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "build":
        sys.exit(cmd_build())
    elif a[0] == "answers":
        sys.exit(cmd_answers("--write" in a))
    elif a[0] == "queue":
        sys.exit(cmd_queue("--write" in a))
    else:
        print(__doc__)

#!/usr/bin/env python3
"""dashboard_sync_test.py — tools/dashboard-sync.py on a copy of the sample vault.

Requires:
  1. `build` writes only the dashboard-load files; an ask naming Ch02/L5 comes
     with that line's text and the paragraph before it;
  2. with no library index, `build` writes no back-fill cards and says so;
     with an index holding Common Sense, the page gets only The Federalist
     Papers (NOT IN THE LIBRARY); Common Sense (in the library, unread) goes
     to the Fact-checker's reading queue instead, and `queue` without
     --write writes only its sample;
  3. `answers` without --write changes no file;
  4. with --write, an answered ask leaves Open and lands in Answered with the
     author's words;
  5. a back-fill press becomes one row in Back-fill Queue.md;
  6. each press is one decision.recorded event, actor = the author's actor;
  7. a second run with the same snapshot changes nothing.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cardtest as T  # noqa: E402

ASKS = """# Asks

## Open

| id | kind | ask | holds up | if nobody answers | asked |
|---|---|---|---|---|---|
| `A1` | source | Ch02/L5 quotes Federalist No. 1. Is the Project Gutenberg text the edition to cite? | the citation in [^fed1_test] | the note cites the Gutenberg text | 2026-10-13 |

## Answered

| id | kind | ask | answer | written |
|---|---|---|---|---|
"""

bad = []
with T.sample_copy() as v:
    (v / "Fact Check" / "Asks.md").write_text(ASKS, encoding="utf-8")
    load = v / "Handoffs" / "editor-tools" / "dashboard-load"

    # 1 and 2
    before = T.files(v)
    r = T.run(v, "dashboard-sync.py", "build")
    if r.returncode != 0 or "Traceback" in r.stderr:
        bad.append("build failed: " + (r.stdout + r.stderr)[-500:])
    changed = {p for p in set(T.files(v)) ^ set(before)} | {p for p in before if T.files(v).get(p) != before[p]}
    if {p.relative_to(v).as_posix() for p in changed} != {"Handoffs/editor-tools/dashboard-load/asks.json"}:
        bad.append(f"build with no index wrote {sorted(str(p.relative_to(v)) for p in changed)}")
    if "back-fill: NOT BUILT" not in r.stdout:
        bad.append("build with no library index did not say the back-fill was not built")
    asks = json.loads((load / "asks.json").read_text(encoding="utf-8"))
    if len(asks) != 1 or "reflection and design" not in asks[0]["data"]["current"][0]["text"] \
            or "Alexander Hamilton addressed" not in asks[0]["data"]["before"]:
        bad.append(f"the ask card lacks its chapter line or the paragraph before: {asks}")
    idx = v / "Fact Check" / "Library Index.json"
    idx.write_text(json.dumps({"files": [["paine", "PDF/Thomas Paine - Common Sense (1776).txt"]]}),
                   encoding="utf-8")
    r = T.run(v, "dashboard-sync.py", "build")
    lanes = {}
    if (load / "backlog.json").exists():
        lanes = {x["data"]["title"]: x["data"]["lane"]
                 for x in json.loads((load / "backlog.json").read_text(encoding="utf-8"))}
    if "Common Sense" in lanes or lanes.get("The Federalist Papers") != "notondrive":
        bad.append(f"back-fill lanes are wrong: {lanes} {r.stdout[-300:]}")
    before = T.files(v)
    r = T.run(v, "dashboard-sync.py", "queue")
    made = {p.relative_to(v).as_posix() for p in set(T.files(v)) - set(before)}
    sample = [p for p in made if p.startswith("Handoffs/editor-tools/samples/reading-queue/sample-")]
    if r.returncode != 0 or not sample or (v / "Fact Check" / "Reading Queue.md").exists():
        bad.append(f"queue sample: {sorted(made)} {r.stdout[-300:]} {r.stderr[-300:]}")
    else:
        txt = (v / sample[0]).read_text(encoding="utf-8")
        if "### *Common Sense*" not in txt.split("## 2.")[0] or "how it came into the book:" not in txt:
            bad.append("the reading queue sample lacks Common Sense in part 1 with how it came into the book")

    s = v / T.SNAP_REL
    (s / "asks").mkdir(parents=True, exist_ok=True)
    (s / "backlog").mkdir(exist_ok=True)
    (s / "asks" / "A1.json").write_text(json.dumps(
        {"answer": "ok", "words": "TEST WORDS", "answeredAt": "2026-01-01T00:00:00Z"}))
    (s / "backlog" / "bf-test.json").write_text(json.dumps(
        {"title": "Test Work", "chapters": "Ch02", "lane": "unread", "action": "backfill", "note": ""}))

    # 3
    before = T.files(v)
    r = T.run(v, "dashboard-sync.py", "answers")
    if before != T.files(v):
        bad.append("the sample run wrote to disk")
    # 4
    r = T.run(v, "dashboard-sync.py", "answers", "--write")
    a = (v / "Fact Check" / "Asks.md").read_text(encoding="utf-8")
    k = a.index("## Answered")
    if "| `A1` |" in a[:k] or "| `A1` |" not in a[k:] or "TEST WORDS" not in a[k:]:
        bad.append("the answered ask did not move to Answered with the author's words: "
                   + r.stdout[-300:] + r.stderr[-300:])
    # 5
    q = v / "Fact Check" / "Back-fill Queue.md"
    if not q.exists() or q.read_text(encoding="utf-8").count("*Test Work*") != 1:
        bad.append("the back-fill press is not exactly one queue row")
    # 6
    toml = (v / "book.toml").read_text(encoding="utf-8")
    actor = "author"
    for line in toml.splitlines():
        if line.strip().startswith("author_actor"):
            actor = line.split("=", 1)[1].split("#")[0].strip().strip('"')
    ev = [json.loads(l) for f in (v / "Fact Check" / "events").glob("*.jsonl")
          for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    dec = [e for e in ev if e.get("kind") == "decision.recorded" and e.get("actor") == actor]
    if len(dec) != 2:
        bad.append(f"expected 2 decision.recorded events by {actor}, got {len(dec)}")
    # 7
    a1, q1 = (v / "Fact Check" / "Asks.md").read_bytes(), q.read_bytes()
    T.run(v, "dashboard-sync.py", "answers", "--write")
    if (v / "Fact Check" / "Asks.md").read_bytes() != a1:
        bad.append("a second run changed Asks.md again")
    if q.read_bytes() != q1:
        bad.append("a second run queued the same back-fill press twice")

T.finish("dashboard-sync", bad,
         "dashboard-sync: build loads the ask with its line and only the works the library lacks; "
         "the reading queue gets the unread ones; "
         "the sample writes nothing; an answer moves its row with the author's words; one queue row "
         "and one event per press; a second run changes nothing")

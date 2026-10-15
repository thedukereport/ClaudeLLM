#!/usr/bin/env python3
"""prose_test.py — tools/prose.py on a copy of the sample vault.

Requires:
  1. with no audit on record, every open card with text is UNRUN and the run exits 1;
     the applied card is not listed;
  2. --record-card with fewer than fourteen principles records nothing;
  3. --record-card with all fourteen records one prose.audited event, and that card
     reads ok; --patch-dir writes {"proseCheck": {"ok": true, ...}} for it;
  4. after the card's paragraph is rewritten, the same card reads STALE;
  5. reflowing the paragraph (whitespace only) keeps the audit.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cardtest as T  # noqa: E402

FOURTEEN = ("agent-visibility", "verb-priority", "negation", "quantifier", "modal", "comparison",
            "emergence", "complex-equivalence", "mind-reading", "flourish", "telegraphing",
            "epistemic", "actor-verb-headings", "invented-person")

bad = []
with T.sample_copy() as v:
    # 1
    r = T.run(v, "prose.py", "--json")
    got = {x["card"]: x["state"] for x in T.rows(r)}
    if r.returncode != 1 or T.APPLIED in got or got.get(T.CHOICE) != "unrun":
        bad.append(f"first run: exit {r.returncode}, {got} {r.stderr[-300:]}")
    card = T.card_path(v, T.CHOICE)
    part = v / "part.json"
    part.write_text(json.dumps({k: "none" for k in FOURTEEN[:9]}), encoding="utf-8")
    full = v / "full.json"
    full.write_text(json.dumps({k: "none" for k in FOURTEEN}), encoding="utf-8")
    events = lambda: sum(1 for f in (v / "Fact Check" / "events").glob("*.jsonl")  # noqa: E731
                         for l in f.read_text(encoding="utf-8").splitlines() if '"prose.audited"' in l)
    # 2
    r = T.run(v, "prose.py", "--record-card", card, "--findings", part)
    if r.returncode != 2 or events() != 0:
        bad.append(f"a partial audit was recorded: {r.stdout[-300:]}")
    # 3
    patch = v / "patch"
    r = T.run(v, "prose.py", "--record-card", card, "--findings", full, "--patch-dir", patch)
    pc = json.loads((patch / f"{T.CHOICE}.json").read_text(encoding="utf-8"))["proseCheck"] \
        if (patch / f"{T.CHOICE}.json").exists() else {}
    if r.returncode != 0 or events() != 1 or not pc.get("ok"):
        bad.append(f"the full audit: exit {r.returncode}, {events()} events, {pc} {r.stdout[-300:]}{r.stderr[-300:]}")
    r = T.run(v, "prose.py", "--json")
    if {x["card"]: x["state"] for x in T.rows(r)}.get(T.CHOICE) != "audited":
        bad.append("the audited card does not read audited")
    d = json.loads(card.read_text(encoding="utf-8"))
    key = "reviewedPara" if d.get("reviewedPara") else "proposedPara"
    # 5
    T.edit_card(v, T.CHOICE, **{key: "  " + d[key].replace(" ", "\n", 1) + "  "})
    r = T.run(v, "prose.py", "--card", card)
    if r.returncode != 0:
        bad.append(f"a reflow made the audit stale: {r.stdout[-300:]}")
    # 4
    T.edit_card(v, T.CHOICE, **{key: d[key] + " One sentence more."})
    r = T.run(v, "prose.py", "--card", card, "--json")
    if r.returncode != 1 or [x["state"] for x in T.rows(r)] != ["stale"]:
        bad.append(f"a rewrite did not make the audit stale: {r.stdout[-300:]}")

T.finish("prose", bad,
         "prose: unaudited cards are listed and fail; a partial audit is refused; a full audit records "
         "one event and the card reads ok; a rewrite makes it stale; a reflow does not")

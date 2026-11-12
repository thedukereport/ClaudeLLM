#!/usr/bin/env python3
"""desk_audit.py — every page the author sees on the card desk, drawn and read the way he reads it.

    python3 tools/desk_audit.py              # the home page, each chapter page, each card he can rule on
    python3 tools/desk_audit.py --card <id>  # one card's page

WHOSE RULE THIS IS

    The author of the system this kit comes from, after a card reached his desk with asterisks, role names and a
    note code on it: "You never checked it, and you never built an agent that would make sure you checked it,
    either." This is the check. It draws each page with the desk's own code, sets aside the edit boxes (his words
    to edit) and the fold "What Claude is fixing" (Claude's), and reads the rest for what has no place on his page:

        asterisk    a * outside the edit boxes: the book's italics and bold are drawn, never shown as marks
        role        a role's name (Editor, Fact-checker, Production, Managing Editor, Systems, QA): a card says
                    what it does, not who did it
        path        a file path or a tool's name (tools/…, ….py, Fact Check/…, Handoffs/…)
        code        an event hash or a block id
        plumbing    a gate's or a mode's name ("card_reads", "refuse mode", "write-gate")

    `tools/cards.py release` runs it on the card it releases (book.toml [gates] card_desk_audit, "warn" or
    "refuse"). It exits 1 when any page has a fault.
"""
import html as H
import importlib.util
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

ROLE = re.compile(r"\b(?:Editor|Fact[- ]checker|Production|Managing Editor|Systems|QA)\b")
PATH = re.compile(r"\btools/\S+|\b[\w-]+\.(?:py|sh|jsonl?|md)\b|\b(?:Fact Check|Handoffs|Methodology)/\S*")
CODE = re.compile(r"\b[0-9a-f]{16}\b|\bblock [a-z0-9]{6}\b|<!--\s*b:")
PLUMBING = re.compile(r"\bcard_[a-z_]+\b|\b(?:refuse|warn) mode\b|\bwrite-gate\b|\bgate-mode\b")


def _desk():
    spec = importlib.util.spec_from_file_location("desk", TOOLS / "card-desk.py")
    d = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(d)
    return d


def visible(page_html):
    """The text the author reads: edit boxes, scripts, styles and Claude's fold set aside."""
    h = re.sub(r"<(script|style|textarea)[^>]*>.*?</\1>", " ", page_html, flags=re.S)
    h = re.sub(r"<details><summary>What Claude is fixing</summary>.*?</details>", " ", h, flags=re.S)
    h = re.sub(r"<nav>.*?</nav>", " ", h, flags=re.S)
    return H.unescape(re.sub(r"<[^>]+>", " ", h))


def faults(page_html):
    """[(kind, the words around it)]."""
    t = visible(page_html)
    out = []
    for kind, rx in (("asterisk", re.compile(r"\*")), ("role", ROLE), ("path", PATH), ("code", CODE),
                     ("plumbing", PLUMBING)):
        for m in rx.finditer(t):
            out.append((kind, re.sub(r"\s+", " ", t[max(0, m.start() - 40):m.end() + 40]).strip()))
    return out


def card_faults(card_id, rec=None):
    """The faults on one card's page as the author would see it; `rec`, a version not yet written, drawn in its place."""
    d = _desk()
    g = d.Gates()
    c = dict(g.folded.get(card_id) or {}, **(rec or {}))
    if not c:
        return [("missing", f"no card {card_id!r}")]
    c.setdefault("_version", 0)
    c["status"] = "yours" if (rec or {}).get("status") in (None, "held") else c.get("status")
    lane, why = g.lane(card_id, c)
    return faults(d.show_card(card_id, c, lane if lane != "claude" else "yours", [] if lane == "claude" else why))


def pages():
    """[(name, html)] for every page the author rules from."""
    d = _desk()
    g = d.Gates()
    rows = d.ordered(g)
    out = [("/", d.route("/", {})[0])]
    for n in sorted({d.cards.chapter_of(r[2]) for r in rows if r[0] in ("yours", "reopen")} - {None}):
        out.append((f"/chapter/{n}", d.route(f"/chapter/{n}", {})[0]))
    for lane, cid, c, why in rows:
        if lane in ("question", "reopen", "yours", "approving"):
            out.append((f"/card/{cid}", d.show_card(cid, c, lane, why)))
    return out


def main(argv):
    if "--card" in argv:
        cid = argv[argv.index("--card") + 1]
        got = [(f"/card/{cid}", card_faults(cid))]
    else:
        got = [(name, faults(h)) for name, h in pages()]
    n = 0
    for name, fs in got:
        for kind, ctx in fs:
            n += 1
            print(f"{name:<40} {kind:<9} …{ctx}…")
    print(f"\n{n} fault(s) on {len(got)} page(s) the author reads.")
    return 1 if n else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

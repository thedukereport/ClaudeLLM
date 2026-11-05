#!/usr/bin/env python3
"""card-desk.py — the one place the author rules on a card. One card, one screen.

    python3 tools/card-desk.py              # serves http://127.0.0.1:8766 (book.toml [desk] port)
    python3 tools/card-desk.py --port 8767
    python3 tools/card-desk.py --check      # draws every page once and exits: the smoke test

    /                 the next card for the author, in the order below
    /?after=<id>      the card after that one
    /card/<id>        any card, whatever its lane, with its older versions in a fold
    /lane/<name>      every card in one lane
    /all              every card, by lane, each with the reason it is there
    /asks             the open asks in Fact Check/Asks.md, one at a time, with ok / no / words
    /sources          the works no shelf has, for the author to get
    /healthz          "ok"

WHY A SERVER OF ITS OWN

    The system this kit comes from first kept its cards on a claude.ai page with
    a database. No script could open the page, so every gate worked from a
    snapshot a chat had copied, and a press the author made after the snapshot
    was invisible to the tools. The author's ruling: "Build the card surface as
    a small server of its own ... One queue still holds: the cards live in one
    place and I rule in one place." The cards live in `Fact Check/Cards/
    cards.jsonl` (`tools/cards.py`); this server reads them, runs every gate on
    each card it draws, and records each press in the event log.

THE LANES, IN THE ORDER THE AUTHOR WORKS THEM

    Reopen?           a card that changes a line the author already approved
                      (`tools/check-card-closed.py`), shown whole, with "Reopen
                      this line" and "Keep it closed". A wrong line comes back as
                      a card; it comes back here.
    Waiting for you   a new card whose every gate passes: Approve, Send my edits
                      for checking, This is a directive, Save my words.
    Approved, going in   approved and not yet in the book: Withdraw my approval.
    In the book       applied: Take a second look.
    With Claude       the author sent edits or a directive (Claude checks and
                      writes a new version), or a gate holds the card, or its
                      owner held it. Shown with each reason and no Approve. The
                      author sees only cards that are ready; this lane is where
                      the others wait.

THE GATES, RUN ON EACH CARD AS IT IS DRAWN (none of them is a stored verdict)

    words    no banned word in the text the author would approve (check-card-words.py)
    reads    every name, number, date and quotation has an opened, logged read (card_reads.py)
    notes    a footnote the author's rules send back (check-card-notes.py)
    prose    the neurolinguistic-prose audit of this exact text, by a second session (prose.py)
    refresh  its lines and neighbours read as the chapter does now (card_refresh.py)
    checked  the text in the box is the text Claude checked (reviewedPara = proposedPara)
    closed   the card meets a line the author approved: the Reopen? lane (check-card-closed.py)

HIS PRESSES

    POST /press. Each press is one `decision.recorded` event: actor = book.toml
    [book] author_actor, the card's id and the version on the author's screen,
    `decision_kind` approve | edit | directive | card-note | withdraw | reopen |
    keep_closed, and the author's words verbatim. `tools/cards.py fold` reads
    them. A press the desk refuses (the card has a newer version, the lane does
    not offer that button, a press that needs words has none) is recorded as a
    `press.refused` event, with the reason and every word typed, and the card
    comes back on screen with the reason. A POST from any page but the desk's
    own is refused and recorded nowhere: it is no press of the author's.

THE AUTHOR'S UNSAVED WORDS

    Each keystroke in a box is kept in this browser (localStorage `desk-drafts`,
    fourteen days) under the card, its version and the box, and goes back into
    the box after a reload, with an "Unsaved draft" mark. When Claude has
    written a newer version since, the draft is shown beside the box, never
    poured over the newer text. A draft clears when a press on that card is
    recorded. Typed words are no ruling, and no draft reaches the log.
"""
import html
import importlib.util
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import bookconfig as B  # noqa: E402
import cards  # noqa: E402

SEP = "\n\n⁂\n\n"
LANES = ("reopen", "yours", "approved", "applied", "claude")
LANE_NAME = {"reopen": "Reopen?", "yours": "Waiting for you", "approved": "Approved, going in",
             "applied": "In the book", "claude": "With Claude", "closed": "Closed"}
BUTTONS = {
    "yours": ("approve", "edit", "directive", "card-note"),
    "reopen": ("reopen", "keep_closed", "card-note"),
    "approved": ("withdraw", "card-note"),
    "applied": ("reopen", "card-note"),
    "claude": ("card-note",),
    "closed": (),
}
LABEL = {"approve": "Approve for the chapter", "edit": "Send my edits for checking",
         "directive": "This is a directive", "card-note": "Save my words", "withdraw": "Withdraw my approval",
         "reopen": "Reopen this line", "keep_closed": "Keep it closed"}
NEEDS_WORDS = ("directive", "card-note")


def _mod(name, file):
    spec = importlib.util.spec_from_file_location(name, TOOLS / file)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Gates:
    """Every gate, loaded once per request so each sees the files as they are now."""

    def __init__(self):
        import card_reads
        import card_refresh
        import prose
        self.reads, self.refresh, self.prose = card_reads, card_refresh, prose
        self.words = _mod("ccw", "check-card-words.py")
        self.notes = _mod("ccn", "check-card-notes.py")
        self.closed_mod = _mod("ccc", "check-card-closed.py")
        self.rulings = self.notes.last_rulings()
        self.audits = prose.audits()
        self.folded = cards.fold()
        self.book = self.closed_mod.Book()
        snap = [dict(c, id=cid) for cid, c in self.folded.items()]
        self.closed = self.closed_mod.closed_set(snap, self.book)
        self.bodies = {}

    def body(self, ch):
        if ch not in self.bodies:
            self.bodies[ch] = self.refresh._body(ch)
        return self.bodies[ch]

    def holds(self, cid, c):
        """[reason] that keep the card off the author's desk, each in words."""
        out = []
        c = dict(c, id=cid)
        for h in self.words.card_hits(c):
            out.append(f"banned word {h['word']!r} in {h['field']}: …{h['context']}…")
        miss = self.reads.unread_facts(c)
        if miss:
            out.append(f"{len(miss)} fact(s) with no opened read in Fact Check/Claims/: "
                       + "; ".join(f"{k} “{v[:60]}”" for k, v in miss[:8]) + ("; …" if len(miss) > 8 else ""))
        r = self.notes.check_card(cid, c, self.rulings)
        if r and not r["ok"]:
            out += [f"note [^{f['slug']}] {f['pile']}: {f['why']}" for f in r["findings"]]
        p = self.prose.prose_check(cid, c, self.audits)
        if not p["ok"]:
            out.append({"unrun": "no prose audit of this text yet", "stale": "the prose audit is of older words",
                        "self-audited": "only the session that wrote it has audited its prose; a second session audits it",
                        "finding": "the second session's prose audit found a fault; a new version is due"
                        }.get(p["state"], f"prose audit: {p['state']}"))
        ch = cards.chapter_of(c)
        if ch is not None:
            a = self.refresh.assess(c, self.body(ch))
            if a["action"] != "ok":
                out.append(f"it no longer reads as the chapter does: {a['why']}")
        if c.get("reviewedPara") is not None and c.get("reviewedPara") != c.get("proposedPara"):
            out.append("the text in the box differs from the text Claude checked")
        return out

    def reopen(self, cid, c):
        r = self.closed_mod.check_card(cid, dict(c, id=cid), self.book, self.closed)
        if not r or r["ok"] or c.get("lineKeptAt") and c.get("lineKeptText") == (c.get("reviewedPara") or c.get("proposedPara")):
            return []
        return [f"{f['where']}: " + "; ".join(x["said"] for x in f["closedBy"]) for f in r["findings"]]

    def lane(self, cid, c):
        """(lane, [reasons])."""
        st = c.get("status")
        if cards.locked(c):
            return "closed", [cards.locked(c)]
        if st == "applied":
            return "applied", []
        if st == "approved":
            return "approved", []
        if st == "superseded":
            return "closed", [c.get("closedReason") or "superseded"]
        if st == "held":
            return "claude", [f"held by {c.get('heldBy')}: {c.get('heldReason')}"] + list(c.get("heldFacts") or [])
        if st == "submitted":
            why = "you sent a directive" if c.get("directiveAt") else "you sent edits"
            return "claude", [f"{why}; Claude checks them and writes a new version"]
        holds = self.holds(cid, c)
        if holds:
            return "claude", holds
        kept = self.reopen(cid, c)
        if kept:
            return "reopen", kept
        return "yours", []


def esc(s):
    return html.escape(str(s or ""), quote=True)


CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a65;--line:#d9d6cf;--box:#fff;--accent:#2f5d8a;--warn:#9a5b00;--ok:#2e6b3a;--bad:#a12d2d}
@media (prefers-color-scheme:dark){:root{--bg:#1b1b1a;--fg:#ecebe6;--muted:#a3a29c;--line:#3a3936;--box:#242422;--accent:#8db4dc;--warn:#e0a85a;--ok:#86c493;--bad:#e78a8a}}
body{background:var(--bg);color:var(--fg);font:16px/1.55 Georgia,serif;margin:0 auto;max-width:880px;padding:16px}
nav a{margin-right:14px;color:var(--accent)} h1{font-size:1.35em} h2{font-size:1.05em;margin-top:1.6em;color:var(--muted)}
.text{white-space:pre-wrap;background:var(--box);border:1px solid var(--line);padding:10px 12px;border-radius:4px}
.ctx{color:var(--muted)} textarea{width:100%;min-height:9em;font:inherit;background:var(--box);color:var(--fg);border:1px solid var(--line);padding:8px;box-sizing:border-box}
textarea.draft{border:2px solid var(--warn)} .badge{color:var(--warn);font-size:.85em}
button{font:inherit;margin:6px 8px 0 0;padding:6px 12px;border:1px solid var(--accent);background:var(--box);color:var(--accent);border-radius:4px;cursor:pointer}
button.primary{background:var(--accent);color:var(--bg)} .why li{color:var(--warn)} .msg{border-left:4px solid var(--ok);padding:6px 10px}
.msg.bad{border-color:var(--bad)} table{border-collapse:collapse;width:100%} td{border-bottom:1px solid var(--line);padding:4px 6px;vertical-align:top}
details{margin-top:1em} small{color:var(--muted)}
"""

DRAFT_JS = """
<script>
(function(){
  var KEY='desk-drafts', DAY=864e5, all={};
  try{all=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){all={}}
  var now=Date.now(); Object.keys(all).forEach(function(k){if(now-(all[k].t||0)>14*DAY)delete all[k]});
  function save(){try{localStorage.setItem(KEY,JSON.stringify(all))}catch(e){}}
  document.querySelectorAll('textarea[data-draft]').forEach(function(box){
    var k=box.getAttribute('data-draft'), base=box.value, d=all[k];
    if(d&&d.base===base&&d.text!==base){box.value=d.text;box.classList.add('draft');
      var b=document.createElement('div');b.className='badge';b.textContent='Unsaved draft';box.parentNode.insertBefore(b,box)}
    var older=Object.keys(all).filter(function(o){return o!==k&&o.split('|')[0]===k.split('|')[0]&&o.split('|')[2]===k.split('|')[2]&&all[o].text!==all[o].base});
    older.forEach(function(o){var p=document.createElement('details');p.innerHTML='<summary class="badge">Your unsaved words on an older version</summary>';
      var q=document.createElement('div');q.className='text';q.textContent=all[o].text;p.appendChild(q);box.parentNode.appendChild(p)});
    box.addEventListener('input',function(){all[k]={base:base,text:box.value,t:Date.now()};box.classList.add('draft');save()});
  });
  document.querySelectorAll('form[data-card]').forEach(function(f){f.addEventListener('submit',function(){
    var c=f.getAttribute('data-card'); Object.keys(all).forEach(function(k){if(k.split('|')[0]===c)delete all[k]}); save()})});
})();
</script>
"""


def page(title, body):
    nav = ("<nav><a href='/'>Next card</a><a href='/lane/yours'>Waiting for you</a><a href='/lane/reopen'>Reopen?</a>"
           "<a href='/lane/approved'>Approved</a><a href='/lane/claude'>With Claude</a><a href='/asks'>Asks</a>"
           "<a href='/sources'>Sources to get</a><a href='/all'>All</a></nav>")
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)} — {esc(B.TITLE)}</title><style>{CSS}</style></head><body>{nav}{body}{DRAFT_JS}</body></html>")


def show_card(cid, c, lane, why, msg=""):
    v = c["_version"]
    out = [f"<p><small>{esc(LANE_NAME[lane])} · {esc(c.get('chapter'))} · {esc(c.get('where'))} · version {v}</small></p>",
           f"<h1>{esc(c.get('title'))}</h1>"]
    if msg:
        bad = msg.startswith("REFUSED")
        out.append(f"<div class='msg{' bad' if bad else ''}'>{esc(msg)}</div>")
    if why:
        out.append("<h2>Why it is here</h2><ul class='why'>" + "".join(f"<li>{esc(w)}</li>" for w in why) + "</ul>")
    if c.get("job"):
        out.append(f"<h2>The paragraph's job</h2><p>{esc(c.get('job'))}</p>")
    if c.get("before"):
        out.append(f"<h2>The paragraph above</h2><div class='text ctx'>{esc(c.get('before'))}</div>")
    out.append("<h2>Current, as in the chapter now</h2>")
    for seg in c.get("current") or []:
        if isinstance(seg, dict):
            out.append(f"<p><small>{esc(seg.get('where'))}</small></p><div class='text'>{esc(seg.get('text'))}</div>")
    proposed = c.get("proposedPara") or ""
    if c.get("after"):
        after_html = f"<h2>The paragraph below</h2><div class='text ctx'>{esc(c.get('after'))}</div>"
    else:
        after_html = ""
    btns = BUTTONS[lane]
    out.append("<h2>Proposed, as it would read</h2>")
    if "edit" in btns:
        out.append(f"<form method='post' action='/press' data-card='{esc(cid)}'>"
                   f"<input type='hidden' name='card' value='{esc(cid)}'><input type='hidden' name='version' value='{v}'>"
                   f"<textarea name='text' data-draft='{esc(cid)}|{v}|para'>{esc(proposed)}</textarea>")
        if c.get("proposedNote") and not c.get("noteless"):
            out.append(f"<p><small>The footnote</small></p><textarea name='note' data-draft='{esc(cid)}|{v}|note'>"
                       f"{esc(c.get('proposedNote'))}</textarea>")
        out.append(f"<button class='primary' name='kind' value='approve'>{LABEL['approve']}</button>"
                   f"<button name='kind' value='edit'>{LABEL['edit']}</button></form>")
    else:
        out.append(f"<div class='text'>{esc(proposed)}</div>")
        if c.get("proposedNote") and not c.get("noteless"):
            out.append(f"<div class='text'>{esc(c.get('proposedNote'))}</div>")
    out.append(after_html)
    if c.get("changes"):
        out.append("<h2>What changes</h2><ul>" + "".join(
            f"<li>{esc(x if not isinstance(x, dict) else (x.get('what') or json.dumps(x, ensure_ascii=False)))}</li>"
            for x in c["changes"]) + "</ul>")
    if c.get("review"):
        out.append(f"<h2>Claude's check against the source</h2><p>{esc(c.get('review'))}</p>")
    if c.get("note"):
        out.append(f"<h2>Your words on this card</h2><div class='text'>{esc(c.get('note'))}</div>")
    rest = [b for b in btns if b not in ("approve", "edit")]
    if rest:
        out.append(f"<h2>Your words to the Editor</h2><form method='post' action='/press' data-card='{esc(cid)}'>"
                   f"<input type='hidden' name='card' value='{esc(cid)}'><input type='hidden' name='version' value='{v}'>"
                   f"<textarea name='text' data-draft='{esc(cid)}|{v}|words' style='min-height:5em'></textarea>"
                   + "".join(f"<button name='kind' value='{b}'>{LABEL[b]}</button>" for b in rest) + "</form>")
    olds = cards.versions(cid)[:-1]
    if olds:
        out.append(f"<details><summary>Older versions ({len(olds)})</summary>" + "".join(
            f"<p><small>v{o['version']}, {esc(o['at'])}, by {esc(o.get('by'))}</small></p>"
            f"<div class='text'>{esc((o.get('card') or {}).get('proposedPara'))}</div>" for o in reversed(olds))
            + "</details>")
    out.append(f"<p><a href='/?after={quote(cid)}'>Next card →</a></p>")
    return "".join(out)


def ordered(g):
    """[(lane, id, card, reasons)] in the order the author works them."""
    rows = []
    for cid, c in g.folded.items():
        lane, why = g.lane(cid, c)
        rows.append((lane, cid, c, why))
    rank = {l: i for i, l in enumerate(LANES + ("closed",))}
    rows.sort(key=lambda r: (rank[r[0]], cards.chapter_of(r[2]) or 999, r[1]))
    return rows


def asks_rows():
    p = B.DESK_LOAD / "asks.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def backlog_rows():
    p = B.DESK_LOAD / "backlog.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def answered(view):
    import vaultlog
    return {e.get("desk_id") for e in vaultlog.fold("decision.recorded", desk_view=view)
            if e.get("actor") == B.AUTHOR_ACTOR}


def asks_page(msg=""):
    rows, done = asks_rows(), answered("asks")
    out = ["<h1>Asks</h1>", f"<div class='msg'>{esc(msg)}</div>" if msg else "",
           f"<p><small>Built by tools/dashboard-sync.py build from {esc(cards.rel(B.ASKS))}. "
           f"Your answer goes to the event log; dashboard-sync.py answers --write moves the row to Answered.</small></p>"]
    for r in rows:
        aid, d = r["id"], r["data"]
        if aid in done:
            continue
        out.append(f"<h2>{esc(aid)} · {esc(d.get('kind'))}</h2><div class='text'>{esc(d.get('ask'))}</div>")
        for k, label in (("before", "The paragraph above"), ("current", "The line"), ("after", "The paragraph below")):
            if d.get(k):
                out.append(f"<p><small>{label}</small></p><div class='text ctx'>{esc(d.get(k))}</div>")
        if d.get("silence"):
            out.append(f"<p><small>If you say nothing: {esc(d.get('silence'))}</small></p>")
        out.append(f"<form method='post' action='/answer'><input type='hidden' name='view' value='asks'>"
                   f"<input type='hidden' name='id' value='{esc(aid)}'>"
                   f"<textarea name='text' data-draft='ask-{esc(aid)}|0|words' style='min-height:4em'></textarea>"
                   f"<button class='primary' name='answer' value='ok'>ok</button><button name='answer' value='no'>no</button>"
                   f"<button name='answer' value=''>Send my words</button></form>")
    if len(out) == 3:
        out.append("<p>No open ask.</p>")
    return "".join(out)


ACTIONS = {"get": "I'll get it", "exception": "Approve citing it unread", "skip": "Skip for now"}


def sources_page(msg=""):
    rows, done = backlog_rows(), answered("backlog")
    out = ["<h1>Sources to get</h1>", f"<div class='msg'>{esc(msg)}</div>" if msg else "",
           "<p><small>Works the footnotes cite that no shelf in your library holds. A work on the shelf that nobody "
           "has read never comes here: it goes to the Fact-checker's reading queue.</small></p>"]
    for r in rows:
        bid, d = r["id"], r["data"]
        if bid in done:
            continue
        out.append(f"<h2><i>{esc(d.get('title'))}</i></h2><p><small>cited in {esc(d.get('chapters'))}, "
                   f"{esc(d.get('cites'))} time(s)</small></p>")
        for x in d.get("current") or []:
            out.append(f"<div class='text ctx'>{esc(x.get('where'))}: {esc(x.get('text'))}</div>")
        out.append(f"<form method='post' action='/answer'><input type='hidden' name='view' value='backlog'>"
                   f"<input type='hidden' name='id' value='{esc(bid)}'>"
                   f"<textarea name='text' data-draft='bf-{esc(bid)}|0|words' style='min-height:3em'></textarea>"
                   + "".join(f"<button name='action' value='{k}'>{esc(v)}</button>" for k, v in ACTIONS.items())
                   + "</form>")
    if len(out) == 3:
        out.append("<p>No work waits on you.</p>")
    return "".join(out)


def record_press(form):
    """(ok, message). One decision.recorded event, or one press.refused event."""
    import vaultlog
    cid = (form.get("card") or [""])[0]
    kind = (form.get("kind") or [""])[0]
    text = (form.get("text") or [""])[0].replace("\r\n", "\n")
    note = form.get("note", [None])[0]
    try:
        version = int((form.get("version") or ["0"])[0])
    except ValueError:
        version = 0

    def refuse(why):
        vaultlog.append("press.refused", actor=B.AUTHOR_ACTOR, card=cid, card_version=version,
                        decision_kind=kind, reason=why, text=text, note=note)
        return False, f"REFUSED, and recorded: {why}. Your words are kept on the card's record."

    g = Gates()
    c = g.folded.get(cid)
    if c is None:
        return refuse(f"no card {cid!r}")
    if version != c["_version"]:
        return refuse(f"you saw version {version}; Claude has written version {c['_version']} since")
    lane, _ = g.lane(cid, c)
    if kind not in BUTTONS[lane]:
        return refuse(f"the {LANE_NAME[lane]} lane offers no {LABEL.get(kind, kind)!r}")
    if kind in NEEDS_WORDS and not text.strip():
        return refuse(f"{LABEL[kind]!r} needs your words, and the box was empty")
    proposed = c.get("proposedPara") or ""
    if kind == "approve" and text.strip() and text.strip() != proposed.strip():
        return refuse("you changed the text in the box: Approve takes only the text Claude checked. "
                      "Press 'Send my edits for checking' to send your words")
    if kind == "edit" and text.strip() == proposed.strip() and (note is None or note == (c.get("proposedNote") or "")):
        return refuse("the box holds the text as Claude wrote it; there are no edits to send")
    payload = {"card": cid, "card_version": version, "decision_kind": kind, "lane": lane}
    if kind in ("edit", "directive", "card-note", "reopen", "keep_closed") and text.strip():
        payload["text"] = text
    if kind == "edit" and note is not None:
        payload["note"] = note
    if kind == "reopen":
        payload["what"] = "applied" if lane == "applied" else "line"
    e = vaultlog.append("decision.recorded", actor=B.AUTHOR_ACTOR,
                        why=f"the author's press on the card desk: {LABEL[kind]}", **payload)
    return True, f"Recorded: {LABEL[kind]} (event {e['hash']})."


def record_answer(form):
    import vaultlog
    view = (form.get("view") or [""])[0]
    rid = (form.get("id") or [""])[0]
    text = (form.get("text") or [""])[0].replace("\r\n", "\n").strip()
    if view == "asks":
        row = next((r for r in asks_rows() if r["id"] == rid), None)
        answer = (form.get("answer") or [""])[0]
        if row is None or (not answer and not text):
            vaultlog.append("press.refused", actor=B.AUTHOR_ACTOR, desk_view=view, desk_id=rid, text=text,
                            reason="no such open ask" if row is None else "no answer and no words")
            return f"REFUSED, and recorded: {'no such open ask' if row is None else 'an answer needs ok, no or your words'}."
        e = vaultlog.append("decision.recorded", actor=B.AUTHOR_ACTOR, desk_view="asks", desk_id=rid, sheet="Asks",
                            item=rid, answer=answer, text=text, decision_kind="answer",
                            why="the author's answer on the card desk, Asks")
        return f"Recorded your answer to {rid} (event {e['hash']})."
    if view == "backlog":
        row = next((r for r in backlog_rows() if r["id"] == rid), None)
        action = (form.get("action") or [""])[0]
        if row is None or action not in ACTIONS:
            vaultlog.append("press.refused", actor=B.AUTHOR_ACTOR, desk_view=view, desk_id=rid, text=text,
                            reason="no such work" if row is None else "no such button")
            return "REFUSED, and recorded."
        d = row["data"]
        e = vaultlog.append("decision.recorded", actor=B.AUTHOR_ACTOR, desk_view="backlog", desk_id=rid,
                            sheet="Back-fill", item=d.get("title"), title=d.get("title"), chapters=d.get("chapters"),
                            lane=d.get("lane"), action=action, text=text, decision_kind="source",
                            why="the author's press on the card desk, Sources to get")
        return f"Recorded: {ACTIONS[action]} (event {e['hash']})."
    return "REFUSED: no such view."


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        msg = (q.get("msg") or [""])[0]
        try:
            self._send(200, *route(u.path, q, msg)) if u.path != "/healthz" else self._send(200, "ok", "text/plain")
        except LookupError as e:
            self._send(404, page("Not found", f"<p>{esc(e)}</p>"))

    def do_POST(self):
        origin = self.headers.get("Origin") or self.headers.get("Referer") or ""
        host = self.headers.get("Host") or ""
        if not origin or urlparse(origin).netloc != host:
            self._send(403, "A press comes only from the card desk's own pages.", "text/plain")
            return
        n = int(self.headers.get("Content-Length") or 0)
        form = parse_qs(self.rfile.read(n).decode("utf-8"), keep_blank_values=True)
        u = urlparse(self.path)
        if u.path == "/press":
            _ok, msg = record_press(form)
            where = f"/card/{quote((form.get('card') or [''])[0])}"
        elif u.path == "/answer":
            msg = record_answer(form)
            where = "/asks" if (form.get("view") or [""])[0] == "asks" else "/sources"
        else:
            self._send(404, "no such form", "text/plain")
            return
        self.send_response(303)
        self.send_header("Location", f"{where}?msg={quote(msg)}")
        self.end_headers()


def route(path, q, msg=""):
    if path == "/asks":
        return (page("Asks", asks_page(msg)),)
    if path == "/sources":
        return (page("Sources to get", sources_page(msg)),)
    g = Gates()
    rows = ordered(g)
    if path.startswith("/card/"):
        cid = unquote(path[len("/card/"):])
        r = next((r for r in rows if r[1] == cid), None)
        if r is None:
            raise LookupError(f"no card {cid!r}")
        return (page(r[2].get("title") or cid, show_card(cid, r[2], r[0], r[3], msg)),)
    if path.startswith("/lane/") or path == "/all":
        want = path[len("/lane/"):] if path.startswith("/lane/") else None
        if want and want not in LANE_NAME:
            raise LookupError(f"no lane {want!r}")
        out = [f"<h1>{esc(LANE_NAME[want]) if want else 'Every card'}</h1><table>"]
        for lane, cid, c, why in rows:
            if want and lane != want:
                continue
            out.append(f"<tr><td>{esc(LANE_NAME[lane])}</td><td><a href='/card/{quote(cid)}'>{esc(c.get('title'))}</a>"
                       f"<br><small>{esc(c.get('where'))}</small>"
                       + (f"<br><small>{esc('; '.join(str(w) for w in why)[:300])}</small>" if why else "")
                       + "</td></tr>")
        out.append("</table>")
        return (page(LANE_NAME[want] if want else "All", "".join(out)),)
    if path == "/":
        after = (q.get("after") or [""])[0]
        mine = [r for r in rows if r[0] in ("reopen", "yours")]
        if after:
            ids = [r[1] for r in mine]
            mine = mine[ids.index(after) + 1:] if after in ids else mine
        if not mine:
            counts = {}
            for r in rows:
                counts[r[0]] = counts.get(r[0], 0) + 1
            return (page("Nothing waiting", "<h1>No card waits on you.</h1><p>"
                         + ", ".join(f"{LANE_NAME[k]}: {v}" for k, v in counts.items()) + "</p>"),)
        lane, cid, c, why = mine[0]
        return (page(c.get("title") or cid, show_card(cid, c, lane, why, msg)),)
    raise LookupError(f"no page {path!r}")


def main(argv):
    port = int(argv[argv.index("--port") + 1]) if "--port" in argv else B.DESK_PORT
    if "--check" in argv:
        g = Gates()
        rows = ordered(g)
        for p in ["/", "/all", "/asks", "/sources"] + [f"/lane/{l}" for l in LANES] + [f"/card/{quote(r[1])}" for r in rows]:
            route(urlparse(p).path, {})
        lanes = {}
        for r in rows:
            lanes[LANE_NAME[r[0]]] = lanes.get(LANE_NAME[r[0]], 0) + 1
        print(f"card desk: {len(rows)} card(s) drawn — " + (", ".join(f"{k} {v}" for k, v in lanes.items()) or "none"))
        return 0
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"card desk on http://127.0.0.1:{port}  (cards: {cards.rel(B.CARD_STORE)})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

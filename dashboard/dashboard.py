#!/usr/bin/env python3
"""
Reframing Reality — Local Manuscript Dashboard

Run from the vault root:
    python3 dashboard.py

Then open http://127.0.0.1:8765 in any browser.

What it shows:
    - Live word counts pulled from Chapters/ and Appendices/ on every request
    - Lock / Deferred status parsed from Book Structure.md headings
    - Last-modified time per chapter
    - Stacked progress bar across all chapters
    - Click a chapter title to open the file in your default markdown app

Press Ctrl-C in the terminal to stop the server.
"""

import http.server
import os
import re
import socketserver
import subprocess
import sys
import datetime
from pathlib import Path
from html import escape
from urllib.parse import quote, parse_qs

VAULT_ROOT = Path(__file__).resolve().parent
CHAPTERS_DIR = VAULT_ROOT / "Chapters"
APPENDICES_DIR = VAULT_ROOT / "Appendices"
BOOK_STRUCTURE = VAULT_ROOT / "Book Structure.md"
PUNCH_LIST = VAULT_ROOT / "Punch List.md"
PROJECT_STATE = VAULT_ROOT / "Project State.md"
FACT_CHECK_DIR = VAULT_ROOT / "Fact Check"

# Local Servers panel — engine lives in the `servers` bash wrapper next to this file.
SERVERS_SCRIPT = VAULT_ROOT / "servers"
LOG_DIR = Path.home() / "Library" / "Logs" / "RR"
PID_DIR = Path("/tmp")
PROBLADE_ALEXANDRIA = Path("/Volumes/PRO-BLADE/Alexandria")

# PDF Publish workflow — uses pandoc + xelatex + DejaVu Serif (handles polytonic
# Greek and Hebrew glyphs in chapter content and lexicon entries). See
# publish-pdfs.sh for the publish workflow:
#   ./publish-pdfs.sh            # publish all chapters + appendices
#   ./publish-pdfs.sh ch 23      # publish Ch. 23 only
#   ./publish-pdfs.sh app F      # publish Appendix F only
PUBLISH_SCRIPT = VAULT_ROOT / "publish-pdfs.sh"
DROPBOX_REVIEW = Path("/Volumes/G-RAID MIRROR/Dropbox/Reframing Reality Draft For Review")

# Greek Server — local Perseus/TLG + Greek-NT + LXX + LSJ corpus on PRO-BLADE.
# PRIMARY source for any Greek primary text (NT, classical, patristic, LXX).
# See feedback_greek_server_use_first.md memory + the README.md inside the
# directory itself, plus Methodology/Greek-Server-Reference.md in the vault.
GREEK_RESOURCES = PROBLADE_ALEXANDRIA / "Greek-resources"
GREEK_LOOKUP_SCRIPT = GREEK_RESOURCES / "greek_lookup.py"
GREEK_README = GREEK_RESOURCES / "README.md"
GREEK_LSJ_INDEX = GREEK_RESOURCES / "lsj-index.json"
GREEK_TAGNT_INDEX = GREEK_RESOURCES / "tagnt-index.json"
GREEK_VAULT_DOC = VAULT_ROOT / "Methodology" / "Greek-Server-Reference.md"

# Service registry — mirrors the bash wrapper. Keep these two in sync.
# port:        TCP port, or "stdio", or None
# controllable: whether this dashboard can start/stop it
# note:        one-line description
SERVICES = [
    {
        "name": "rag-ui",
        "port": 5050,  # moved off 5000 (AirPlay Receiver) 2026-07-02
        "controllable": True,
        "note": "Alexandria RAG Web UI",
        "open_url": "http://127.0.0.1:5050",
    },
    # MCP servers — launched on demand by Claude Desktop / Cowork over stdio.
    # Registered in the Claude Desktop config's "mcpServers"; this dashboard
    # only reports them (it can't start/stop what Claude Desktop owns).
    {
        "name": "rag-mcp",
        "port": "stdio",
        "controllable": False,
        "note": "Alexandria RAG — MCP (managed by Claude Desktop / Cowork)",
        "open_url": None,
    },
    {
        "name": "greek-mcp",
        "port": "stdio",
        "controllable": False,
        "note": "Greek Resources — MCP (managed by Claude Desktop / Cowork)",
        "open_url": None,
    },
    {
        "name": "latin-mcp",
        "port": "stdio",
        "controllable": False,
        "note": "Latin Resources — MCP, Perseus TEI corpus (managed by Claude Desktop / Cowork)",
        "open_url": None,
    },
    {
        "name": "perseus-mcp",
        "port": "stdio",
        "controllable": False,
        "note": "Perseus Canonical — MCP, complete greekLit+latinLit, 156 authors / 2,299 texts (managed by Claude Desktop / Cowork)",
        "open_url": None,
    },
    {
        "name": "wikispooks-mcp",
        "port": "stdio",
        "controllable": False,
        "note": "WikiSpooks — MCP, full wiki ~37.7k articles (managed by Claude Desktop / Cowork)",
        "open_url": None,
    },
    {
        "name": "pleiades-mcp",
        "port": "stdio",
        "controllable": False,
        "note": "Pleiades — MCP, ancient places gazetteer (managed by Claude Desktop / Cowork)",
        "open_url": None,
    },
    {
        "name": "wikipedia-mcp",
        "port": "stdio",
        "controllable": False,
        "note": "Wikipedia — MCP, offline Kiwix ZIM (managed by Claude Desktop / Cowork)",
        "open_url": None,
    },
    {
        "name": "scriptures-mcp",
        "port": "stdio",
        "controllable": False,
        "note": "Scriptures — MCP, Qur'an/Enoch/Tanakh/Talmud/Mishnah + Ethiopian (Tewahedo) canon (managed by Claude Desktop / Cowork)",
        "open_url": None,
    },
    {
        "name": "gutenberg-mcp",
        "port": "stdio",
        "controllable": False,
        "note": "Project Gutenberg — MCP, public-domain books by LCC subject (managed by Claude Desktop / Cowork)",
        "open_url": None,
    },
    {
        "name": "papyri-mcp",
        "port": "stdio",
        "controllable": False,
        "note": "Papyri (DDbDP) — MCP, ~67.6k documentary papyri, CC BY (managed by Claude Desktop / Cowork)",
        "open_url": None,
    },
    # Port-based background services.
    {
        "name": "rr-dash",
        "port": 8765,
        "controllable": False,
        "note": "This dashboard (won't kill itself)",
        "open_url": "http://127.0.0.1:8765",
    },
]

PORT = 8765
HOST = "127.0.0.1"

# Auto-reload: track the script's mtime at startup. When a request comes in and
# the script has been modified, the server re-execs itself so the next refresh
# picks up the new code. Data files (chapters, Book Structure, Punch List) are
# already read fresh on every request, so this only matters for edits to
# dashboard.py itself.
_SCRIPT_PATH = Path(__file__).resolve()
_SCRIPT_MTIME = _SCRIPT_PATH.stat().st_mtime


# ---------- data ----------


def count_words(path: Path) -> int:
    """Word count for a markdown file. Strips footnote definitions and code fences."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^\[\^[^\]]+\]:.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return len(text.split())


def count_footnotes(path: Path) -> tuple[int, int]:
    """Returns (footnote_count, footnote_word_count) for a markdown file.
    Footnote count = number of distinct [^name]: definitions.
    Footnote word count = words in the definition text (after the [^name]: prefix).
    """
    text = path.read_text(encoding="utf-8")
    defs = re.findall(r"^\[\^[^\]]+\]:\s*(.*)$", text, flags=re.MULTILINE)
    count = len(defs)
    words = sum(len(d.split()) for d in defs)
    return count, words


def parse_lock_status() -> dict:
    """Parse status markers from Book Structure (primary) and the Punch List status
    table (secondary). Book Structure headings win where both sources have an entry.
    Returns: {chapter_number: (status_label, date)}.

    The Book Structure heading conventions have drifted over time; this parser is
    tolerant of every format actually observed in the vault:
        ### Chapter 15: The Game Theory of Governance 🔒
        ### Chapter 17: The Alternate Reality Game 🔒🔒 *(LOCKED 2026-06-24 — ...)*
        ### Chapter 14: A Mind Control Survey ... 🔒 RE-LOCKED 2026-06-01 ...
        ### Chapter 23: The Paradox of Perception ✅ *(Renamed 2026-06-27 ...)*
        ### Chapter 24: The Phantom Cell ✅ *(Spec-complete 2026-06-26; drafted and audited through 2026-07-02. ...)*

    Rules:
      1. Presence of "DEFERRED" in the heading prefix wins over any lock marker.
      2. Otherwise, a 🔒 emoji OR a ✅ emoji OR the word "LOCKED"/"RE-LOCKED"
         in the heading prefix marks the chapter as a lock candidate.
      3. Lock candidates are validated against Punch List open-item counts.
         LOCKED requires zero open items. If open items exist, the chapter is
         labeled UNLOCKED. Rule: a chapter is either LOCKED or not; if it has
         open items, it is not locked. No intermediate state.
      4. Date extraction: latest YYYY-MM-DD on the heading line.

    Rationale for the UNLOCKED state: a chapter cannot be locked while its
    punch list still has open items. Either the items are stale (completed
    but not checked off) or the lock declaration is premature. Either way,
    UNLOCKED surfaces the contradiction instead of hiding it behind a green
    checkmark.
    """
    status = {}

    def extract_date(line: str) -> str:
        """Return the latest YYYY-MM-DD on the line — reflects current audit
        status when a chapter has been through multiple lock/audit passes.
        ISO date strings sort correctly lexicographically."""
        all_dates = re.findall(r"\d{4}-\d{2}-\d{2}", line)
        return max(all_dates) if all_dates else ""

    # Primary source: Book Structure headings.
    #
    # Split each heading into a "prefix" (state markers) and a "note" (descriptive
    # parenthetical). The prefix carries the primary state; the parenthetical
    # often mentions content-routing words like "Deferred to Ch. 25" that must
    # NOT be read as a chapter-level DEFERRED status.
    if BOOK_STRUCTURE.exists():
        bs_text = BOOK_STRUCTURE.read_text(encoding="utf-8")
        heading_pattern = re.compile(r"^### Chapter (\d+):([^\n]*)$", re.MULTILINE)
        for m in heading_pattern.finditer(bs_text):
            chnum = int(m.group(1))
            rest = m.group(2)

            # Split off the descriptive parenthetical `*(...)*` if present.
            paren_split = re.split(r"\s*\*\(", rest, maxsplit=1)
            prefix = paren_split[0]
            full = rest  # for date extraction (dates may live inside the parenthetical)

            if re.search(r"\bDEFERRED\b", prefix, re.IGNORECASE):
                status[chnum] = ("DEFERRED", extract_date(full))
                continue

            has_lock = (
                "🔒" in prefix
                or "✅" in prefix
                or re.search(r"\b(?:RE-LOCKED|LOCKED)\b", prefix, re.IGNORECASE)
            )
            if has_lock:
                status[chnum] = ("LOCKED", extract_date(full))

    # Secondary source: Punch List status table rows like
    #   | 2 | EpiWar™ — The War Has a Name | 🔒 | **LOCKED 2026-05-07.** ...
    # Fills in chapters the Book Structure didn't mark.
    if PUNCH_LIST.exists():
        pl_text = PUNCH_LIST.read_text(encoding="utf-8")
        pl_pattern = re.compile(
            r"^\|\s*(\d+)\s*\|[^|]+\|\s*(?:🔒|✅)\s*\|.*?(?:LOCKED|Locked)\s+(\d{4}-\d{2}-\d{2})",
            re.MULTILINE,
        )
        for m in pl_pattern.finditer(pl_text):
            chnum, date = m.groups()
            chnum_i = int(chnum)
            if chnum_i not in status:
                status[chnum_i] = ("LOCKED", date)

    # Validate LOCKED against Punch List open-item counts. A chapter is either
    # locked or not; if it has open items, it is not locked. Downgrade the
    # label to UNLOCKED so the true state is visible.
    #
    # Exception (2026-08-04): sections whose heading marks them as post-lock
    # work ("post-lock", "deferred", "wishlist", "standing leads", "acquisition")
    # hold enhancements Mr. Duke deferred AT lock — they describe work beyond
    # the locked text, not open chapter work, so they don't block the label.
    # Ruling case: Ch. 25 locked 2026-08-03 with Rounds 4-5 + acquisitions
    # explicitly deferred to the Punch List.
    punch_counts = parse_punch_items(blocking_only=True)
    for chnum, (label, date) in list(status.items()):
        if label == "LOCKED":
            open_ct, _total = punch_counts.get(chnum, (0, 0))
            if open_ct > 0:
                status[chnum] = ("UNLOCKED", date)

    # Sync-miss alarm (2026-08-04). Project State's "Active chapter" section is
    # the curated current state written at session close. When it declares a
    # chapter LOCKED and the sources above (Book Structure heading, Punch List
    # table, open-item validation) do NOT agree, the true condition is a missed
    # file sync — the dashboard shows OUT OF SYNC in red instead of silently
    # keeping the stale label. Added after two locks in two days reached
    # Project State but not Book Structure or the Punch List table.
    for chnum, ps_date in parse_project_state_locks().items():
        label, _d = status.get(chnum, (None, ""))
        if label != "LOCKED":
            status[chnum] = ("OUT OF SYNC", ps_date)

    return status


def parse_project_state_locks() -> dict:
    """Lock declarations from Project State's '## Active chapter' section.

    Only that section is read — it is curated current state. The decision log
    is history (it keeps old "Ch. N LOCKED" entries for chapters legitimately
    unlocked later) and would produce false drift alarms.

    Matches "**Ch. N ... LOCKED ...**" bullets; RE-LOCKED counts as locked;
    UNLOCKED never matches (no word boundary inside "UNLOCKED"). Returns
    {chapter_number: latest-date-on-line}.
    """
    out = {}
    if not PROJECT_STATE.exists():
        return out
    text = PROJECT_STATE.read_text(encoding="utf-8")
    m = re.search(
        r"^## Active chapter\s*\n(.*?)(?=^## )", text, re.MULTILINE | re.DOTALL
    )
    if not m:
        return out
    for line in m.group(1).splitlines():
        lm = re.search(r"\*\*Ch\.\s*(\d+)\b[^*]*?\bLOCKED\b", line)
        if lm:
            dates = re.findall(r"\d{4}-\d{2}-\d{2}", line)
            out[int(lm.group(1))] = max(dates) if dates else ""
    return out


def chapter_number(filename: str):
    m = re.match(r"Chapter (\d+)\b", filename)
    return int(m.group(1)) if m else None


# Punch List sections whose heading marks their items as post-lock /
# non-blocking work. These items are real and stay visible in detail views,
# but they don't disqualify a chapter's LOCKED label (see parse_lock_status).
NONBLOCKING_SECTION_RE = re.compile(
    r"post-lock|deferred|wishlist|standing leads|acquisition|corroborating",
    re.IGNORECASE,
)


def parse_punch_items(blocking_only: bool = False) -> dict:
    """Parse Punch List.md, counting open '- [ ]' and done '- [x]' items per chapter.
    Sections start with '### Ch. N ...' headings. Items aggregate across multiple
    sections for the same chapter number (e.g., the LOCKED section + any legacy
    section both contribute to that chapter's totals).

    With blocking_only=True, sections matching NONBLOCKING_SECTION_RE are
    skipped — used by the lock validator so post-lock deferred enhancements
    don't downgrade a locked chapter.

    Returns: {chapter_number: (open_count, total_count)}.
    """
    counts = {}
    if not PUNCH_LIST.exists():
        return counts
    text = PUNCH_LIST.read_text(encoding="utf-8")
    # Split into sections at ANY heading (#, ##, or ###). A "### Ch. N" section
    # ends at the next heading of any level — previously only ### terminated a
    # section, so a following "## Bibliography" block's items were silently
    # counted into the preceding chapter (the Ch. 26 phantom-18 bug, 2026-08-04).
    sections = re.split(r"^#{1,3} ", text, flags=re.MULTILINE)[1:]
    for section in sections:
        lines = section.split("\n", 1)
        heading = lines[0]
        body = lines[1] if len(lines) > 1 else ""
        m = re.match(r"Ch\.\s*(\d+)\b", heading)
        if not m:
            continue
        if blocking_only and NONBLOCKING_SECTION_RE.search(heading):
            continue
        chnum = int(m.group(1))
        open_count = len(re.findall(r"^- \[ \]", body, re.MULTILINE))
        done_count = len(re.findall(r"^- \[[xX]\]", body, re.MULTILINE))
        total = open_count + done_count
        prev_open, prev_total = counts.get(chnum, (0, 0))
        counts[chnum] = (prev_open + open_count, prev_total + total)
    return counts


def parse_punch_items_detail() -> tuple:
    """Extract the actual text of open '- [ ]' items per chapter from Punch List.md,
    split into blocking items and post-lock deferred items (sections matching
    NONBLOCKING_SECTION_RE).

    Returns: (blocking, deferred) — each {chapter_number: [item_text, ...]}.
    """
    blocking, deferred = {}, {}
    if not PUNCH_LIST.exists():
        return blocking, deferred
    text = PUNCH_LIST.read_text(encoding="utf-8")
    # Same any-level heading boundary as parse_punch_items (Ch. 26 phantom-18 bug).
    sections = re.split(r"^#{1,3} ", text, flags=re.MULTILINE)[1:]
    for section in sections:
        lines = section.split("\n", 1)
        heading = lines[0]
        body = lines[1] if len(lines) > 1 else ""
        m = re.match(r"Ch\.\s*(\d+)\b", heading)
        if not m:
            continue
        chnum = int(m.group(1))
        bucket = deferred if NONBLOCKING_SECTION_RE.search(heading) else blocking
        for line in body.split("\n"):
            mm = re.match(r"^- \[ \]\s*(.+)$", line)
            if mm:
                bucket.setdefault(chnum, []).append(mm.group(1).strip())
    return blocking, deferred


def parse_markdown_table(section_text: str) -> list[dict]:
    """Parse the first markdown table inside a section. Returns a list of row dicts
    keyed by the table's column headers. Empty tables (or sections marked 'Not
    applicable') return an empty list.
    """
    lines = section_text.split("\n")
    rows = []
    header = None
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            if header is not None:
                # We were in a table; a non-pipe line ends it.
                break
            continue
        # Split on pipes, drop the empty boundary cells from leading/trailing |
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        # Header separator row: cells are all dashes/colons
        if all(re.fullmatch(r":?-+:?", c) for c in cells if c):
            continue
        if header is None:
            header = cells
        else:
            if len(cells) == len(header):
                rows.append(dict(zip(header, cells)))
    return rows


def parse_open_questions(section_text: str) -> list[dict]:
    """Parse bullet items in the Open Questions section. Returns list of
    {checked, text, blocking} dicts. Items under a "### Corroborating reading"
    sub-section are marked blocking=False; items under "### Required" or any
    other sub-section default to blocking=True. Items in the legacy flat-list
    format (no sub-section) also default to blocking=True.
    """
    items = []
    blocking = True
    for line in section_text.split("\n"):
        # Track sub-section context
        sub = re.match(r"^###\s+(.+?)\s*$", line)
        if sub:
            heading = sub.group(1).lower()
            blocking = not (
                "corroborating" in heading
                or "closed" in heading
                or "completed" in heading
            )
            continue
        m = re.match(r"^- \[([ xX])\]\s*(.+)$", line)
        if m:
            items.append({
                "checked": m.group(1).lower() == "x",
                "text": m.group(2).strip(),
                "blocking": blocking,
            })
    return items


def parse_ledger(path: Path) -> dict:
    """Parse one Fact Check ledger file into structured data.

    Sections recognized:
      1. Claims Register
      2. Source Pages Consulted
      3. Greek Verification Log
      4. Translation Checks
      5. Editorial Decisions
      6. Open Questions

    Also captures Last updated, lock-status prose, and audit-report links.
    """
    text = path.read_text(encoding="utf-8")
    out = {
        "path": path,
        "last_updated": "",
        "audit_reports": [],
        "lock_status": "",
        "claims": [],
        "sources": [],
        "greek": [],
        "translation": [],
        "editorial": [],
        "open_questions": [],
    }

    m = re.search(r"\*\*Last updated:\*\*\s*([^\n]+)", text)
    if m:
        out["last_updated"] = m.group(1).strip()

    # Capture audit report bullets right after "Audit reports:"
    m = re.search(r"\*\*Audit reports:\*\*(.*?)(?:\n---|\n##)", text, re.DOTALL)
    if m:
        for line in m.group(1).split("\n"):
            line = line.strip()
            if line.startswith("-"):
                out["audit_reports"].append(line.lstrip("- ").strip())

    # Split on level-2 headings into named sections
    sections = re.split(r"^## ", text, flags=re.MULTILINE)
    for section in sections[1:]:
        heading_line, _, body = section.partition("\n")
        heading = heading_line.strip()
        body = body.strip()
        if heading.upper().startswith("CHAPTER LOCK STATUS"):
            out["lock_status"] = body.split("\n---", 1)[0].strip()
        elif heading.startswith("1.") or "Claims Register" in heading:
            out["claims"] = parse_markdown_table(body)
        elif heading.startswith("2.") or "Source Pages" in heading:
            out["sources"] = parse_markdown_table(body)
        elif heading.startswith("3.") or "Greek Verification" in heading:
            out["greek"] = parse_markdown_table(body)
        elif heading.startswith("4.") or "Translation Checks" in heading:
            out["translation"] = parse_markdown_table(body)
        elif heading.startswith("5.") or "Editorial Decisions" in heading:
            out["editorial"] = parse_markdown_table(body)
        elif heading.startswith("6.") or "Open Questions" in heading:
            out["open_questions"] = parse_open_questions(body)
    return out


def ledger_chapter_number(filename: str):
    m = re.match(r"Ch\.\s*(\d+)\b", filename)
    return int(m.group(1)) if m else None


def gather_ledgers() -> dict:
    """Find Fact Check/Ch. N — Title.md files and parse each.
    Returns {chapter_number: ledger_dict}.
    """
    out = {}
    if not FACT_CHECK_DIR.exists():
        return out
    for path in FACT_CHECK_DIR.glob("Ch.*.md"):
        num = ledger_chapter_number(path.name)
        if num is None:
            continue
        out[num] = parse_ledger(path)
    return out


def publish_status() -> dict:
    """Compare source markdown mtimes against Dropbox review PDF mtimes.

    Returns:
        {
            "dropbox_available": bool,
            "chapters": [
                {"num": int, "title": str, "src_mtime": float,
                 "pdf_path": Path|None, "pdf_mtime": float|None,
                 "stale": bool, "missing": bool},
                ...
            ],
            "appendices": [...same shape, letter instead of num...],
            "publish_script": Path,
        }
    Source-newer-than-PDF chapters have stale=True. Chapters with no PDF in
    Dropbox have missing=True. Run `./publish-pdfs.sh` to regenerate.
    """
    out = {
        "dropbox_available": DROPBOX_REVIEW.is_dir(),
        "chapters": [],
        "appendices": [],
        "publish_script": PUBLISH_SCRIPT,
    }
    if not out["dropbox_available"]:
        return out

    # Build PDF index from Dropbox: filename stem → (path, mtime)
    pdf_index = {}
    for pdf_path in DROPBOX_REVIEW.glob("*.pdf"):
        pdf_index[pdf_path.stem] = (pdf_path, pdf_path.stat().st_mtime)

    for src in CHAPTERS_DIR.glob("Chapter *.md"):
        if "Intake" in src.name:
            continue
        num = chapter_number(src.name)
        if num is None:
            continue
        stem = src.stem  # e.g., "Chapter 23 - The Paradox of Perception"
        src_mtime = src.stat().st_mtime
        pdf_entry = pdf_index.get(stem)
        if pdf_entry is None:
            out["chapters"].append({
                "num": num, "title": stem, "src_mtime": src_mtime,
                "pdf_path": None, "pdf_mtime": None,
                "stale": False, "missing": True,
            })
        else:
            pdf_path, pdf_mtime = pdf_entry
            out["chapters"].append({
                "num": num, "title": stem, "src_mtime": src_mtime,
                "pdf_path": pdf_path, "pdf_mtime": pdf_mtime,
                "stale": src_mtime > pdf_mtime, "missing": False,
            })

    out["chapters"].sort(key=lambda e: e["num"])

    for src in APPENDICES_DIR.glob("Appendix *.md"):
        m = re.match(r"Appendix ([A-Z])\b", src.name)
        if not m:
            continue
        letter = m.group(1)
        stem = src.stem
        src_mtime = src.stat().st_mtime
        pdf_entry = pdf_index.get(stem)
        if pdf_entry is None:
            out["appendices"].append({
                "letter": letter, "title": stem, "src_mtime": src_mtime,
                "pdf_path": None, "pdf_mtime": None,
                "stale": False, "missing": True,
            })
        else:
            pdf_path, pdf_mtime = pdf_entry
            out["appendices"].append({
                "letter": letter, "title": stem, "src_mtime": src_mtime,
                "pdf_path": pdf_path, "pdf_mtime": pdf_mtime,
                "stale": src_mtime > pdf_mtime, "missing": False,
            })

    out["appendices"].sort(key=lambda e: e["letter"])
    return out


def audit_counts(ledger: dict) -> dict:
    """Counts of claim statuses for a chapter's ledger."""
    counts = {"verified": 0, "corrected": 0, "pending": 0, "interpretive": 0, "other": 0, "total": 0}
    for row in ledger.get("claims", []):
        status = (row.get("Status") or row.get("status") or "").upper()
        counts["total"] += 1
        if "VERIFIED" in status and "CORRECTED" not in status:
            counts["verified"] += 1
        elif "CORRECTED" in status:
            counts["corrected"] += 1
        elif "PENDING" in status:
            counts["pending"] += 1
        elif "INTERPRETIVE" in status or status in {"N/A", ""}:
            counts["interpretive"] += 1
        else:
            counts["other"] += 1
    return counts


def gather_chapters():
    lock_status = parse_lock_status()
    punch = parse_punch_items()
    # Blocking counts exclude "post-lock"/"deferred" sections — those hold
    # enhancements Mr. Duke deferred AT lock. A locked chapter must show ZERO
    # open items; its deferred work is counted separately (2026-08-04, after
    # Ch. 25 showed LOCKED alongside an open-item count).
    punch_blocking = parse_punch_items(blocking_only=True)
    punch_detail, punch_detail_deferred = parse_punch_items_detail()
    ledgers = gather_ledgers()
    out = []
    for path in CHAPTERS_DIR.glob("Chapter *.md"):
        if "Intake" in path.name:
            continue
        num = chapter_number(path.name)
        if num is None:
            continue
        title_part = path.stem
        title_part = re.sub(r"^Chapter \d+\s*[-:]\s*", "", title_part).strip()
        status, date = lock_status.get(num, ("Draft", ""))
        all_open, total_items = punch.get(num, (0, 0))
        open_items, _bt = punch_blocking.get(num, (0, 0))
        deferred_items = all_open - open_items
        ledger = ledgers.get(num)
        audit = audit_counts(ledger) if ledger else None
        # Strict lock-means-complete rule: open items = open punch-list items +
        # BLOCKING ledger Open Questions. Items in "Corroborating reading" or
        # "Closed" sub-sections don't block lock.
        ledger_oq_open = (
            sum(1 for q in ledger.get("open_questions", [])
                if not q.get("checked") and q.get("blocking", True))
            if ledger else 0
        )
        ledger_oq_corroborating = (
            sum(1 for q in ledger.get("open_questions", [])
                if not q.get("checked") and not q.get("blocking", True))
            if ledger else 0
        )
        total_open = open_items + ledger_oq_open
        fn_count, fn_words = count_footnotes(path)
        out.append({
            "num": num,
            "title": title_part,
            "words": count_words(path),
            "footnote_count": fn_count,
            "footnote_words": fn_words,
            "status": status,
            "date": date,
            "path": path,
            "mtime": datetime.datetime.fromtimestamp(path.stat().st_mtime),
            "open_items": open_items,
            "deferred_items": deferred_items,
            "total_items": total_items,
            "punch_open": punch_detail.get(num, []),
            "punch_deferred": punch_detail_deferred.get(num, []),
            "ledger_oq_open": ledger_oq_open,
            "ledger_oq_corroborating": ledger_oq_corroborating,
            "total_open": total_open,
            "ledger": ledger,
            "audit": audit,
        })
    out.sort(key=lambda c: c["num"])
    return out


def gather_appendices():
    if not APPENDICES_DIR.exists():
        return []
    out = []
    for path in APPENDICES_DIR.glob("Appendix *.md"):
        fn_count, fn_words = count_footnotes(path)
        out.append({
            "title": path.stem,
            "words": count_words(path),
            "footnote_count": fn_count,
            "footnote_words": fn_words,
            "mtime": datetime.datetime.fromtimestamp(path.stat().st_mtime),
            "path": path,
        })
    out.sort(key=lambda a: a["title"])
    return out


# ---------- local servers ----------


def is_port_listening(port) -> bool:
    """Probe whether anything is listening on 127.0.0.1:<port>.

    More reliable than `lsof` on macOS — works regardless of loopback-only
    binding, lsof permissions, or PATH availability.
    """
    if not isinstance(port, int):
        return False
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        try:
            return s.connect_ex(("127.0.0.1", port)) == 0
        except OSError:
            return False


def port_pid(port) -> str:
    """PID currently bound to a TCP port (empty string if nothing listening,
    "?" if listening but the PID can't be resolved).
    """
    if not isinstance(port, int):
        return ""
    if not is_port_listening(port):
        return ""
    # Port is up; try to get the PID via lsof, but degrade gracefully.
    try:
        result = subprocess.run(
            # -sTCP:LISTEN: listeners only — otherwise browser tabs polling
            # the port show up as the "server" PID.
            ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
            capture_output=True, text=True, timeout=2,
        )
        pid = result.stdout.strip().split("\n")[0] if result.stdout.strip() else ""
        return pid or "?"
    except (subprocess.SubprocessError, FileNotFoundError):
        return "?"


def pid_file_pid(name: str) -> str:
    """PID written by the wrapper, only if that process is still alive."""
    pf = PID_DIR / f"rr-{name}.pid"
    if not pf.exists():
        return ""
    try:
        pid = pf.read_text().strip()
        if pid and pid.isdigit():
            os.kill(int(pid), 0)  # check alive
            return pid
    except (OSError, ValueError):
        pass
    return ""


def service_status(svc: dict) -> dict:
    """Returns {state, pid} for a registered service."""
    port = svc["port"]
    if isinstance(port, int):
        pid = port_pid(port)
        if pid:
            return {"state": "running", "pid": pid}
    # Fall back to PID file (covers stdio servers and port-down-but-process-up)
    pid = pid_file_pid(svc["name"])
    if pid:
        return {"state": "running", "pid": pid}
    # Stdio services (MCP servers spawned by Claude Desktop / Cowork) are
    # "on-demand" rather than "stopped" — they only run while a client is
    # connected and exit when it disconnects. Showing them as stopped is
    # technically true but visually reads as broken.
    if svc.get("port") == "stdio":
        return {"state": "on-demand", "pid": ""}
    return {"state": "stopped", "pid": ""}


def problade_mounted() -> bool:
    return PROBLADE_ALEXANDRIA.exists()


def greek_server_status() -> dict:
    """Status of the local Greek primary-source server.

    Returns:
        {
            "mounted": bool,              # PRO-BLADE is mounted AND Greek-resources/ exists
            "lookup_script": bool,        # greek_lookup.py is present
            "lsj_index_mtime": float|None,
            "tagnt_index_mtime": float|None,
            "readme_exists": bool,
            "vault_doc_exists": bool,
            "readme_path": Path,
            "vault_doc_path": Path,
            "server_root": Path,
        }

    The Greek server is the PRIMARY source for any Greek primary text (NT,
    classical, patristic, LXX). English translations in Alexandria's PDF
    library are SECONDARY references. See feedback_greek_server_use_first.md
    in the project memory.
    """
    out = {
        "mounted": False,
        "lookup_script": False,
        "lsj_index_mtime": None,
        "tagnt_index_mtime": None,
        "readme_exists": False,
        "vault_doc_exists": GREEK_VAULT_DOC.exists(),
        "readme_path": GREEK_README,
        "vault_doc_path": GREEK_VAULT_DOC,
        "server_root": GREEK_RESOURCES,
    }
    if not GREEK_RESOURCES.is_dir():
        return out
    out["mounted"] = True
    out["lookup_script"] = GREEK_LOOKUP_SCRIPT.exists()
    out["readme_exists"] = GREEK_README.exists()
    if GREEK_LSJ_INDEX.exists():
        out["lsj_index_mtime"] = GREEK_LSJ_INDEX.stat().st_mtime
    if GREEK_TAGNT_INDEX.exists():
        out["tagnt_index_mtime"] = GREEK_TAGNT_INDEX.stat().st_mtime
    return out


def run_servers_command(action: str, name: str) -> tuple[int, str]:
    """Shell out to the `servers` wrapper. Returns (exit_code, combined_output)."""
    if not SERVERS_SCRIPT.exists():
        return 127, f"Wrapper script not found at {SERVERS_SCRIPT}"
    try:
        result = subprocess.run(
            ["bash", str(SERVERS_SCRIPT), action, name],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode, (result.stdout + result.stderr).strip()
    except subprocess.SubprocessError as e:
        return 1, str(e)


def read_service_log_tail(name: str, lines: int = 100) -> str:
    """Last N lines of the service log file."""
    log = LOG_DIR / f"{name}.log"
    if not log.exists():
        return "(no log file yet)"
    try:
        result = subprocess.run(
            ["tail", "-n", str(lines), str(log)],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout
    except subprocess.SubprocessError as e:
        return f"(error reading log: {e})"


def render_health_page() -> str:
    """Run alexandria-health.sh and show its output (RAG pipeline integrity)."""
    import subprocess
    script = PROBLADE_ALEXANDRIA / "RAG_system" / "alexandria-health.sh"
    if not script.exists():
        body = "alexandria-health.sh not found — is PRO-BLADE mounted?"
        ok = False
    else:
        try:
            r = subprocess.run(["bash", str(script)], capture_output=True,
                               text=True, timeout=300)
            body = (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")
            ok = r.returncode == 0
        except subprocess.TimeoutExpired:
            body = "Health check timed out after 300s."
            ok = False
    badge = ('<span class="srv-mount srv-mount-ok">HEALTHY</span>' if ok else
             '<span class="srv-mount srv-mount-bad">PROBLEMS FOUND</span>')
    import html as _html
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<title>RAG Health — Reframing Reality</title>
<style>{CSS}{SERVERS_CSS}</style>
</head><body>
<div class="case-container">
  <a class="case-back" href="/servers">← Back to Local Servers</a>
  <div class="case-header"><h1>Alexandria RAG Health</h1>
  <div class="case-meta">{datetime.datetime.now().strftime("%H:%M:%S")} — invariant chain: manifest = metadata = embeddings = index</div></div>
  <div class="srv-mount-row">{badge}</div>
  <pre style="white-space:pre-wrap;font-size:13px;line-height:1.5;background:#111;color:#ddd;padding:16px;border-radius:8px;">{_html.escape(body)}</pre>
</div></body></html>"""


def render_servers_page(notice: str = "") -> str:
    """The Local Servers panel."""
    pb = problade_mounted()
    pb_html = (
        '<span class="srv-mount srv-mount-ok">PRO-BLADE mounted</span>'
        '<span class="srv-mount-sub">Alexandria available</span>'
        if pb else
        '<span class="srv-mount srv-mount-bad">PRO-BLADE NOT MOUNTED</span>'
        '<span class="srv-mount-sub">Alexandria + MCP server unreachable</span>'
    )

    # Greek server status — primary source for any Greek primary text.
    gs = greek_server_status()
    if gs["mounted"]:
        # Build small docs-link cluster
        doc_links = []
        if gs["readme_exists"]:
            doc_links.append(f'<a href="{file_url(gs["readme_path"])}">Server README</a>')
        if gs["vault_doc_exists"]:
            doc_links.append(f'<a href="{file_url(gs["vault_doc_path"])}">Vault Methodology doc</a>')
        docs_html = (
            f'<span class="srv-mount-sub"> · Docs: {" · ".join(doc_links)}</span>'
            if doc_links else ""
        )
        # Build index-freshness line
        idx_parts = []
        if gs["lsj_index_mtime"]:
            d = datetime.datetime.fromtimestamp(gs["lsj_index_mtime"]).strftime("%Y-%m-%d")
            idx_parts.append(f"LSJ index built {d}")
        else:
            idx_parts.append("LSJ index NOT built")
        if gs["tagnt_index_mtime"]:
            d = datetime.datetime.fromtimestamp(gs["tagnt_index_mtime"]).strftime("%Y-%m-%d")
            idx_parts.append(f"TAGNT index built {d}")
        else:
            idx_parts.append("TAGNT index NOT built")
        lookup_status = "greek_lookup.py present" if gs["lookup_script"] else "greek_lookup.py MISSING"
        gs_html = (
            f'<span class="srv-mount srv-mount-ok">Greek server available</span>'
            f'<span class="srv-mount-sub">{lookup_status} · {" · ".join(idx_parts)}</span>'
            f'{docs_html}'
        )
    else:
        # Even when unmounted, show docs link from the vault (it's a local file)
        docs_html = (
            f'<span class="srv-mount-sub"> · Vault doc: <a href="{file_url(gs["vault_doc_path"])}">Methodology/Greek-Server-Reference.md</a></span>'
            if gs["vault_doc_exists"] else ""
        )
        gs_html = (
            '<span class="srv-mount srv-mount-bad">Greek server unavailable</span>'
            '<span class="srv-mount-sub">PRO-BLADE mount required for Greek primary text (Perseus/TLG + GNT + LSJ)</span>'
            f'{docs_html}'
        )

    rows = []
    for svc in SERVICES:
        status = service_status(svc)
        state_cls = {
            "running": "srv-running",
            "on-demand": "srv-on-demand",
            "stopped": "srv-stopped",
        }.get(status["state"], "srv-stopped")
        port_str = svc["port"] if isinstance(svc["port"], int) else (svc["port"] or "—")
        pid_str = status["pid"] or "—"

        # Action buttons
        actions = []
        if svc["controllable"]:
            if status["state"] == "running":
                actions.append(
                    f'<form method="post" action="/servers/stop/{svc["name"]}" class="srv-btn-form">'
                    f'<button class="srv-btn srv-btn-stop">Stop</button></form>'
                )
                actions.append(
                    f'<form method="post" action="/servers/restart/{svc["name"]}" class="srv-btn-form">'
                    f'<button class="srv-btn srv-btn-restart">Restart</button></form>'
                )
            else:
                actions.append(
                    f'<form method="post" action="/servers/start/{svc["name"]}" class="srv-btn-form">'
                    f'<button class="srv-btn srv-btn-start">Start</button></form>'
                )
        # Always show the Logs link
        actions.append(
            f'<a class="srv-btn srv-btn-logs" href="/servers/tail/{svc["name"]}">Logs</a>'
        )
        # If running and has an open URL, show Open
        if status["state"] == "running" and svc.get("open_url"):
            actions.append(
                f'<a class="srv-btn srv-btn-open" href="{svc["open_url"]}" target="_blank" rel="noopener">Open ↗</a>'
            )

        rows.append(f"""
        <tr class="{state_cls}">
          <td class="srv-name"><code>{escape(svc["name"])}</code></td>
          <td class="srv-state"><span class="srv-dot {state_cls}"></span>{status["state"]}</td>
          <td class="srv-port">{port_str}</td>
          <td class="srv-pid">{pid_str}</td>
          <td class="srv-note">{escape(svc["note"])}</td>
          <td class="srv-actions">{"".join(actions)}</td>
        </tr>""")

    notice_html = ""
    if notice:
        notice_html = f'<div class="srv-notice"><pre>{escape(notice)}</pre></div>'

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Local Servers — Reframing Reality</title>
<style>{CSS}{SERVERS_CSS}</style>
</head><body>
<div class="case-container">
  <a class="case-back" href="/">← Back to dashboard</a>
  <div class="case-header">
    <h1>Local Servers</h1>
    <div class="case-meta">Start, stop, and monitor the local services from one place. {datetime.datetime.now().strftime("%H:%M:%S")}</div>
  </div>

  <div class="srv-mount-row">{pb_html}
    <a class="srv-btn" style="margin-left:12px;text-decoration:none;" href="/servers/health">Run RAG Health Check</a></div>
  <div class="srv-mount-row">{gs_html}</div>

  {notice_html}

  <table class="srv-table">
    <thead><tr>
      <th>Service</th><th>State</th><th>Port</th><th>PID</th><th>Description</th><th>Actions</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>

  <p class="meta">
    Wrapper: <code>{escape(str(SERVERS_SCRIPT))}</code> ·
    Logs: <code>~/Library/Logs/RR/</code> ·
    <a href="/servers" style="color:var(--accent);text-decoration:none">Refresh</a>
  </p>
</div>
</body></html>
"""


def render_log_tail_page(name: str) -> str:
    """The log-tail page for a single service."""
    valid = any(s["name"] == name for s in SERVICES)
    if not valid:
        return "<p>Unknown service. <a href='/servers'>← Back</a></p>"
    log_text = read_service_log_tail(name, lines=200)
    log_path = LOG_DIR / f"{name}.log"
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<title>{escape(name)} log — Reframing Reality</title>
<style>{CSS}{SERVERS_CSS}</style>
</head><body>
<div class="case-container">
  <a class="case-back" href="/servers">← Back to Local Servers</a>
  <div class="case-header">
    <h1>{escape(name)} log<span class="count" style="color:var(--muted);font-weight:400;font-size:0.85rem;margin-left:0.5rem">last 200 lines</span></h1>
    <div class="case-meta">Path: <code>{escape(str(log_path))}</code></div>
  </div>
  <pre class="srv-log">{escape(log_text) or "(empty)"}</pre>
  <p class="meta"><a href="/servers/tail/{escape(name)}" style="color:var(--accent);text-decoration:none">Refresh</a></p>
</div>
</body></html>
"""


SERVERS_CSS = """
  .srv-mount-row {
    background: var(--card);
    border: 1px solid var(--line);
    padding: 0.7rem 1rem;
    border-radius: 6px;
    margin-bottom: 1rem;
    font-size: 0.9rem;
  }
  .srv-mount {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 10px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    margin-right: 0.6rem;
  }
  .srv-mount-ok { background: var(--locked-soft); color: var(--locked); }
  .srv-mount-bad { background: #f7d9d0; color: #b8523a; }
  .srv-mount-sub { color: var(--muted); font-size: 0.85rem; }
  .srv-notice {
    background: var(--card);
    border: 1px solid var(--line);
    border-left: 3px solid var(--accent);
    border-radius: 4px;
    padding: 0.6rem 0.9rem;
    margin-bottom: 1rem;
  }
  .srv-notice pre {
    margin: 0;
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    font-size: 0.8rem;
    white-space: pre-wrap;
    word-break: break-word;
    color: var(--ink);
  }
  table.srv-table { width: 100%; }
  table.srv-table td, table.srv-table th { padding: 0.7rem 0.9rem; }
  td.srv-name { width: 110px; font-size: 0.88rem; }
  td.srv-name code { background: transparent; color: var(--ink); padding: 0; }
  td.srv-state { width: 110px; font-size: 0.88rem; }
  td.srv-port { width: 70px; font-variant-numeric: tabular-nums; color: var(--muted); font-size: 0.88rem; }
  td.srv-pid  { width: 70px; font-variant-numeric: tabular-nums; color: var(--muted); font-size: 0.88rem; }
  td.srv-note { color: var(--muted); font-size: 0.88rem; }
  td.srv-actions { width: 290px; text-align: right; }
  .srv-dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    margin-right: 0.4rem;
    vertical-align: middle;
  }
  tr.srv-running .srv-dot { background: var(--locked); box-shadow: 0 0 0 2px var(--locked-soft); }
  tr.srv-stopped .srv-dot { background: var(--draft); }
  tr.srv-on-demand .srv-dot { background: var(--accent); box-shadow: 0 0 0 2px #d6e3ed; }
  tr.srv-on-demand .srv-state { color: var(--accent); }
  .srv-btn-form { display: inline-block; margin: 0 0.2rem 0 0; }
  .srv-btn {
    display: inline-block;
    padding: 0.3rem 0.7rem;
    border-radius: 4px;
    font-size: 0.78rem;
    font-weight: 500;
    border: 1px solid var(--line);
    background: var(--card);
    color: var(--ink);
    cursor: pointer;
    text-decoration: none;
    margin: 0 0.2rem;
    font-family: inherit;
  }
  .srv-btn:hover { border-color: var(--accent); color: var(--accent); }
  .srv-btn-stop:hover, .srv-btn-stop { color: #b8523a; border-color: #f0c4ba; }
  .srv-btn-stop:hover { background: #fdf2ef; border-color: #b8523a; }
  .srv-btn-start, .srv-btn-restart { color: var(--locked); border-color: #c5e3cc; }
  .srv-btn-start:hover, .srv-btn-restart:hover { background: #eef8f0; border-color: var(--locked); }
  .srv-btn-open { color: var(--accent); }
  pre.srv-log {
    background: #1e1e1e;
    color: #e0e0e0;
    padding: 1rem;
    border-radius: 6px;
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    font-size: 0.78rem;
    line-height: 1.5;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-word;
    max-height: 70vh;
  }
"""


# ---------- rendering ----------


def file_url(p: Path) -> str:
    return "file://" + quote(str(p))


def fmt_date(dt: datetime.datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def render_progress_bar(chapters):
    """A horizontal stacked bar showing word count by status."""
    total = sum(c["words"] for c in chapters) or 1
    buckets = {"LOCKED": 0, "UNLOCKED": 0, "OUT OF SYNC": 0, "DEFERRED": 0, "Draft": 0}
    for c in chapters:
        bucket = c["status"] if c["status"] in buckets else "Draft"
        buckets[bucket] += c["words"]
    segments = []
    for label in ("LOCKED", "UNLOCKED", "OUT OF SYNC", "Draft", "DEFERRED"):
        pct = (buckets[label] / total) * 100
        if pct == 0:
            continue
        cls = {
            "LOCKED": "locked",
            "UNLOCKED": "drift",
            "OUT OF SYNC": "drift",
            "Draft": "draft",
            "DEFERRED": "deferred",
        }[label]
        segments.append(
            f'<div class="seg seg-{cls}" style="width:{pct:.2f}%" '
            f'title="{label}: {buckets[label]:,} words ({pct:.1f}%)"></div>'
        )
    return f'<div class="progress-bar">{"".join(segments)}</div>'


def render_chapter_row(c, max_words):
    status_cls = {
        "LOCKED": "locked",
        "UNLOCKED": "drift",
        "OUT OF SYNC": "drift",
        "DEFERRED": "deferred",
    }.get(c["status"], "draft")
    status_label = c["status"]
    if c["date"]:
        status_label += f" · {c['date']}"
    bar_pct = (c["words"] / max_words) * 100 if max_words else 0
    # Title now links to the per-chapter open-issues page (/case/N).
    # The chapter file itself is one click away from the case page.
    title_link = f'<a href="/case/{c["num"]}" title="Open issues for this chapter">{escape(c["title"])}</a>'
    # Strict lock-means-complete rule: items = punch-list open + ledger open-questions
    total_open = c.get("total_open", c["open_items"])
    punch_open = c["open_items"]
    ledger_oq_open = c.get("ledger_oq_open", 0)
    deferred = c.get("deferred_items", 0)
    if total_open == 0:
        # Zero OPEN items. Post-lock deferred work, if any, is shown in gray —
        # it is future enhancement, not open chapter work, and never counts
        # against a lock.
        if deferred:
            items_display = f'—<span class="def-note"> +{deferred} deferred</span>'
            items_title = (
                f"No open items. {deferred} post-lock deferred item(s) "
                f"(future enhancements — do not affect the lock)"
            )
        else:
            items_display = "—"
            items_title = (
                f"All items complete (0 of {c['total_items']} punch-list items open; "
                f"0 ledger open-questions)"
                if c["total_items"]
                else "No open items"
            )
        items_cls = "items all-done"
    else:
        items_display = str(total_open)
        items_cls = "items has-open"
        parts = []
        if punch_open:
            parts.append(f"{punch_open} punch-list")
        if ledger_oq_open:
            parts.append(f"{ledger_oq_open} ledger Open-Questions")
        if deferred:
            parts.append(f"{deferred} deferred (not counted)")
        items_title = f"{total_open} open ({' + '.join(parts)})"

    # Audit column: link to /case/<n> if ledger exists, otherwise dash
    if c["audit"]:
        a = c["audit"]
        # Format: "12 V · 4 C · 8 P" — verified · corrected · pending
        pieces = []
        if a["verified"]:
            pieces.append(f'<span class="aud aud-v" title="Verified">{a["verified"]}V</span>')
        if a["corrected"]:
            pieces.append(f'<span class="aud aud-c" title="Errors caught and corrected">{a["corrected"]}C</span>')
        if a["pending"]:
            pieces.append(f'<span class="aud aud-p" title="Pending external acquisition">{a["pending"]}P</span>')
        audit_inner = " · ".join(pieces) if pieces else "—"
        audit_cell = f'<a class="audit-link" href="/case/{c["num"]}" title="Open audit detail">{audit_inner}</a>'
    else:
        audit_cell = '<span class="aud-none" title="No ledger yet">—</span>'

    return f"""
    <tr class="row-{status_cls}">
      <td class="num">{c['num']}</td>
      <td class="title">{title_link}</td>
      <td class="words">{c['words']:,}</td>
      <td class="bar-cell">
        <div class="row-bar"><div class="row-bar-fill bar-{status_cls}" style="width:{bar_pct:.1f}%"></div></div>
      </td>
      <td class="status"><span class="badge badge-{status_cls}">{escape(status_label)}</span></td>
      <td class="{items_cls}" title="{escape(items_title)}">{items_display}</td>
      <td class="audit-cell">{audit_cell}</td>
      <td class="mtime">{fmt_date(c['mtime'])}</td>
    </tr>"""


def render_appendix_row(a):
    title_link = f'<a href="{file_url(a["path"])}" title="Open file">{escape(a["title"])}</a>'
    return f"""
    <tr>
      <td class="title">{title_link}</td>
      <td class="words">{a['words']:,}</td>
      <td class="mtime">{fmt_date(a['mtime'])}</td>
    </tr>"""


CSS = """
  :root {
    --bg: #fafaf8;
    --card: #ffffff;
    --ink: #1f1f1f;
    --muted: #6b6b6b;
    --line: #e9e7e2;
    --locked: #2c8c4c;
    --locked-soft: #d6efdb;
    --deferred: #c08e26;
    --deferred-soft: #faecc8;
    --draft: #7d7d7d;
    --draft-soft: #e8e8e6;
    --accent: #1a4a73;
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    margin: 0; padding: 0;
    background: var(--bg);
    color: var(--ink);
    line-height: 1.5;
  }
  .container { max-width: 1100px; margin: 0 auto; padding: 2.5rem 2rem 4rem; }
  h1 { font-size: 2.25rem; margin: 0 0 0.25rem; letter-spacing: -0.02em; }
  h1 .em { font-style: italic; font-weight: 500; }
  .subtitle { color: var(--muted); font-size: 1rem; margin-bottom: 2rem; }
  h2 { font-size: 1.15rem; margin: 2.5rem 0 0.75rem; letter-spacing: -0.01em; }
  h2 .count { color: var(--muted); font-weight: 400; font-size: 0.9rem; margin-left: 0.5rem; }

  .stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.75rem;
    margin-bottom: 1.25rem;
  }
  .stat {
    background: var(--card);
    border: 1px solid var(--line);
    padding: 0.85rem 1rem;
    border-radius: 6px;
  }
  .stat .label {
    font-size: 0.72rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
  }
  .stat .value {
    font-size: 1.75rem;
    font-weight: 600;
    margin-top: 0.15rem;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.01em;
  }
  .stat .sub {
    font-size: 0.78rem;
    color: var(--muted);
    margin-top: 0.1rem;
  }

  .progress-bar {
    display: flex;
    height: 10px;
    background: var(--draft-soft);
    border-radius: 5px;
    overflow: hidden;
    margin-bottom: 0.5rem;
  }
  .progress-bar .seg { height: 100%; }
  .progress-bar .seg-locked { background: var(--locked); }
  .progress-bar .seg-drift { background: #d97706; }
  .progress-bar .seg-draft { background: var(--draft); }
  .progress-bar .seg-deferred { background: var(--deferred); }
  .progress-legend {
    display: flex;
    gap: 1.25rem;
    font-size: 0.8rem;
    color: var(--muted);
    margin-bottom: 1.5rem;
  }
  .progress-legend .swatch {
    display: inline-block;
    width: 10px; height: 10px;
    border-radius: 2px;
    margin-right: 0.4rem;
    vertical-align: middle;
  }
  .swatch.locked { background: var(--locked); }
  .swatch.draft { background: var(--draft); }
  .swatch.deferred { background: var(--deferred); }

  table {
    width: 100%;
    border-collapse: collapse;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 6px;
    overflow: hidden;
  }
  thead th {
    background: var(--bg);
    border-bottom: 1px solid var(--line);
    text-align: left;
    padding: 0.6rem 0.9rem;
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  tbody td {
    padding: 0.6rem 0.9rem;
    border-bottom: 1px solid var(--line);
    font-size: 0.92rem;
  }
  tbody tr:last-child td { border-bottom: none; }
  td.num { width: 40px; color: var(--muted); font-variant-numeric: tabular-nums; }
  td.title a { color: var(--ink); text-decoration: none; border-bottom: 1px dashed transparent; }
  td.title a:hover { border-bottom-color: var(--accent); color: var(--accent); }
  td.words { width: 90px; text-align: right; font-variant-numeric: tabular-nums; color: var(--ink); }
  td.bar-cell { width: 160px; }
  td.status { width: 200px; }
  td.items { width: 70px; text-align: center; font-variant-numeric: tabular-nums; font-size: 0.85rem; color: var(--muted); }
  td.items.has-open { color: var(--ink); font-weight: 500; }
  td.items.all-done { color: var(--locked); }
  .def-note { color: var(--muted); font-size: 0.85em; font-weight: 400; }
  td.items.none { color: var(--line); }
  td.audit-cell { width: 130px; text-align: center; font-size: 0.78rem; font-variant-numeric: tabular-nums; }
  td.audit-cell .audit-link { text-decoration: none; color: var(--ink); border-bottom: 1px dashed transparent; padding: 0.15rem 0; }
  td.audit-cell .audit-link:hover { border-bottom-color: var(--accent); }
  .aud { display: inline-block; font-weight: 600; }
  .aud-v { color: var(--locked); }
  .aud-c { color: #b8523a; }
  .aud-p { color: var(--deferred); }
  .aud-none { color: var(--line); }
  .audit-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 1.25rem;
    font-size: 0.78rem;
    color: var(--muted);
    margin: 0 0 0.75rem;
  }
  .audit-legend .item { display: inline-flex; align-items: center; }
  .audit-legend .letter {
    display: inline-block;
    font-weight: 600;
    margin-right: 0.35rem;
    font-variant-numeric: tabular-nums;
    min-width: 0.9em;
    text-align: center;
  }
  .audit-legend .letter.v { color: var(--locked); }
  .audit-legend .letter.c { color: #b8523a; }
  .audit-legend .letter.p { color: var(--deferred); }
  td.mtime { width: 100px; color: var(--muted); font-size: 0.85rem; font-variant-numeric: tabular-nums; }

  .row-bar { background: var(--draft-soft); height: 6px; border-radius: 3px; overflow: hidden; }
  .row-bar-fill { height: 100%; }
  .bar-locked { background: var(--locked); }
  .bar-draft { background: var(--draft); }
  .bar-deferred { background: var(--deferred); }

  .badge {
    display: inline-block;
    padding: 0.2rem 0.55rem;
    border-radius: 10px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.03em;
  }
  .badge-locked { background: var(--locked-soft); color: var(--locked); }
  .badge-drift { background: #fef3c7; color: #d97706; font-weight: 700; }
  .badge-deferred { background: var(--deferred-soft); color: var(--deferred); }
  .badge-draft { background: var(--draft-soft); color: var(--draft); }

  .meta {
    color: var(--muted);
    font-size: 0.8rem;
    margin-top: 2.5rem;
    text-align: center;
  }
  .meta code { background: var(--line); padding: 0.1rem 0.4rem; border-radius: 3px; font-size: 0.85em; }

  /* ===== Case page (per-chapter audit detail) ===== */
  .case-container { max-width: 1600px; margin: 0 auto; padding: 2rem 2rem 4rem; }
  .case-back { display: inline-block; color: var(--muted); text-decoration: none; margin-bottom: 1rem; font-size: 0.85rem; }
  .case-back:hover { color: var(--accent); }
  .case-header h1 { font-size: 1.65rem; margin: 0 0 0.4rem; }
  .case-meta { color: var(--muted); font-size: 0.85rem; margin-bottom: 1.5rem; }
  .case-meta a { color: var(--accent); text-decoration: none; }
  .case-meta a:hover { text-decoration: underline; }
  .case-lockbox {
    background: var(--card);
    border: 1px solid var(--line);
    border-left: 3px solid var(--accent);
    padding: 0.9rem 1.1rem;
    border-radius: 4px;
    margin-bottom: 1.5rem;
    font-size: 0.9rem;
    color: var(--ink);
    white-space: pre-wrap;
    line-height: 1.55;
  }
  .case-section { margin-bottom: 2rem; }
  .case-section h2 { font-size: 1.05rem; margin: 0 0 0.5rem; }
  .case-section .count { color: var(--muted); font-weight: 400; font-size: 0.85rem; margin-left: 0.5rem; }
  .case-table {
    width: 100%;
    border-collapse: collapse;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 4px;
    overflow: hidden;
    font-size: 0.82rem;
    table-layout: fixed;
  }
  .case-table thead th {
    background: var(--bg);
    border-bottom: 1px solid var(--line);
    text-align: left;
    padding: 0.5rem 0.65rem;
    font-size: 0.66rem;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    position: sticky;
    top: 0;
  }
  .case-table tbody td {
    padding: 0.55rem 0.65rem;
    border-bottom: 1px solid var(--line);
    vertical-align: top;
    word-wrap: break-word;
    overflow-wrap: anywhere;
    overflow: hidden;
  }
  .case-table tbody tr:last-child td { border-bottom: none; }
  /* col-ref is for short paragraph refs like "L26" — keep nowrap */
  .case-table .col-ref, .case-table .col-tier, .case-table .col-fn { white-space: nowrap; color: var(--muted); font-variant-numeric: tabular-nums; }
  /* col-date is short — keep nowrap */
  .case-table .col-date { white-space: nowrap; color: var(--muted); font-variant-numeric: tabular-nums; }
  /* col-pages can be long ("pp. 19-28 (PDF lines 660-665)") — allow wrap */
  .case-table .col-pages { white-space: normal; color: var(--muted); font-variant-numeric: tabular-nums; }
  .case-table .col-claim, .case-table .col-notes, .case-table .col-result, .case-table .col-reason, .case-table .col-change { white-space: normal; }
  .case-table .col-source { white-space: normal; }
  /* Status badges: wrap their text inside the cell instead of overflowing */
  .status-badge {
    display: inline-block;
    padding: 0.15rem 0.45rem;
    border-radius: 3px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    line-height: 1.3;
    white-space: normal;
    word-break: break-word;
    max-width: 100%;
  }
  .status-VERIFIED { background: var(--locked-soft); color: var(--locked); }
  .status-CORRECTED { background: #f7d9d0; color: #b8523a; }
  .status-PENDING { background: var(--deferred-soft); color: var(--deferred); }
  .status-INTERPRETIVE, .status-OTHER { background: var(--draft-soft); color: var(--draft); }
  .status-CITATIONALLY { background: var(--draft-soft); color: var(--draft); }
  .status-PARTIAL { background: var(--deferred-soft); color: var(--deferred); }
  .case-section ul.openq { list-style: none; padding: 0; margin: 0; background: var(--card); border: 1px solid var(--line); border-radius: 4px; }
  .case-section ul.openq li { padding: 0.55rem 0.85rem; border-bottom: 1px solid var(--line); font-size: 0.88rem; }
  .case-section ul.openq li:last-child { border-bottom: none; }
  .case-section ul.openq li.done { color: var(--muted); text-decoration: line-through; }
  .case-section ul.openq li::before { content: "☐ "; color: var(--muted); margin-right: 0.3rem; }
  .case-section ul.openq li.done::before { content: "☑ "; color: var(--locked); }
  .case-empty { color: var(--muted); font-size: 0.85rem; font-style: italic; padding: 0.5rem 0; }

  /* ===== Audit overview page ===== */
  .audit-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.75rem; margin-bottom: 1.5rem; }
  .toplinks { font-size: 0.85rem; margin-bottom: 0.5rem; }
  .toplinks a { color: var(--accent); text-decoration: none; margin-right: 1rem; }
  .toplinks a:hover { text-decoration: underline; }
  .topflag {
    display: inline-block;
    padding: 0.12rem 0.5rem;
    border-radius: 10px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    margin-left: 0.3rem;
    vertical-align: middle;
  }
  .topflag-ok { background: var(--locked-soft); color: var(--locked); }
  .topflag-bad { background: #f7d9d0; color: #b8523a; }
  .topflag-bad a { color: #b8523a; margin-right: 0; }
"""


def _status_cell(status_raw: str) -> str:
    """Render a status cell with a coloured badge. Handles multi-status strings
    like 'CORRECTED (PHANTOM QUOTE REMOVED)' or 'VERIFIED + CORRECTED' by
    colouring on the first canonical token.
    """
    raw = (status_raw or "").strip()
    upper = raw.upper()
    # Pick the first canonical status token that appears in the string
    canonical = ["VERIFIED", "CORRECTED", "PENDING", "INTERPRETIVE", "PARTIAL", "CITATIONALLY"]
    cls = "OTHER"
    for token in canonical:
        if token in upper:
            cls = token
            break
    return f'<span class="status-badge status-{cls}">{escape(raw or "—")}</span>'


def render_case_page(num: int, c: dict) -> str:
    """Render the per-chapter open-issues page. Works for chapters with or
    without a fact-check ledger; always shows open punch-list items.
    """
    ledger = c.get("ledger") or {}
    title = c.get("title") or f"Chapter {num}"
    last_updated = ledger.get("last_updated") or "—"
    audit_reports = ledger.get("audit_reports") or []
    lock_status = ledger.get("lock_status") or ""
    has_ledger = bool(ledger)

    # Reports list (links to vault files if we can resolve them)
    report_links = []
    for r in audit_reports:
        # The bullet is usually like: "Working Drafts/Citation Audit ... (2026-05-17)"
        # Try to find the actual file.
        rel = r.split(" (")[0].strip()
        candidate = VAULT_ROOT / rel
        if candidate.exists():
            report_links.append(f'<a href="{file_url(candidate)}">{escape(r)}</a>')
        else:
            report_links.append(escape(r))
    reports_html = " · ".join(report_links) if report_links else "—"

    # --- Claims Register ---
    claims_rows = []
    for row in ledger.get("claims", []):
        ref = row.get("¶", "")
        claim = row.get("Claim", "")
        tier = row.get("Tier", "")
        status_html = _status_cell(row.get("Status", ""))
        sources = row.get("Source(s)", "") or row.get("Source", "")
        fn = row.get("Footnote", "")
        notes = row.get("Notes", "")
        last_checked = row.get("Last checked", "")
        claims_rows.append(f"""
        <tr>
          <td class="col-ref">{escape(ref)}</td>
          <td class="col-claim">{escape(claim)}</td>
          <td class="col-tier">{escape(tier)}</td>
          <td>{status_html}</td>
          <td class="col-notes">{escape(sources)}</td>
          <td class="col-fn"><code>{escape(fn)}</code></td>
          <td class="col-notes">{escape(notes)}</td>
          <td class="col-date">{escape(last_checked)}</td>
        </tr>""")
    if claims_rows:
        claims_table = f"""
        <table class="case-table">
          <colgroup>
            <col style="width:48px"><col style="width:28%"><col style="width:40px">
            <col style="width:170px"><col style="width:13%"><col style="width:110px">
            <col style="width:auto"><col style="width:90px">
          </colgroup>
          <thead><tr>
            <th>¶</th><th>Claim</th><th>Tier</th><th>Status</th><th>Source(s)</th>
            <th>Footnote</th><th>Notes</th><th>Last checked</th>
          </tr></thead>
          <tbody>{''.join(claims_rows)}</tbody>
        </table>"""
    else:
        claims_table = '<div class="case-empty">No claims register entries yet.</div>'

    # --- Source Pages Consulted ---
    src_rows = []
    for row in ledger.get("sources", []):
        src_rows.append(f"""
        <tr>
          <td class="col-source">{escape(row.get('Source', ''))}</td>
          <td class="col-pages">{escape(row.get('Pages', ''))}</td>
          <td class="col-result">{escape(row.get('Result', ''))}</td>
          <td class="col-date">{escape(row.get('Date', ''))}</td>
        </tr>""")
    if src_rows:
        src_table = f"""
        <table class="case-table">
          <colgroup>
            <col style="width:22%"><col style="width:18%"><col style="width:auto"><col style="width:90px">
          </colgroup>
          <thead><tr><th>Source</th><th>Pages</th><th>Result</th><th>Date</th></tr></thead>
          <tbody>{''.join(src_rows)}</tbody>
        </table>"""
    else:
        src_table = '<div class="case-empty">No source-pages-consulted entries yet.</div>'

    # --- Editorial Decisions ---
    ed_rows = []
    for row in ledger.get("editorial", []):
        ed_rows.append(f"""
        <tr>
          <td class="col-date">{escape(row.get('Date', ''))}</td>
          <td class="col-change">{escape(row.get('Change', ''))}</td>
          <td class="col-reason">{escape(row.get('Reason', ''))}</td>
        </tr>""")
    if ed_rows:
        ed_table = f"""
        <table class="case-table">
          <colgroup><col style="width:110px"><col style="width:45%"><col style="width:1*"></colgroup>
          <thead><tr><th>Date</th><th>Change</th><th>Reason</th></tr></thead>
          <tbody>{''.join(ed_rows)}</tbody>
        </table>"""
    else:
        ed_table = '<div class="case-empty">No editorial decisions recorded.</div>'

    # --- Greek Verification Log ---
    greek_rows = []
    for row in ledger.get("greek", []):
        greek_rows.append(f"""
        <tr>
          <td class="col-ref">{escape(row.get('Passage', ''))}</td>
          <td class="col-notes">{escape(row.get('Greek claimed', ''))}</td>
          <td class="col-notes">{escape(row.get('Actually in text?', ''))}</td>
          <td class="col-notes">{escape(row.get('Notes', ''))}</td>
        </tr>""")
    if greek_rows:
        greek_section = f"""
        <div class="case-section">
          <h2>3. Greek Verification Log<span class="count">{len(greek_rows)} entries</span></h2>
          <table class="case-table">
            <thead><tr><th>Passage</th><th>Greek claimed</th><th>In text?</th><th>Notes</th></tr></thead>
            <tbody>{''.join(greek_rows)}</tbody>
          </table>
        </div>"""
    else:
        greek_section = ""

    # --- Open Questions ---
    oq_items = ledger.get("open_questions", [])
    if oq_items:
        def _li(it):
            cls = ' class="done"' if it["checked"] else ""
            return f"<li{cls}>{escape(it['text'])}</li>"
        items_html = "".join(_li(it) for it in oq_items)
        # Note: escape() preserves markdown bold markers — fine for plain rendering
        oq_section = f"""
        <div class="case-section">
          <h2>6. Open Questions<span class="count">{len(oq_items)} items</span></h2>
          <ul class="openq">{items_html}</ul>
        </div>"""
    else:
        oq_section = ""

    audit = c.get("audit") or {}
    if has_ledger:
        counts_html = (
            f'<span class="aud aud-v">{audit.get("verified", 0)} verified</span> · '
            f'<span class="aud aud-c">{audit.get("corrected", 0)} corrected</span> · '
            f'<span class="aud aud-p">{audit.get("pending", 0)} pending</span>'
        )
    else:
        counts_html = '<span class="aud-none">No fact-check ledger yet</span>'

    # Punch List open items for this chapter
    punch_open = c.get("punch_open", [])
    if punch_open:
        # Clean up bold markers for HTML rendering while preserving the rest
        def _strip_bold(s):
            return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        punch_items_html = "".join(
            f"<li>{_strip_bold(escape(item))}</li>" for item in punch_open
        )
        punch_section = f"""
        <div class="case-section">
          <h2>Open Punch-List Items<span class="count">{len(punch_open)} open</span></h2>
          <ul class="openq">{punch_items_html}</ul>
        </div>"""
    else:
        punch_section = """
        <div class="case-section">
          <h2>Open Punch-List Items<span class="count">0 open</span></h2>
          <div class="case-empty">No open punch-list items for this chapter.</div>
        </div>"""

    # Post-lock deferred items get their own section — they are future
    # enhancements Mr. Duke deferred at lock, not open chapter work, and are
    # never counted against the lock.
    punch_deferred = c.get("punch_deferred", [])
    if punch_deferred:
        def _strip_bold_d(s):
            return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        deferred_html = "".join(
            f"<li>{_strip_bold_d(escape(item))}</li>" for item in punch_deferred
        )
        punch_section += f"""
        <div class="case-section">
          <h2>Deferred (post-lock enhancements)<span class="count">{len(punch_deferred)} deferred — not counted against the lock</span></h2>
          <ul class="openq">{deferred_html}</ul>
        </div>"""

    # If no ledger exists, render a minimal page focused on the punch list.
    if not has_ledger:
        chapter_file_link = f'<a href="{file_url(c["path"])}">Open chapter file →</a>' if c.get("path") else ""
        return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Ch. {num} — Open Issues · Reframing Reality</title>
<style>{CSS}</style>
</head><body>
<div class="case-container">
  <a class="case-back" href="/">← Back to dashboard</a>
  <div class="case-header">
    <h1>Ch. {num} — {escape(title)}</h1>
    <div class="case-meta">{counts_html} · {chapter_file_link}</div>
  </div>

  {punch_section}

  <p class="meta">No fact-check ledger file at <code>Fact Check/Ch. {num} — …md</code>. When one is created, the Claims Register, Source Pages Consulted, Editorial Decisions, and audit Open Questions will appear here.</p>
</div>
</body></html>
"""

    # Full case page (with ledger)
    ledger_file_link = f'<a href="{file_url(ledger["path"])}">Open ledger file →</a>' if ledger.get("path") else ""
    chapter_file_link = f'<a href="{file_url(c["path"])}">Open chapter file →</a>' if c.get("path") else ""

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Ch. {num} — Open Issues · Reframing Reality</title>
<style>{CSS}</style>
</head><body>
<div class="case-container">
  <a class="case-back" href="/">← Back to dashboard</a>
  <div class="case-header">
    <h1>Ch. {num} — {escape(title)}</h1>
    <div class="case-meta">
      Last updated {escape(last_updated)} · {counts_html}
      <br>Reports: {reports_html}
      <br>{chapter_file_link} · {ledger_file_link}
    </div>
  </div>

  {f'<div class="case-lockbox">{escape(lock_status)}</div>' if lock_status else ''}

  {punch_section}

  {oq_section}

  <div class="case-section">
    <h2>Claims Register<span class="count">{len(ledger.get('claims', []))} entries</span></h2>
    {claims_table}
  </div>

  <div class="case-section">
    <h2>Source Pages Consulted<span class="count">{len(ledger.get('sources', []))} entries</span></h2>
    {src_table}
  </div>

  {greek_section}

  <div class="case-section">
    <h2>Editorial Decisions<span class="count">{len(ledger.get('editorial', []))} entries</span></h2>
    {ed_table}
  </div>
</div>
</body></html>
"""


def render_audit_overview() -> str:
    """Cross-chapter rollup: all pending acquisitions, all editorial decisions,
    summary counts.
    """
    chapters = gather_chapters()

    # Aggregate
    total = {"verified": 0, "corrected": 0, "pending": 0, "interpretive": 0, "other": 0}
    all_editorial = []  # (chapter_num, title, date, change, reason)
    all_open_qs = []    # (chapter_num, title, text, checked)
    chapters_with_ledger = 0
    for c in chapters:
        if not c.get("audit"):
            continue
        chapters_with_ledger += 1
        for k in total:
            total[k] += c["audit"].get(k, 0)
        ledger = c.get("ledger") or {}
        for row in ledger.get("editorial", []):
            all_editorial.append((c["num"], c["title"], row.get("Date", ""), row.get("Change", ""), row.get("Reason", "")))
        for q in ledger.get("open_questions", []):
            all_open_qs.append((c["num"], c["title"], q.get("text", ""), q.get("checked", False)))

    # Sort open questions: unchecked first, then by chapter
    all_open_qs.sort(key=lambda x: (x[3], x[0]))
    all_editorial.sort(key=lambda x: (x[0], x[2]))

    stats_html = f"""
    <div class="audit-stats">
      <div class="stat"><div class="label">Chapters Audited</div><div class="value">{chapters_with_ledger}</div><div class="sub">with ledger files</div></div>
      <div class="stat"><div class="label">Claims Verified</div><div class="value" style="color:var(--locked)">{total['verified']}</div><div class="sub">verbatim against source</div></div>
      <div class="stat"><div class="label">Errors Corrected</div><div class="value" style="color:#b8523a">{total['corrected']}</div><div class="sub">in-place fixes</div></div>
      <div class="stat"><div class="label">Pending Items</div><div class="value" style="color:var(--deferred)">{total['pending']}</div><div class="sub">awaiting source / verification</div></div>
    </div>"""

    # Editorial decisions across all chapters
    ed_rows = []
    for chnum, title, date, change, reason in all_editorial:
        ed_rows.append(f"""
        <tr>
          <td class="col-ref"><a href="/case/{chnum}">Ch. {chnum}</a></td>
          <td class="col-date">{escape(date)}</td>
          <td class="col-change">{escape(change)}</td>
          <td class="col-reason">{escape(reason)}</td>
        </tr>""")
    if ed_rows:
        ed_table = f"""
        <table class="case-table">
          <colgroup><col style="width:70px"><col style="width:90px"><col style="width:45%"><col style="width:1*"></colgroup>
          <thead><tr><th>Chapter</th><th>Date</th><th>Change</th><th>Reason</th></tr></thead>
          <tbody>{''.join(ed_rows)}</tbody>
        </table>"""
    else:
        ed_table = '<div class="case-empty">No editorial decisions recorded across audited chapters.</div>'

    # Open questions across all chapters
    oq_rows = []
    for chnum, title, text, checked in all_open_qs:
        mark = "☑" if checked else "☐"
        cls = ' class="done"' if checked else ""
        oq_rows.append(f"""
        <tr{cls}>
          <td class="col-ref"><a href="/case/{chnum}">Ch. {chnum}</a></td>
          <td>{mark}</td>
          <td class="col-notes">{escape(text)}</td>
        </tr>""")
    if oq_rows:
        oq_table = f"""
        <table class="case-table">
          <colgroup><col style="width:70px"><col style="width:30px"><col style="width:1*"></colgroup>
          <thead><tr><th>Chapter</th><th></th><th>Open question / pending acquisition</th></tr></thead>
          <tbody>{''.join(oq_rows)}</tbody>
        </table>"""
    else:
        oq_table = '<div class="case-empty">No open questions across audited chapters.</div>'

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Audit — Reframing Reality</title>
<style>{CSS}</style>
</head><body>
<div class="case-container">
  <a class="case-back" href="/">← Back to dashboard</a>
  <div class="case-header">
    <h1>Audit overview</h1>
    <div class="case-meta">Cross-chapter rollup of all citation-audit work. Click any chapter link to drill in.</div>
  </div>

  {stats_html}

  <div class="case-section">
    <h2>Editorial Decisions<span class="count">{len(all_editorial)} fixes across the book</span></h2>
    {ed_table}
  </div>

  <div class="case-section">
    <h2>Open Questions &amp; Pending Acquisitions<span class="count">{len(all_open_qs)} items</span></h2>
    {oq_table}
  </div>
</div>
</body></html>
"""


def render_html():
    chapters = gather_chapters()
    appendices = gather_appendices()

    total_chap = sum(c["words"] for c in chapters)
    total_app = sum(a["words"] for a in appendices)
    total = total_chap + total_app
    total_footnotes = sum(c["footnote_count"] for c in chapters) + sum(a["footnote_count"] for a in appendices)
    footnote_words = sum(c["footnote_words"] for c in chapters) + sum(a["footnote_words"] for a in appendices)
    chap_footnotes = sum(c["footnote_count"] for c in chapters)
    app_footnotes = sum(a["footnote_count"] for a in appendices)
    locked = [c for c in chapters if c["status"] == "LOCKED"]
    lock_drift = [c for c in chapters if c["status"] in ("UNLOCKED", "OUT OF SYNC")]
    deferred = [c for c in chapters if c["status"] == "DEFERRED"]
    drafts = [c for c in chapters if c["status"] not in ("LOCKED", "UNLOCKED", "OUT OF SYNC", "DEFERRED")]
    locked_words = sum(c["words"] for c in locked)
    pct_locked = (locked_words / total_chap * 100) if total_chap else 0

    max_words = max((c["words"] for c in chapters), default=1)

    rows = "".join(render_chapter_row(c, max_words) for c in chapters)
    app_rows = "".join(render_appendix_row(a) for a in appendices)

    progress = render_progress_bar(chapters)

    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8">
<title>Reframing Reality — Manuscript Dashboard</title>
<style>{CSS}</style>
</head><body>
<div class="container">
  <h1>Reframing Reality</h1>
  <p class="subtitle">Manuscript dashboard — live from the vault. {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}</p>

  <div class="toplinks">
    <a href="/audit">Audit overview →</a>
    <a href="/servers">Local servers →</a>
    <a href="http://127.0.0.1:5050/management" target="_blank" rel="noopener">RAG management ↗</a>
    <a href="http://127.0.0.1:5050" target="_blank" rel="noopener">RAG search ↗</a>
    <a href="/servers/health">RAG health →</a>
    {(
        '<span class="topflag topflag-ok" title="Greek server available — primary source for any Greek primary text">Greek server: ✓</span>'
        if greek_server_status()["mounted"]
        else '<span class="topflag topflag-bad" title="PRO-BLADE not mounted — Greek primary text unavailable; click Local servers for details"><a href="/servers">Greek server: ✗</a></span>'
    )}
  </div>

  <div class="stats">
    <div class="stat">
      <div class="label">Total Words</div>
      <div class="value">{total:,}</div>
      <div class="sub">{total_chap:,} chapters · {total_app:,} appendices</div>
    </div>
    <div class="stat">
      <div class="label">Chapters</div>
      <div class="value">{len(chapters)}</div>
      <div class="sub">{len(appendices)} appendices</div>
    </div>
    <div class="stat">
      <div class="label">Locked</div>
      <div class="value">{len(locked)}</div>
      <div class="sub">{locked_words:,} words ({pct_locked:.0f}% of book)</div>
    </div>
    <div class="stat">
      <div class="label">Draft / Spec</div>
      <div class="value">{len(drafts)}</div>
      <div class="sub">{len(deferred)} deferred</div>
    </div>
    <div class="stat">
      <div class="label">Footnotes</div>
      <div class="value">{total_footnotes:,}</div>
      <div class="sub">{chap_footnotes:,} chapters · {app_footnotes:,} appendices</div>
    </div>
    <div class="stat">
      <div class="label">Footnote Words</div>
      <div class="value">{footnote_words:,}</div>
      <div class="sub">{(footnote_words / total * 100):.0f}% of total book words</div>
    </div>
  </div>

  {progress}
  <div class="progress-legend">
    <span><span class="swatch locked"></span>Locked</span>
    <span><span class="swatch draft"></span>Draft / Spec-complete</span>
    <span><span class="swatch deferred"></span>Deferred</span>
  </div>

  <h2>Chapters<span class="count">{total_chap:,} words</span></h2>
  <div class="audit-legend">
    <span class="item"><span class="letter v">V</span>verified verbatim against source</span>
    <span class="item"><span class="letter c">C</span>error caught &amp; corrected in-place</span>
    <span class="item"><span class="letter p">P</span>pending external source</span>
  </div>
  <table>
    <thead><tr>
      <th>#</th><th>Title</th><th class="words">Words</th><th>Relative</th><th>Status</th><th title="Open items per chapter (Punch List open + Ledger Open Questions). Under the strict lock-means-complete rule, all must be 0 to lock.">Open</th><th title="Audit: V=verified · C=corrected · P=pending. Click to open case page.">Audit</th><th>Modified</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>

  <h2>Appendices<span class="count">{total_app:,} words</span></h2>
  <table>
    <thead><tr><th>Title</th><th class="words">Words</th><th>Modified</th></tr></thead>
    <tbody>{app_rows}</tbody>
  </table>

  <p class="meta">Refresh to update. Server: <code>http://{HOST}:{PORT}</code> · Press <code>Ctrl-C</code> in the terminal to stop.</p>
</div>
</body></html>
"""


# ---------- server ----------


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Auto-reload: if dashboard.py has been modified since the server started,
        # serve a tiny "reloading" page that auto-refreshes in 1 second, then
        # re-exec the script. The next request will hit the new code.
        try:
            current_mtime = _SCRIPT_PATH.stat().st_mtime
        except OSError:
            current_mtime = _SCRIPT_MTIME
        if current_mtime > _SCRIPT_MTIME:
            reload_html = (
                "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                "<title>Reloading...</title>"
                "<meta http-equiv='refresh' content='1'>"
                "<style>body{font-family:-apple-system,sans-serif;color:#6b6b6b;"
                "background:#fafaf8;display:flex;align-items:center;justify-content:center;"
                "height:100vh;margin:0;}p{font-size:0.9rem;letter-spacing:0.04em;}</style>"
                "</head><body><p>dashboard.py changed — reloading...</p></body></html>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(reload_html)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(reload_html)
            try:
                self.wfile.flush()
            except Exception:
                pass
            print(f"\n[reload] {_SCRIPT_PATH.name} changed — re-executing server...")
            sys.stdout.flush()
            os.execv(sys.executable, [sys.executable] + sys.argv)
            return  # not reached

        if self.path in ("/", "/index.html"):
            html = render_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(html)
            return
        if self.path == "/audit":
            html = render_audit_overview().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(html)
            return
        m = re.match(r"^/case/(\d+)/?$", self.path)
        if m:
            num = int(m.group(1))
            chapters = gather_chapters()
            chap = next((c for c in chapters if c["num"] == num), None)
            if chap is None:
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    f"<p>No Chapter {num} found in the vault. "
                    f'<a href="/">← Back to dashboard</a></p>'.encode("utf-8")
                )
                return
            # render_case_page handles chapters with or without a ledger
            html = render_case_page(num, chap).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(html)
            return
        if self.path == "/servers" or self.path.startswith("/servers?"):
            # Allow an optional `?notice=...` query string to surface the result
            # of the most recent start/stop action after the POST → GET redirect.
            notice = ""
            if "?" in self.path:
                qs = self.path.split("?", 1)[1]
                params = parse_qs(qs)
                notice = params.get("notice", [""])[0]
            html = render_servers_page(notice=notice).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(html)
            return
        if self.path == "/servers/health":
            html = render_health_page().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(html)
            return
        m = re.match(r"^/servers/tail/([\w-]+)/?$", self.path)
        if m:
            html = render_log_tail_page(m.group(1)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(html)
            return
        if self.path == "/healthz":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        # Server action routes: /servers/(start|stop|restart)/<name>
        m = re.match(r"^/servers/(start|stop|restart)/([\w-]+)/?$", self.path)
        if m:
            action, name = m.group(1), m.group(2)
            # Only allow names from the registered service list.
            if not any(s["name"] == name for s in SERVICES):
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"unknown service")
                return
            code, output = run_servers_command(action, name)
            # PRG: redirect to GET /servers with the wrapper's output surfaced
            # as a notice block. Brief sleep so port-state has settled.
            import time
            time.sleep(0.5)
            from urllib.parse import quote as urlquote
            notice = output if output else f"{action} {name}: exit {code}"
            self.send_response(303)  # See Other — convert POST → GET
            self.send_header("Location", f"/servers?notice={urlquote(notice)}")
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        # Quieter than the default; one line per request
        print(f"[{self.log_date_time_string()}] {self.address_string()} {format % args}")


def main():
    if not CHAPTERS_DIR.exists():
        print(f"Chapters directory not found at {CHAPTERS_DIR}")
        print("Run this script from the Reframing Reality Vault root.")
        return
    print(f"Reframing Reality dashboard")
    print(f"  Vault:  {VAULT_ROOT}")
    print(f"  Open:   http://{HOST}:{PORT}")
    print(f"  Stop:   Ctrl-C\n")
    with socketserver.TCPServer((HOST, PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""citedworks.py — the works the chapters cite, and the Claims records about them.

    import citedworks as W
    W.cited_works(B.chapter_files())   {title: Counter({chapter: count})}
    W.ledger_records()                 {normalised title: (file, line, record, has_path)}
    W.match(W.norm(title), recs)       the record key that names this work, or None
    W.load_tool("have.sh")             a sibling tool, imported as a module

WHY ONE MODULE

    check-read.sh, check-path.sh and resolve-sources.sh each held their own copy
    of the footnote extractor and the title matcher. Two matchers drift: a fix
    to one leaves the others wrong, and in the system this kit comes from that
    happened often enough that the author said so. So the extractor, the
    normaliser and the record matcher live here once, and every tool that asks
    "which works does the book cite" imports them.
"""
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from importlib.machinery import SourceFileLoader
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

# A periodical is cited by article, not read whole. Listed, not counted.
PERIODICAL = re.compile(
    r"\b(times|post|journal|review|report|magazine|gazette|herald|tribune|"
    r"news|daily|weekly|quarterly|substack|proceedings|bulletin|record|"
    r"dispatch|chronicle)\b", re.I)

STOP = re.compile(r"^(see|cf|ibid|op\. cit|the same|above|below|verbatim)\b", re.I)

# Italics in a footnote are not always a work. A publisher's city, a ship, a
# foreign phrase and a case name all take italics too, and the extractor
# cannot tell them apart. A city reached the resolver once and matched an
# article that happened to name it. A city is not a book, and no path will
# ever be right for it.
NOT_A_WORK = re.compile(
    r"^(new york|london|paris|boston|philadelphia|chicago|washington|"
    r"cambridge|oxford|geneva|amsterdam|venice|rome|berlin|vienna|"
    r"new haven|princeton|chapel hill|ann arbor|los angeles|san francisco|"
    r"ibid|passim|sic|et al|inter alia|op cit|loc cit)\s*$", re.I)

# ITALIC MEANS ONE ASTERISK. `**bold**` contains `*bold*`, so a looser pattern
# read every bolded phrase in a footnote as a book title, and an agent then
# spent searches failing to find each phantom work. The lookarounds require
# the delimiters to be single asterisks.
ITALIC = re.compile(r"(?<!\*)\*(?!\*)([A-Z][^*]{6,90})\*(?!\*)")


def norm(s: str) -> str:
    s = re.sub(r"[^a-z0-9 ]+", " ", str(s).lower())
    s = re.sub(r"\b(the|a|an|of|and|in|on|to|for|its|his|her|their)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def cited_works(chapters):
    """Italicised work titles inside footnote definitions, and where they appear."""
    out = defaultdict(Counter)
    for f in chapters:
        n = B.chapter_number(f)
        if n is None:
            continue
        for l in Path(f).read_text(encoding="utf-8").split("\n"):
            if not l.startswith("[^"):
                continue
            for m in ITALIC.finditer(l):
                s = m.group(1).strip().rstrip(",.;:")
                if (len(s.split()) < 2 or s.isupper() or STOP.match(s)
                        or NOT_A_WORK.match(s)):
                    continue
                out[s][n] += 1
    return out


def claims_files():
    """Every live Claims file. A .bak is a snapshot, not the book's state."""
    if not B.CLAIMS.is_dir():
        return []
    return [f for f in sorted(B.CLAIMS.glob("*.jsonl")) if not B.is_backup(f)]


def claims_rows():
    """(file, line number, record) for every parseable row in every Claims file."""
    for f in claims_files():
        for n, line in enumerate(f.read_text(encoding="utf-8",
                                             errors="replace").splitlines(), 1):
            if not line.strip():
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if isinstance(o, dict):
                yield f, n, o


def declared_elsewhere(o) -> bool:
    """Did somebody SAY where this was read, or is the field just null?

    The Claims template writes `"drive_path": null` into every record whether
    or not anyone thought about it, so the presence of the key proves nothing.
    Reading a null as a deliberate "not in the library" once reported hundreds
    of works as honest Sources Wanted entries and none as forgotten: a check
    that congratulates itself. A declaration has to say something: a
    `location` naming where the work was read instead, or a note that it could
    not be found.
    """
    # A NON-WORK NEEDS NO PATH, and saying so is a declaration like any other.
    # The extractor pulls italics, so a religious name or a society's name
    # arrives looking like a title. Recording it as not_a_work is the
    # resolution; leaving it unanswered would keep asking for a file that can
    # never exist.
    if o.get("not_a_work"):
        return True
    loc = (o.get("location") or "").strip()
    if not loc:
        return False
    return bool(re.search(r"\b(not on the drive|not in the|could not|unavailable|"
                          r"no copy|archive|https?://|corpus|tlg|phi\d|perseus)\b",
                          loc, re.I))


def ledger_records():
    """Every Claims record carrying a title, keyed by normalised title.

    Keeps the record with a path in preference to one without, because two
    agents can write the same work from two chapters and only one looked up
    the file. A record that DECLARES the work absent beats a silent one:
    without that, a Sources Wanted record written today loses to an older
    record that never filled the field, and the work keeps reporting as
    forgotten after somebody searched for it and wrote down that it is not
    there.
    """
    out = {}
    for f, n, o in claims_rows():
        t = (o.get("title") or "").strip()
        k = norm(t) if t else ""
        if not k:
            continue
        has = bool((o.get("drive_path") or "").strip())
        rank = 2 if has else (1 if declared_elsewhere(o) else 0)
        prior = out.get(k)
        prior_rank = 0
        if prior is not None:
            prior_rank = 2 if prior[3] else (1 if declared_elsewhere(prior[2]) else 0)
        if prior is None or rank > prior_rank:
            out[k] = (f, n, o, has)
    return out


def match(k: str, recs: dict):
    """The record key that names this work: exact, or containment either way
    on a key long enough not to collide. A footnote cites a short title where
    the Claims row holds the full title with its subtitle; exact keys alone
    once matched a quarter of what had been read."""
    if k in recs:
        return k
    if len(k) < 10:
        return None
    for rk in recs:
        if len(rk) >= 10 and (k in rk or rk in k):
            return rk
    return None


def load_tool(name: str):
    """Import a sibling tool by file name, `.sh` included.

    Most tools here are Python behind a .sh name, and importlib infers a loader
    from the extension, so it returns a spec with no loader and the import dies
    on an AttributeError that says nothing about the cause. Naming the loader
    is the whole fix. sys.argv is swapped while the module runs its top level,
    so a tool that reads its arguments at import time sees none.
    """
    path = str(Path(__file__).resolve().parent / name)
    modname = re.sub(r"\W", "_", Path(name).stem)
    spec = importlib.util.spec_from_file_location(
        modname, path, loader=SourceFileLoader(modname, path))
    m = importlib.util.module_from_spec(spec)
    argv, sys.argv = sys.argv, [name]
    try:
        spec.loader.exec_module(m)
    finally:
        sys.argv = argv
    return m

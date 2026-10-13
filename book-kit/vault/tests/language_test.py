#!/usr/bin/env python3
"""language_test.py — the language and footnote checks find the sample book's planted faults and pass its clean notes.

    python3 vault/tests/language_test.py        # or: pytest vault/tests/language_test.py

Each test copies the sample vault to a temporary folder, sets BOOK_VAULT to
it, copies in Methodology/Word Lists.md (and Glossary Terms.md where needed)
from this kit, and runs the tools there. Nothing is written outside the
temporary folder.

What it holds the tools to (sample/README.md lists the planted faults):
  * fault 3: check-banned-words.sh reports "carries" in Chapter 1, and the
    carve-out pattern keeps "the edition printed by" a printer out of the work;
  * fault 2: check-note-content.py and assess-notes.py flag the sentence of
    interpretation in [^fed1_test], and pass every plain citation;
  * check-footnotes, check-anchors, check-crossrefs, check-footnote-length and
    check-epistemics run clean on the sample;
  * check-footnotes catches an orphan, an unanchored note and a slug defined
    twice when they are planted;
  * check-ellipsis prints the words an ellipsis took out, found in the library
    across a line break;
  * check-glossary reports a term used without a gloss and passes a glossed one.
"""
import importlib.util
from importlib.machinery import SourceFileLoader
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

KIT_VAULT = Path(__file__).resolve().parent.parent
TOOLS = KIT_VAULT / "tools"
SAMPLE = KIT_VAULT.parent / "sample"


def make_vault():
    d = Path(tempfile.mkdtemp(prefix="lang_test_"))
    v = d / "sample"
    shutil.copytree(SAMPLE, v)
    (v / "Methodology").mkdir(exist_ok=True)
    shutil.copy(KIT_VAULT / "Methodology" / "Word Lists.md", v / "Methodology" / "Word Lists.md")
    return v


def run(vault, script, *args):
    env = dict(os.environ, BOOK_VAULT=str(vault))
    p = subprocess.run([sys.executable, str(TOOLS / script), *args], env=env,
                       capture_output=True, text=True, timeout=120)
    assert "Traceback" not in p.stderr, f"{script} crashed:\n{p.stderr}"
    return p.returncode, p.stdout


def load(name, file, vault):
    """Import a tool as a module, against `vault`. bookconfig reads BOOK_VAULT at import."""
    os.environ["BOOK_VAULT"] = str(vault)
    for m in [m for m in sys.modules if m in ("bookconfig", "notelib")]:
        del sys.modules[m]
    sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_loader(
        name, SourceFileLoader(name, str(TOOLS / file)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def chapter(vault, n):
    return next((vault / "Chapters").glob(f"Chapter {n:02d}*.md"))


# ── fault 3: the banned word ─────────────────────────────────────────────────

def test_banned_word_carries_in_chapter_1():
    v = make_vault()
    rc, out = run(v, "check-banned-words.sh")
    assert rc == 0
    assert re.search(r"Ch01/L\d+\s+carries\b", out), out
    assert "--- Ch02: clean" in out, out
    # "the edition printed by W. and T. Bradford": a printer as subject, carved.
    assert not re.search(r"Ch01/L\d+\s+printed\b", out), out
    assert "1 unruled hit(s)" in out, out
    rc, out = run(v, "check-banned-words.sh", "--counts")
    assert re.search(r"^\s*Ch01\s+1\s*$", out, re.M) and re.search(r"^\s*Ch02\s+0\s*$", out, re.M), out


def test_banned_word_list_has_one_loader():
    v = make_vault()
    cbw = load("cbw", "check-banned-words.sh", v)
    pats = cbw.load_list()
    assert len(pats) >= 15
    rx, pattern, carve, auto = next(p for p in pats if "carr" in p[1])
    assert rx.search("The sentence carries the frame.") and carve


def test_epistemics_clean_on_sample():
    v = make_vault()
    rc, out = run(v, "check-epistemics.sh")
    assert rc == 0 and "0 unruled candidate(s)" in out, out
    # And it does find a planted borrowed-authority line.
    ch = chapter(v, 1)
    ch.write_text(ch.read_text(encoding="utf-8") + "\nMost historians agree that the pamphlet sold well.\n",
                  encoding="utf-8")
    rc, out = run(v, "check-epistemics.sh", "1")
    assert "borrowed authority" in out, out


# ── fault 2: the note that holds an argument ─────────────────────────────────

def test_note_content_flags_fed1_test_only():
    v = make_vault()
    rc, out = run(v, "check-note-content.py")
    assert rc == 1, out
    assert "[^fed1_test]" in out and "philosophical experiment" in out, out
    for clean in ("paine_edition", "paine_society", "paine_wants", "fed1_heading"):
        assert f"[^{clean}]" not in out, f"{clean} flagged:\n{out}"
    assert "1 note(s)" in out, out


def test_assess_notes_flags_fed1_test_and_passes_citations():
    v = make_vault()
    an = load("assess_notes", "assess-notes.py", v)
    rows = {r["slug"]: r for r in an.rows()}
    assert set(rows) == {"paine_edition", "paine_society", "paine_wants", "fed1_heading", "fed1_test"}
    bad = rows["fed1_test"]
    assert bad["verdict"] == "CARRIES CONTENT", bad
    assert [f["pile"] for f in bad["findings"]] == ["CONTENT"], bad
    assert "philosophical experiment" in bad["findings"][0]["sentence"]
    for slug in ("paine_edition", "paine_society", "paine_wants", "fed1_heading"):
        assert rows[slug]["verdict"] == "CLEAN", rows[slug]
        assert rows[slug]["findings"] == [], rows[slug]
    # The public functions other tools import.
    assert an.classify("Paine, *Common Sense*, 14.", set(), "")[0] == "CITATION"
    assert an.classify("This book argues the founders were wrong.", set(), "")[0] == "JUDGEMENT"
    assert an.words("A b's") == ["a", "b's"]
    assert an.overlap("government society wants", {"government", "society"}) == 2 / 3
    rc, out = run(v, "assess-notes.py", "--json")
    assert rc == 1 and out.count("\n") == 1 and "fed1_test" in out, out


def test_check_note_content_api():
    v = make_vault()
    cnc = load("cnc", "check-note-content.py", v)
    s = cnc.sentences('Hamilton, *Federalist* No. 1. This shows that the founders saw it.')
    assert len(s) == 2, s
    assert cnc.LOCATOR.search(s[0]) and not cnc.LOCATOR.search(s[1])
    assert cnc.judge("Paine, *Common Sense* (Philadelphia, 1776).", set()) == []
    assert cnc.judge("This shows that the founders saw the Constitution as an experiment.", set())
    assert cnc.quoted_runs('the "a" and the "b"') == ["a", "b"]
    assert cnc.titlecased("Of the Origin and Design of Government in General")
    assert cnc.TITLE.search("*Common Sense*")


# ── the structural checks run clean, and catch what is planted ───────────────

def test_footnotes_clean_then_catch_planted_faults():
    v = make_vault()
    rc, out = run(v, "check-footnotes.sh", "--all")
    assert rc == 0 and out.count("no findings") == 2, out
    ch = chapter(v, 1)
    ch.write_text(ch.read_text(encoding="utf-8")
                  + "[^paine_wants]: Paine, *Common Sense*, a second definition.\n"
                  + "[^stray]: A note nothing points at, found in Chapters/ of the vault.\n"
                  + "A paragraph after the notes.\n", encoding="utf-8")
    rc, out = run(v, "check-footnotes.sh", "1")
    assert "G DUP-DEF" in out and "[^paine_wants]" in out, out
    assert "G NO-ANCHOR" in out and "[^stray]" in out, out
    assert "A ORPHAN" in out, out
    assert "D SELF-TALK" in out, out
    rc, out = run(v, "check-footnotes.sh", "1", "--json")
    assert '"class": "G DUP-DEF"' in out, out


def test_anchors_crossrefs_length_clean():
    v = make_vault()
    rc, out = run(v, "check-anchors.sh", "--all")
    assert re.search(r"ANCHORED\s+5", out) and re.search(r"NO ANCHOR\s+0", out), out
    rc, out = run(v, "check-crossrefs.sh")
    assert rc == 0 and "0 flagged" in out, out
    rc, out = run(v, "check-footnote-length.sh")
    assert rc == 0 and "0 unruled note(s)" in out, out
    rc, out = run(v, "check-footnote-length.sh", "--cap", "15")
    assert "[^fed1_heading]" in out, out


def test_crossref_to_missing_chapter_is_flagged():
    v = make_vault()
    ch = chapter(v, 2)
    ch.write_text(ch.read_text(encoding="utf-8").replace(
        "Hamilton framed", "As Chapter 9 shows, Hamilton framed", 1), encoding="utf-8")
    rc, out = run(v, "check-crossrefs.sh")
    assert rc == 1 and "NO SUCH CHAPTER FILE" in out, out


# ── the ellipsis check opens the library ─────────────────────────────────────

def test_ellipsis_recovers_the_cut_across_a_line_break():
    v = make_vault()
    rc, out = run(v, "check-ellipsis.sh")
    assert rc == 0 and "RECOVERED 0" in out and "NO SOURCE 0" in out, out
    ch = chapter(v, 2)
    ch.write_text(ch.read_text(encoding="utf-8").rstrip("\n") + "\n\n"
                  "Hamilton put it as a question, \"whether societies of men are really capable or not "
                  "of establishing good government … depend for their political constitutions on "
                  "accident and force.\"[^fed1_cut]\n\n"
                  "[^fed1_cut]: Hamilton, *The Federalist Papers*, No. 1.\n", encoding="utf-8")
    rc, out = run(v, "check-ellipsis.sh", "2")
    assert "RECOVERED" in out and "RECOVERED 1" in out, out
    assert "from reflection and choice, or whether they are forever destined to" in out, out
    e = load("e", "check-ellipsis.sh", v)
    assert e.flat("except\nin case  of attack") == "except in case of attack"


# ── the glossary check reads its term list from a file ───────────────────────

def test_glossary_reads_terms_file():
    v = make_vault()
    terms = v / "Methodology" / "Glossary Terms.md"
    if terms.exists():
        terms.unlink()                              # the copy only: start with no term list
    rc, out = run(v, "check-glossary.sh", "--all")
    assert rc == 0 and "No term list" in out, out
    shutil.copy(KIT_VAULT / "Methodology" / "Glossary Terms.md", terms)
    rc, out = run(v, "check-glossary.sh", "--terms")
    assert "0 terms defined" in out, out          # the template's examples are not entries
    terms.write_text(terms.read_text(encoding="utf-8")
                     + "**Publius**: the pen name the three authors signed.\n"
                     + "**Necessary Evil**: Paine's name for government.\n", encoding="utf-8")
    ch = chapter(v, 2)
    ch.write_text(ch.read_text(encoding="utf-8").rstrip("\n")
                  + "\n\nPublius signed every paper in the series\n", encoding="utf-8")
    rc, out = run(v, "check-glossary.sh", "--all")
    assert "Publius" in out and re.search(r"Ch02/L\d+", out), out
    assert "Necessary Evil" not in out, out      # glossed where it first appears
    rc, out = run(v, "check-glossary.sh", "--terms")
    assert "2 terms defined" in out and "2 of them appear" in out, out


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok    {name}")
            except AssertionError as exc:
                failed += 1
                print(f"  FAIL  {name}\n{exc}")
    print(f"\n{'FAILED' if failed else 'passed'}: {failed} failure(s)")
    sys.exit(1 if failed else 0)

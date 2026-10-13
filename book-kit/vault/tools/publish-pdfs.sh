#!/usr/bin/env python3
"""publish-pdfs.sh — make a PDF of each chapter and appendix, into [output] pdf_dir.

    tools/publish-pdfs.sh                     # every chapter and appendix
    tools/publish-pdfs.sh chapters            # chapters only
    tools/publish-pdfs.sh appendices          # appendices only
    tools/publish-pdfs.sh ch 2                # chapter 2 only
    tools/publish-pdfs.sh ch 2 3              # chapters 2 and 3
    tools/publish-pdfs.sh app F               # Appendix F only
    tools/publish-pdfs.sh --clean [...]       # DELETE every PDF in pdf_dir first, then publish

    --clean removes each *.pdf in the output folder before publishing. Use it
    when chapter numbering changes, so no PDF of an old draft is left behind.

WHAT IT NEEDS

    pandoc, and the xelatex engine from a TeX distribution:
        macOS:   brew install pandoc; brew install --cask mactex-no-gui
        Linux:   apt install pandoc texlive-xetex texlive-fonts-recommended texlive-fonts-extra
        Windows: install pandoc from pandoc.org and MiKTeX or TeX Live (tug.org/texlive)
    The Libertinus font, through TeX Live's package manager (any system):
        tlmgr install libertinus-fonts libertinust1math
    Libertinus has Greek (with accents), Latin and Hebrew. DejaVu Sans is used
    for one Hebrew point Libertinus lacks.

    When pandoc or xelatex is missing, the script says which one, prints the
    install line above, and stops before it touches the output folder: in the
    original system a publish aborted after the old PDFs had already been
    deleted, and the review folder was left empty.

WHERE THE PDFs GO

    `[output] pdf_dir` in book.toml. The script refuses when it is empty or
    the folder does not exist (a drive that is not mounted).

WHAT IT LEAVES OUT

    Anything between `<!-- PUBLISH-SKIP-START -->` and `<!-- PUBLISH-SKIP-END -->`
    in a chapter. The author keeps the outline, the decisions on record and any
    parked material in the chapter file, in context while drafting; this strips
    them at publish time.

HOW IT TYPESETS

    * `--from` turns off YAML front matter, so an early `---` section rule in a
      chapter is never read as the start of a metadata block.
    * It turns off pandoc's simple, multiline and grid tables: a `---` rule
      next to a line of text parses as a table header, and pandoc then sets the
      whole next paragraph in a column three characters wide. The chapters
      use no markdown tables, so nothing is lost. (Pipe tables still work.)
    * Footnotes print as endnotes, under "Notes" at the end of each chapter
      PDF: the author's choice, so page bottoms stay clean.
    * Glyphs the font lacks fail SILENTLY: xelatex prints "Missing character"
      and sets nothing, so the PDF looks finished while a character has
      vanished. In the original system a Hebrew vowel point disappeared from a
      footnote this way while the build reported OK. Three known gaps are
      mapped: ⊙ (U+2299) to math \\odot; HEBREW POINT QAMATS QATAN (U+05C7) from
      DejaVu Sans, because replacing it with the plain qamats would change the
      text; VARIATION SELECTOR-16 (U+FE0F) dropped. When you add a script or a
      symbol the book has not used before, check the xelatex output for
      "Missing character".

    The run goes on past a file that fails, and lists each failure at the end.

EXIT CODES
    0  every file published
    1  something failed, a converter is missing, or pdf_dir is not set
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookconfig as B  # noqa: E402

INSTALL = """  macOS:   brew install pandoc; brew install --cask mactex-no-gui
  Linux:   apt install pandoc texlive-xetex texlive-fonts-recommended texlive-fonts-extra
  Windows: pandoc from pandoc.org, and MiKTeX or TeX Live (tug.org/texlive)
  then:    tlmgr install libertinus-fonts libertinust1math"""

SKIP = re.compile(r"^<!-- PUBLISH-SKIP-START.*?^<!-- PUBLISH-SKIP-END[^\n]*\n?", re.M | re.S)


def converters_ok() -> bool:
    missing = [c for c in ("pandoc", "xelatex") if shutil.which(c) is None]
    if missing:
        print(f"ERROR: {' and '.join(missing)} not found. publish-pdfs.sh needs pandoc and the "
              f"xelatex engine:\n{INSTALL}\nNothing was changed.")
        return False
    return True


def pandoc_opts(endnotes_tex: Path):
    have_pkg = subprocess.run(["kpsewhich", "libertinus-otf.sty"], capture_output=True,
                              text=True).returncode == 0 if shutil.which("kpsewhich") else False
    if have_pkg:
        font = ["-V", r"header-includes=\usepackage{libertinus-otf}"]
    else:
        # Not every TeX installation ships the package (a Linux texlive-xetex
        # install has the fonts and not the package); load the same family
        # through fontconfig. Without this the run dies on a bare "Error
        # producing PDF" with no sign a LaTeX package is missing.
        print("Note: libertinus-otf.sty not found; loading Libertinus Serif via fontconfig.")
        font = ["-V", "mainfont=Libertinus Serif"]
    return [
        "--from=markdown-yaml_metadata_block-simple_tables-multiline_tables-grid_tables",
        "--pdf-engine=xelatex",
        *font,
        "-V", r"header-includes=\usepackage{endnotes}\let\footnote=\endnote\renewcommand\notesname{Notes}",
        "-V", r"header-includes=\usepackage{newunicodechar}\newunicodechar{⊙}{\ensuremath{\odot}}",
        "-V", r"header-includes=\newfontfamily\hebpoint{DejaVu Sans}\newunicodechar{ׇ}{{\hebpoint\char" + '"' + "05C7}}",
        "-V", "header-includes=\\newunicodechar{\ufe0f}{}",
        "-V", "geometry:margin=1in",
        f"--include-after-body={endnotes_tex}",
    ]


def appendices():
    if not B.APPENDICES.is_dir():
        return []
    return sorted(p for p in B.APPENDICES.glob("*.md") if not B.is_backup(p))


def publish(src: Path, out: Path, opts, failed):
    dest = out / f"{src.stem}.pdf"
    print(f"  → {dest.name}")
    with tempfile.TemporaryDirectory() as tmp:
        trimmed = Path(tmp) / src.name
        trimmed.write_text(SKIP.sub("", src.read_text(encoding="utf-8")), encoding="utf-8")
        r = subprocess.run(["pandoc", str(trimmed), "-o", str(dest), *opts],
                           capture_output=True, text=True, cwd=src.parent)
    if r.returncode == 0:
        print(f"    OK ({dest.stat().st_size // 1024} KB)")
        missing = [l for l in r.stderr.splitlines() if "Missing character" in l]
        for l in missing[:5]:
            print(f"    ! {l.strip()}")
        return
    print("    FAILED — pandoc error follows:")
    for l in (r.stderr or r.stdout).splitlines():
        print(f"      {l}")
    failed.append(src.stem)


def usage():
    print(__doc__.split("WHAT IT NEEDS")[0])
    return 1


def main(argv):
    clean = bool(argv) and argv[0] in ("--clean", "-c")
    if clean:
        argv = argv[1:]
    what = argv[0] if argv else ""
    if what in ("-h", "--help"):
        print(__doc__)
        return 0

    files, failed = [], []
    if what == "":
        files = B.chapter_files() + appendices()
    elif what in ("chapters", "chaps", "ch-all"):
        files = B.chapter_files()
    elif what in ("appendices", "apps", "app-all"):
        files = appendices()
    elif what == "ch":
        for a in argv[1:]:
            f = B.chapter_file(int(a)) if a.isdigit() else None
            if f is None:
                print(f"  ! Chapter {a} not found")
                failed.append(f"Chapter {a}")
            else:
                files.append(f)
    elif what == "app":
        for a in argv[1:]:
            hit = [p for p in appendices() if re.match(rf"Appendix\s+{re.escape(a)}\b", p.name, re.I)]
            if not hit:
                print(f"  ! Appendix {a} not found")
                failed.append(f"Appendix {a}")
            else:
                files.append(hit[0])
    else:
        return usage()

    out = B.PDF_OUT
    if out is None:
        print("No PDF folder set. Put one in book.toml:\n\n    [output]\n"
              "    pdf_dir = \"/path/to/Draft For Review\"")
        return 1
    if not out.is_dir():
        print(f"ERROR: the PDF folder is not there (a drive not mounted?): {out}")
        return 1
    if not converters_ok():
        return 1

    if clean:
        old = sorted(out.glob("*.pdf"))
        print(f"Clean: removing {len(old)} existing PDF(s) from {out}" if old
              else "Clean: no existing PDFs to remove.")
        for p in old:
            print(f"  - {p.name}")
            p.unlink()
        print()

    with tempfile.TemporaryDirectory() as tmp:
        endnotes = Path(tmp) / "endnotes.tex"
        endnotes.write_text("\\theendnotes\n", encoding="utf-8")
        opts = pandoc_opts(endnotes)
        print(f"Publishing {len(files)} file(s) to {out}")
        for f in files:
            publish(f, out, opts, failed)

    print()
    if not failed:
        print("Done. All files published successfully.")
        return 0
    print(f"Done with {len(failed)} failure(s):")
    for f in failed:
        print(f"  - {f}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

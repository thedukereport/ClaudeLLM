#!/usr/bin/env python3
"""
Alexandria — parallel PDF/EPUB text extractor with on-disk cache (TORCH-FREE).

Extraction is the slow phase of indexing (single-threaded pdfplumber over
thousands of books = ~13-14 h). This module parallelizes it across CPU cores
and caches each book's extracted text to disk, keyed by path + mtime + size.

Result:
  * First run: extraction runs in parallel (~hours → a few hours).
  * Later runs: unchanged books are read straight from cache (seconds), so
    re-indexing for a new model / chunk size / a few added books skips the
    14-hour extraction entirely.

This file imports ONLY pdf/epub libraries — never torch/faiss — so its worker
processes stay light and there is no OpenMP conflict.

Run standalone to (re)populate the cache:
    python3 extract_text.py --input /Volumes/PRO-BLADE/Alexandria/PDF \
        --cache-dir /Volumes/PRO-BLADE/Alexandria/text_cache
"""

import os
import re
import sys
import time
import hashlib
import logging
import argparse
import warnings
from pathlib import Path
from multiprocessing import Pool, cpu_count

warnings.filterwarnings("ignore")


# --------------------------------------------------------------------------- #
# Cache helpers (also imported by index_books.py)
# --------------------------------------------------------------------------- #
def _key(path):
    return hashlib.sha1(os.path.abspath(path).encode("utf-8")).hexdigest()


def cache_files(cache_dir, path):
    k = _key(path)
    d = Path(cache_dir)
    return d / (k + ".txt"), d / (k + ".meta")


def _sig(path):
    """A cheap fingerprint of the source file: modification time + size."""
    st = os.stat(path)
    return f"{st.st_mtime_ns} {st.st_size}"


def is_cached(cache_dir, path):
    """True if a fresh cached extraction exists for this file."""
    txt, meta = cache_files(cache_dir, path)
    if not (txt.exists() and meta.exists()):
        return False
    try:
        return meta.read_text().strip() == _sig(path)
    except OSError:
        return False


# Some PDFs carry NUL bytes and other C0/C1 control characters in their text
# layer (bad OCR/generation); pdfplumber extracts them verbatim, which pollutes
# the cache and the embeddings — a chunk that is 20% NUL embeds to noise. Strip
# them at the cache boundary. Tab, newline and carriage return are preserved.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(text):
    return _CONTROL_RE.sub("", text) if text else text


def read_cached_text(cache_dir, path):
    txt, _ = cache_files(cache_dir, path)
    try:
        return sanitize_text(txt.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return ""


def write_cache(cache_dir, path, text):
    txt, meta = cache_files(cache_dir, path)
    txt.parent.mkdir(parents=True, exist_ok=True)
    txt.write_text(sanitize_text(text), encoding="utf-8")
    meta.write_text(_sig(path))


# --------------------------------------------------------------------------- #
# Extraction (torch-free)
# --------------------------------------------------------------------------- #
def _extract_pdf(path):
    """Return (text, [pdfminer warnings]) for a PDF."""
    import pdfplumber

    msgs = []

    class _Col(logging.Handler):
        def __init__(self):
            super().__init__(logging.WARNING)

        def emit(self, record):
            msgs.append(record.getMessage())

    lg = logging.getLogger("pdfminer")
    handler = _Col()
    lg.addHandler(handler)
    lg.setLevel(logging.WARNING)
    text = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text.append(t)
    finally:
        lg.removeHandler(handler)
    return "\n".join(text), sorted(set(msgs))


def _extract_epub(path):
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup

    text = []
    book = epub.read_epub(path)
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            try:
                soup = BeautifulSoup(item.get_content(), "html.parser")
                content = soup.get_text(separator=" ", strip=True)
                if content:
                    text.append(content)
            except Exception:
                continue
    return "\n".join(text), []


import signal


class _ExtractTimeout(Exception):
    pass


def _on_alarm(signum, frame):
    raise _ExtractTimeout()


# A single malformed PDF can send pdfminer into an effectively infinite loop and
# DEADLOCK the whole worker pool — one bad file freezes the entire index build
# (observed 2026-07). Each worker runs one file on its main thread, so a SIGALRM
# watchdog aborts that file and records it as an error, letting the run continue
# instead of hanging forever.
#
# The limit has to scale with the book. A flat 90 seconds silently truncated
# Michael L. Rodkinson's *New Edition of the Babylonian Talmud* — 2,437 pages,
# 200 MB, 1,043,500 words — which pdfplumber cannot read anywhere near that fast.
# What stayed in the cache was 20 KB of Google Books front matter, and that is
# what got embedded: the book indexed, reported six chunks, appeared in the
# library list, and would never have returned a passage. Nothing distinguished it
# from a book that genuinely holds two thousand words (2026-08-08).
#
# Scaling by file size costs one stat and bounds the damage either way: a normal
# book still gets the old 90-second floor, a 200 MB volume gets twenty minutes,
# and a genuine infinite loop still dies at the ceiling.
PER_FILE_TIMEOUT = int(os.environ.get("ALEX_EXTRACT_TIMEOUT", "90"))
TIMEOUT_CEILING = int(os.environ.get("ALEX_EXTRACT_TIMEOUT_MAX", "1800"))
SECONDS_PER_MB = float(os.environ.get("ALEX_EXTRACT_SECONDS_PER_MB", "6"))


def timeout_for(path):
    """Seconds to allow this file: the floor, or six seconds a megabyte, capped."""
    try:
        mb = os.path.getsize(path) / 1_000_000
    except OSError:
        return PER_FILE_TIMEOUT
    return int(max(PER_FILE_TIMEOUT, min(TIMEOUT_CEILING, mb * SECONDS_PER_MB)))


def extract_one(task):
    """Worker: extract one book to cache. Returns (path, status, [issues])."""
    path, cache_dir, use_cache = task
    if use_cache and is_cached(cache_dir, path):
        return (path, "cached", [])
    armed = False
    try:
        low = path.lower()
        if not (low.endswith(".pdf") or low.endswith(".epub")):
            return (path, "skip", [])
        budget = timeout_for(path)
        try:
            signal.signal(signal.SIGALRM, _on_alarm)
            signal.alarm(budget)
            armed = True
        except (ValueError, AttributeError):
            armed = False          # not on the main thread / unsupported platform
        if low.endswith(".pdf"):
            text, warns = _extract_pdf(path)
        else:
            text, warns = _extract_epub(path)
        write_cache(cache_dir, path, text)
        status = "ok" if text.strip() else "empty"
        return (path, status, warns)
    except _ExtractTimeout:
        return (path, "error",
                [f"timeout: extraction exceeded {budget}s "
                 f"({os.path.getsize(path)/1e6:.0f} MB) — malformed, or raise "
                 f"ALEX_EXTRACT_SECONDS_PER_MB"])
    except Exception as e:
        return (path, "error", [f"{type(e).__name__}: {e}"])
    finally:
        if armed:
            signal.alarm(0)


def find_books(input_dir, include_epub):
    root = Path(input_dir)
    exts = {".pdf"} | ({".epub"} if include_epub else set())
    return sorted(str(p) for p in root.rglob("*") if p.suffix.lower() in exts)


def run_extract(input_dir, cache_dir, workers=None, include_epub=False,
                use_cache=True, output_dir=None):
    """Parallel-extract every book into the cache. Returns a summary dict."""
    # Cap workers hard. PDF parsing (pdfplumber) is MEMORY-heavy — image-rich
    # PDFs can use hundreds of MB to GBs each. Too many parallel workers exhaust
    # RAM/swap and can kernel-panic the Mac (watchdog timeout). 4 is a safe
    # default even on many-core machines; override with --workers if you know
    # your library is light and your RAM is ample.
    workers = workers or max(1, min(cpu_count() - 1, 4))
    books = find_books(input_dir, include_epub)
    if not books:
        print(f"No books found under {input_dir}")
        return {"total": 0}

    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    print(f"Extracting {len(books):,} books with {workers} workers "
          f"(cache: {cache_dir}) ...", flush=True)

    counts = {"cached": 0, "ok": 0, "empty": 0, "error": 0, "skip": 0}
    problems = []
    tasks = [(b, cache_dir, use_cache) for b in books]
    t0 = time.perf_counter()
    with Pool(workers) as pool:
        for i, (path, status, issues) in enumerate(
                pool.imap_unordered(extract_one, tasks, chunksize=4), 1):
            counts[status] = counts.get(status, 0) + 1
            if status == "error" or issues:
                problems.append((path, issues or [status]))
            if i % 250 == 0 or i == len(books):
                rate = (time.perf_counter() - t0) / i
                eta = rate * (len(books) - i) / 60
                print(f"  ...{i:,}/{len(books):,}  "
                      f"(cached {counts['cached']:,}, extracted {counts['ok']:,}, "
                      f"errors {counts['error']}) ~{eta:.0f} min left", flush=True)

    if problems and output_dir:
        report = Path(output_dir) / "problem_pdfs.txt"
        with open(report, "w") as f:
            f.write(f"# {len(problems)} books had extraction issues — {time.ctime()}\n\n")
            for path, iss in sorted(problems):
                f.write(f"{path}\n    {'; '.join(iss)}\n")
        print(f"⚠ {len(problems)} book(s) with issues — see {report}", flush=True)

    mins = (time.perf_counter() - t0) / 60
    print(f"✓ Extraction done in {mins:.1f} min — "
          f"{counts['cached']:,} from cache, {counts['ok']:,} freshly extracted, "
          f"{counts['empty']:,} empty, {counts['error']} errors.", flush=True)
    return {"total": len(books), **counts, "minutes": round(mins, 1)}


def main():
    ap = argparse.ArgumentParser(description="Parallel torch-free book text extractor")
    ap.add_argument("--input", required=True, help="Directory of books")
    ap.add_argument("--cache-dir", required=True, help="Where to store cached text")
    ap.add_argument("--workers", type=int, default=None,
                    help="Parallel workers (default: min(cores-1, 4); PDF parsing is "
                         "memory-heavy, so keep this modest to avoid swap exhaustion).")
    ap.add_argument("--include-epub", action="store_true", default=False)
    ap.add_argument("--no-cache", action="store_true", default=False,
                    help="Ignore existing cache and re-extract everything")
    ap.add_argument("--output", default=None, help="Dir for problem_pdfs.txt")
    args = ap.parse_args()
    run_extract(args.input, args.cache_dir, workers=args.workers,
                include_epub=args.include_epub, use_cache=not args.no_cache,
                output_dir=args.output or args.cache_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""OCR an image-only scan into a NEW " - OCR.pdf" beside it. Never overwrite.

Doc 07 exists because ocrmypdf --force-ocr was pointed at files that already had
text and grew one from 4.2 MB to 1.24 GB. This runner cannot repeat that:

  - it writes a new file and never touches the original;
  - it refuses any source that already yields text;
  - it re-encodes nothing. Tesseract reads a rendered image, and the recognised
    words go back on the ORIGINAL page object as invisible text (render mode 3).
    The page still rasterises to identical pixels, so the added bytes are words,
    not a second copy of the scan.

Resumable to the page. Each page's overlay lands in a work directory, so a run
cut off mid-book resumes at the next page instead of restarting.

  python3 ocr_to_copy.py --list five.txt --budget 35
"""
import argparse, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import alexandria_optimize as AO

# The work list carries Mac paths. On the Mac they resolve as written; inside a
# Cowork sandbox the same volume appears under a session mount, so translate only
# when that mount is the one we are standing on. The script then runs unchanged
# in both places, and the work directory is shared, so a run started in one
# finishes in the other.
MAC = os.environ.get("ALEX_PDF_MAC_ROOT", "/Volumes/PRO-BLADE/Alexandria/PDF")
MOUNT = os.environ.get("ALEX_PDF_ROOT", str(HERE.parent))
WORK = HERE / ".ocrcopy"
os.environ.setdefault("TESSDATA_PREFIX", str(HERE / ".tessdata"))
DPI = 300
WORKERS = int(os.environ.get("ALEX_WORKERS", "4"))          # doc 07 rule 5
WORD = re.compile(r"[^\W\d_]{2,}", re.UNICODE)


def local(p):
    return p.replace(MAC, MOUNT) if p.startswith(MAC) else p


def pages_of(p):
    o = subprocess.run(["pdfinfo", p], capture_output=True, timeout=60).stdout.decode("utf-8", "ignore")
    m = re.search(r"Pages:\s+(\d+)", o)
    return int(m.group(1)) if m else 0


def already_has_text(p, n):
    """Refuse anything that is not genuinely image-only. Sample page PAIRS:
    these scans print one side, so single pages at a fixed stride hit the blanks."""
    span = max(2, n // 9)
    for i in range(8):
        pg = min(max(1, span * (i + 1)), max(1, n - 1))
        t = subprocess.run(["pdftotext", "-layout", "-f", str(pg), "-l", str(pg + 1), p, "-"],
                           capture_output=True, timeout=120).stdout.decode("utf-8", "ignore")
        if len(WORD.findall(t)) >= 25:
            return True
    return False


def _one_page(task):
    src, pg, work, lang = task
    png = os.path.join(work, f"p{pg:05d}.png")
    hoc = os.path.join(work, f"p{pg:05d}.hocr")
    if os.path.exists(hoc):
        return pg
    # Each worker renders under its own prefix. Sharing one prefix let four
    # workers pick up each other's output and re-render the same pages.
    stem = os.path.join(work, f"t{os.getpid()}_{pg}")
    subprocess.run(["pdftoppm", "-r", str(DPI), "-gray", "-png", "-f", str(pg), "-l", str(pg),
                    src, stem], capture_output=True, timeout=300)
    made = [f for f in os.listdir(work)
            if f.startswith(os.path.basename(stem) + "-") and f.endswith(".png")]
    if not made:
        return None
    os.rename(os.path.join(work, made[0]), png)
    # One OpenMP thread per worker. Tesseract 4 fans out internally, so four
    # workers each spawning four threads oversubscribes a four-core box and the
    # whole run crawls — the same lesson ocr_chunked.py already carries.
    subprocess.run(["tesseract", png, hoc[:-5], "-l", lang, "--psm", "3", "hocr"],
                   capture_output=True, timeout=600,
                   env={**os.environ, "OMP_THREAD_LIMIT": "1"})
    return pg if os.path.exists(hoc) else None


def run(mac_path, lang, deadline):
    src = local(mac_path)
    dst = src[:-4] + " - OCR.pdf"
    if os.path.exists(dst):
        return "done", 0
    n = pages_of(src)
    if n < 1:
        return "no pages", 0
    work = WORK / re.sub(r"[^A-Za-z0-9]+", "_", os.path.basename(src))[:60]
    work.mkdir(parents=True, exist_ok=True)
    if not (work / "checked").exists():
        if already_has_text(src, n):
            return "REFUSED: already has text", 0
        (work / "checked").write_text("image-only confirmed")
    # Match the page files by shape, not by suffix. A sibling tool left
    # cut_26.hocr in the work directory and int("ut_26") ended the run.
    PAGE = re.compile(r"^p(\d{5})\.hocr$")
    have = {int(m.group(1)) for m in (PAGE.match(f) for f in os.listdir(work)) if m}
    todo = [p for p in range(1, n + 1) if p not in have]
    while todo and time.time() < deadline:
        batch = todo[:WORKERS * 4]
        # Threads, not processes. Every worker does nothing but wait on
        # pdftoppm and tesseract, so the interpreter lock is free the whole
        # time and threads parallelise exactly as well. Processes bought
        # nothing here and cost a whole failure class: macOS spawns rather
        # than forks, a spawned child re-imports this module, and the run
        # collapsed into recursive RuntimeErrors on Mr. Duke's machine while
        # running clean on Linux, which forks.
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            got = list(pool.map(_one_page, [(src, p, str(work), lang) for p in batch]))
        have |= {g for g in got if g}
        todo = [p for p in todo if p not in have]
    if todo:
        return f"partial {n - len(todo)}/{n} pages", n - len(todo)

    from pypdf import PdfReader, PdfWriter
    from PIL import Image
    reader, writer = PdfReader(src), PdfWriter()
    words = 0
    for i in range(1, n + 1):
        page = reader.pages[i - 1]
        h, png = work / f"p{i:05d}.hocr", work / f"p{i:05d}.png"
        if h.exists() and png.exists():
            with Image.open(png) as im:
                iw, ih = im.size
            layer = work / f"p{i:05d}_layer.pdf"
            words += AO.build_text_layer(str(h), iw, ih, float(page.mediabox.width),
                                         float(page.mediabox.height), str(layer))
            page.merge_page(PdfReader(str(layer)).pages[0])
        writer.add_page(page)
    tmp = dst + ".part"
    with open(tmp, "wb") as fh:
        writer.write(fh)
    os.replace(tmp, dst)
    shutil.rmtree(work, ignore_errors=True)
    return "ok", words


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", required=True)
    ap.add_argument("--budget", type=float, default=35.0)
    a = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + a.budget
    log = HERE / "ocr_to_copy.log"
    for line in open(a.list):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        mac, lang = (line.split("\t") + ["eng"])[:2]
        t0 = time.time()
        # One book must not end the pass. Before this, an unhandled error inside
        # run() -- Peter Duke's 2-billion-pixel infographic raised
        # PIL.Image.DecompressionBombError -- killed the whole run, and the
        # wrapper restarted it, so the same book failed all night.
        try:
            status, words = run(mac, lang, deadline)
        except Exception as exc:
            status, words = f"FAILED {type(exc).__name__}", 0
        el = time.time() - t0
        src = local(mac)
        dst = src[:-4] + " - OCR.pdf"
        if status == "ok":
            a_, b_ = os.path.getsize(src), os.path.getsize(dst)
            msg = (f"OK      {os.path.basename(mac)[:44]:<46} {a_/1e6:7.1f} -> {b_/1e6:7.1f} MB "
                   f"({b_/a_:4.2f}x)  {words:,} words  {el:.0f}s")
        else:
            msg = f"{status:<12} {os.path.basename(mac)[:44]:<46} {el:.0f}s"
        print(" ", msg, flush=True)
        with open(log, "a") as fh:
            fh.write(msg + "\n")
        if time.time() > deadline:
            print("  BUDGET — resume by re-running", flush=True)
            return


if __name__ == "__main__":
    main()

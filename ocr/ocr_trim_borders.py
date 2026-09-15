#!/usr/bin/env python3
"""Fill a book's .ocrcopy work directory when a white scan frame blinds tesseract.

A. E Waite, 'Lives of Alchemystical Philosophers' (1888) came out of the main run
at 25 words a page across 315 pages; 279 pages held no text at all. The pages
render as a gray scan inside a pure-white frame, and tesseract reads the whole
image as one picture and returns nothing. Crop the frame and the same page gives
310 words.

So: render the page whole, OCR only the cropped part, then push every hOCR box
back by the crop offset. The page image on disk stays full size, so
ocr_to_copy.py merges the words onto the original page object exactly as before
and nothing downstream changes.

  python3 ocr_trim_borders.py "<source.pdf>" [--workers 4]
"""
import argparse, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
WORK = HERE / ".ocrcopy"
DPI = 300
BBOX = re.compile(r"bbox (\d+) (\d+) (\d+) (\d+)")


def paper_box(im):
    a = np.asarray(im, dtype=np.uint8)
    ink = a < 250
    rows = np.where(ink.mean(axis=1) > 0.5)[0]
    cols = np.where(ink.mean(axis=0) > 0.5)[0]
    h, w = a.shape
    if len(rows) < h * 0.3 or len(cols) < w * 0.3:
        return (0, 0, w, h)
    return (int(cols[0]), int(rows[0]), int(cols[-1]) + 1, int(rows[-1]) + 1)


def shift(hocr_text, dx, dy, w, h):
    first = [True]

    def f(m):
        x0, y0, x1, y1 = (int(v) for v in m.groups())
        if first[0]:                      # the page element keeps the full frame
            first[0] = False
            return f"bbox 0 0 {w} {h}"
        return f"bbox {x0+dx} {y0+dy} {x1+dx} {y1+dy}"

    return BBOX.sub(f, hocr_text)


def one(task):
    src, pg, work, lang = task
    png = work / f"p{pg:05d}.png"
    hoc = work / f"p{pg:05d}.hocr"
    if hoc.exists() and png.exists():
        return 0
    stem = work / f"trim_{pg}"
    subprocess.run(["pdftoppm", "-r", str(DPI), "-gray", "-png", "-f", str(pg), "-l", str(pg),
                    src, str(stem)], capture_output=True, timeout=300)
    made = [f for f in os.listdir(work)
            if f.startswith(stem.name + "-") and f.endswith(".png")]
    if not made:
        return 0
    full = work / made[0]
    im = Image.open(full).convert("L")
    w, h = im.size
    box = paper_box(im)
    cut = work / f"cut_{pg}.png"
    im.crop(box).save(cut, dpi=(DPI, DPI))
    out = work / f"cut_{pg}"
    subprocess.run(["tesseract", str(cut), str(out), "-l", lang, "--psm", "3", "hocr"],
                   capture_output=True, timeout=600,
                   env={**os.environ, "OMP_THREAD_LIMIT": "1"})
    made_hocr = out.with_suffix(".hocr")
    if not made_hocr.exists():
        return 0
    hoc.write_text(shift(made_hocr.read_text(errors="ignore"), box[0], box[1], w, h))
    os.replace(full, png)
    for junk in (cut, made_hocr):
        try:
            junk.unlink()
        except OSError:
            pass
    return len(re.findall(r"[^\W\d_]{2,}", re.sub(r"<[^>]+>", " ", hoc.read_text(errors="ignore")), re.UNICODE))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--lang", default="eng")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    src = a.src
    o = subprocess.run(["pdfinfo", src], capture_output=True).stdout.decode("utf8", "ignore")
    n = int(re.search(r"Pages:\s+(\d+)", o).group(1))
    work = WORK / re.sub(r"[^A-Za-z0-9]+", "_", os.path.basename(src))[:60]
    work.mkdir(parents=True, exist_ok=True)
    (work / "checked").write_text("image-only confirmed")
    tasks = [(src, p, work, a.lang) for p in range(1, n + 1)]
    total = 0
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for i, got in enumerate(pool.map(one, tasks), 1):
            total += got
            if i % 25 == 0:
                print(f"  {i}/{n} pages, {total:,} words", flush=True)
    done = len(list(work.glob("p?????.hocr")))
    print(f"DONE {done}/{n} pages carry hOCR, {total:,} words", flush=True)


if __name__ == "__main__":
    main()

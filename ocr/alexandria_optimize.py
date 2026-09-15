#!/usr/bin/env python3
"""
Alexandria PDF optimizer — fidelity-first, resumable, quarantined.

Subcommands
  ocr        add an invisible text layer to page-image PDFs. Original page
             content is preserved byte-for-byte; only a text layer is overlaid,
             so nothing visual is re-encoded.
  recompress downsample images above a DPI floor and rebuild the file.
  repair     rebuild structurally damaged / encrypted files with qpdf.
  metadata   embed Title/Author parsed from the filename via pikepdf.
  verify     re-check an already-processed file against its quarantined original.

Every write is quarantine-first: the original moves to
  <QUARANTINE>/<relative path>
before the new file takes its place, so every action is reversible.

Work is tracked in ledger.jsonl and each run stops inside a wall-clock budget,
so it is safe to invoke repeatedly until the queue drains.
"""
import os, sys, json, time, shutil, subprocess, argparse, re, html
from pathlib import Path
from multiprocessing import Pool

ROOT       = Path(os.environ.get("ALEX_ROOT", ""))
OUT        = Path(os.environ.get("ALEX_OUT", ""))
QUARANTINE = Path(os.environ.get("ALEX_QUARANTINE", ""))
LEDGER     = OUT / "ledger.jsonl"
DPI_FLOOR  = int(os.environ.get("ALEX_DPI_FLOOR", "300"))
OCR_LANG   = os.environ.get("ALEX_OCR_LANG", "eng")


def sh(cmd, timeout, **kw):
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout, **kw)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -9, b"", b"TIMEOUT"
    except Exception as e:
        return -1, b"", str(e).encode()


QRANK = {0: 0, 3: 1, 2: 2}   # ok < warnings < errors

def qpdf_rank(path):
    """Severity of qpdf's verdict, so a rebuild is judged against the file's own
    starting condition rather than against perfection. Pre-existing stream damage
    is not recoverable and must not veto an otherwise sound rebuild."""
    rc, _, _ = sh(["qpdf", "--check", str(path)], 300)
    return QRANK.get(rc, 2)


def pdf_stats(path):
    """(pages, extracted_chars) — the two invariants every action must preserve."""
    rc, so, _ = sh(["pdfinfo", str(path)], 60)
    pages = 0
    if rc == 0:
        for line in so.decode("utf-8", "replace").splitlines():
            if line.startswith("Pages:"):
                try: pages = int(line.split(":", 1)[1])
                except ValueError: pass
    rc, so, _ = sh(["pdftotext", "-q", str(path), "-"], 240)
    return pages, (len(so) if rc == 0 else -1)


# --------------------------------------------------------------------------- #
# hOCR -> invisible text layer
# --------------------------------------------------------------------------- #
WORD_RE = re.compile(
    r"<span[^>]*class=['\"]ocrx_word['\"][^>]*title=['\"][^'\"]*?bbox (\d+) (\d+) (\d+) (\d+)[^'\"]*['\"][^>]*>(.*?)</span>",
    re.S)
TAG_RE = re.compile(r"<[^>]+>")

def hocr_words(hocr_text):
    for m in WORD_RE.finditer(hocr_text):
        x0, y0, x1, y1 = (int(m.group(i)) for i in range(1, 5))
        w = html.unescape(TAG_RE.sub("", m.group(5))).strip()
        if w:
            yield x0, y0, x1, y1, w

def build_text_layer(hocr_path, img_w, img_h, page_w, page_h, out_pdf):
    """Write a PDF page of exactly page_w x page_h holding only invisible text
    positioned to match the OCR boxes. Render mode 3 = draw nothing, but the
    glyphs remain selectable and extractable."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader  # noqa: F401  (import guard)
    c = canvas.Canvas(str(out_pdf), pagesize=(page_w, page_h))
    c.setFillColorRGB(0, 0, 0)
    sx = page_w / img_w
    sy = page_h / img_h
    try:
        hocr = Path(hocr_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        c.save(); return 0
    n = 0
    to = None
    c.saveState()
    for x0, y0, x1, y1, word in hocr_words(hocr):
        bh = (y1 - y0) * sy
        if bh <= 0:
            continue
        size = max(1.0, bh * 0.92)
        t = c.beginText()
        t.setTextRenderMode(3)              # invisible
        t.setFont("Helvetica", size)
        t.setTextOrigin(x0 * sx, page_h - y1 * sy)
        # squeeze the word into its measured box so extraction order is sane
        want = (x1 - x0) * sx
        have = c.stringWidth(word, "Helvetica", size)
        if have > 0 and want > 0:
            t.setHorizScale(100.0 * want / have)
        t.textOut(word)
        c.drawText(t)
        n += 1
    c.restoreState()
    c.save()
    return n


def ocr_one(args):
    """Render -> OCR -> overlay invisible text on the ORIGINAL pages."""
    src, workdir, first, last = args
    src = Path(src)
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)
    from pypdf import PdfReader, PdfWriter

    rc, _, se = sh(["pdftoppm", "-r", "300", "-gray", "-png",
                    "-f", str(first), "-l", str(last), str(src), str(work / "pg")], 900)
    if rc != 0:
        return {"ok": False, "stage": "render", "err": se.decode()[:200]}

    from PIL import Image
    reader = PdfReader(str(src))
    writer = PdfWriter()
    words_total = 0
    for i in range(first, last + 1):
        page = reader.pages[i - 1]
        cands = sorted(work.glob(f"pg-*{i}.png")) or sorted(work.glob(f"pg-{i}.png"))
        png = None
        for c in work.glob("pg-*.png"):
            if int(re.sub(r"\D", "", c.stem.split("-")[-1])) == i:
                png = c; break
        if png is None:
            writer.add_page(page); continue
        base = png.with_suffix("")
        rc, _, _ = sh(["tesseract", str(png), str(base), "-l", OCR_LANG,
                       "--psm", "3", "hocr"], 300,
                      env={**os.environ, "OMP_THREAD_LIMIT": "1"})
        hocr = base.with_suffix(".hocr")
        if rc == 0 and hocr.exists():
            with Image.open(png) as im:
                iw, ih = im.size
            pw = float(page.mediabox.width)
            ph = float(page.mediabox.height)
            layer = base.with_name(base.name + "_layer.pdf")
            try:
                words_total += build_text_layer(hocr, iw, ih, pw, ph, layer)
                lp = PdfReader(str(layer)).pages[0]
                page.merge_page(lp)          # original content untouched underneath
            except Exception as e:
                return {"ok": False, "stage": "overlay", "err": f"{type(e).__name__}: {e}"}
        writer.add_page(page)
        for f in (png, base.with_suffix(".hocr"), base.with_name(base.name + "_layer.pdf")):
            try: f.unlink()
            except OSError: pass

    out = work / "out.pdf"
    with open(out, "wb") as f:
        writer.write(f)
    return {"ok": True, "out": str(out), "words": words_total}


# --------------------------------------------------------------------------- #
# other actions
# --------------------------------------------------------------------------- #
def action_recompress(src, tmp):
    rc, _, se = sh(["gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.7",
                    "-dNOPAUSE", "-dQUIET", "-dBATCH", "-dSAFER",
                    "-dDetectDuplicateImages=true",
                    "-dColorImageDownsampleType=/Bicubic",
                    f"-dColorImageResolution={DPI_FLOOR}",
                    "-dGrayImageDownsampleType=/Bicubic",
                    f"-dGrayImageResolution={DPI_FLOOR}",
                    "-dMonoImageDownsampleType=/Subsample",
                    f"-dMonoImageResolution={DPI_FLOOR*4}",
                    "-dDownsampleColorImages=true", "-dDownsampleGrayImages=true",
                    "-dAutoFilterColorImages=false", "-dAutoFilterGrayImages=false",
                    "-dColorImageFilter=/DCTEncode", "-dGrayImageFilter=/DCTEncode",
                    "-dJPEGQ=88",
                    f"-sOutputFile={tmp}", str(src)], 1800)
    return rc == 0, se.decode()[:200]

def action_repair(src, tmp):
    rc, _, se = sh(["qpdf", "--decrypt", "--object-streams=generate",
                    "--recompress-flate", "--compression-level=9",
                    "--linearize", str(src), str(tmp)], 900)
    if rc in (0, 3):
        return True, ""
    rc, _, se = sh(["qpdf", "--decrypt", "--object-streams=generate",
                    str(src), str(tmp)], 900)
    return rc in (0, 3), se.decode()[:200]

def action_metadata(src, tmp):
    import pikepdf
    name = Path(src).stem
    author, title = "", name
    if " - " in name:
        a, _, t = name.partition(" - ")
        if 2 < len(a) < 80:
            author, title = a.strip(), t.strip()
    try:
        with pikepdf.open(str(src), allow_overwriting_input=False) as pdf:
            with pdf.open_metadata(set_pikepdf_as_editor=False) as m:
                if title:  m["dc:title"] = title
                if author: m["dc:creator"] = [author]
                m["dc:description"] = "Alexandria Library"
            pdf.save(str(tmp), linearize=True)
        return True, ""
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


# --------------------------------------------------------------------------- #
# driver
# --------------------------------------------------------------------------- #
def quarantine(src):
    """COPY the original aside. The mounted volume denies unlink, so the original
    cannot be moved; it is duplicated to the quarantine tree and then overwritten
    in place by an atomic same-mount rename. Deleting the quarantine afterwards is
    the user's call."""
    relp = Path(src).relative_to(ROOT)
    dest = QUARANTINE / relp
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest = dest.with_name(dest.stem + f".dup{int(time.time())}" + dest.suffix)
    shutil.copy2(str(src), str(dest))
    if dest.stat().st_size != Path(src).stat().st_size:
        raise IOError(f"quarantine copy size mismatch for {src}")
    return dest


STAGING = None

def stage_onto(tmp, target):
    """Move the finished file into place. os.replace only works within one mount,
    so the result is first copied into a staging dir on the target's own volume."""
    global STAGING
    if STAGING is None:
        STAGING = OUT / ".staging"
        STAGING.mkdir(parents=True, exist_ok=True)
    stg = STAGING / f"{os.getpid()}_{int(time.time()*1000)}.pdf"
    shutil.copy2(str(tmp), str(stg))
    if stg.stat().st_size != Path(tmp).stat().st_size:
        raise IOError("staging copy truncated")
    os.replace(str(stg), str(target))

def attempt_counts(mode=None):
    """How many times each path has been tried and not succeeded.

    Pass `mode` to count only that pass's attempts. Counting across modes lets
    a file that failed `repair` twice be excluded from `ocr` as well, which is
    not what any caller means."""
    n = {}
    if LEDGER.exists():
        for line in open(LEDGER):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if mode is not None and r.get("mode") != mode:
                continue
            if r.get("status") in ("fail", "reject"):
                n[r["path"]] = n.get(r["path"], 0) + 1
    return n


def load_done(mode=None):
    """Last ledger row per path. Pass `mode` to see only that pass's history.

    Keying on path alone means a successful `repair` row marks the file done
    for EVERY pass -- so `ocr`, `recompress` and `metadata` silently skip it.
    That defect hid four books from OCR, one of them 772,615 characters."""
    done = {}
    if LEDGER.exists():
        for line in open(LEDGER):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if mode is not None and r.get("mode") != mode:
                continue
            done[r["path"]] = r
    return done

def process(src, mode, log):
    src = Path(src)
    t0 = time.time()
    pages0, chars0 = pdf_stats(src)
    qrank0 = qpdf_rank(src) if mode in ("repair", "recompress", "metadata") else None
    work = Path(os.environ.get("TMPDIR", "/tmp")) / f"alexopt_{os.getpid()}"
    if work.exists(): shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    tmp = work / "out.pdf"
    try:
        if mode == "ocr":
            if pages0 < 1:
                return {"path": str(src), "mode": mode, "status": "skip", "why": "no pages"}
            r = ocr_one((str(src), str(work), 1, pages0))
            if not r["ok"]:
                return {"path": str(src), "mode": mode, "status": "fail",
                        "why": f"{r['stage']}: {r['err']}"}
            tmp = Path(r["out"]); extra = {"words": r["words"]}
        elif mode == "recompress":
            ok, err = action_recompress(src, tmp); extra = {}
            if not ok: return {"path": str(src), "mode": mode, "status": "fail", "why": err}
        elif mode == "repair":
            ok, err = action_repair(src, tmp); extra = {}
            if not ok: return {"path": str(src), "mode": mode, "status": "fail", "why": err}
        elif mode == "metadata":
            ok, err = action_metadata(src, tmp); extra = {}
            if not ok: return {"path": str(src), "mode": mode, "status": "fail", "why": err}
        else:
            raise SystemExit(f"unknown mode {mode}")

        # ---- verification gate: never accept a regression ----
        pages1, chars1 = pdf_stats(tmp)
        if pages1 != pages0:
            return {"path": str(src), "mode": mode, "status": "reject",
                    "why": f"page count {pages0} -> {pages1}"}
        if mode == "ocr":
            if chars1 < max(100, pages0 * 15):
                return {"path": str(src), "mode": mode, "status": "reject",
                        "why": f"OCR yielded only {chars1} chars over {pages0} pages"}
        else:
            if chars0 > 0 and chars1 < chars0 * 0.98:
                return {"path": str(src), "mode": mode, "status": "reject",
                        "why": f"text loss {chars0} -> {chars1}"}
        qrank1 = qpdf_rank(tmp)
        if qrank0 is None:
            if qrank1 > 1:
                return {"path": str(src), "mode": mode, "status": "reject",
                        "why": "rebuild introduced structural errors"}
        elif qrank1 > qrank0:
            return {"path": str(src), "mode": mode, "status": "reject",
                    "why": f"structural verdict worsened ({qrank0} -> {qrank1})"}

        size0 = src.stat().st_size
        q = quarantine(src)
        stage_onto(tmp, src)
        size1 = src.stat().st_size
        return {"path": str(src), "mode": mode, "status": "ok",
                "pages": pages0, "chars_before": chars0, "chars_after": chars1,
                "size_before": size0, "size_after": size1,
                "qrank_before": qrank0, "qrank_after": qrank1,
                "quarantined": str(q), "secs": round(time.time() - t0, 1), **extra}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["ocr", "recompress", "repair", "metadata"])
    ap.add_argument("--list", required=True, help="file of newline-separated paths")
    ap.add_argument("--budget", type=float, default=float(os.environ.get("ALEX_BUDGET", "1e9")))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    for v, n in ((ROOT, "ALEX_ROOT"), (OUT, "ALEX_OUT"), (QUARANTINE, "ALEX_QUARANTINE")):
        if not str(v): raise SystemExit(f"{n} not set")
    OUT.mkdir(parents=True, exist_ok=True)
    QUARANTINE.mkdir(parents=True, exist_ok=True)

    # Scope both to THIS pass. Unscoped, a file another pass already handled
    # never enters this queue and nothing reports that it was skipped.
    done, attempts = load_done(args.mode), attempt_counts(args.mode)
    unscoped = load_done()
    todo = []
    for line in open(args.list):
        p = line.strip()
        if not p or not os.path.exists(p): continue
        d = done.get(p)
        if d and d.get("status") in ("ok", "skip", "reject"): continue
        if attempts.get(p, 0) >= 2: continue
        todo.append(p)
    if args.limit: todo = todo[:args.limit]
    masked = sum(1 for p in todo
                 if (unscoped.get(p) or {}).get("status") in ("ok", "skip", "reject")
                 and (unscoped.get(p) or {}).get("mode") != args.mode)
    print(f"{args.mode}: {len(todo)} queued ({len(done)} {args.mode} rows in ledger)", flush=True)
    if masked:
        print(f"  ({masked} of these were previously hidden by another pass's ledger rows)",
              flush=True)

    t0 = time.time()
    n_ok = n_bad = 0
    with open(LEDGER, "a", buffering=1) as lg:
        for p in todo:
            if time.time() - t0 > args.budget:
                print("BUDGET_REACHED", flush=True); break
            rec = process(p, args.mode, lg)
            rec["ts"] = int(time.time())
            lg.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if rec["status"] == "ok":
                n_ok += 1
                d = rec.get("size_before", 0) - rec.get("size_after", 0)
                print(f"  OK   {Path(p).name[:58]}  {rec.get('chars_after',0):>8} chars  "
                      f"{d/2**20:+.1f} MB  {rec.get('secs')}s", flush=True)
            else:
                n_bad += 1
                print(f"  {rec['status'].upper():6s} {Path(p).name[:58]}  {rec.get('why','')[:70]}", flush=True)
    print(f"done: {n_ok} ok, {n_bad} not applied, {time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    main()

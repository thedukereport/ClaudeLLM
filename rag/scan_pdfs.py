#!/usr/bin/env python3
"""
Alexandria — fast PDF integrity scanner (TORCH-FREE), incremental.

Decompresses each stream via pdfminer — the exact code path that emits
"Data-loss while decompressing corrupted data" during real indexing —
WITHOUT chunking, embedding, or building any index.

Incremental by default: results live in scan_manifest.json (next to
problem_pdfs.txt). A file is skipped when its size and mtime match the
manifest, so after the first full run only new or changed files get scanned.
problem_pdfs.txt is regenerated from the manifest every run, so it always
lists every currently-known problem file, scanned this run or not.

Modes:
    (default)   skip files whose size+mtime match the manifest
    --verify    also re-hash (md5) size/mtime matches; rescan if content changed
                (catches files replaced with backup copies that keep old dates)
    --full      rescan everything, rebuild the manifest from scratch

~0.8 s/PDF scanned, parallel across CPU cores (no torch/faiss, so no OpenMP
conflict). Skipped files cost ~nothing; --verify costs one file read (hash),
no decompression.

Usage:
    python3 scan_pdfs.py --input /Volumes/PRO-BLADE/Alexandria/PDF
    python3 scan_pdfs.py --input /Volumes/PRO-BLADE/Alexandria/PDF --verify
    python3 scan_pdfs.py --input /Volumes/PRO-BLADE/Alexandria/PDF --full --workers 4
"""

import os
import sys
import json
import time
import hashlib
import logging
import argparse
import warnings
from pathlib import Path
from datetime import datetime
from multiprocessing import Pool, cpu_count

warnings.filterwarnings("ignore")

MANIFEST_NAME = "scan_manifest.json"
MANIFEST_VERSION = 1


def md5_file(path, bufsize=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(bufsize), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_one(path):
    """Decompress every stream in one PDF. Returns a manifest record:
    (path, {"size", "mtime", "md5", "status", "msgs", "scanned"})."""
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdftypes import PDFStream

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
    try:
        st = os.stat(path)
        digest = md5_file(path)
        with open(path, "rb") as f:
            doc = PDFDocument(PDFParser(f))
            for xref in doc.xrefs:
                for oid in list(xref.get_objids()):
                    try:
                        obj = doc.getobj(oid)
                        if isinstance(obj, PDFStream):
                            obj.get_data()  # triggers FlateDecode → warning if corrupt
                    except Exception:
                        pass  # individual object errors are common & non-fatal
    except Exception as e:
        msgs.append(f"parse error: {type(e).__name__}: {e}")
        try:
            st = os.stat(path)
            digest = md5_file(path)
        except Exception:
            st, digest = None, None
    finally:
        lg.removeHandler(handler)

    uniq = sorted(set(msgs))
    return (path, {
        "size": st.st_size if st else None,
        "mtime": st.st_mtime if st else None,
        "md5": digest,
        "status": "problem" if uniq else "ok",
        "msgs": uniq,
        "scanned": datetime.now().isoformat(timespec="seconds"),
    })


def find_pdfs(input_dir):
    root = Path(input_dir)
    return sorted(p for p in root.rglob("*") if p.suffix.lower() == ".pdf")


def load_manifest(out_dir):
    p = Path(out_dir) / MANIFEST_NAME
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())
        if data.get("version") == MANIFEST_VERSION:
            return data.get("files", {})
    except Exception as e:
        print(f"  (manifest unreadable, starting fresh: {e})")
    return {}


def save_manifest(out_dir, files):
    p = Path(out_dir) / MANIFEST_NAME
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(
        {"version": MANIFEST_VERSION,
         "updated": datetime.now().isoformat(timespec="seconds"),
         "files": files},
        indent=1))
    tmp.replace(p)  # atomic — a crash mid-write never corrupts the manifest


def write_report(out_dir, files, scanned_now, skipped, total):
    problems = {p: rec for p, rec in files.items() if rec["status"] == "problem"}
    report = Path(out_dir) / "problem_pdfs.txt"
    with open(report, "w") as f:
        f.write(f"# {len(problems)} of {total} PDFs had issues — {time.ctime()}\n")
        f.write(f"# This run: {scanned_now} scanned, {skipped} skipped (unchanged per manifest).\n")
        f.write("# These triggered pdfminer warnings or failed to parse.\n")
        f.write("# Text may still extract partially; consider re-sourcing them.\n\n")
        for path, rec in sorted(problems.items()):
            f.write(f"{path}\n    {'; '.join(rec['msgs'])}\n")
    return report, len(problems)


def main():
    ap = argparse.ArgumentParser(description="Fast incremental PDF integrity scanner (torch-free)")
    ap.add_argument("--input", required=True, help="Directory of PDFs to scan")
    ap.add_argument("--output", default=None,
                    help="Where to write problem_pdfs.txt + scan_manifest.json (default: --input dir)")
    ap.add_argument("--workers", type=int, default=min(4, max(1, cpu_count() - 1)),
                    help="Parallel worker processes (default: min(4, cores-1))")
    ap.add_argument("--verify", action="store_true",
                    help="Re-hash size/mtime matches; rescan any whose content changed")
    ap.add_argument("--full", action="store_true",
                    help="Ignore the manifest and rescan everything")
    args = ap.parse_args()

    out_dir = Path(args.output or args.input)
    out_dir.mkdir(parents=True, exist_ok=True)

    pdfs = [str(p) for p in find_pdfs(args.input)]
    if not pdfs:
        print(f"No PDFs found under {args.input}")
        return 0

    manifest = {} if args.full else load_manifest(out_dir)

    # Drop entries for files that no longer exist
    current = set(pdfs)
    stale = [p for p in manifest if p not in current]
    for p in stale:
        del manifest[p]

    # Decide what to scan
    to_scan, skipped = [], 0
    for p in pdfs:
        rec = manifest.get(p)
        if rec is None or rec.get("size") is None:
            to_scan.append(p)
            continue
        st = os.stat(p)
        if st.st_size != rec["size"] or abs(st.st_mtime - rec["mtime"]) > 1:
            to_scan.append(p)
        elif args.verify:
            if md5_file(p) != rec.get("md5"):
                to_scan.append(p)
            else:
                skipped += 1
        else:
            skipped += 1

    mode = "full" if args.full else ("verify" if args.verify else "incremental")
    print(f"Scanning {len(to_scan):,} of {len(pdfs):,} PDFs "
          f"({skipped:,} unchanged, {len(stale)} removed) — mode: {mode}, {args.workers} workers ...")

    t0 = time.perf_counter()
    new_problems = 0
    if to_scan:
        with Pool(args.workers) as pool:
            for i, (path, rec) in enumerate(
                    pool.imap_unordered(scan_one, to_scan, chunksize=4), 1):
                manifest[path] = rec
                if rec["status"] == "problem":
                    new_problems += 1
                    print(f"  ⚠ {Path(path).name}: {'; '.join(rec['msgs'])}")
                if i % 250 == 0:
                    rate = (time.perf_counter() - t0) / i
                    eta = rate * (len(to_scan) - i) / 60
                    print(f"  ...{i:,}/{len(to_scan):,}  ({rate:.2f}s/pdf, ~{eta:.0f} min left)")
                if i % 500 == 0:
                    save_manifest(out_dir, manifest)  # checkpoint: a crash costs ≤500 files

    save_manifest(out_dir, manifest)
    report, total_problems = write_report(out_dir, manifest, len(to_scan), skipped, len(pdfs))

    mins = (time.perf_counter() - t0) / 60
    print(f"\nDone in {mins:.1f} min. Scanned {len(to_scan):,}, skipped {skipped:,} unchanged.")
    print(f"{total_problems} problem PDFs on record ({new_problems} from this run).")
    print(f"Report: {report}")
    print(f"Manifest: {out_dir / MANIFEST_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

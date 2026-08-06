#!/usr/bin/env python3
"""
Alexandria RAG — standalone FAISS index builder (TORCH-FREE).

This script deliberately imports ONLY numpy + faiss. It must never import
torch / sentence_transformers: torch, sklearn and faiss each bundle their own
libomp.dylib, and loading two OpenMP runtimes into one process segfaults FAISS
the instant it enters a parallel section (k-means training, HNSW graph build)
on macOS Apple Silicon. Keeping torch out of THIS process is the whole fix.

It builds any of the FAISS index families from existing embeddings:
    flat     IndexFlatL2            exact, 100% accurate, slowest
    ivfflat  IndexIVFFlat           cluster buckets, fast, ~exact (tune nprobe)
    ivfpq    IndexIVFPQ             clusters + compression, smallest/fastest
    hnsw     IndexHNSWFlat          graph index, very fast queries, high RAM

Vectors come from one of:
    --from-index PATH   reconstruct exact vectors from an existing FAISS index
                        (defaults to <index-dir>/alexandria.index)
    --from-npy PATH     load a saved float32 embeddings matrix (.npy)

Outputs into --index-dir:
    alexandria.index            the new index (old one backed up once)
    alexandria.index.<t>.backup backup of whatever was there before
    index_params.json           records index type + params (UI reads this)

Usage:
    python3 build_index_cli.py --index-dir /Volumes/PRO-BLADE/Alexandria \
        --index-type ivfflat --nlist 1000 --nprobe 50
"""

import os
# --- OpenMP safety guards: set BEFORE importing faiss -----------------------
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "4")

import sys
import json
import time
import shutil
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
import faiss

VALID_TYPES = ("flat", "ivfflat", "ivfpq", "hnsw")


def log(msg):
    """Print and flush immediately so a parent process can stream progress."""
    print(msg, flush=True)


def nearest_divisor(d, m):
    """Return the divisor of d closest to m (PQ requires m | d)."""
    divisors = [i for i in range(1, d + 1) if d % i == 0]
    return min(divisors, key=lambda x: abs(x - m))


def metadata_count(index_dir):
    """Count chunk records in alexandria_metadata.json.

    Row i of the vector source MUST correspond to metadata[i]; if the counts
    disagree, every search hit maps to the wrong book. Counting the '"file"'
    key tokens is exact here: JSON escapes any quote characters inside string
    values, so the raw byte sequence '"file"' occurs once per record.
    Returns None when the metadata file is absent.
    """
    meta = Path(index_dir) / "alexandria_metadata.json"
    if not meta.exists():
        return None
    with open(meta, "rb") as f:
        data = f.read()
    return data.count(b'"file"')


def load_vectors(args):
    """Load exact float32 vectors from an existing index or an .npy file."""
    if args.from_npy:
        log(f"Loading embeddings from {args.from_npy} ...")
        vectors = np.load(args.from_npy)
    else:
        src = args.from_index or str(Path(args.index_dir) / "alexandria.index")
        if not Path(src).exists():
            raise FileNotFoundError(f"No source index at {src}")
        log(f"Loading source index {src} ...")
        src_index = faiss.read_index(src)
        n = src_index.ntotal
        log(f"  source has {n:,} vectors; reconstructing ...")
        # IVF indexes need a direct map before reconstruct_n works.
        try:
            src_index.make_direct_map()
        except Exception:
            pass
        vectors = src_index.reconstruct_n(0, n)

    vectors = np.ascontiguousarray(vectors, dtype="float32")
    # Cosine similarity = inner product on L2-normalized vectors. all-MiniLM
    # (and bge/e5/gte) are trained for cosine, so normalize by default.
    if args.metric == "ip":
        faiss.normalize_L2(vectors)
        log("  normalized vectors (cosine / inner-product mode)")
    log(f"✓ Vectors ready: {vectors.shape[0]:,} x {vectors.shape[1]}")
    return vectors


def build_index(vectors, args):
    """Construct the requested FAISS index from in-memory vectors."""
    n, d = vectors.shape
    faiss.omp_set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
    t = args.index_type
    metric = faiss.METRIC_INNER_PRODUCT if args.metric == "ip" else faiss.METRIC_L2
    flat_cls = faiss.IndexFlatIP if args.metric == "ip" else faiss.IndexFlatL2
    params = {"index_type": t, "metric": args.metric, "dimension": d, "ntotal": int(n)}

    log(f"\n=== Building {t.upper()} index ({args.metric}) for {n:,} vectors (dim {d}) ===")
    start = time.time()

    if t == "flat":
        index = flat_cls(d)
        index.add(vectors)

    elif t == "ivfflat":
        nlist = args.nlist
        quantizer = flat_cls(d)
        index = faiss.IndexIVFFlat(quantizer, d, nlist, metric)
        log(f"  nlist={nlist}; training centroids ...")
        index.train(vectors)
        index.add(vectors)
        index.nprobe = args.nprobe
        params.update(nlist=nlist, nprobe=args.nprobe)

    elif t == "ivfpq":
        nlist = args.nlist
        m = args.pq_m
        if d % m != 0:
            snapped = nearest_divisor(d, m)
            log(f"  ⚠ pq_m={m} does not divide d={d}; using m={snapped}")
            m = snapped
        nbits = args.pq_nbits
        quantizer = flat_cls(d)
        index = faiss.IndexIVFPQ(quantizer, d, nlist, m, nbits, metric)
        log(f"  nlist={nlist}, pq_m={m}, nbits={nbits}; training ...")
        index.train(vectors)
        index.add(vectors)
        index.nprobe = args.nprobe
        params.update(nlist=nlist, nprobe=args.nprobe, pq_m=m, pq_nbits=nbits)

    elif t == "hnsw":
        M = args.hnsw_m
        index = faiss.IndexHNSWFlat(d, M, metric)
        index.hnsw.efConstruction = args.hnsw_efc
        log(f"  M={M}, efConstruction={args.hnsw_efc}; building graph ...")
        index.add(vectors)
        index.hnsw.efSearch = args.hnsw_efs
        params.update(hnsw_m=M, hnsw_ef_construction=args.hnsw_efc,
                      hnsw_ef_search=args.hnsw_efs)
    else:
        raise ValueError(f"Unknown index type: {t}")

    params["build_seconds"] = round(time.time() - start, 1)
    log(f"✓ Built in {params['build_seconds']}s ({index.ntotal:,} vectors)")
    return index, params


def quick_accuracy(index, vectors, args, n_queries=200, k=10):
    """Top-k overlap vs exact Flat search, on a random sample of queries."""
    if args.index_type == "flat":
        return 100.0
    n = vectors.shape[0]
    sample = vectors[np.random.choice(n, min(n_queries, n), replace=False)]
    flat_cls = faiss.IndexFlatIP if args.metric == "ip" else faiss.IndexFlatL2
    flat = flat_cls(vectors.shape[1])
    flat.add(vectors)
    _, I_true = flat.search(sample, k)
    _, I_new = index.search(sample, k)
    overlap = np.mean([len(set(I_true[i]) & set(I_new[i])) / k
                       for i in range(sample.shape[0])]) * 100
    return round(float(overlap), 1)


def save_index(index, params, args):
    """Save the new index, back up the old one, and write index_params.json."""
    index_dir = Path(args.index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    index_path = index_dir / "alexandria.index"

    if index_path.exists() and not args.no_backup:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = index_dir / f"alexandria.index.{stamp}.backup"
        shutil.copy(index_path, backup)
        log(f"✓ Backed up previous index → {backup.name}")

    faiss.write_index(index, str(index_path))
    size_gb = index_path.stat().st_size / 1e9
    params["index_size_gb"] = round(size_gb, 3)
    params["built_at"] = datetime.now().isoformat()

    with open(index_dir / "index_params.json", "w") as f:
        json.dump(params, f, indent=2)
    log(f"✓ Saved {index_path.name} ({size_gb:.2f} GB)")
    log(f"✓ Wrote index_params.json")


def main():
    p = argparse.ArgumentParser(description="Torch-free FAISS index builder")
    p.add_argument("--index-dir", default="/Volumes/PRO-BLADE/Alexandria")
    p.add_argument("--index-type", choices=VALID_TYPES, default="ivfflat")
    p.add_argument("--metric", choices=("ip", "l2"), default="ip",
                   help="ip = cosine (normalized inner product, recommended); l2 = Euclidean")
    p.add_argument("--from-index", help="Source FAISS index to reconstruct vectors from")
    p.add_argument("--from-npy", help="Source embeddings .npy file")
    # IVF
    p.add_argument("--nlist", type=int, default=1000)
    p.add_argument("--nprobe", type=int, default=50)
    # PQ
    p.add_argument("--pq-m", type=int, default=64, help="PQ subquantizers (must divide dim)")
    p.add_argument("--pq-nbits", type=int, default=8)
    # HNSW
    p.add_argument("--hnsw-m", type=int, default=32)
    p.add_argument("--hnsw-efc", type=int, default=200, help="efConstruction")
    p.add_argument("--hnsw-efs", type=int, default=64, help="efSearch")
    p.add_argument("--no-backup", action="store_true")
    p.add_argument("--force-mismatch", action="store_true",
                   help="Build even if vector count disagrees with metadata (DANGEROUS)")
    p.add_argument("--no-accuracy", action="store_true", help="Skip the accuracy check")
    args = p.parse_args()

    log("=" * 70)
    log(f"Alexandria index builder — {args.index_type.upper()}")
    log("=" * 70)

    vectors = load_vectors(args)

    # ── Alignment guard (added 2026-07-24) ──────────────────────────────
    # A stale alexandria_embeddings.npy silently scrambles the id→metadata
    # mapping: the index answers queries confidently while attributing every
    # passage to the wrong book (observed 2026-07-22 and 2026-07-24).
    # Refuse to build from any source whose row count disagrees with
    # alexandria_metadata.json; if the .npy is stale but the live index is
    # aligned, fall back to reconstructing exact vectors from the index.
    meta_n = metadata_count(args.index_dir)
    if meta_n is not None and meta_n != vectors.shape[0] and not args.force_mismatch:
        log(f"\n✗ ALIGNMENT MISMATCH: vector source has {vectors.shape[0]:,} rows; "
            f"alexandria_metadata.json has {meta_n:,} entries.")
        log("  An index built from this source would map every search result to")
        log("  the wrong book. Refusing to proceed.")
        fell_back = False
        if args.from_npy:
            live = str(Path(args.index_dir) / "alexandria.index")
            if Path(live).exists():
                probe = faiss.read_index(live)
                n_live = probe.ntotal
                del probe
                if n_live == meta_n:
                    log(f"  → {Path(args.from_npy).name} is STALE; the current "
                        f"alexandria.index ({n_live:,} vectors) matches the metadata.")
                    log("  → Falling back to --from-index (exact reconstruction).")
                    args.from_npy = None
                    args.from_index = live
                    vectors = load_vectors(args)
                    fell_back = (vectors.shape[0] == meta_n)
        if not fell_back:
            log("\n  Fix: run the full encoder (index_books.py) so embeddings,")
            log("  metadata and index regenerate together — or pass --force-mismatch")
            log("  only if you are certain (NOT recommended).")
            return 2
    index, params = build_index(vectors, args)

    if not args.no_accuracy:
        log("\nMeasuring top-10 overlap vs exact Flat search ...")
        acc = quick_accuracy(index, vectors, args)
        params["accuracy_vs_flat_pct"] = acc
        log(f"✓ Top-10 overlap: {acc}%")

    save_index(index, params, args)
    log("\n✓ Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

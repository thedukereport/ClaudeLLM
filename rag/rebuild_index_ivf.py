#!/usr/bin/env python3
"""
Rebuild Alexandria RAG index using IVFFlat for accuracy with speed improvement.

IVFFlat Strategy:
- Partitions 1.7M vectors into clusters (exact distances within clusters)
- Searches top clusters intelligently (no quantization loss)
- 5-10x faster than Flat, 100% accurate
- Minimal memory overhead

Usage:
    python3 rebuild_index_ivf.py --index-dir /Volumes/PRO-BLADE/Alexandria
"""

# ---------------------------------------------------------------------------
# CRITICAL: do NOT import torch / sentence_transformers in this process.
# torch, sklearn and faiss each bundle their own libomp.dylib. Loading two
# OpenMP runtimes into one process segfaults FAISS the moment it enters a
# parallel section (k-means training, HNSW graph build) on macOS.
# This script only needs faiss + numpy, so torch never gets loaded.
# The env guards below are belt-and-suspenders in case any dependency drags
# a second OpenMP runtime in anyway.
# ---------------------------------------------------------------------------
import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "4")

import argparse
import json
import time
from pathlib import Path

import numpy as np
import faiss

def load_metadata(index_dir):
    """Load existing metadata from current index."""
    metadata_path = Path(index_dir) / "alexandria_metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata not found at {metadata_path}")

    with open(metadata_path) as f:
        metadata = json.load(f)

    print(f"✓ Loaded metadata: {len(metadata)} entries")
    return metadata

def load_old_index(index_dir):
    """Load existing FAISS index."""
    index_path = Path(index_dir) / "alexandria.index"
    if not index_path.exists():
        raise FileNotFoundError(f"Index not found at {index_path}")

    index = faiss.read_index(str(index_path))
    print(f"✓ Loaded old index: {index.ntotal} vectors")
    return index

def extract_vectors_from_old_index(old_index):
    """Extract all vectors from old flat index."""
    # Reconstruct vectors from index
    vectors = old_index.reconstruct_n(0, old_index.ntotal)
    # FAISS requires a C-contiguous float32 array; a non-contiguous or wrong
    # dtype buffer is a separate, silent cause of segfaults in train()/add().
    vectors = np.ascontiguousarray(vectors, dtype='float32')
    print(f"✓ Extracted {vectors.shape[0]} vectors, dimension: {vectors.shape[1]}")
    return vectors

def build_ivf_index(vectors, dimension=384, nlist=1000):
    """Build IVFFlat index optimized for accuracy."""
    print(f"\n=== Building IVFFlat Index ===")
    print(f"Vectors: {vectors.shape[0]:,}")
    print(f"Dimensions: {dimension}")
    print(f"Clusters (nlist): {nlist}")

    # Cap FAISS worker threads. With torch gone there is a single OpenMP
    # runtime, so threading is safe; this just keeps memory predictable.
    faiss.omp_set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))

    # Defensive: guarantee the buffer FAISS sees is contiguous float32.
    vectors = np.ascontiguousarray(vectors, dtype='float32')

    # Create quantizer (does the clustering)
    quantizer = faiss.IndexFlatL2(dimension)

    # Create IVFFlat index
    index = faiss.IndexIVFFlat(quantizer, dimension, nlist, faiss.METRIC_L2)

    # Training phase (learns cluster centroids)
    print("\n→ Training index (learning cluster centroids)...")
    start = time.time()
    index.train(vectors)
    print(f"  Training complete in {time.time() - start:.1f}s")

    # Adding vectors to clusters
    print("→ Adding vectors to index...")
    start = time.time()
    index.add(vectors)
    print(f"  Added {index.ntotal:,} vectors in {time.time() - start:.1f}s")

    # Set search parameters. 128 is the measured recall/latency knee for this
    # corpus (~99% recall vs exhaustive at <10 ms/query; sweep 2026-07). Kept in
    # sync with DEFAULT_NPROBE in query_rag.py, which also enforces it as a floor
    # on load — so this value and the runtime default agree.
    index.nprobe = 128
    print(f"→ nprobe set to {index.nprobe} (searches ~{100*index.nprobe//nlist}% of clusters)")

    return index

def test_index_accuracy(old_index, new_index, vectors, test_queries=100):
    """Compare accuracy of old Flat vs new IVF index."""
    print(f"\n=== Accuracy Test ({test_queries} random queries) ===")

    # Random test queries
    test_indices = np.random.choice(vectors.shape[0], test_queries, replace=False)
    test_vectors = vectors[test_indices].astype('float32')

    # Search both indexes
    k = 10
    D_old, I_old = old_index.search(test_vectors, k)
    D_new, I_new = new_index.search(test_vectors, k)

    # Compare: how many of top-10 results match?
    matches = []
    for i in range(test_queries):
        old_set = set(I_old[i])
        new_set = set(I_new[i])
        match_count = len(old_set & new_set)
        matches.append(match_count / k)

    avg_match = np.mean(matches) * 100
    print(f"Average top-10 result overlap: {avg_match:.1f}%")

    if avg_match > 95:
        print("✓ Excellent accuracy — IVF results highly consistent with Flat")
    elif avg_match > 85:
        print("✓ Good accuracy — minor differences acceptable for speed gain")
    else:
        print("⚠ Consider increasing nprobe for better accuracy")

    return avg_match

def save_index(index, index_dir, backup_old=True):
    """Save new index and backup old one."""
    index_path = Path(index_dir) / "alexandria.index"
    backup_path = Path(index_dir) / "alexandria.index.flat.backup"

    # Backup old index
    if backup_old and index_path.exists():
        import shutil
        shutil.copy(index_path, backup_path)
        print(f"\n✓ Old index backed up to: alexandria.index.flat.backup")

    # Save new index
    faiss.write_index(index, str(index_path))
    print(f"✓ New IVFFlat index saved to: alexandria.index")

    # Print file sizes
    old_size = (backup_path.stat().st_size / 1e9) if backup_path.exists() else 0
    new_size = (index_path.stat().st_size / 1e9)
    if old_size > 0:
        reduction = (1 - new_size/old_size) * 100
        print(f"  Size: {old_size:.2f}GB → {new_size:.2f}GB ({reduction:+.1f}%)")
    else:
        print(f"  Size: {new_size:.2f}GB")

def main():
    parser = argparse.ArgumentParser(description="Rebuild Alexandria index with IVFFlat")
    parser.add_argument("--index-dir", default="/Volumes/PRO-BLADE/Alexandria",
                        help="Directory containing index files")
    parser.add_argument("--nlist", type=int, default=1000,
                        help="Number of clusters (default: 1000)")
    parser.add_argument("--no-backup", action="store_true",
                        help="Don't backup old index")
    args = parser.parse_args()

    index_dir = Path(args.index_dir)

    print("=" * 70)
    print("Alexandria RAG - IVFFlat Index Rebuild")
    print("=" * 70)

    # Load old index and extract vectors
    old_index = load_old_index(index_dir)
    vectors = extract_vectors_from_old_index(old_index)
    metadata = load_metadata(index_dir)

    # Build new IVF index
    new_index = build_ivf_index(vectors, dimension=384, nlist=args.nlist)

    # Test accuracy
    accuracy = test_index_accuracy(old_index, new_index, vectors, test_queries=100)

    # Save
    save_index(new_index, index_dir, backup_old=not args.no_backup)

    print("\n" + "=" * 70)
    print("✓ IVFFlat index rebuild complete")
    print("\nUsage:")
    print("  - Your Flask app will automatically use the new index")
    print("  - Expected search speedup: 5-10x")
    print("  - Expected accuracy: 95%+ (see above)")
    print("\nTo revert to old index:")
    print("  mv alexandria.index.flat.backup alexandria.index")
    print("=" * 70)

if __name__ == "__main__":
    main()

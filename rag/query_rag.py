#!/usr/bin/env python3
"""
Alexandria RAG Query Interface
Search through your indexed book collection using semantic similarity.
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

# Baked-in default for IVF indexes. 128 is the recall/latency knee for the
# current index: ~99% recall vs an exhaustive scan at <10 ms/query, measured by
# the Recall-vs-Latency sweep (2026-07). Below this you lose real recall; above
# it latency climbs while recall is already flat. Applied on every load, so the
# MCP server, the web UI, and any rebuild all start here. It is a FLOOR, not a
# cap — a higher value deliberately persisted in the index is left untouched.
DEFAULT_NPROBE = 128


class RAGQuerier:
    """Query semantic search index."""

    def __init__(self, index_dir: str = ".", model_name: str = "all-MiniLM-L6-v2"):
        """Load index and metadata."""
        index_dir = Path(index_dir)

        index_path = index_dir / "alexandria.index"
        metadata_path = index_dir / "alexandria_metadata.json"

        if not index_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(
                f"Index files not found in {index_dir}. "
                "Run index_books.py first."
            )

        print(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)

        print(f"Loading FAISS index from {index_path}")
        self.index = faiss.read_index(str(index_path))

        # This process also has torch loaded (SentenceTransformer). torch and
        # faiss each bundle their own OpenMP runtime, and heavy parallel FAISS
        # work (e.g. an exhaustive nprobe=nlist scan) can segfault the process
        # on macOS. Pin FAISS to ONE thread here so all in-process search/sweep
        # is crash-proof. The multi-threaded index BUILD runs separately in a
        # torch-free subprocess (build_index_cli.py), so it keeps full speed.
        faiss.omp_set_num_threads(1)

        # Detect index family so we know which knobs are tunable at search time.
        self.is_ivf = hasattr(self.index, "nprobe")
        self.is_hnsw = hasattr(self.index, "hnsw")
        self.index_type = type(self.index).__name__
        # Detect metric: inner product (cosine, on normalized vectors) vs L2.
        self.is_cosine = (self.index.metric_type == faiss.METRIC_INNER_PRODUCT)
        self.metric = "cosine" if self.is_cosine else "l2"

        # Apply the baked-in nprobe default (floor). See DEFAULT_NPROBE above.
        if self.is_ivf and self.index.nprobe < DEFAULT_NPROBE:
            self.index.nprobe = DEFAULT_NPROBE

        with open(metadata_path) as f:
            self.metadata = json.load(f)

        print(f"Loaded index with {len(self.metadata)} chunks from {len(set(m['file'] for m in self.metadata))} books")
        print(f"Index type: {self.index_type} (ivf={self.is_ivf}, hnsw={self.is_hnsw})")

    def get_index_info(self) -> Dict:
        """Report index type, vector count, and which params can be tuned live."""
        info = {
            "index_type": self.index_type,
            "metric": self.metric,
            "ntotal": int(self.index.ntotal),
            "tunable": [],
        }
        if self.is_ivf:
            info["nprobe"] = int(self.index.nprobe)
            info["nlist"] = int(getattr(self.index, "nlist", 0))
            info["tunable"].append("nprobe")
        if self.is_hnsw:
            info["ef_search"] = int(self.index.hnsw.efSearch)
            info["tunable"].append("ef_search")
        return info

    def set_search_params(self, nprobe: int = None, ef_search: int = None):
        """Apply live search-time tuning. No rebuild required."""
        if nprobe is not None and self.is_ivf:
            self.index.nprobe = int(nprobe)
        if ef_search is not None and self.is_hnsw:
            self.index.hnsw.efSearch = int(ef_search)

    def sweep(self, queries: List[str], values: List[int] = None, k: int = 10) -> Dict:
        """Measure recall + latency across the tunable param (nprobe for IVF,
        efSearch for HNSW). Recall is top-k overlap vs an exhaustive search of
        the SAME index (nprobe=nlist / very large efSearch), so 100% = exact.
        Encodes queries once, then only re-runs the cheap search per value."""
        import time
        if not (self.is_ivf or self.is_hnsw):
            return {"supported": False, "param": None, "points": []}

        # Defensive: keep FAISS single-threaded here. The reference pass scans
        # many/all clusters, and multi-threaded FAISS beside torch can segfault.
        faiss.omp_set_num_threads(1)

        emb = self.model.encode(queries, convert_to_numpy=True).astype("float32")
        if self.is_cosine:
            faiss.normalize_L2(emb)
        nq = len(queries)

        def recall_vs(ref, cur):
            return float(np.mean([len(set(ref[i]) & set(cur[i])) / k for i in range(nq)])) * 100

        if self.is_ivf:
            nlist = int(getattr(self.index, "nlist", 0)) or 1
            # Bound the "exhaustive" reference so the sweep stays fast even
            # single-threaded. 2048 clusters is effectively exact for recall.
            ref_nprobe = min(nlist, 2048)
            if not values:
                values = [v for v in [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048] if v <= ref_nprobe]
            orig = int(self.index.nprobe)
            self.index.nprobe = ref_nprobe                 # near-exhaustive reference
            _, ref = self.index.search(emb, k)
            points = []
            for v in values:
                self.index.nprobe = int(v)
                t0 = time.perf_counter(); _, cur = self.index.search(emb, k)
                dt = (time.perf_counter() - t0) * 1000.0
                points.append({"x": int(v), "recall": round(recall_vs(ref, cur), 1),
                               "latency_ms": round(dt / nq, 2)})
            self.index.nprobe = orig
            return {"supported": True, "param": "nprobe", "nlist": nlist, "points": points}

        # HNSW
        if not values:
            values = [8, 16, 32, 64, 128, 256, 512]
        orig = int(self.index.hnsw.efSearch)
        self.index.hnsw.efSearch = max(max(values), 1024)  # near-exhaustive reference
        _, ref = self.index.search(emb, k)
        points = []
        for v in values:
            self.index.hnsw.efSearch = int(v)
            t0 = time.perf_counter(); _, cur = self.index.search(emb, k)
            dt = (time.perf_counter() - t0) * 1000.0
            points.append({"x": int(v), "recall": round(recall_vs(ref, cur), 1),
                           "latency_ms": round(dt / nq, 2)})
        self.index.hnsw.efSearch = orig
        return {"supported": True, "param": "ef_search", "points": points}

    def search(self, query: str, k: int = 5,
               nprobe: int = None, ef_search: int = None) -> List[Dict]:
        """Search for similar passages, optionally overriding tuning params."""
        if nprobe is not None or ef_search is not None:
            self.set_search_params(nprobe=nprobe, ef_search=ef_search)

        # Encode query
        query_embedding = self.model.encode([query], convert_to_numpy=True).astype("float32")
        # For cosine indexes, the query must be normalized the same way the
        # stored vectors were, so inner product equals cosine similarity.
        if self.is_cosine:
            faiss.normalize_L2(query_embedding)

        # Search index
        scores, indices = self.index.search(query_embedding, k)

        # Retrieve results
        results = []
        for i, idx in enumerate(indices[0]):
            if idx >= 0:
                meta = self.metadata[idx]
                score = float(scores[0][i])
                # IP score IS the cosine similarity; L2 needs the 1/(1+d) map.
                similarity = score if self.is_cosine else 1 / (1 + score)
                results.append({
                    "rank": i + 1,
                    "distance": score,
                    "similarity": similarity,
                    "file": meta["file"],
                    "title": meta["title"],
                    "chunk": meta["chunk_idx"],
                    "preview": meta["text_preview"],
                })

        return results

    def interactive_search(self):
        """Interactive search loop."""
        print("\n" + "=" * 70)
        print("Alexandria RAG - Semantic Search")
        print("=" * 70)
        print("Type your query and press Enter. Type 'quit' to exit.\n")

        while True:
            query = input("Query: ").strip()

            if query.lower() in ["quit", "exit", "q"]:
                break

            if not query:
                continue

            results = self.search(query, k=5)

            print(f"\nTop 5 results for: '{query}'")
            print("-" * 70)

            for result in results:
                print(f"\n[{result['rank']}] {result['title']}")
                print(f"    File: {result['file']}")
                print(f"    Chunk {result['chunk']} | Similarity: {result['similarity']:.2%}")
                print(f"    Preview: {result['preview']}")

            print("\n" + "=" * 70)

    def batch_search(self, queries: List[str], k: int = 5, output_file: str = None) -> List[Dict]:
        """Search multiple queries and optionally save results."""
        all_results = []

        for query in queries:
            results = self.search(query, k=k)
            all_results.append({
                "query": query,
                "results": results
            })

        if output_file:
            with open(output_file, "w") as f:
                json.dump(all_results, f, indent=2)
            print(f"Results saved to {output_file}")

        return all_results


def main():
    parser = argparse.ArgumentParser(description="Query Alexandria RAG")
    parser.add_argument("--index-dir", default=".", help="Directory containing index")
    parser.add_argument("--query", help="Single query (use for non-interactive mode)")
    parser.add_argument("--queries-file", help="JSON file with list of queries")
    parser.add_argument("--output", help="Output file for batch results")
    parser.add_argument("--k", type=int, default=5, help="Number of results to return")
    parser.add_argument("--model", default="all-MiniLM-L6-v2", help="SentenceTransformer model")

    args = parser.parse_args()

    # Initialize querier
    querier = RAGQuerier(index_dir=args.index_dir, model_name=args.model)

    # Mode: Single query
    if args.query:
        results = querier.search(args.query, k=args.k)
        print(f"\nTop {args.k} results for: '{args.query}'")
        print("=" * 70)
        for result in results:
            print(f"\n[{result['rank']}] {result['title']}")
            print(f"    File: {result['file']}")
            print(f"    Chunk {result['chunk']} | Similarity: {result['similarity']:.2%}")
            print(f"    Preview: {result['preview']}")

    # Mode: Batch queries from file
    elif args.queries_file:
        with open(args.queries_file) as f:
            queries = json.load(f)
        querier.batch_search(queries, k=args.k, output_file=args.output)

    # Mode: Interactive search
    else:
        querier.interactive_search()


if __name__ == "__main__":
    main()

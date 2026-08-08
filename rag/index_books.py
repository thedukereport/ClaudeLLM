#!/usr/bin/env python3
"""
Alexandria RAG Indexer
Extracts text from PDFs, generates embeddings, and builds a FAISS index.
By default, indexes PDF files only. Use --include-epub to also process EPUB files.
"""

import os
# ── Memory/thread safety (MUST run before numpy/torch/faiss import) ──────────
# The full-library embed crashed a 128 GB Mac twice: a single Python process hit
# 123 GB with load average 321. Two causes, both tamed here + in generate_embeddings:
#   1. MPS (Apple GPU) uses UNIFIED system RAM and its allocator accumulates
#      across the ~25k encode() calls of a full run unless the cache is flushed.
#   2. Unbounded thread fan-out (OpenMP/tokenizers) drove the load to 321.
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
# GPU (MPS) is the DEFAULT again and is safe now that (a) the streaming embed
# never holds the matrix in RAM, (b) empty_cache runs every batch, (c) the web UI
# frees its index during a rebuild, (d) only one embed runs at a time (lockfile),
# and (e) an RSS watchdog aborts gracefully long before the machine can freeze.
# We deliberately do NOT set PYTORCH_MPS_*_WATERMARK_RATIO: setting the HIGH ratio
# below the default LOW ratio makes torch raise "invalid low watermark ratio" at
# model load (hit 2026-07). Memory is bounded by empty_cache + the watchdog, not
# by fighting the watermarks. Force CPU with ALEX_EMBED_DEVICE=cpu if ever needed.
import sys
import json
import logging
import argparse
import warnings
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np
from tqdm import tqdm
import pdfplumber
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
import faiss

warnings.filterwarnings("ignore")


# --------------------------------------------------------------------------- #
# Memory instrumentation — so a run TELLS us where RAM goes instead of us
# reading Activity Monitor tea leaves. _rss_gb() returns the process's current
# resident set in GB (psutil if present; falls back to resource peak).
# --------------------------------------------------------------------------- #
def _rss_gb() -> float:
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / 1e9
    except Exception:
        try:
            import resource
            m = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # macOS reports bytes; Linux reports kilobytes.
            return (m / 1e9) if sys.platform == "darwin" else (m / 1e6)
        except Exception:
            return -1.0


def _log_rss(phase: str) -> float:
    g = _rss_gb()
    if g >= 0:
        print(f"  [mem] {phase}: {g:.1f} GB RSS", flush=True)
    return g


# Files that triggered recoverable extraction issues (e.g. pdfminer's
# "Data-loss while decompressing corrupted data"). pdfminer logs those as bare
# warnings with NO filename, so we capture them per-file and record the path.
PROBLEM_PDFS = []  # list of (file_path, [messages])


class _PdfWarningCollector(logging.Handler):
    """Capture WARNING+ records emitted by pdfminer while one file is parsed."""
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def write_manifest(output_dir: str, metadata: list):
    """Record each indexed file's signature (mtime+size) and chunk count so a
    later --incremental run can detect which books changed."""
    from extract_text import _sig
    counts = {}
    for m in metadata:
        counts[m["file"]] = counts.get(m["file"], 0) + 1
    manifest = {}
    for fp, n in counts.items():
        try:
            manifest[fp] = {"sig": _sig(fp), "chunks": n}
        except OSError:
            manifest[fp] = {"sig": None, "chunks": n}
    (Path(output_dir) / "alexandria_manifest.json").write_text(json.dumps(manifest))
    print(f"✓ Manifest written ({len(manifest)} files)")


def write_problem_report(output_dir: str = "."):
    """Write the list of PDFs with recoverable extraction issues, if any."""
    if not PROBLEM_PDFS:
        return None
    out = Path(output_dir) / "problem_pdfs.txt"
    with open(out, "w") as f:
        f.write(f"# {len(PROBLEM_PDFS)} PDFs had recoverable extraction issues\n")
        f.write("# (text was still extracted where possible; consider replacing these)\n\n")
        for path, msgs in PROBLEM_PDFS:
            f.write(f"{path}\n    {'; '.join(sorted(set(msgs)))}\n")
    print(f"\n⚠ {len(PROBLEM_PDFS)} PDF(s) had recoverable issues — see {out}")
    return out

# Configuration
# NOTE: chunking counts whitespace WORDS, but all-MiniLM-L6-v2's tokenizer caps
# input at 256 SUBWORD tokens (~1.3 tokens/word). A 256-word chunk is ~330
# tokens, so the model would silently truncate the last ~25%. 200 words keeps
# each chunk at/under the model limit so the whole chunk actually gets embedded.
CHUNK_SIZE = 200  # words per chunk (kept under the 256-token model limit)

# Long-context models make the 200-word ceiling pointless: it exists only
# because MiniLM truncates at 256 subword tokens. 400 words (~520 tokens) fits
# any 512+ token model, keeps an argument intact instead of splitting it mid
# paragraph, and still localises a hit to roughly a page -- which matters when
# the result has to support a footnote. Overridable with ALEX_CHUNK_WORDS.
LONG_CONTEXT_CHUNK_SIZE = 400
LONG_CONTEXT_OVERLAP = 80


def prefixes_for(model_name: str) -> tuple:
    """(document prefix, query prefix). The e5 family is TRAINED with these; omit
    them and retrieval quality drops measurably. Both sides must agree, or the
    query lands in a different region of the space than the passages."""
    n = (model_name or "").lower()
    if "e5" in n:
        return "passage: ", "query: "
    return "", ""


def write_embedding_meta(output_dir, indexer):
    """Record WHICH model built this index, beside the index itself.

    Without this the querier defaults to all-MiniLM-L6-v2. multilingual-e5-small
    is also 384-dim, so querying an e5 index with MiniLM raises no dimension
    error -- it just returns quiet nonsense. This file is what prevents that."""
    meta = {
        "model": getattr(indexer, "model_name", None),
        "dim": indexer.embedding_dim,
        "doc_prefix": getattr(indexer, "doc_prefix", ""),
        "query_prefix": getattr(indexer, "query_prefix", ""),
        "max_seq_length": getattr(indexer.model, "max_seq_length", None),
        "chunk_words": chunk_params_for(indexer.model)[0],
    }
    (Path(output_dir) / "embedding_model.json").write_text(json.dumps(meta, indent=2))
    print(f"  recorded embedding model: {meta['model']} (dim {meta['dim']}, "
          f"prefix {meta['doc_prefix']!r})", flush=True)


def chunk_params_for(model) -> tuple:
    """Pick (words, overlap) from the loaded model's real token limit, so that
    switching models in the UI cannot silently mis-size chunks in either
    direction."""
    override = os.environ.get("ALEX_CHUNK_WORDS")
    if override:
        w = int(override)
        return w, max(1, int(w * 0.2))
    limit = getattr(model, "max_seq_length", 0) or 0
    # ~1.4 subword tokens per whitespace word; leave headroom so a chunk's tail
    # is never silently truncated. A 512-token model takes ~350 words, not the
    # 400 a coarse threshold would have handed it.
    if limit >= 2048:
        return LONG_CONTEXT_CHUNK_SIZE, LONG_CONTEXT_OVERLAP
    if limit >= 512:
        w = int(limit / 1.45)
        return w, max(1, int(w * 0.2))
    return CHUNK_SIZE, CHUNK_OVERLAP
CHUNK_OVERLAP = 40  # words of overlap between chunks
MODEL_NAME = "all-MiniLM-L6-v2"  # Fast, effective, 384-dim embeddings
BATCH_SIZE = 128  # Batch size for embedding generation
DUPLICATE_SIMILARITY_THRESHOLD = 0.95  # Threshold for flagging duplicates


class DuplicateDetector:
    """Detect duplicate documents using embedding similarity only."""

    def __init__(self, similarity_threshold: float = DUPLICATE_SIMILARITY_THRESHOLD):
        self.threshold = similarity_threshold
        self.documents = []  # List of (file_path, title, embedding)
        self.suspected_duplicates = []

    def register_document(self, file_path: str, title: str,
                         embedding_signature: Optional[np.ndarray] = None) -> Optional[Dict]:
        """
        Register a document and check for duplicates against previously indexed documents.

        Returns:
            Dict with duplicate info if suspected duplicate found, None otherwise.
        """
        if embedding_signature is None:
            return None

        # Check against all previously registered documents
        duplicate_found = None
        for prev_file, prev_title, prev_embedding in self.documents:
            similarity = self._cosine_similarity(embedding_signature, prev_embedding)

            if similarity >= self.threshold:
                duplicate_found = {
                    'new_file': file_path,
                    'new_title': title,
                    'existing_file': prev_file,
                    'existing_title': prev_title,
                    'similarity': float(similarity),
                }
                self.suspected_duplicates.append(duplicate_found)
                break

        # Register this document
        self.documents.append((file_path, title, embedding_signature))

        return duplicate_found

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def save_report(self, output_path: str):
        """Save duplicate detection report."""
        report = {
            'summary': {
                'total_documents': len(self.documents),
                'suspected_duplicates_count': len(self.suspected_duplicates),
                'similarity_threshold_used': self.threshold,
            },
            'suspected_duplicates': self.suspected_duplicates,
        }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n✓ Duplicate detection report saved to {output_file}")


class BookExtractor:
    """Extract text from PDF and EPUB files."""

    @staticmethod
    def extract_pdf(file_path: str) -> str:
        """Extract text from PDF.

        pdfminer logs corrupted-stream warnings (e.g. "Data-loss while
        decompressing corrupted data") without naming the file. We attach a
        temporary handler to the pdfminer logger so we can attribute any such
        warning to THIS file and record it for the end-of-run report.
        """
        text = []
        pdf_logger = logging.getLogger("pdfminer")
        collector = _PdfWarningCollector()
        prev_level = pdf_logger.level
        pdf_logger.setLevel(logging.WARNING)
        pdf_logger.addHandler(collector)
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text.append(page_text)
            if collector.messages:
                uniq = sorted(set(collector.messages))
                print(f"  ⚠ Recoverable issue in {file_path}: {'; '.join(uniq)}")
                PROBLEM_PDFS.append((file_path, collector.messages))
            return "\n".join(text)
        except Exception as e:
            print(f"  ⚠ Error extracting PDF {file_path}: {e}")
            PROBLEM_PDFS.append((file_path, [str(e)]))
            return ""
        finally:
            pdf_logger.removeHandler(collector)
            pdf_logger.setLevel(prev_level)

    @staticmethod
    def extract_epub(file_path: str) -> str:
        """Extract text from EPUB."""
        text = []
        try:
            book = epub.read_epub(file_path)
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    try:
                        soup = BeautifulSoup(item.get_content(), "html.parser")
                        content = soup.get_text(separator=" ", strip=True)
                        if content:
                            text.append(content)
                    except Exception:
                        continue
            return "\n".join(text)
        except Exception as e:
            print(f"  ⚠ Error extracting EPUB {file_path}: {e}")
            return ""


class TextChunker:
    """Split text into overlapping chunks."""

    @staticmethod
    def tokenize_simple(text: str) -> List[str]:
        """Simple whitespace tokenization."""
        return text.split()

    @classmethod
    def chunk_text(cls, text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
        """Split text into chunks with overlap."""
        tokens = cls.tokenize_simple(text)
        chunks = []

        for i in range(0, len(tokens), chunk_size - overlap):
            chunk_tokens = tokens[i : i + chunk_size]
            if chunk_tokens:
                chunks.append(" ".join(chunk_tokens))

        return chunks


class RAGIndexer:
    """Build FAISS index from book collection."""

    def __init__(self, model_name: str = MODEL_NAME, batch_size: int = BATCH_SIZE,
                 detect_duplicates: bool = False):
        """Initialize embedder and FAISS index."""
        print(f"Loading embedding model: {model_name}")
        # Device: DEFAULT TO MPS (Apple GPU) for speed. The earlier 25 GB climb
        # was MPS competing with a stale index in the web UI (~8 GB) + duplicate
        # MCP servers (~16 GB), not MPS alone — a single streaming embed is well
        # within 48 GB now. If MPS isn't available (non-Mac, older torch) we fall
        # back to CPU automatically. Force CPU with ALEX_EMBED_DEVICE=cpu.
        requested = os.environ.get("ALEX_EMBED_DEVICE", "mps").lower()
        device = requested
        if requested == "mps":
            try:
                import torch
                if not (hasattr(torch.backends, "mps") and
                        torch.backends.mps.is_available()):
                    print("  ⚠ MPS not available on this machine — using CPU.")
                    device = "cpu"
            except Exception:
                device = "cpu"
        self.model = SentenceTransformer(model_name, device=device)
        self.model_name = model_name
        self.doc_prefix, self.query_prefix = prefixes_for(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        self.batch_size = batch_size

        # BATCH_SIZE=128 was tuned for MiniLM: 22M params, 384 dims, 256-token
        # ceiling. A 568M-param 1024-dim model at that batch size drove a 48 GB
        # machine to 59 GB resident and 39 GB of swap -- 11 s/batch of pure
        # paging, a 40-hour ETA for work that takes well under an hour resident.
        # Scale the batch to the model, and cap the sequence window to what we
        # actually feed it (400-word chunks are ~520 tokens; 8192 is dead weight).
        try:
            if self.embedding_dim >= 1024:
                self.batch_size = int(os.environ.get("ALEX_BATCH_SIZE", "16"))
                if getattr(self.model, "max_seq_length", 0) > 1024:
                    self.model.max_seq_length = int(
                        os.environ.get("ALEX_MAX_SEQ", "1024"))
            elif os.environ.get("ALEX_BATCH_SIZE"):
                self.batch_size = int(os.environ["ALEX_BATCH_SIZE"])
        except Exception:
            pass
        print(f"  batch_size={self.batch_size}  dim={self.embedding_dim}  "
              f"max_seq={getattr(self.model, 'max_seq_length', '?')}", flush=True)

        # Cap torch's intra-op threads so embedding can't spawn a thread storm
        # (the crash showed load average 321). Safe if torch isn't present.
        try:
            import torch
            torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "4")))
        except Exception:
            pass

        if hasattr(self.model, 'device'):
            print(f"Using device: {self.model.device}")

        # Index will be created in build_index() after we have embeddings
        self.index = None
        self.metadata = []
        self.chunks = []
        self.document_file_paths = []  # Track which document each chunk belongs to

        # Initialize duplicate detector if enabled
        self.duplicate_detector = DuplicateDetector() if detect_duplicates else None

    def add_document(self, file_path: str, text: str, metadata: Dict) -> int:
        """Add document chunks to index."""
        if not text.strip():
            return 0

        # Guard against ONE pathological document exploding memory. A malformed
        # PDF can extract to GIGABYTES of garbage text; chunking that builds a
        # word list + chunk list large enough to OOM the machine (observed: a
        # single added PDF drove the process to 37 GB at 1% progress). ~50 MB of
        # text is already a ~10,000-page book — beyond that, truncate and warn.
        max_chars = int(os.environ.get("ALEX_MAX_DOC_CHARS", str(50_000_000)))
        if len(text) > max_chars:
            print(f"  ⚠ {Path(file_path).name}: {len(text)/1e6:.0f} MB of extracted "
                  f"text — truncating to {max_chars // 10**6} MB (malformed PDF?)",
                  flush=True)
            text = text[:max_chars]

        _cw, _co = chunk_params_for(getattr(self, "model", None))
        chunks = TextChunker.chunk_text(text, chunk_size=_cw, overlap=_co)
        for i, chunk in enumerate(chunks):
            self.chunks.append(chunk)
            self.document_file_paths.append(file_path)
            self.metadata.append({
                "file": metadata["file"],
                "title": metadata["title"],
                "chunk_idx": i,
                "total_chunks": len(chunks),
                "text_preview": chunk[:200] + "..." if len(chunk) > 200 else chunk,
            })

        return len(chunks)

    def generate_embeddings(self, show_progress: bool = True) -> np.ndarray:
        """STAGE 1 (uses torch via SentenceTransformer): embed all chunks.

        Returns a contiguous float32 matrix. This is the only stage that needs
        torch, so it is kept separate from FAISS index construction.
        """
        if not self.chunks:
            print("No chunks to embed.")
            return np.empty((0, self.embedding_dim), dtype="float32")

        import gc
        n = len(self.chunks)
        print(f"\nGenerating embeddings for {n} chunks...")

        # Preallocate ONE contiguous output matrix and fill it in place. The old
        # code accumulated a list, then np.vstack, then np.ascontiguousarray —
        # THREE full copies of the matrix resident at once. For 3.3M chunks that
        # is ~15 GB of avoidable churn on top of the real killer below.
        out = np.empty((n, self.embedding_dim), dtype="float32")

        # Is MPS (Apple GPU, unified RAM) in play? If so we must release its
        # allocator cache each batch, or it hoards every batch it ever saw and
        # the process climbs to 100 GB+ over a full run.
        mps_flush = None
        try:
            import torch
            if getattr(self.model, "device", None) is not None and \
               str(self.model.device).startswith("mps") and \
               hasattr(getattr(torch, "mps", None), "empty_cache"):
                mps_flush = torch.mps.empty_cache
        except Exception:
            pass

        iterator = tqdm(range(0, n, self.batch_size)) if show_progress else range(0, n, self.batch_size)
        for step, i in enumerate(iterator):
            batch = self.chunks[i : i + self.batch_size]
            # normalize_embeddings=True → unit vectors, so inner product == cosine.
            _b = [self.doc_prefix + c for c in batch] if self.doc_prefix else batch
            be = self.model.encode(
                _b, convert_to_numpy=True, show_progress_bar=False,
                normalize_embeddings=True)
            out[i : i + len(batch)] = be
            del be
            if mps_flush is not None:
                mps_flush()                      # hand memory back every batch
            if step % 200 == 0:
                gc.collect()

        return out

    def embed_and_save(self, output_dir: str = ".", show_progress: bool = True):
        """STAGE 1, MEMORY-BOUNDED: embed straight into a memory-mapped .npy on
        disk. Unlike generate_embeddings(), the full embedding matrix is NEVER
        resident in RAM — only one batch at a time. Essential on <=64 GB Macs,
        where a 3M-chunk matrix (~5 GB) plus the model plus MPS churn is enough
        to tip the machine into swap. Writes metadata + returns the .npy path."""
        import gc
        from numpy.lib.format import open_memmap
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        emb_path = output_dir / "alexandria_embeddings.npy"
        meta_path = output_dir / "alexandria_metadata.json"

        n = len(self.chunks)
        if n == 0:
            print("No chunks to embed.")
            np.save(emb_path, np.empty((0, self.embedding_dim), dtype="float32"))
            meta_path.write_text(json.dumps(self.metadata))
            return emb_path

        print(f"\nStreaming embeddings for {n} chunks → {emb_path.name} (memory-bounded)...")
        _log_rss("embed start")
        mm = open_memmap(emb_path, mode="w+", dtype="float32",
                         shape=(n, self.embedding_dim))

        # MPS memory management: empty_cache hands each batch's buffers back to
        # the allocator; synchronize forces the GPU queue to drain so nothing
        # lingers. Both are no-ops on CPU.
        mps_flush = None
        mps_sync = None
        try:
            import torch
            if getattr(self.model, "device", None) is not None and \
               str(self.model.device).startswith("mps"):
                if hasattr(getattr(torch, "mps", None), "empty_cache"):
                    mps_flush = torch.mps.empty_cache
                if hasattr(getattr(torch, "mps", None), "synchronize"):
                    mps_sync = torch.mps.synchronize
        except Exception:
            pass

        # RSS watchdog: hard insurance so a runaway (MPS or otherwise) can NEVER
        # freeze the Mac again. Warn at ALEX_RSS_WARN_GB, abort gracefully at
        # ALEX_RSS_ABORT_GB. Defaults sized for a 48 GB machine; a clean MPS embed
        # peaks well under the warn line, so these should never trip in practice.
        warn_gb = float(os.environ.get("ALEX_RSS_WARN_GB", "30"))
        abort_gb = float(os.environ.get("ALEX_RSS_ABORT_GB", "42"))
        warned = False

        it = tqdm(range(0, n, self.batch_size)) if show_progress else range(0, n, self.batch_size)
        for step, i in enumerate(it):
            batch = self.chunks[i : i + self.batch_size]
            _b = [self.doc_prefix + c for c in batch] if self.doc_prefix else batch
            be = self.model.encode(_b, convert_to_numpy=True,
                                   show_progress_bar=False, normalize_embeddings=True)
            mm[i : i + len(batch)] = be           # write straight to disk
            del be
            if mps_flush is not None:
                mps_flush()
            if step % 50 == 0 and mps_sync is not None:
                mps_sync()                         # drain the GPU queue
            if step % 100 == 0:
                mm.flush(); gc.collect()
            # Emit a parseable progress line the GUI can read, so the bar MOVES
            # during the long embed instead of sitting at the cached-extraction
            # number (which looks frozen and tempts a fatal second click).
            if step % 40 == 0:
                done = min(i + self.batch_size, n)
                print(f"  embedded {done:,}/{n:,} chunks", flush=True)
                g = _log_rss(f"embed {done:,}/{n:,}")
                if g >= 0 and g >= warn_gb and not warned:
                    print(f"  ⚠ RSS {g:.1f} GB is above the {warn_gb:.0f} GB warn line "
                          f"— watching closely.", flush=True)
                    warned = True
                if g >= 0 and g >= abort_gb:
                    mm.flush(); del mm; gc.collect()
                    raise MemoryError(
                        f"RSS {g:.1f} GB exceeded ALEX_RSS_ABORT_GB={abort_gb:.0f} GB; "
                        f"aborting the embed to protect the machine. The partial "
                        f".npy was flushed; rerun (or set ALEX_EMBED_DEVICE=cpu).")

        mm.flush()
        del mm                                     # close the memmap
        meta_path.write_text(json.dumps(self.metadata))
        print(f"✓ Embeddings streamed to {emb_path} ({n} x {self.embedding_dim})")
        print(f"✓ Metadata saved to {meta_path}")
        return emb_path

    def save_embeddings(self, embeddings: np.ndarray, output_dir: str = "."):
        """Persist the embedding matrix + metadata so a SEPARATE, torch-free
        process (build_index_cli.py) can construct any FAISS index from them.
        This is what avoids the dual-OpenMP segfault on macOS."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        emb_path = output_dir / "alexandria_embeddings.npy"
        metadata_path = output_dir / "alexandria_metadata.json"
        np.save(emb_path, embeddings)
        with open(metadata_path, "w") as f:
            json.dump(self.metadata, f, indent=2)
        print(f"✓ Embeddings saved to {emb_path} ({embeddings.shape[0]} x {embeddings.shape[1]})")
        print(f"✓ Metadata saved to {metadata_path}")

    def build_index(self, show_progress: bool = True) -> Tuple:
        """Generate embeddings and build a Flat FAISS index (in-process).

        NOTE: only the Flat index is safe to build in this (torch-loaded)
        process. For IVFFlat / IVFPQ / HNSW, save embeddings with
        save_embeddings() and build them with build_index_cli.py, which runs
        torch-free to avoid the dual-OpenMP segfault.
        """
        if not self.chunks:
            print("No chunks to index.")
            return self.index, self.metadata

        embeddings = self.generate_embeddings(show_progress=show_progress)

        # Build Flat index (reliable, no parallel construction → no segfault).
        # IndexFlatIP + normalized embeddings = cosine similarity search.
        print(f"\nBuilding Flat (cosine/IP) index for {embeddings.shape[0]} embeddings...")
        self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.index.add(embeddings)
        print(f"✓ Index built successfully ({embeddings.shape[0]} vectors)")

        # Compute document-level embedding signatures for duplicate detection
        if self.duplicate_detector:
            print("\nComputing document embeddings for duplicate detection...")
            self._compute_document_signatures(embeddings)

        return self.index, self.metadata

    def _compute_document_signatures(self, all_embeddings: np.ndarray):
        """Compute document embeddings and check for duplicates."""
        # Build mapping of file_path to chunk indices
        file_to_chunks = {}
        for i, file_path in enumerate(self.document_file_paths):
            if file_path not in file_to_chunks:
                file_to_chunks[file_path] = []
            file_to_chunks[file_path].append(i)

        # Process each unique document
        processed_files = set()
        for file_path, chunk_indices in file_to_chunks.items():
            if file_path in processed_files:
                continue
            processed_files.add(file_path)

            # Get embeddings for this document's chunks
            doc_embeddings = all_embeddings[chunk_indices]

            # Compute average embedding
            avg_embedding = np.mean(doc_embeddings, axis=0).astype('float32')

            # Find the title for this file
            title = None
            for m in self.metadata:
                if m['file'] == file_path:
                    title = m['title']
                    break

            if title:
                # Register with duplicate detector
                duplicate_found = self.duplicate_detector.register_document(
                    file_path=file_path,
                    title=title,
                    embedding_signature=avg_embedding
                )
                if duplicate_found:
                    print(f"  ⚠ Potential duplicate:")
                    print(f"    New: {Path(file_path).name}")
                    print(f"    Existing: {Path(duplicate_found['existing_file']).name}")
                    print(f"    Similarity: {duplicate_found['similarity']:.1%}")

    def save(self, output_dir: str = "."):
        """Save index and metadata."""
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)

        index_path = output_dir / "alexandria.index"
        metadata_path = output_dir / "alexandria_metadata.json"

        faiss.write_index(self.index, str(index_path))
        with open(metadata_path, "w") as f:
            json.dump(self.metadata, f, indent=2)

        print(f"\n✓ Index saved to {index_path}")
        print(f"✓ Metadata saved to {metadata_path}")

        # Save duplicate detection report if detector is enabled
        if self.duplicate_detector:
            report_path = output_dir / "duplicate_detection_report.json"
            self.duplicate_detector.save_report(str(report_path))


def scan_books(directory: str, pdf_only: bool = True) -> List[Tuple[str, str]]:
    """Scan directory for book files.

    Args:
        directory: Path to scan
        pdf_only: If True, only index PDF files. If False, also include EPUB files.
    """
    books = []
    directory = Path(directory)

    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        return books

    # Determine which file types to scan
    if pdf_only:
        extensions = ["*.pdf", "*.PDF"]
        file_type_desc = "PDF files"
    else:
        extensions = ["*.pdf", "*.PDF", "*.epub", "*.EPUB"]
        file_type_desc = "PDF and EPUB files"

    print(f"Scanning {directory} for {file_type_desc}...")

    # Working trees that live under the library root but are NOT library books.
    # Without this, rglob sweeps in the pre-optimisation quarantine copies, and
    # every book that was repaired or OCR'd gets indexed twice -- once as the
    # searchable version and once as its damaged predecessor.
    SKIP_DIR_NAMES = {
        "_Optimization", "_retired", "_originals_pre_optimization",
        ".ocrwork", ".textcache", "_gaveston_page_scans",
    }

    # Files whose text layer is unreadable glyph codes. Indexing them injects
    # nonsense tokens that look like real content to the retriever.
    excluded = set()
    _cands = [Path(__file__).resolve().parent / "index_exclude.txt",
              directory / "_Optimization" / "index_exclude.txt",
              directory / "PDF" / "_Optimization" / "index_exclude.txt",
              directory.parent / "PDF" / "_Optimization" / "index_exclude.txt"]
    for cand in _cands:
        if cand.exists():
            for line in cand.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    excluded.add(os.path.realpath(line))
            print(f"  exclude list: {cand} ({len(excluded)} file(s))")

    skipped_dirs = skipped_excluded = 0
    seen = set()
    for ext in extensions:
        for file_path in directory.rglob(ext):
            if SKIP_DIR_NAMES.intersection(file_path.parts):
                skipped_dirs += 1
                continue
            real = os.path.realpath(str(file_path))
            if real in excluded:
                skipped_excluded += 1
                continue
            if real in seen:          # same file reached by two paths
                continue
            seen.add(real)
            books.append((str(file_path), file_path.stem))

    if skipped_dirs:
        print(f"  skipped {skipped_dirs} file(s) in working/quarantine directories")
    if skipped_excluded:
        print(f"  skipped {skipped_excluded} file(s) on the exclude list")
    print(f"  {len(books)} book(s) to index")

    return books


def run_incremental(args, cache_dir, dry_run=False):
    """Update the index in place: re-embed only added/changed books, drop removed
    ones, and rebuild the FAISS index keeping its tuned parameters.

    dry_run=True: report health + the pending diff and EXIT without embedding."""
    import subprocess, gc
    import faiss
    from extract_text import _sig, read_cached_text, is_cached, extract_one

    out = Path(args.output)
    index_path = out / "alexandria.index"
    meta_path = out / "alexandria_metadata.json"
    if not index_path.exists() or not meta_path.exists():
        print("No existing index/metadata found — run a full index first.")
        return 1

    faiss.omp_set_num_threads(1)  # safe in this torch-loaded process

    with open(meta_path) as f:
        metadata = json.load(f)
    emb_path = out / "alexandria_embeddings.npy"
    forced = set()
    if emb_path.exists():
        # Common path: the streamed .npy exists — memmap it (nothing resident) and
        # DON'T load the 4.7 GB FAISS index at all; we rebuild it from the .npy.
        existing = np.load(emb_path, mmap_mode="r")
    else:
        # Fallback only: no .npy on disk, so reconstruct exact vectors from the
        # index, then free the index immediately (it's ~4.7 GB and unused after).
        index = faiss.read_index(str(index_path))
        try:
            index.make_direct_map()
        except Exception:
            pass
        existing = np.ascontiguousarray(index.reconstruct_n(0, index.ntotal), dtype="float32")
        del index
        gc.collect()
    if len(metadata) != existing.shape[0]:
        if len(metadata) > existing.shape[0]:
            # Self-heal: tail metadata rows were written without vectors
            # (an extraction ran without the embedding stage). Drop the tail
            # rows and force their files through re-embedding.
            tail = metadata[existing.shape[0]:]
            forced = {m["file"] for m in tail}
            print(f"⚠ self-heal: {len(tail)} metadata rows have no vectors "
                  f"({len(forced)} file(s)) — re-embedding them.")
            metadata = metadata[:existing.shape[0]]
        else:
            print(f"⚠ vectors ({existing.shape[0]}) exceed metadata "
                  f"({len(metadata)}) — cannot self-heal; do a full re-index.")
            return 1

    # Diff disk against what's indexed
    books = scan_books(args.input, pdf_only=not args.include_epub)
    on_disk = {fp for fp, _ in books}
    titles = {fp: t for fp, t in books}
    indexed = {m["file"] for m in metadata}

    manifest_path = out / "alexandria_manifest.json"
    old_manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    added = on_disk - indexed
    removed = indexed - on_disk
    changed = set()
    for fp in (on_disk & indexed):
        prev = old_manifest.get(fp, {}).get("sig")
        try:
            if prev is not None and prev != _sig(fp):
                changed.add(fp)
        except OSError:
            pass
    reprocess = added | changed | forced
    drop = removed | changed | forced

    # ── --dry-run: health + pending-diff report, no embedding ──────────────
    if dry_run:
        lock = out / ".indexing.lock"
        lock_note = "absent (clear)"
        if lock.exists():
            try:
                holder = int((lock.read_text().strip() or "0"))
            except Exception:
                holder = 0
            lock_note = (f"PRESENT, held by LIVE pid {holder}" if _pid_alive(holder)
                         else f"PRESENT but STALE (pid {holder} gone) — delete: rm '{lock}'")
        print("\n=== incremental dry-run ===")
        print(f"  metadata rows      : {len(metadata):,}")
        print(f"  embedding vectors  : {existing.shape[0]:,}  "
              f"({'.npy on disk' if emb_path.exists() else 'reconstructed from index'})")
        print(f"  alignment          : {'OK' if len(metadata) == existing.shape[0] else 'MISMATCH'}"
              + ("" if len(metadata) == existing.shape[0] else "  ← would block the rebuild"))
        print(f"  manifest present   : {'yes' if manifest_path.exists() else 'NO (changed-file detection disabled until next full build)'}")
        print(f"  indexing lock      : {lock_note}")
        print(f"  books on disk      : {len(on_disk):,}")
        print(f"  → would ADD        : {len(added):,}")
        print(f"  → would re-embed CHANGED: {len(changed):,}")
        print(f"  → would REMOVE     : {len(removed):,}")
        if forced:
            print(f"  → self-heal re-embed: {len(forced):,} file(s) whose metadata had no vectors")
        for label, s in (("add", added), ("changed", changed), ("remove", removed)):
            for fp in list(sorted(s))[:5]:
                print(f"      [{label}] {fp}")
        verdict = ("nothing to do — index is up to date" if not reprocess and not removed
                   else "healthy — a real run would process the above")
        if len(metadata) != existing.shape[0] and not forced:
            verdict = "BLOCKED — vector/metadata mismatch; run a full rebuild"
        print(f"  VERDICT: {verdict}")
        print("=== end dry-run (nothing was embedded) ===\n")
        return 0

    if not reprocess and not removed:
        print("✓ Index already up to date — nothing added, changed or removed.")
        return 0
    print(f"Incremental update: +{len(added)} new, ~{len(changed)} changed, -{len(removed)} removed")

    # Keep vectors/metadata for files we're not dropping
    keep_mask = np.fromiter((m["file"] not in drop for m in metadata), dtype=bool, count=len(metadata))
    keep_emb = existing[keep_mask]
    keep_meta = [m for m, k in zip(metadata, keep_mask) if k]

    # Embed only the reprocess files
    add_emb = np.empty((0, existing.shape[1]), dtype="float32")
    add_meta = []
    if reprocess:
        indexer = RAGIndexer(model_name=args.model)
        # Extract ONLY the new/changed books (inline, one at a time — a handful,
        # so no parallel worker swarm that could exhaust memory). Cache them.
        for fp in sorted(reprocess):
            if not is_cached(cache_dir, fp):
                extract_one((fp, cache_dir, True))  # extracts + writes cache
            text = read_cached_text(cache_dir, fp)
            if text and text.strip():
                indexer.add_document(fp, text, {"file": fp, "title": titles.get(fp, Path(fp).stem)})
        if indexer.chunks:
            add_emb = indexer.generate_embeddings()
            add_meta = indexer.metadata

    # Concatenate kept + newly-embedded vectors. np.vstack already returns a
    # contiguous C-ordered float32 array (both inputs are float32), and fancy
    # indexing (existing[keep_mask]) is contiguous too — so the old extra
    # np.ascontiguousarray() was a needless third full copy of a ~5 GB matrix.
    if add_emb.shape[0]:
        new_emb = np.vstack([keep_emb, add_emb])
        del keep_emb
        gc.collect()
    else:
        new_emb = np.ascontiguousarray(keep_emb, dtype="float32")
    new_meta = keep_meta + add_meta

    np.save(out / "alexandria_embeddings.npy", new_emb)
    total_rows = new_emb.shape[0]
    del new_emb                        # free ~5 GB before the build subprocess
    gc.collect()
    with open(meta_path, "w") as f:
        json.dump(new_meta, f)
    write_manifest(out, new_meta)
    print(f"✓ Updated: {total_rows} chunks total "
          f"({len(keep_meta)} kept, {len(add_meta)} newly embedded)")

    # Rebuild the FAISS index torch-free, preserving the tuned parameters
    params = json.loads((out / "index_params.json").read_text()) if (out / "index_params.json").exists() else {}
    bcmd = [sys.executable, str(Path(__file__).parent / "build_index_cli.py"),
            "--index-dir", str(out),
            "--index-type", params.get("index_type", "ivfflat"),
            "--metric", params.get("metric", "ip"),
            "--from-npy", str(out / "alexandria_embeddings.npy"),
            "--nlist", str(params.get("nlist", 1024)),
            "--nprobe", str(params.get("nprobe", 128))]
    print("Rebuilding index (torch-free, preserving tuned params)...")
    return subprocess.call(bcmd)


_LOCK_PATH = None


def _pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True          # exists but owned by another user → treat as alive


def _acquire_index_lock(index_dir):
    """Create index_dir/.indexing.lock unless a LIVE process already holds it.
    Returns True on success. Guards CLI and GUI alike (the GUI shells out to
    this same script), so only one embed can run per index at a time."""
    global _LOCK_PATH
    import atexit
    lock = Path(index_dir) / ".indexing.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        # O_CREAT|O_EXCL is ATOMIC: exactly one process can create the file. Two
        # embeds spawned milliseconds apart can no longer both "win" — the loser
        # gets FileExistsError. (The old exists()-then-write() raced and let both
        # through; that is what put two embeds on a 48 GB Mac.) We deliberately do
        # NOT auto-reclaim stale locks — that reintroduces a delete/create race.
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        _LOCK_PATH = lock
        atexit.register(_release_index_lock)
        return True
    except FileExistsError:
        try:
            holder = int((lock.read_text().strip() or "0"))
        except Exception:
            holder = 0
        if _pid_alive(holder):
            print(f"\n⚠ Another indexing run is already active (PID {holder}).")
            print("  Refusing to start a second — two concurrent embeds exhaust RAM.")
        else:
            print(f"\n⚠ A stale lock from a hard-killed run is present (PID {holder}, gone).")
            print(f"  Delete it, then retry:\n    rm '{lock}'")
        return False


def _release_index_lock():
    """Remove the lock, but only if it is still OURS (never delete a live
    successor's lock)."""
    global _LOCK_PATH
    try:
        if _LOCK_PATH and _LOCK_PATH.exists() and \
           _LOCK_PATH.read_text().strip() == str(os.getpid()):
            _LOCK_PATH.unlink()
    except Exception:
        pass
    _LOCK_PATH = None


def main():
    parser = argparse.ArgumentParser(description="Build FAISS index from book collection")
    parser.add_argument("--input", required=True, help="Directory containing books")
    parser.add_argument("--output", default=".", help="Output directory for index")
    parser.add_argument("--model", default=MODEL_NAME, help="SentenceTransformer model name")
    parser.add_argument("--include-epub", action="store_true", default=False,
                        help="Include EPUB files in addition to PDFs (default: PDFs only)")
    parser.add_argument("--detect-duplicates", action="store_true", default=False,
                        help="Enable duplicate detection during indexing (generates detailed report)")
    parser.add_argument("--similarity-threshold", type=float, default=DUPLICATE_SIMILARITY_THRESHOLD,
                        help=f"Similarity threshold for duplicate detection (default: {DUPLICATE_SIMILARITY_THRESHOLD})")
    parser.add_argument("--embeddings-only", action="store_true", default=False,
                        help="STAGE 1: extract + embed + save .npy and metadata, then EXIT "
                             "(no FAISS index built). Build the index afterward with "
                             "build_index_cli.py in a separate torch-free process.")
    parser.add_argument("--scan-only", action="store_true", default=False,
                        help="Just check every PDF for corruption (fast, parallel, no "
                             "embedding) and write problem_pdfs.txt, then EXIT. Delegates "
                             "to the torch-free scan_pdfs.py.")
    parser.add_argument("--cache-dir", default=None,
                        help="Where extracted text is cached (default: <output>/text_cache). "
                             "Unchanged books are read from here instead of re-extracted.")
    parser.add_argument("--workers", type=int, default=None,
                        help="Parallel extraction workers (default: CPU count - 1).")
    parser.add_argument("--no-cache", action="store_true", default=False,
                        help="Ignore the text cache and re-extract every book.")
    parser.add_argument("--no-parallel-extract", action="store_true", default=False,
                        help="Skip the parallel pre-extraction pass; extract inline (slow).")
    parser.add_argument("--incremental", action="store_true", default=False,
                        help="Only process books that were ADDED, CHANGED or REMOVED since "
                             "the last index, re-embedding just those, then rebuild the index "
                             "(keeping its tuned nlist/nprobe/metric). Fast for small updates.")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="With --incremental: report health (manifest/.npy present, "
                             "vector↔metadata alignment, stale lock) and exactly what WOULD be "
                             "added/changed/removed, then EXIT without embedding. Diagnostic only.")

    args = parser.parse_args()
    cache_dir = args.cache_dir or str(Path(args.output) / "text_cache")

    if args.scan_only:
        # Delegate to the standalone torch-free scanner so worker processes stay
        # light (no torch/faiss) and fast. No lock — it doesn't embed.
        import subprocess
        script = Path(__file__).parent / "scan_pdfs.py"
        cmd = [sys.executable, str(script), "--input", args.input, "--output", args.output]
        return subprocess.call(cmd)

    # --dry-run diagnostic: read-only, embeds nothing, so it takes NO lock (and
    # reports whether a lock is present as part of its health check).
    if args.incremental and args.dry_run:
        return run_incremental(args, cache_dir, dry_run=True)

    # Cross-process lock: refuse to start if another embed (CLI *or* GUI) is
    # already running against this index dir. Two concurrent embeds OOM a 48 GB
    # Mac (observed: two 25 GB Python processes). Stale locks (from a hard kill)
    # are detected via PID liveness and overwritten.
    if not _acquire_index_lock(args.output):
        return 1

    if args.incremental:
        return run_incremental(args, cache_dir)

    # Scan for books (PDF-only by default)
    books = scan_books(args.input, pdf_only=not args.include_epub)

    if not books:
        if not args.include_epub:
            print("No PDF files found in the specified directory.")
        else:
            print("No PDF or EPUB files found.")
        return

    print(f"Found {len(books)} books")

    # Initialize indexer with duplicate detection if requested
    indexer = RAGIndexer(model_name=args.model, detect_duplicates=args.detect_duplicates)

    # --- Parallel pre-extraction (torch-free subprocess) -------------------
    # Extraction is the slow phase. Run it across all CPU cores in a separate
    # torch-free process that caches each book's text to disk. Unchanged books
    # are reused from cache, so repeat runs skip extraction almost entirely.
    if not args.no_parallel_extract:
        import subprocess
        ex = Path(__file__).parent / "extract_text.py"
        cmd = [sys.executable, str(ex), "--input", args.input,
               "--cache-dir", cache_dir, "--output", args.output]
        if args.include_epub:
            cmd.append("--include-epub")
        if args.no_cache:
            cmd.append("--no-cache")
        if args.workers:
            cmd += ["--workers", str(args.workers)]
        print("\nPre-extracting text (parallel, cached)...")
        rc = subprocess.call(cmd)
        if rc != 0:
            print("⚠ Parallel extraction returned non-zero; falling back to inline.")

    from extract_text import read_cached_text, is_cached

    # Process books: read cached text (fast); fall back to inline extraction
    # only if a book somehow isn't in the cache.
    extractor = BookExtractor()
    total_chunks = 0

    for file_path, title in tqdm(books, desc="Indexing books"):
        if not args.no_cache and is_cached(cache_dir, file_path):
            text = read_cached_text(cache_dir, file_path)
        elif file_path.lower().endswith(".pdf"):
            text = extractor.extract_pdf(file_path)
        elif file_path.lower().endswith(".epub"):
            text = extractor.extract_epub(file_path)
        else:
            continue

        if text:
            chunks = indexer.add_document(
                file_path,
                text,
                {"file": file_path, "title": title}
            )
            total_chunks += chunks

    print(f"\nTotal chunks created: {total_chunks}")
    write_problem_report(args.output)

    if args.embeddings_only:
        # STAGE 1 only: stream embeddings + metadata to disk (memory-bounded),
        # then exit so torch (and its OpenMP runtime) is gone before
        # build_index_cli.py constructs the index.
        indexer.embed_and_save(args.output)
        write_manifest(args.output, indexer.metadata)
        write_embedding_meta(args.output, indexer)
        print("\n✓ Stage 1 complete. Now build the index torch-free, e.g.:")
        print(f"  python3 build_index_cli.py --index-dir {args.output} "
              f"--index-type ivfflat --from-npy {Path(args.output)/'alexandria_embeddings.npy'}")
        return

    # Default full build — MEMORY-BOUNDED, identical to the GUI path:
    #   (1) STREAM embeddings to disk (the matrix is never resident in RAM), then
    #   (2) build the tuned index in a SEPARATE torch-free process.
    # This removes the last way to trigger the old in-process ~24 GB build that
    # OOM'd a 48 GB Mac. There is no longer a code path that holds the whole
    # embedding matrix in RAM.
    import subprocess, gc
    indexer.embed_and_save(args.output)
    write_manifest(args.output, indexer.metadata)
    write_embedding_meta(args.output, indexer)

    # Release the ~4 GB of chunk text now that it's embedded and on disk, BEFORE
    # the torch-free build subprocess loads the .npy and constructs the index.
    # Otherwise the parent holds all chunks resident while the child needs ~10 GB.
    indexer.chunks = []
    if not indexer.duplicate_detector:      # dup-detection still needs the paths
        indexer.document_file_paths = []
    gc.collect()
    _log_rss("after embed, chunks freed")

    # Optional duplicate detection reads the on-disk embeddings via mmap
    # (small slices), never a resident copy.
    if indexer.duplicate_detector:
        print("\nComputing document embeddings for duplicate detection...")
        emb_mm = np.load(Path(args.output) / "alexandria_embeddings.npy", mmap_mode="r")
        indexer._compute_document_signatures(emb_mm)
        dups = indexer.duplicate_detector.suspected_duplicates
        msg = f"⚠ {len(dups)} potential duplicate(s) — see report" if dups else "✓ No duplicates detected"
        print(f"  {msg}")
        indexer.duplicate_detector.save_report(
            str(Path(args.output) / "duplicate_detection_report.json"))

    # Build the tuned index torch-free (IVFFlat, nprobe 128), preserving any
    # saved index_params.json.
    params_path = Path(args.output) / "index_params.json"
    params = json.loads(params_path.read_text()) if params_path.exists() else {}
    bcmd = [sys.executable, str(Path(__file__).parent / "build_index_cli.py"),
            "--index-dir", str(args.output),
            "--index-type", params.get("index_type", "ivfflat"),
            "--metric", params.get("metric", "ip"),
            "--from-npy", str(Path(args.output) / "alexandria_embeddings.npy"),
            "--nlist", str(params.get("nlist", 1024)),
            "--nprobe", str(params.get("nprobe", 128))]
    print("\nBuilding index (torch-free subprocess, tuned params)...")
    rc = subprocess.call(bcmd)
    print("\n✓ Indexing complete! (memory-bounded, IVFFlat, nprobe 128)"
          if rc == 0 else f"\n⚠ Index build subprocess exited {rc}.")


if __name__ == "__main__":
    main()

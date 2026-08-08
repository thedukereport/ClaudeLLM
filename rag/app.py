#!/usr/bin/env python3
"""
Alexandria RAG Web UI
Management dashboard for semantic search across your book collection.
"""

import os
import re
import sys
import json
import subprocess
import threading
from pathlib import Path
from datetime import datetime
import traceback

# This process loads BOTH torch (SentenceTransformer) and faiss, each with its
# own OpenMP runtime. Set these guards BEFORE importing them to reduce the
# chance of a dual-OpenMP segfault. (query_rag also pins faiss to 1 thread.)
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from flask import Flask, render_template, request, jsonify, send_from_directory
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

from index_books import (RAGIndexer, BookExtractor, TextChunker, scan_books,
                         write_problem_report, write_manifest, PROBLEM_PDFS)
from query_rag import RAGQuerier

# Initialize Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['JSON_SORT_KEYS'] = False

# Global state
STATE = {
    'indexing': False,
    'progress': 0,
    'progress_message': '',
    'querier': None,
    'index_dir': '.',
    'books_dir': '.',
}

LOCK = threading.Lock()

def get_config_file():
    """Get config file path - stored in current working directory."""
    config_path = Path.cwd() / 'rag_config.json'
    return config_path

CONFIG_FILE = None  # Will be set by init_app()


def load_config():
    """Load saved configuration from file."""
    global STATE, CONFIG_FILE
    if CONFIG_FILE is None:
        CONFIG_FILE = get_config_file()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
                STATE['index_dir'] = config.get('index_dir', '.')
                STATE['books_dir'] = config.get('books_dir', '.')
                print(f"✓ Loaded config: books_dir={STATE['books_dir']}, index_dir={STATE['index_dir']}")
        except Exception as e:
            print(f"⚠ Could not load config: {e}")


def save_config():
    """Save current configuration to file."""
    global CONFIG_FILE
    try:
        if CONFIG_FILE is None:
            CONFIG_FILE = get_config_file()
        config = {
            'books_dir': STATE['books_dir'],
            'index_dir': STATE['index_dir'],
            'saved_at': datetime.now().isoformat()
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"✓ Saved config to {CONFIG_FILE}")
    except Exception as e:
        print(f"⚠ Could not save config: {e}")


def load_querier(index_dir='.'):
    """Load or reload the querier."""
    try:
        querier = RAGQuerier(index_dir=index_dir)
        STATE['querier'] = querier
        return True
    except Exception as e:
        print(f"Error loading querier: {e}")
        return False


def _free_querier():
    """Drop the in-memory index + metadata (~8 GB) and force a GC. Called before
    a rebuild/update so the loaded copy doesn't compete for RAM with the build
    subprocesses; the querier is reloaded from disk once the build completes."""
    import gc
    if STATE.get('querier') is not None:
        STATE['querier'] = None
        gc.collect()
        print("✓ Released loaded index for the duration of the build (~8 GB freed)")


def get_index_stats():
    """Get statistics about the current index."""
    index_path = Path(STATE['index_dir']) / 'alexandria.index'
    metadata_path = Path(STATE['index_dir']) / 'alexandria_metadata.json'

    if not index_path.exists() or not metadata_path.exists():
        return {
            'indexed': False,
            'chunks': 0,
            'books': 0,
            'index_size_mb': 0,
            'metadata_size_mb': 0,
            'created_at': None,
        }

    with open(metadata_path) as f:
        metadata = json.load(f)

    unique_books = len(set(m['file'] for m in metadata))
    index_size = index_path.stat().st_size / (1024 * 1024)
    metadata_size = metadata_path.stat().st_size / (1024 * 1024)
    created_at = datetime.fromtimestamp(index_path.stat().st_mtime).isoformat()

    return {
        'indexed': True,
        'chunks': len(metadata),
        'books': unique_books,
        'index_size_mb': round(index_size, 2),
        'metadata_size_mb': round(metadata_size, 2),
        'created_at': created_at,
    }


def scan_books_in_dir(directory):
    """Scan for books in directory."""
    books = scan_books(directory)
    return [{'path': path, 'title': title} for path, title in books]


# ============================================================================
# Routes
# ============================================================================

@app.route('/')
def dashboard():
    """Main dashboard."""
    stats = get_index_stats()
    return render_template('index.html', stats=stats)


@app.route('/search')
def search_page():
    """Search page."""
    return render_template('search.html')


@app.route('/indexing')
def indexing_page():
    """Indexing page."""
    return render_template('indexing.html')


@app.route('/management')
def management_page():
    """Index management page."""
    stats = get_index_stats()
    return render_template('management.html', stats=stats)


@app.route('/tuning')
def tuning_page():
    """Index tuning page — pick index type/params and tune search live."""
    return render_template('tuning.html')


@app.route('/guide')
def guide_page():
    """Optimization guide — recommendations rendered in-app."""
    return render_template('guide.html')


@app.route('/books')
def books_page():
    """Books browser page."""
    return render_template('books.html')


# ============================================================================
# API Routes - Search
# ============================================================================

@app.route('/api/search', methods=['POST'])
def api_search():
    """Search the index."""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        k = int(data.get('k', 5))
        # Live tuning knobs (ignored if the index type doesn't support them)
        nprobe = data.get('nprobe')
        ef_search = data.get('ef_search')

        if not query:
            return jsonify({'error': 'Query cannot be empty'}), 400

        if STATE['querier'] is None:
            return jsonify({'error': 'Index not loaded. Build index first.'}), 400

        results = STATE['querier'].search(
            query, k=k,
            nprobe=int(nprobe) if nprobe is not None else None,
            ef_search=int(ef_search) if ef_search is not None else None,
        )
        return jsonify({'success': True, 'query': query, 'results': results,
                        'index_info': STATE['querier'].get_index_info()})

    except Exception as e:
        print(f"Search error: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# API Routes - Indexing
# ============================================================================

@app.route('/api/scan-books', methods=['POST'])
def api_scan_books():
    """Scan for books in a directory."""
    try:
        data = request.get_json()
        directory = data.get('directory', '.')

        books = scan_books_in_dir(directory)
        return jsonify({'success': True, 'books': books, 'count': len(books)})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/start-indexing', methods=['POST'])
def api_start_indexing():
    """Start indexing in background."""
    try:
        data = request.get_json()
        books_dir = data.get('books_dir', '.')
        output_dir = data.get('output_dir', '.')
        model = data.get('model', 'all-MiniLM-L6-v2')

        # Atomic check-and-claim: without holding LOCK across BOTH the test and
        # the set, two near-simultaneous clicks can each pass the test before
        # either marks indexing started — spawning two full embeds at once
        # (observed: two 25 GB Python processes → OOM on a 48 GB Mac).
        with LOCK:
            if STATE['indexing']:
                return jsonify({'error': 'Indexing already in progress'}), 400
            STATE['indexing'] = True   # claim the slot before releasing the lock

        # Start indexing in background thread
        thread = threading.Thread(
            target=run_indexing,
            args=(books_dir, output_dir, model),
            daemon=True
        )
        thread.start()

        return jsonify({'success': True, 'message': 'Indexing started'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


def run_indexing(books_dir, output_dir, model):
    """Run indexing in background."""
    with LOCK:
        STATE['indexing'] = True
        STATE['progress'] = 0
        STATE['progress_message'] = 'Initializing...'
        STATE['books_dir'] = books_dir
        STATE['index_dir'] = output_dir

    # Release the currently-loaded index (~8 GB: FAISS index + metadata) while the
    # rebuild subprocesses run — they need the RAM and would otherwise compete with
    # a stale copy this server no longer uses. Reloaded from disk when we finish.
    _free_querier()

    try:
        # Scan books
        STATE['progress_message'] = 'Scanning for books...'
        STATE['progress'] = 5
        books = scan_books(books_dir)

        if not books:
            STATE['progress_message'] = 'No books found'
            STATE['indexing'] = False
            return

        cache_dir = str(Path(output_dir) / 'text_cache')

        # --- Parallel, cached extraction (torch-free subprocess) --------------
        # This is the SAME fast path the CLI uses: extract across all cores and
        # cache each book's text, so re-runs skip extraction. (The old GUI path
        # extracted one book at a time with no cache — that was the 14+ hours.)
        STATE['progress_message'] = f'Found {len(books)} books. Extracting text (parallel, cached)...'
        STATE['progress'] = 8
        ex = Path(__file__).parent / 'extract_text.py'
        child_env = os.environ.copy()
        child_env['OMP_NUM_THREADS'] = '4'
        proc = subprocess.Popen(
            [sys.executable, str(ex), '--input', books_dir,
             '--cache-dir', cache_dir, '--output', output_dir],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            cwd=str(Path(__file__).parent), env=child_env)
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            STATE['progress_message'] = line
            if '...' in line and 'left' in line:
                try:
                    seg = line.split('...', 1)[1]
                    i, tot = seg.split('(')[0].strip().split('/')
                    i = int(i.replace(',', '')); tot = int(tot.replace(',', ''))
                    STATE['progress'] = 8 + int(i / tot * 52)  # 8..60 during extraction
                except Exception:
                    pass
        proc.wait()

        # ── STAGE 1: chunk + embed in an ISOLATED subprocess ───────────────
        # index_books.py --embeddings-only reads the cache we just built, chunks,
        # and embeds with the memory-safe path (preallocated matrix + MPS cache
        # flush + thread caps). Running it as a subprocess means a heavy embed
        # CANNOT take down this web server, memory is isolated, and it always
        # uses the current code — no rag-ui restart needed after an edit.
        STATE['progress_message'] = 'Embedding (isolated subprocess)...'
        STATE['progress'] = 62
        ib = Path(__file__).parent / 'index_books.py'
        emb_cmd = [sys.executable, str(ib), '--input', books_dir,
                   '--output', output_dir, '--cache-dir', cache_dir,
                   '--model', model, '--embeddings-only', '--no-parallel-extract']
        proc = subprocess.Popen(emb_cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                cwd=str(Path(__file__).parent), env=child_env)
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                STATE['progress_message'] = line
                # "embedded X/N chunks" → advance the bar 62..82 so it visibly
                # moves through the long embed (prevents the "looks stuck → click
                # again → two embeds" trap).
                m = re.search(r'embedded ([\d,]+)/([\d,]+) chunks', line)
                if m:
                    done = int(m.group(1).replace(',', ''))
                    tot = int(m.group(2).replace(',', '')) or 1
                    STATE['progress'] = 62 + int(done / tot * 20)
        if proc.wait() != 0:
            STATE['progress_message'] = 'Error: embedding subprocess failed (see terminal)'
            return

        # ── STAGE 2: build the tuned IVFFlat index, TORCH-FREE subprocess ───
        # No torch here → no dual-OpenMP segfault; produces the IVF index the
        # search side expects (nprobe 128), not a Flat one you'd rebuild later.
        STATE['progress_message'] = 'Building IVFFlat index (torch-free)...'
        STATE['progress'] = 84
        params_path = Path(output_dir) / 'index_params.json'
        params = json.loads(params_path.read_text()) if params_path.exists() else {}
        bcli = Path(__file__).parent / 'build_index_cli.py'
        b_cmd = [sys.executable, str(bcli), '--index-dir', output_dir,
                 '--index-type', params.get('index_type', 'ivfflat'),
                 '--metric', params.get('metric', 'ip'),
                 '--from-npy', str(Path(output_dir) / 'alexandria_embeddings.npy'),
                 '--nlist', str(params.get('nlist', 1024)),
                 '--nprobe', str(params.get('nprobe', 128))]
        bproc = subprocess.Popen(b_cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True,
                                 cwd=str(Path(__file__).parent), env=child_env)
        for line in bproc.stdout:
            line = line.rstrip()
            if line:
                STATE['progress_message'] = line
        if bproc.wait() != 0:
            STATE['progress_message'] = 'Error: index build subprocess failed (see terminal)'
            return

        # (the embedding subprocess already wrote problem_pdfs.txt)
        STATE['progress_message'] = 'Finalizing...'
        STATE['progress'] = 96
        STATE['index_dir'] = output_dir
        load_querier(output_dir)

        STATE['progress'] = 100
        STATE['progress_message'] = 'Complete! Built a tuned IVFFlat index (nprobe 128).'

    except Exception as e:
        STATE['progress_message'] = f'Error: {str(e)}'
        print(f"Indexing error: {e}")
        traceback.print_exc()

    finally:
        save_config()
        STATE['indexing'] = False


@app.route('/api/indexing-status', methods=['GET'])
def api_indexing_status():
    """Get current indexing status."""
    return jsonify({
        'indexing': STATE['indexing'],
        'progress': STATE['progress'],
        'message': STATE['progress_message'],
    })


# ============================================================================
# API Routes - Tuning & Rebuild (torch-free subprocess)
# ============================================================================

def _index_params_path():
    return Path(STATE['index_dir']) / 'index_params.json'


@app.route('/api/index-params', methods=['GET'])
def api_index_params():
    """Return current index type, live-tunable knobs, and last build params."""
    info = {}
    if STATE['querier'] is not None:
        try:
            info = STATE['querier'].get_index_info()
        except Exception as e:
            info = {'error': str(e)}
    saved = {}
    if _index_params_path().exists():
        try:
            saved = json.loads(_index_params_path().read_text())
        except Exception:
            saved = {}
    return jsonify({'live': info, 'build': saved})


@app.route('/api/nprobe-sweep', methods=['POST'])
def api_nprobe_sweep():
    """Sweep the tunable param and return recall + latency for a graph."""
    try:
        if STATE['querier'] is None:
            return jsonify({'error': 'Index not loaded. Build index first.'}), 400

        data = request.get_json() or {}
        k = int(data.get('k', 10))

        # Use provided test queries, else sample chunk previews as proxy queries.
        queries = [q for q in (data.get('queries') or []) if q and q.strip()]
        if not queries:
            import random
            previews = [m.get('text_preview', '') for m in STATE['querier'].metadata]
            previews = [p for p in previews if len(p) > 40]
            queries = random.sample(previews, min(25, len(previews))) if previews else []
        if not queries:
            return jsonify({'error': 'No queries available to sweep'}), 400

        result = STATE['querier'].sweep(queries, k=k)
        result['n_queries'] = len(queries)
        result['k'] = k
        return jsonify(result)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def run_rebuild(opts):
    """Rebuild the index in a SEPARATE torch-free process via build_index_cli.py.

    Running the FAISS build out-of-process is what prevents the dual-OpenMP
    segfault: this Flask process has torch loaded, the subprocess does not.
    """
    with LOCK:
        STATE['indexing'] = True
        STATE['progress'] = 5
        STATE['progress_message'] = f"Starting {opts['index_type']} rebuild..."

    # A rebuild reconstructs vectors from the live index in a child process; free
    # our resident copy first so the two don't both hold the index (~4.7 GB each).
    _free_querier()

    try:
        index_dir = STATE['index_dir']
        script = Path(__file__).parent / 'build_index_cli.py'
        cmd = [sys.executable, str(script),
               '--index-dir', index_dir,
               '--index-type', opts['index_type'],
               '--metric', opts.get('metric', 'ip')]

        # Reconstruct exact vectors from the LIVE index (always aligned with
        # metadata after a healthy build). Use the saved .npy only when no
        # index exists yet: a stale .npy silently scrambles the id->metadata
        # mapping (observed 2026-07-22 and 2026-07-24), and build_index_cli.py
        # now also hard-checks alignment as a second line of defense.
        live_index = Path(index_dir) / 'alexandria.index'
        npy = Path(index_dir) / 'alexandria_embeddings.npy'
        if live_index.exists():
            cmd += ['--from-index', str(live_index)]
        elif npy.exists():
            cmd += ['--from-npy', str(npy)]

        # Per-type parameters
        for flag, key in [('--nlist', 'nlist'), ('--nprobe', 'nprobe'),
                          ('--pq-m', 'pq_m'), ('--pq-nbits', 'pq_nbits'),
                          ('--hnsw-m', 'hnsw_m'), ('--hnsw-efc', 'hnsw_efc'),
                          ('--hnsw-efs', 'hnsw_efs')]:
            if opts.get(key) is not None:
                cmd += [flag, str(opts[key])]

        # The builder is torch-free, so it's safe (and desirable) to let it use
        # multiple threads even though THIS process is pinned to 1.
        child_env = os.environ.copy()
        child_env["OMP_NUM_THREADS"] = "4"
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                cwd=str(Path(__file__).parent), env=child_env)
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                STATE['progress_message'] = line
                if 'training' in line.lower() or 'graph' in line.lower():
                    STATE['progress'] = 40
                elif 'built' in line.lower():
                    STATE['progress'] = 70
                elif 'overlap' in line.lower():
                    STATE['progress'] = 85
                elif 'saved' in line.lower():
                    STATE['progress'] = 95
        proc.wait()

        if proc.returncode == 0:
            STATE['progress'] = 98
            STATE['progress_message'] = 'Reloading index...'
            load_querier(index_dir)
            STATE['progress'] = 100
            STATE['progress_message'] = 'Rebuild complete!'
        else:
            STATE['progress_message'] = f'Rebuild failed (exit {proc.returncode})'

    except Exception as e:
        STATE['progress_message'] = f'Error: {e}'
        traceback.print_exc()
    finally:
        STATE['indexing'] = False


@app.route('/api/rebuild-index', methods=['POST'])
def api_rebuild_index():
    """Kick off a torch-free index rebuild with the chosen type + params."""
    try:
        data = request.get_json() or {}
        index_type = data.get('index_type', 'ivfflat')
        if index_type not in ('flat', 'ivfflat', 'ivfpq', 'hnsw'):
            return jsonify({'error': f'Unknown index type: {index_type}'}), 400

        # Atomic check-and-claim under LOCK: a plain check-then-start lets two fast
        # clicks each spawn a build_index_cli process (~10 GB each). Claim the slot
        # here so the second click is rejected. run_rebuild's finally releases it.
        with LOCK:
            if STATE.get('scanning') or STATE['indexing']:
                return jsonify({'error': 'A scan or build is already in progress'}), 400
            STATE['indexing'] = True

        opts = {
            'index_type': index_type,
            'metric': data.get('metric', 'ip'),
            'nlist': data.get('nlist'),
            'nprobe': data.get('nprobe'),
            'pq_m': data.get('pq_m'),
            'pq_nbits': data.get('pq_nbits'),
            'hnsw_m': data.get('hnsw_m'),
            'hnsw_efc': data.get('hnsw_efc'),
            'hnsw_efs': data.get('hnsw_efs'),
        }
        thread = threading.Thread(target=run_rebuild, args=(opts,), daemon=True)
        thread.start()
        return jsonify({'success': True, 'message': f'{index_type} rebuild started'})

    except Exception as e:
        with LOCK:                       # release the slot if we claimed then failed
            STATE['indexing'] = False
        return jsonify({'error': str(e)}), 500


# ============================================================================
# API Routes - Incremental Update
# ============================================================================

def run_update():
    """Run index_books.py --incremental as a subprocess: re-embed only new/
    changed books and rebuild the index, then reload the querier."""
    STATE['indexing'] = True
    STATE['progress'] = 0
    STATE['progress_message'] = 'Starting incremental update...'
    # Incremental re-embeds only new/changed books but still rebuilds the index in
    # a child; free our resident copy for the duration, reload when done.
    _free_querier()
    try:
        ib = Path(__file__).parent / 'index_books.py'
        cmd = [sys.executable, str(ib), '--input', STATE['books_dir'],
               '--output', STATE['index_dir'], '--incremental']
        child_env = os.environ.copy()
        child_env['OMP_NUM_THREADS'] = '4'
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                cwd=str(Path(__file__).parent), env=child_env)
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            STATE['progress_message'] = line
            low = line.lower()
            if 'incremental update' in low or 'up to date' in low:
                STATE['progress'] = 15
            elif 'extracting' in low:
                STATE['progress'] = 30
            elif 'generating embeddings' in low:
                STATE['progress'] = 55
            elif low.startswith('✓ updated'):
                STATE['progress'] = 80
            elif 'building' in low and 'index' in low:
                STATE['progress'] = 88
            elif 'saved' in low:
                STATE['progress'] = 95
        proc.wait()
        if proc.returncode == 0:
            STATE['progress'] = 98
            STATE['progress_message'] = 'Reloading index...'
            load_querier(STATE['index_dir'])
            STATE['progress'] = 100
            STATE['progress_message'] = 'Update complete!'
        else:
            STATE['progress_message'] = f'Update failed (exit {proc.returncode})'
    except Exception as e:
        STATE['progress_message'] = f'Error: {e}'
        traceback.print_exc()
    finally:
        STATE['indexing'] = False


@app.route('/api/update-index', methods=['POST'])
def api_update_index():
    """Start an incremental update (add new / changed / removed books)."""
    try:
        # Atomic check-and-claim so two clicks can't launch two updates.
        with LOCK:
            if STATE.get('scanning') or STATE['indexing']:
                return jsonify({'error': 'A scan, build or update is already running'}), 400
            STATE['indexing'] = True
        thread = threading.Thread(target=run_update, daemon=True)
        thread.start()
        return jsonify({'success': True, 'message': 'Incremental update started'})
    except Exception as e:
        with LOCK:
            STATE['indexing'] = False
        return jsonify({'error': str(e)}), 500


# ============================================================================
# API Routes - PDF Health Check (torch-free scan subprocess)
# ============================================================================

def run_scan(books_dir, out_dir, mode='incremental'):
    """Run scan_pdfs.py as a background subprocess and stream progress into STATE.

    mode: 'incremental' (skip unchanged per manifest, default),
          'verify' (also re-hash unchanged files), 'full' (rescan everything).
    """
    STATE['scanning'] = True
    STATE['scan_progress'] = 0
    STATE['scan_message'] = f'Starting PDF scan ({mode})...'
    try:
        script = Path(__file__).parent / 'scan_pdfs.py'
        cmd = [sys.executable, str(script), '--input', books_dir, '--output', out_dir]
        if mode == 'verify':
            cmd.append('--verify')
        elif mode == 'full':
            cmd.append('--full')
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                cwd=str(Path(__file__).parent))
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            if '...' in line and 'left' in line:
                try:
                    seg = line.split('...', 1)[1]
                    i, tot = seg.split('(')[0].strip().split('/')
                    i = int(i.replace(',', '').strip())
                    tot = int(tot.replace(',', '').strip())
                    STATE['scan_progress'] = min(98, int(i / tot * 100))
                except Exception:
                    pass
                STATE['scan_message'] = line.strip()
            elif line.startswith('Scanning') or line.startswith('Done') or line.lstrip().startswith('⚠'):
                STATE['scan_message'] = line.strip()
        proc.wait()
        STATE['scan_progress'] = 100
        STATE['scan_message'] = 'Scan complete'
    except Exception as e:
        STATE['scan_message'] = f'Error: {e}'
        traceback.print_exc()
    finally:
        STATE['scanning'] = False


@app.route('/api/scan-pdfs', methods=['POST'])
def api_scan_pdfs():
    """Start a background PDF integrity scan."""
    try:
        data = request.get_json() or {}
        books_dir = data.get('books_dir') or STATE['books_dir']
        mode = data.get('mode', 'incremental')
        if mode not in ('incremental', 'verify', 'full'):
            return jsonify({'error': f'Unknown scan mode: {mode}'}), 400
        # Atomic check-and-claim so a scan can't overlap a build/update or a
        # second scan (run_scan's finally clears the flag).
        with LOCK:
            if STATE.get('scanning') or STATE['indexing']:
                return jsonify({'error': 'A scan or build is already running'}), 400
            STATE['scanning'] = True
        out_dir = STATE['index_dir']
        thread = threading.Thread(target=run_scan, args=(books_dir, out_dir, mode), daemon=True)
        thread.start()
        return jsonify({'success': True, 'message': f'PDF scan started ({mode})', 'books_dir': books_dir})
    except Exception as e:
        with LOCK:
            STATE['scanning'] = False
        return jsonify({'error': str(e)}), 500


@app.route('/api/scan-status', methods=['GET'])
def api_scan_status():
    """Progress of the running PDF scan."""
    return jsonify({
        'scanning': STATE.get('scanning', False),
        'progress': STATE.get('scan_progress', 0),
        'message': STATE.get('scan_message', ''),
    })


@app.route('/api/scan-results', methods=['GET'])
def api_scan_results():
    """Parsed problem_pdfs.txt from the last scan."""
    import re
    report = Path(STATE['index_dir']) / 'problem_pdfs.txt'
    if not report.exists():
        return jsonify({'exists': False})
    count = total = None
    problems = []
    for ln in report.read_text().splitlines():
        if ln.startswith('#') and 'had issues' in ln:
            m = re.search(r'#\s*(\d+)\s+of\s+([\d,]+)', ln)
            if m:
                count = int(m.group(1)); total = int(m.group(2).replace(',', ''))
        elif ln and not ln.startswith('#'):
            if ln.startswith('    '):
                if problems:
                    problems[-1]['issue'] = ln.strip()
            else:
                problems.append({'file': ln.strip(), 'issue': ''})
    return jsonify({'exists': True,
                    'count': count if count is not None else len(problems),
                    'total': total, 'problems': problems,
                    'modified': datetime.fromtimestamp(report.stat().st_mtime).isoformat()})


# ============================================================================
# API Routes - Management
# ============================================================================

@app.route('/api/index-stats', methods=['GET'])
def api_index_stats():
    """Get index statistics."""
    stats = get_index_stats()
    return jsonify(stats)


@app.route('/api/refresh-queues', methods=['POST'])
def api_refresh_queues():
    """Rebuild the work queues from what is actually on disk.

    The queues were hand-maintained, so any book added after they were written
    stayed invisible to every pass: 65 books sat with no text layer while the
    OCR queue reported empty and success. This asks the library instead."""
    try:
        data = request.get_json(silent=True) or {}
        do_apply = bool(data.get('apply'))
        books_dir = Path(STATE['books_dir'])
        script = books_dir / '_Optimization' / 'refresh_queues.py'
        if not script.exists():
            return jsonify({'error': f'refresh_queues.py not found at {script}'}), 404
        cmd = [sys.executable, str(script)]
        if do_apply:
            # OCR queue only. Writing index_exclude.txt from a button would let
            # one click remove 65 books from search with nothing reviewed.
            cmd.append('--apply-ocr')
        env = os.environ.copy()
        env['ALEX_ROOT'] = str(books_dir)
        env['ALEX_OUT'] = str(books_dir / '_Optimization')
        # Prefer the native arm64 poppler; /usr/local is the x86_64 prefix and
        # would run every pdfinfo/pdftotext under Rosetta.
        env['PATH'] = '/opt/homebrew/bin:' + env.get('PATH', '')
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=2400, env=env)
        return jsonify({'success': r.returncode == 0,
                        'applied': do_apply,
                        'output': (r.stdout + r.stderr)[-12000:]})
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'refresh_queues.py exceeded 40 minutes'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/clear-index', methods=['POST'])
def api_clear_index():
    """Delete the current index."""
    try:
        index_path = Path(STATE['index_dir']) / 'alexandria.index'
        metadata_path = Path(STATE['index_dir']) / 'alexandria_metadata.json'

        if index_path.exists():
            index_path.unlink()
        if metadata_path.exists():
            metadata_path.unlink()

        STATE['querier'] = None

        return jsonify({'success': True, 'message': 'Index cleared'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config', methods=['POST'])
def api_set_config():
    """Set configuration (index/books directories)."""
    try:
        data = request.get_json()
        index_dir = data.get('index_dir', '.')
        books_dir = data.get('books_dir', '.')

        STATE['index_dir'] = index_dir
        STATE['books_dir'] = books_dir

        # Save configuration
        save_config()

        # Try to load querier
        load_querier(index_dir)

        return jsonify({'success': True, 'message': 'Configuration updated and saved'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config', methods=['GET'])
def api_get_config():
    """Get current configuration."""
    return jsonify({
        'index_dir': STATE['index_dir'],
        'books_dir': STATE['books_dir'],
    })


# ============================================================================
# API Routes - Books
# ============================================================================

@app.route('/api/books', methods=['GET'])
def api_get_books():
    """Get list of indexed books."""
    try:
        if STATE['querier'] is None:
            return jsonify({'books': []})

        metadata = STATE['querier'].metadata
        books_dict = {}

        for entry in metadata:
            file_path = entry['file']
            title = entry['title']
            if file_path not in books_dict:
                books_dict[file_path] = {
                    'file': file_path,
                    'title': title,
                    'chunks': 0,
                }
            books_dict[file_path]['chunks'] += 1

        books = list(books_dict.values())
        books.sort(key=lambda x: x['title'].lower())

        return jsonify({'books': books, 'total': len(books)})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Static Files
# ============================================================================

@app.route('/static/<path:path>')
def send_static(path):
    """Serve static files."""
    return send_from_directory('static', path)


# ============================================================================
# Error Handlers
# ============================================================================

@app.route('/favicon.ico')
def favicon():
    """Browsers auto-request this; return empty so it doesn't 404-spam the log."""
    return ('', 204)


@app.errorhandler(404)
def not_found(e):
    """404 handler."""
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    """500 handler."""
    return render_template('500.html'), 500


# ============================================================================
# Initialization
# ============================================================================

def init_app():
    """Initialize app on startup."""
    global CONFIG_FILE
    print("Alexandria RAG - Web Management UI")
    print("=" * 50)

    # Initialize config file path
    CONFIG_FILE = get_config_file()
    print(f"Config file: {CONFIG_FILE}")
    print(f"Working directory: {Path.cwd()}")

    # Load saved configuration
    load_config()

    # Try to load existing index
    if load_querier(STATE['index_dir']):
        print("✓ Existing index loaded")
    else:
        print("⚠ No index found. Build one from the Indexing page.")

    print(f"\nBooks directory: {STATE['books_dir']}")
    print(f"Index directory: {STATE['index_dir']}")
    print("\nWeb UI starting at http://127.0.0.1:5050")
    print("=" * 50)


if __name__ == '__main__':
    init_app()
    # use_reloader=False prevents Flask from restarting when you click tabs
    # Bind to 127.0.0.1 directly — on this machine the 'localhost' hostname
    # doesn't resolve, so use the loopback IP.
    # Port 5050, NOT 5000: macOS AirPlay Receiver (ControlCenter) listens on
    # 5000 and launchd respawns it when killed. Moved 2026-07-02.
    app.run(debug=True, host='127.0.0.1', port=5050, use_reloader=False)

# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

"""Embedding-based semantic search via local Ollama (BGE-M3).

Flow:
- build_index: each leaf rate (name + desc) is embedded through Ollama's
  /api/embed endpoint and stored as a row of an L2-normalised float32 matrix
- search: the query is embedded the same way; cosine similarity is a single
  numpy matrix-vector product (instant, fully local)
- search_hybrid: Reciprocal Rank Fusion of BM25 (semantic_search) and
  embedding rankings — exact-term precision plus synonym recall

Caching: one .npz per price list in the Blender config dir, with mtime
invalidation for file-based sources (same scheme as semantic_search).
"""

import hashlib
import json
import os
import threading
import time
import urllib.request

try:
    import numpy as _np  # bundled with Blender's Python
except ImportError:
    _np = None

OLLAMA_URL  = "http://localhost:11434"
EMBED_MODEL = "bge-m3"
# Per-item overhead in Ollama dominates over text length. Measured on an
# RTX 2000 Ada: 68 ms/item at batch 64, 31 ms/item at batch 128. Batch 256
# is no faster in practice because it crashes Ollama's runner every other
# request (connection-refused on its internal tokenize service).
BATCH_SIZE  = 128
RRF_K       = 60   # standard reciprocal-rank-fusion constant

# ── Active index ──────────────────────────────────────────────────────────────

_matrix = None        # (n_docs, dim) float32, rows L2-normalised
_item_indices = []    # row → original rate list position
_ready = False
_query_cache = {}     # query string → normalised query vector


# ── Availability ──────────────────────────────────────────────────────────────

def is_available():
    """True if numpy is importable and Ollama serves the embedding model."""
    if _np is None:
        return False
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as resp:
            tags = json.loads(resp.read())
        return any(m.get("name", "").startswith(EMBED_MODEL)
                   for m in tags.get("models", []))
    except Exception:
        return False


def is_ready():
    return _ready


# ── Ollama embedding call ─────────────────────────────────────────────────────

def _embed(texts, retries=2):
    payload = {"model": EMBED_MODEL, "input": texts}
    data = json.dumps(payload).encode()
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                f"{OLLAMA_URL}/api/embed",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                body = json.loads(resp.read())
            return body["embeddings"]
        except Exception:
            # Ollama's runner occasionally dies and gets respawned; give it
            # a moment and retry before giving up.
            if attempt == retries:
                raise
            time.sleep(1.5)


# ── Disk cache ────────────────────────────────────────────────────────────────

def _cache_file(key):
    try:
        import bpy
        d = os.path.join(bpy.utils.user_resource('CONFIG'), 'bonsai5d_embed_cache')
        os.makedirs(d, exist_ok=True)
    except Exception:
        return None
    h = hashlib.md5(key.encode('utf-8', 'replace')).hexdigest()
    return os.path.join(d, f"{h}.npz")


def _save_cache(key, matrix, indices):
    path = _cache_file(key)
    if not path:
        return
    mtime = -1.0
    if not key.startswith('ifc:'):
        try:
            mtime = os.path.getmtime(key)
        except Exception:
            mtime = -1.0
    try:
        _np.savez_compressed(
            path,
            matrix=matrix,
            indices=_np.asarray(indices, dtype=_np.int64),
            mtime=_np.asarray([mtime]),
            model=_np.asarray([EMBED_MODEL]),
        )
    except Exception:
        pass


def try_activate_cached(key):
    global _matrix, _item_indices, _ready
    _ready = False
    _matrix = None
    _item_indices = []
    _query_cache.clear()
    if _np is None or not key:
        return False
    path = _cache_file(key)
    if not path or not os.path.exists(path):
        return False
    try:
        data = _np.load(path, allow_pickle=False)
        if str(data['model'][0]) != EMBED_MODEL:
            return False
        mtime = float(data['mtime'][0])
        if not key.startswith('ifc:') and mtime >= 0.0:
            if os.path.getmtime(key) != mtime:
                return False
        _matrix = data['matrix']
        _item_indices = data['indices'].tolist()
        _ready = True
        return True
    except Exception:
        return False


# ── Index build ───────────────────────────────────────────────────────────────

def _collect_texts(rates):
    texts, indices = [], []
    for i, rate in enumerate(rates):
        if rate.get("is_parent", False):
            continue
        name = rate.get("name", "") or ""
        desc = rate.get("desc", "") or ""
        text = (name + "\n" + desc).strip() or (rate.get("id", "") or " ")
        texts.append(text)
        indices.append(i)
    return texts, indices


def _finalize(vectors, indices, key):
    global _matrix, _item_indices, _ready
    matrix = _np.asarray(vectors, dtype=_np.float32)
    norms = _np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    matrix /= norms

    _matrix = matrix
    _item_indices = indices
    _query_cache.clear()
    _ready = True
    if key:
        _save_cache(key, matrix, indices)


def build_index(rates, key=None, progress=None):
    """Embed all leaf rates synchronously. progress(done, total) per batch."""
    if _np is None:
        return False
    texts, indices = _collect_texts(rates)
    if not texts:
        return False

    vectors = []
    total = len(texts)
    for start in range(0, total, BATCH_SIZE):
        vectors.extend(_embed(texts[start:start + BATCH_SIZE]))
        if progress:
            progress(min(start + BATCH_SIZE, total), total)

    _finalize(vectors, indices, key)
    return True


# ── Background index build ────────────────────────────────────────────────────

class IndexJob:
    """Progress/state handle for a background index build."""

    def __init__(self, total):
        self.total = total
        self.done = 0
        self.started = time.monotonic()
        self.finished = False
        self.cancelled = False
        self.error = None

    def cancel(self):
        self.cancelled = True

    @property
    def elapsed(self):
        return time.monotonic() - self.started

    @property
    def eta(self):
        """Estimated remaining seconds, or None before the first batch."""
        if self.done <= 0:
            return None
        return self.elapsed / self.done * (self.total - self.done)


_active_job = None


def active_job():
    """The currently running IndexJob, or None."""
    return _active_job


def build_index_async(rates, key=None):
    """Start a background-thread index build. Returns the IndexJob, or None."""
    global _active_job
    if _np is None or _active_job is not None:
        return None
    texts, indices = _collect_texts(rates)
    if not texts:
        return None

    job = IndexJob(len(texts))
    _active_job = job

    def _worker():
        global _active_job
        try:
            vectors = []
            for start in range(0, job.total, BATCH_SIZE):
                if job.cancelled:
                    return
                vectors.extend(_embed(texts[start:start + BATCH_SIZE]))
                job.done = min(start + BATCH_SIZE, job.total)
            _finalize(vectors, indices, key)
        except Exception as e:
            job.error = str(e)
        finally:
            job.finished = True
            _active_job = None

    threading.Thread(target=_worker, daemon=True).start()
    return job


# ── Search ────────────────────────────────────────────────────────────────────

def search(query, n=10):
    """Pure embedding search. Returns [(rate_index, cosine_similarity), ...]."""
    if not _ready or _matrix is None:
        return []
    qv = _query_cache.get(query)
    if qv is None:
        try:
            emb = _embed([query])[0]
        except Exception:
            return []
        qv = _np.asarray(emb, dtype=_np.float32)
        norm = _np.linalg.norm(qv)
        if norm > 0.0:
            qv /= norm
        if len(_query_cache) > 256:
            _query_cache.clear()
        _query_cache[query] = qv

    sims = _matrix @ qv
    n = min(n, len(sims))
    if n <= 0:
        return []
    top = _np.argpartition(-sims, n - 1)[:n]
    top = top[_np.argsort(-sims[top])]
    return [(int(_item_indices[i]), float(sims[i])) for i in top]


def search_hybrid(query, n=10):
    """Reciprocal Rank Fusion of BM25 and embedding rankings.

    Falls back to whichever index is available. Scores are normalised to
    [0, 1] relative to the best hit (display-friendly).
    """
    from . import semantic_search as _ss

    pool = max(30, n * 3)
    bm25 = _ss.search(query, n=pool) if _ss.is_ready() else []
    emb = search(query, n=pool) if _ready else []

    if not bm25 and not emb:
        return []
    if not emb:
        ranked = bm25
    elif not bm25:
        ranked = emb
    else:
        fused = {}
        for results in (bm25, emb):
            for rank, (idx, _) in enumerate(results):
                fused[idx] = fused.get(idx, 0.0) + 1.0 / (RRF_K + rank + 1)
        ranked = sorted(fused.items(), key=lambda x: -x[1])

    top = ranked[:n]
    if not top:
        return []
    best = top[0][1] or 1.0
    return [(idx, score / best) for idx, score in top]

# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

"""TF-IDF semantic search — pure Python, no external dependencies.

Features:
- Italian suffix stemmer (fondazioni → fonda, scavi → scav)
- Italian stop words: removed from unigrams, skipped when forming bigrams
- Skip-gram bigrams: connect adjacent content words across stop words
- BM25 scoring (k1=1.5, b=0.75): length-normalised, better ranking than cosine
- Field weighting: name indexed 3×, id 2×, desc 1×
- Per-prezzario disk cache with mtime invalidation
"""

import math
import os
import pickle
import re
from collections import Counter, defaultdict

# ── Active index ──────────────────────────────────────────────────────────────

_inverted  = {}   # {token: [(doc_idx, raw_tf), ...]}
_doc_lens  = []   # token count per document (for BM25 length norm)
_avgdl     = 0.0  # average document length
_idf_map   = {}   # {token: BM25-IDF value}
_item_indices = []
_ready = False

# ── Disk cache ────────────────────────────────────────────────────────────────

_cache = {}
_disk_cache_loaded = False


def _cache_path():
    try:
        import bpy
        return os.path.join(bpy.utils.user_resource('CONFIG'), 'bonsai5d_semantic_cache.pkl')
    except Exception:
        return None


def _file_mtime(path):
    try:
        return os.path.getmtime(path)
    except Exception:
        return None


def _load_disk_cache():
    global _disk_cache_loaded
    _disk_cache_loaded = True
    path = _cache_path()
    if not path or not os.path.exists(path):
        return
    try:
        with open(path, 'rb') as f:
            saved = pickle.load(f)
        for key, entry in saved.items():
            mtime_saved = entry.get('mtime')
            if mtime_saved is not None and _file_mtime(key) != mtime_saved:
                continue
            _cache[key] = entry['data']
    except Exception:
        pass


def _save_disk_cache():
    path = _cache_path()
    if not path:
        return
    try:
        to_save = {}
        for key, data in _cache.items():
            mtime = _file_mtime(key) if not key.startswith('ifc:') else None
            to_save[key] = {'data': data, 'mtime': mtime}
        with open(path, 'wb') as f:
            pickle.dump(to_save, f)
    except Exception:
        pass


# ── Italian stemmer ───────────────────────────────────────────────────────────

# Each entry: (suffix, min_stem_length)
# 'azione' needs min=5 so "fondazione" (→4 chars) falls through to 'zione' → "fonda",
# while "pavimentazione" (→8 chars) correctly gives "paviment".
_SUFFIXES = (
    ('izzazioni', 4),
    ('izzazione', 4),
    ('zioni',     4),
    ('azioni',    4),
    ('azione',    5),
    ('zione',     4),
    ('imenti',    4),
    ('imento',    4),
    ('amenti',    4),
    ('amento',    4),
    ('iture',     4),
    ('itura',     4),
    ('ature',     4),
    ('atura',     4),
    ('ibili',     4),
    ('ibile',     4),
    ('abili',     4),
    ('abile',     4),
    ('mente',     4),
    ('enti',      6),  # min=6: shorter words fall through to vowel-strip (pavimenti→paviment)
    ('ente',      6),
    ('anti',      4),
    ('ante',      4),
    ('ali',       4),
    ('ale',       4),
    ('oni',       4),
    ('one',       4),
    ('osi',       4),
    ('oso',       4),
    ('osa',       4),
    ('ose',       4),
    ('are',       4),
    ('ere',       4),
    ('ire',       4),
    ('ati',       4),
    ('ato',       4),
    ('ate',       4),
    ('ata',       4),
    ('uti',       4),
    ('uto',       4),
    ('ute',       4),
    ('uta',       4),
    ('iti',       4),
    ('ito',       4),
    ('ite',       4),
    ('ita',       4),
)

_MIN_STEM = 4


def _stem(word):
    n = len(word)
    if n <= 3:
        return word
    for sfx, min_s in _SUFFIXES:
        candidate = n - len(sfx)
        if word.endswith(sfx) and candidate >= min_s:
            return word[:candidate]
    if n >= 5 and word[-1] in 'aeiou':
        stem = word[:-1]
        if len(stem) >= _MIN_STEM:
            return stem
    return word


# ── Stop words ────────────────────────────────────────────────────────────────

# Italian function words + prezzario-specific filler terms
_STOPS = {
    'di', 'in', 'con', 'per', 'su', 'a', 'e', 'il', 'la', 'i', 'gli',
    'le', 'un', 'una', 'del', 'della', 'dei', 'delle', 'dello', 'al',
    'alla', 'ai', 'agli', 'alle', 'da', 'dal', 'dalla', 'dai', 'dagli',
    'nel', 'nella', 'nei', 'negli', 'nelle', 'col', 'coi', 'tra', 'fra',
    'o', 'ed', 'ad', 'od', 'che', 'non', 'si', 'ci', 'lo', 'ne', 'se',
    'come', 'anche', 'solo', 'fino', 'oltre', 'circa',
    # Common prezzario filler words (appear in almost every description)
    'compreso', 'compresi', 'compresi', 'compresa', 'comprese',
    'escluso', 'esclusi', 'esclusa', 'escluse',
    'incluso', 'inclusi', 'inclusa', 'incluse',
    'mediante', 'oppure', 'ovvero', 'ossia',
    'nonche', 'nonché', 'qualsiasi', 'qualunque',
}


# ── Tokenization ──────────────────────────────────────────────────────────────

def _tokens(text):
    """Stemmed content unigrams + skip-gram bigrams (bridging stop words)."""
    raw = re.findall(r'\w+', text.lower())
    stemmed = [(_stem(w), w in _STOPS) for w in raw]

    unigrams = [s for s, is_stop in stemmed if not is_stop]

    # Bigrams between adjacent content words, skipping stop words
    content = [s for s, is_stop in stemmed if not is_stop]
    bigrams = [f"{content[i]}_{content[i+1]}" for i in range(len(content) - 1)]

    return unigrams + bigrams


# ── Index computation ─────────────────────────────────────────────────────────

# BM25 parameters
_K1 = 1.5
_B  = 0.75


def _compute_index(rates):
    """Returns (inverted, doc_lens, avgdl, idf_map, item_indices) or None."""
    docs = []      # token lists
    indices = []   # original rate list positions

    for i, rate in enumerate(rates):
        if not rate.get("is_parent", False):
            # Field weighting: name 3×, id 2×, desc 1×
            name = rate.get("name", "") or ""
            rid  = rate.get("id",   "") or ""
            desc = rate.get("desc", "") or ""
            text = " ".join([name, name, name, rid, rid, desc])
            docs.append(text)
            indices.append(i)

    if not docs:
        return None

    n = len(docs)
    tokenized = [_tokens(doc) for doc in docs]

    doc_lens = [len(toks) for toks in tokenized]
    avgdl = sum(doc_lens) / n if n else 1.0

    # Document frequency
    df = defaultdict(int)
    for toks in tokenized:
        for tok in set(toks):
            df[tok] += 1

    # BM25 IDF: log((N - df + 0.5) / (df + 0.5) + 1), always positive
    idf_map = {
        tok: math.log((n - count + 0.5) / (count + 0.5) + 1.0)
        for tok, count in df.items()
    }

    # Inverted index stores raw TF per document
    inverted = defaultdict(list)
    for doc_idx, toks in enumerate(tokenized):
        for tok, tf in Counter(toks).items():
            inverted[tok].append((doc_idx, tf))

    return dict(inverted), doc_lens, avgdl, idf_map, indices


def _activate(data):
    global _inverted, _doc_lens, _avgdl, _idf_map, _item_indices, _ready
    _inverted, _doc_lens, _avgdl, _idf_map, _item_indices = data
    _ready = True


# ── Public API ────────────────────────────────────────────────────────────────

def try_activate_cached(key):
    global _ready
    if not _disk_cache_loaded:
        _load_disk_cache()
    _ready = False
    if key and key in _cache:
        _activate(_cache[key])
        return True
    return False


def build_index(rates, key=None):
    data = _compute_index(rates)
    if data is None:
        return False
    if key:
        _cache[key] = data
        _save_disk_cache()
    _activate(data)
    return True


def is_ready():
    return _ready


# ── Search (BM25) ─────────────────────────────────────────────────────────────

def search(query, n=10):
    if not _inverted:
        return []

    toks = _tokens(query)
    if not toks:
        return []

    scores = defaultdict(float)
    for tok in set(toks):
        idf = _idf_map.get(tok, 0.0)
        if idf == 0.0:
            continue
        for doc_idx, tf in _inverted.get(tok, []):
            dl   = _doc_lens[doc_idx]
            norm = 1.0 - _B + _B * dl / _avgdl
            scores[doc_idx] += idf * (tf * (_K1 + 1.0)) / (tf + _K1 * norm)

    results = [(int(_item_indices[doc_idx]), score)
               for doc_idx, score in scores.items()]
    results.sort(key=lambda x: -x[1])
    return results[:n]


def is_available():
    return True

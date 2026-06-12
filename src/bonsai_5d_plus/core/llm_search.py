# Bonsai - OpenBIM 5D Blender Add-on based on Bonsai
# Copyright (C) 2026 Carlo Pavan <carlopav@gmail.com>
#
# This file is part of Bonsai5D+.  GNU GPL v3 or later.

"""LLM-assisted rate search via local Ollama instance.

Flow:
  1. TF-IDF (semantic_search) retrieves top-N candidates
  2. Candidates + user description sent to Ollama
  3. Ollama returns ranked top-3 with reasoning
  4. User confirms choice → saved to preference store
"""

import json
import os
import urllib.request
import urllib.error

OLLAMA_URL   = "http://localhost:11434"
DEFAULT_MODEL = "mistral"
CANDIDATES_N  = 20   # how many TF-IDF candidates to send to Ollama
RESULTS_N     = 3    # how many results to return


# ── Availability ──────────────────────────────────────────────────────────────

def is_available():
    """True if Ollama is reachable."""
    try:
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2)
        return True
    except Exception:
        return False


# ── Preference store ──────────────────────────────────────────────────────────

def _pref_path():
    try:
        import bpy
        return os.path.join(bpy.utils.user_resource('CONFIG'), 'bonsai5d_llm_prefs.json')
    except Exception:
        return None


def load_prefs():
    path = _pref_path()
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def save_pref(description, chosen_id, chosen_name):
    """Record a confirmed user choice for future few-shot prompting."""
    prefs = load_prefs()
    prefs.append({"desc": description, "id": chosen_id, "name": chosen_name})
    prefs = prefs[-200:]  # keep last 200
    path = _pref_path()
    if not path:
        return
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _similar_prefs(description, n=3):
    """Return n past choices whose description shares words with the current one."""
    words = set(description.lower().split())
    scored = []
    for p in load_prefs():
        overlap = len(words & set(p['desc'].lower().split()))
        if overlap > 0:
            scored.append((overlap, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:n]]


# ── Suggestion ────────────────────────────────────────────────────────────────

def suggest(description, candidates, model=DEFAULT_MODEL):
    """
    Ask Ollama to rank candidates for the given description.

    candidates: list of dicts {id, name, desc}
    Returns: list of {rank, id, name, motivo} or raises on error
    """
    # Build candidate list (id + name + first 120 chars of desc)
    lines = []
    id_to_name = {}
    for i, c in enumerate(candidates[:CANDIDATES_N]):
        short_desc = (c.get('desc') or '')[:120].replace('\n', ' ')
        line = f"{i+1}. {c['id']} – {c['name']}"
        if short_desc:
            line += f" | {short_desc}"
        lines.append(line)
        id_to_name[c['id']] = c['name']

    # Include similar past choices as few-shot examples
    examples_block = ""
    past = _similar_prefs(description)
    if past:
        ex_lines = "\n".join(f"  - '{p['desc']}' → {p['id']} ({p['name']})" for p in past)
        examples_block = f"\nScelte precedenti simili (usa come riferimento):\n{ex_lines}\n"

    system_msg = (
        "Sei un esperto di prezzari edili italiani. "
        f"Rispondi SOLO con JSON valido: "
        '{"risultati": [{"rank": 1, "id": "...", "motivo": "..."}, ...]}'
    )

    user_msg = (
        f"Voce di computo: '{description}'\n"
        f"{examples_block}\n"
        f"Voci disponibili dal prezzario:\n" + "\n".join(lines) +
        f"\n\nSeleziona le {RESULTS_N} voci più pertinenti. "
        "Includi solo voci chiaramente attinenti. "
        "Per ogni voce: rank (intero), id (esatto), motivo (una frase breve in italiano)."
    )

    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
        ],
    }

    data = json.dumps(payload).encode()
    req  = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read())

    content = body["message"]["content"]
    parsed  = json.loads(content)
    results = parsed.get("risultati", [])

    # Enrich with name field for display
    for r in results:
        r['name'] = id_to_name.get(r.get('id', ''), '')

    return results

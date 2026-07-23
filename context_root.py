"""Resolve host-cabinet context slots through one configurable root.

This is the seam the Context Layer Contract (see ``CONTEXT.md``) is built on. A
product reads the host cabinet by *slot* (a role: BRAND, AUDIENCE, …), never by a
hardcoded ``../../brand/arbi-character.md`` path. The host declares which of its
docs fills each slot (via a per-slot env override) and where its cabinet root is
(``STUDIO_CONTEXT_ROOT``, legacy: ``CABINET_CONTEXT_ROOT`` still honored). Swap
the cabinet, set the root, the runtime is unchanged.

Default = this cabinet. When neither ``STUDIO_CONTEXT_ROOT`` nor the legacy
``CABINET_CONTEXT_ROOT`` is set, the root resolves to two levels above the tool
dir — the behavior the code had before Part B — so instance #0 keeps working
with zero config. The default is *depth-stable*: it
survived the ``tools/new-arbi → products/new-arbi → products/character-pipeline`` moves
because all three locations sit two levels under the cabinet root.
"""

import os

# Slot name -> (env override var, default path relative to the cabinet root).
# Each row is a ROLE, not Arbi's answer. The defaults happen to point at how
# instance #0 fills the slot; another cabinet overrides via the env var.
_SLOTS = {
    "spine":     ("CONTEXT_SPINE",     os.path.join("foundation", "one-pager.md")),
    "brand":     ("CONTEXT_BRAND",     os.path.join("brand", "arbi-character.md")),
    "voice":     ("CONTEXT_VOICE",     os.path.join("brand", "voice")),
    "audience":  ("CONTEXT_AUDIENCE",  os.path.join("growth", "character-pipeline-content-icp.md")),
    "relevance": ("CONTEXT_RELEVANCE", os.path.join("foundation", "keywords.md")),
}

_TOOL_DIR = os.path.dirname(os.path.abspath(__file__))


def cabinet_root() -> str:
    """Absolute path to the host cabinet's context root.

    ``STUDIO_CONTEXT_ROOT`` if set (used as-is; legacy ``CABINET_CONTEXT_ROOT``
    still honored as a fallback for one version); otherwise the cabinet two
    levels above this tool dir — i.e. *this* cabinet (instance #0)."""
    override = os.environ.get("STUDIO_CONTEXT_ROOT", "").strip()
    if not override:
        # Legacy name, honored as a silent fallback for one version
        # (renamed 2026-07-23, portable-context design).
        override = os.environ.get("CABINET_CONTEXT_ROOT", "").strip()
    if override:
        return os.path.abspath(override)
    return os.path.dirname(os.path.dirname(_TOOL_DIR))


def slot_path(name: str) -> str:
    """Resolve a context slot to an absolute path.

    A per-slot env override wins (absolute used as-is; relative resolved under the
    cabinet root); otherwise the slot's documented default under the cabinet root.
    Resolution only — existence/"""
    if name not in _SLOTS:
        raise KeyError(f"unknown context slot {name!r}; known slots: {sorted(_SLOTS)}")
    env_var, default_rel = _SLOTS[name]
    override = os.environ.get(env_var, "").strip()
    if override:
        return override if os.path.isabs(override) else os.path.join(cabinet_root(), override)
    return os.path.join(cabinet_root(), default_rel)

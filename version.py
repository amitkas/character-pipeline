"""Engine version + contract-revision stamp — the single source of truth for
"what version of the Arbi Flow engine is this, and which slot-contract revision
does it require?"

Read by two callers:
  - the orchestrator (logs it at startup + writes it into every run summary), so
    every instance can say what it runs — the pin that makes "call in Arbi" (M2)
    legible across a network of cabinets.
  - ``scripts/update_engine.py`` (the ``/update`` mechanism), which compares the
    installed stamp against a candidate release to compute the risk level.

Two surfaces, by design (see ``foundation/_planning/distribution-and-versioning.md`` §3):
  - ``VERSION``  — semver MAJOR.MINOR.PATCH of the *engine code*.
  - ``Contract-Revision: N`` in ``CONTEXT.md`` — the revision of the *slot contract*
    the engine requires. This is the surface the customer's context actually
    touches, so a contract bump is what makes an update MAJOR/breaking.

Fail-loud: a missing or malformed ``VERSION`` / contract stamp raises
``VersionError`` rather than guessing. An instance that cannot say what it is
must not pretend to be something. (Callers that must not abort a finished run —
e.g. writing a run summary — use ``safe_stamp()``, which records the error
instead of raising.)
"""

import os
import re

_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
# Matches a line like "**Contract-Revision:** 1" or "Contract-Revision: 1".
_CONTRACT_RE = re.compile(r"Contract-Revision[:*\s]+(\d+)", re.IGNORECASE)


class VersionError(RuntimeError):
    """Raised when the engine version or contract revision can't be read."""


def _engine_dir(engine_dir=None) -> str:
    return engine_dir or _ENGINE_DIR


def engine_version(engine_dir=None) -> str:
    """Return the engine semver string (e.g. ``"1.0.0"``). Fail-loud."""
    path = os.path.join(_engine_dir(engine_dir), "VERSION")
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read().strip()
    except OSError as e:
        raise VersionError(f"cannot read VERSION at {path}: {e}") from e
    if not _SEMVER_RE.match(raw):
        raise VersionError(
            f"VERSION at {path} is {raw!r}; expected semver MAJOR.MINOR.PATCH"
        )
    return raw


def version_tuple(version: str):
    """Parse a semver string into an ``(int, int, int)`` tuple. Fail-loud."""
    m = _SEMVER_RE.match(version.strip())
    if not m:
        raise VersionError(f"not a semver string: {version!r}")
    return tuple(int(x) for x in m.groups())


def contract_revision(engine_dir=None) -> int:
    """Return the slot-contract revision declared in ``CONTEXT.md``. Fail-loud."""
    path = os.path.join(_engine_dir(engine_dir), "CONTEXT.md")
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        raise VersionError(f"cannot read CONTEXT.md at {path}: {e}") from e
    m = _CONTRACT_RE.search(text)
    if not m:
        raise VersionError(
            f"no 'Contract-Revision: N' stamp found in {path} — the slot contract "
            f"must declare its revision (see CONTEXT.md / distribution-and-versioning.md §3)"
        )
    return int(m.group(1))


def stamp(engine_dir=None) -> dict:
    """Strict stamp: ``{'engine_version', 'contract_revision'}``. Raises on failure."""
    return {
        "engine_version": engine_version(engine_dir),
        "contract_revision": contract_revision(engine_dir),
    }


def safe_stamp(engine_dir=None) -> dict:
    """Best-effort stamp for contexts that must not abort (e.g. summary writing).

    On any read error returns ``engine_version='unknown'`` /
    ``contract_revision=None`` plus a ``version_stamp_error`` note, so the run
    record is still written and the failure is visible — degrade loud, not silent.
    """
    try:
        return stamp(engine_dir)
    except VersionError as e:
        return {
            "engine_version": "unknown",
            "contract_revision": None,
            "version_stamp_error": str(e),
        }


if __name__ == "__main__":
    s = stamp()
    print(f"engine_version    {s['engine_version']}")
    print(f"contract_revision {s['contract_revision']}")

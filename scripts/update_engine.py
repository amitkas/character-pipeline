#!/usr/bin/env python3
"""update_engine.py — pull a new Arbi Flow *engine* version into this install
without ever touching the customer's context.

This is the mechanism behind the ``/update`` skill and the engineering decision
recorded in ``foundation/_planning/distribution-and-versioning.md`` (propagation
model **B**: a versioned engine + ``/update``). The job is narrow on purpose:

  - the engine lives in *this* directory (``products/character-pipeline/``);
  - the customer's **context slots** (BRAND & VOICE, AUDIENCE, …) live in the host
    cabinet *two levels up* (``brand/``, ``foundation/``) — outside this tree;
  - per-instance state (``.env``, ``youtube_token.json``, ``data/``, run logs and
    output) lives *inside* this tree but is **not** engine code.

So an update replaces engine code and nothing else. The PROTECTED list below is a
hard wall the swap never crosses; everything outside this directory is unreachable
by construction (we refuse any write target that escapes it). "Boring tech,
fail-loud": stdlib only, no merge engine, every refusal is explicit.

GitOps-for-growth flow:
    1. STAGE  — fetch the candidate engine, read its VERSION + contract revision.
    2. PLAN   — compute the file diff (add / modify / delete) and a RISK level.
    3. REVIEW — print the diff + risk; do nothing unless --apply is passed.
    4. APPLY  — back up everything about to change, then swap engine files.
    5. ROLLBACK — restore the last (or a chosen) backup at any time.

Usage:
    python3 scripts/update_engine.py --source <PATH|GIT_URL> [--ref REF] [--subdir DIR]
    python3 scripts/update_engine.py --source ... --apply [--allow-major] [--yes]
    python3 scripts/update_engine.py --rollback [BACKUP_ID]
    python3 scripts/update_engine.py --list-backups

--source defaults to $ARBI_ENGINE_SOURCE. A local path is used as-is; a git URL is
shallow-cloned at --ref (default "main"). --subdir locates the engine within a
cloned repo (default $ARBI_ENGINE_SUBDIR, else repo root).
"""

import argparse
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

# This script lives in <engine>/scripts/, so the engine root is its parent's parent.
ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_ROOT = os.path.join(ENGINE_DIR, ".engine-backups")
MANIFEST_FILE = os.path.join(ENGINE_DIR, ".engine-manifest.txt")

sys.path.insert(0, ENGINE_DIR)
from version import engine_version, contract_revision, version_tuple, VersionError  # noqa: E402


# ── The hard wall: paths /update never reads from a release nor writes/deletes ──
# Directory patterns (trailing /) match at any depth by segment name; file
# patterns match an exact relative path OR a basename anywhere. This is the
# customer's half of the Context Layer Contract — secrets, tokens, per-instance
# state, run history, and our own backups. The host's context slots (brand/,
# foundation/) sit OUTSIDE this dir and so are unreachable regardless.
PROTECTED = [
    # secrets & per-instance config — NEVER touched (see task constraints)
    ".env",
    ".env.local",
    "youtube_token.json",
    "client_secret.json",
    "credentials/",
    # per-instance state & run history — out of scope of an engine swap
    "data/",
    "logs/",
    "output/",
    "artifacts/",
    # tooling / generated / VCS — not engine source
    ".engine-backups/",
    "__pycache__/",
    ".git/",
    ".venv/",
    "venv/",
    ".DS_Store",
]

# Belt-and-suspenders: even if someone mis-set --source to the host cabinet, these
# segments may never appear in an engine release manifest. Context slots.
FORBIDDEN_SEGMENTS = {"brand", "foundation", "projects"}

RISK_NONE = "NONE"
RISK_LOW = "LOW"        # PATCH — engine-internal fix, contract unchanged
RISK_MEDIUM = "MEDIUM"  # MINOR — new capability, contract backward-compatible
RISK_HIGH = "HIGH"      # MAJOR / contract bump / downgrade — needs --allow-major


def fail(msg: str, code: int = 1):
    print(f"\n[FAIL] {msg}", file=sys.stderr)
    sys.exit(code)


# ── protected-path matching ────────────────────────────────────────────────
def is_protected(rel: str) -> bool:
    rel = rel.replace(os.sep, "/").strip("/")
    if not rel:
        return True
    parts = rel.split("/")
    for pat in PROTECTED:
        if pat.endswith("/"):
            if pat.rstrip("/") in parts:        # directory segment anywhere
                return True
        else:
            if rel == pat or parts[-1] == pat:  # exact path or basename anywhere
                return True
    return False


def assert_inside_engine(rel: str):
    """Refuse any path that would escape the engine dir or hit a context slot."""
    norm = os.path.normpath(rel).replace(os.sep, "/")
    if norm.startswith("..") or os.path.isabs(norm):
        fail(f"refusing path that escapes the engine directory: {rel!r}")
    if set(norm.split("/")) & FORBIDDEN_SEGMENTS:
        fail(f"refusing to touch a context slot path: {rel!r} (brand/foundation are host-owned)")


# ── manifests ──────────────────────────────────────────────────────────────
def build_manifest(root: str) -> list:
    """Engine-owned files in a tree (relative posix paths), minus PROTECTED."""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        rel_dir = "" if rel_dir == "." else rel_dir
        # prune protected/forbidden dirs so we never descend into them
        dirnames[:] = [
            d for d in dirnames
            if not is_protected(os.path.join(rel_dir, d)) and d not in FORBIDDEN_SEGMENTS
        ]
        for fn in filenames:
            rel = os.path.join(rel_dir, fn) if rel_dir else fn
            rel = rel.replace(os.sep, "/")
            if is_protected(rel):
                continue
            files.append(rel)
    return sorted(files)


def read_installed_manifest():
    """The set of engine files the last /update installed, or None if never run."""
    if not os.path.exists(MANIFEST_FILE):
        return None
    with open(MANIFEST_FILE, encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]


def write_manifest(path: str, manifest: list):
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Arbi Flow engine manifest — files owned by /update. Do not edit by hand.\n")
        for rel in manifest:
            f.write(rel + "\n")


# ── source resolution / staging ─────────────────────────────────────────────
def stage_source(source: str, ref: str, subdir: str) -> tuple:
    """Return (engine_root, cleanup_fn) for the candidate engine.

    Local path: used as-is. Git URL: shallow-cloned at ref into a temp dir.
    """
    looks_like_git = source.endswith(".git") or "://" in source or source.startswith("git@")
    if looks_like_git:
        tmp = tempfile.mkdtemp(prefix="arbi-engine-")
        print(f"  Cloning {source} @ {ref} …")
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", ref, source, tmp],
                check=True, capture_output=True, text=True,
            )
        except subprocess.CalledProcessError as e:
            shutil.rmtree(tmp, ignore_errors=True)
            fail(f"git clone failed: {e.stderr.strip() or e}")
        root = os.path.join(tmp, subdir) if subdir else tmp
        return root, (lambda: shutil.rmtree(tmp, ignore_errors=True))

    root = os.path.abspath(source)
    if subdir:
        root = os.path.join(root, subdir)
    if not os.path.isdir(root):
        fail(f"--source is not a directory: {root}")
    return root, (lambda: None)


def validate_engine_root(root: str):
    """An engine release must carry a VERSION and the CONTEXT.md contract."""
    for marker in ("VERSION", "CONTEXT.md", "main.py"):
        if not os.path.exists(os.path.join(root, marker)):
            fail(f"{root} does not look like an Arbi Flow engine (missing {marker})")


# ── diff / plan ──────────────────────────────────────────────────────────────
def files_differ(a: str, b: str) -> bool:
    return not filecmp.cmp(a, b, shallow=False)


def compute_plan(src_root: str) -> dict:
    src_manifest = build_manifest(src_root)
    for rel in src_manifest:
        assert_inside_engine(rel)

    added, modified, unchanged = [], [], []
    for rel in src_manifest:
        dst = os.path.join(ENGINE_DIR, rel)
        src = os.path.join(src_root, rel)
        if not os.path.exists(dst):
            added.append(rel)
        elif files_differ(src, dst):
            modified.append(rel)
        else:
            unchanged.append(rel)

    # Deletions: files the *previous* engine owned that this release no longer
    # ships. Computed from the installed manifest, never by scanning the tree —
    # that way a customer's own added files (never in the manifest) are safe.
    deleted = []
    old_manifest = read_installed_manifest()
    if old_manifest is not None:
        newset = set(src_manifest)
        for rel in old_manifest:
            if rel in newset or is_protected(rel):
                continue
            if os.path.exists(os.path.join(ENGINE_DIR, rel)):
                deleted.append(rel)

    cur_v, new_v = engine_version(ENGINE_DIR), engine_version(src_root)
    cur_c, new_c = contract_revision(ENGINE_DIR), contract_revision(src_root)
    risk, reasons = assess_risk(cur_v, new_v, cur_c, new_c, added, modified, deleted)

    return {
        "src_root": src_root,
        "src_manifest": src_manifest,
        "old_manifest_present": old_manifest is not None,
        "added": sorted(added), "modified": sorted(modified),
        "deleted": sorted(deleted), "unchanged": unchanged,
        "from_version": cur_v, "to_version": new_v,
        "from_contract": cur_c, "to_contract": new_c,
        "risk": risk, "risk_reasons": reasons,
    }


def assess_risk(cur_v, new_v, cur_c, new_c, added, modified, deleted) -> tuple:
    reasons = []
    cur_t, new_t = version_tuple(cur_v), version_tuple(new_v)
    changed = bool(added or modified or deleted)

    if new_c > cur_c:
        reasons.append(f"slot contract revision {cur_c} → {new_c} (BREAKING — re-onboard changed slots)")
        return RISK_HIGH, reasons
    if new_c < cur_c:
        reasons.append(f"slot contract revision DOWNGRADE {cur_c} → {new_c}")
        return RISK_HIGH, reasons
    if new_t < cur_t:
        reasons.append(f"version DOWNGRADE {cur_v} → {new_v}")
        return RISK_HIGH, reasons
    if new_t[0] > cur_t[0]:
        reasons.append(f"MAJOR {cur_v} → {new_v} (contract rev unchanged, but a major engine bump)")
        return RISK_HIGH, reasons
    if not changed:
        reasons.append("no file changes — already up to date")
        return RISK_NONE, reasons
    if new_t[1] > cur_t[1]:
        reasons.append(f"MINOR {cur_v} → {new_v} — new capability, contract compatible")
        return RISK_MEDIUM, reasons
    if new_t[2] > cur_t[2]:
        reasons.append(f"PATCH {cur_v} → {new_v} — engine-internal fix")
        return RISK_LOW, reasons
    # same version but files differ → unversioned drift
    reasons.append(f"files differ but version unchanged ({cur_v}) — unversioned change")
    return RISK_LOW, reasons


# ── reporting ─────────────────────────────────────────────────────────────────
def _is_text(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(4096)
        chunk.decode("utf-8")
        return b"\0" not in chunk
    except (OSError, UnicodeDecodeError):
        return False


def print_diff(plan: dict, show_content: bool):
    import difflib

    print("\n" + "=" * 64)
    print("  ARBI FLOW — ENGINE UPDATE (staged, GitOps review)")
    print("=" * 64)
    print(f"  From: v{plan['from_version']}  (contract rev {plan['from_contract']})")
    print(f"  To:   v{plan['to_version']}  (contract rev {plan['to_contract']})")
    print(f"  RISK: {plan['risk']}")
    for r in plan["risk_reasons"]:
        print(f"        - {r}")
    if not plan["old_manifest_present"]:
        print("  Note: no installed manifest yet — first update is overlay-only")
        print("        (no engine files will be deleted this run).")
    print("-" * 64)
    print(f"  + add     {len(plan['added'])}")
    print(f"  ~ modify  {len(plan['modified'])}")
    print(f"  - delete  {len(plan['deleted'])}")
    print(f"  = same    {len(plan['unchanged'])}")
    print("-" * 64)
    for rel in plan["added"]:
        print(f"  + {rel}")
    for rel in plan["modified"]:
        print(f"  ~ {rel}")
    for rel in plan["deleted"]:
        print(f"  - {rel}")
    print("=" * 64)

    if show_content:
        for rel in plan["modified"]:
            dst, src = os.path.join(ENGINE_DIR, rel), os.path.join(plan["src_root"], rel)
            if _is_text(dst) and _is_text(src):
                a = open(dst, encoding="utf-8", errors="replace").read().splitlines(keepends=True)
                b = open(src, encoding="utf-8", errors="replace").read().splitlines(keepends=True)
                diff = list(difflib.unified_diff(a, b, fromfile=f"installed/{rel}", tofile=f"candidate/{rel}"))
                if diff:
                    print("".join(diff[:400]))
                    if len(diff) > 400:
                        print(f"  … ({len(diff) - 400} more diff lines for {rel})")
            else:
                print(f"  (binary) ~ {rel} — content changed")


# ── apply / rollback ───────────────────────────────────────────────────────────
def _copy(src: str, dst: str):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def apply_update(plan: dict) -> str:
    """Back up everything about to change, then swap engine files. Returns backup id."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_id = f"{plan['from_version']}_{stamp}"
    backup_dir = os.path.join(BACKUP_ROOT, backup_id)
    files_dir = os.path.join(backup_dir, "files")
    os.makedirs(files_dir, exist_ok=True)

    # 1) back up files that will be modified or deleted (so rollback restores them)
    for rel in plan["modified"] + plan["deleted"]:
        _copy(os.path.join(ENGINE_DIR, rel), os.path.join(files_dir, rel))
    # back up the old manifest too, if any
    if os.path.exists(MANIFEST_FILE):
        shutil.copy2(MANIFEST_FILE, os.path.join(backup_dir, "engine-manifest.txt"))

    # 2) record the plan so rollback knows what was added (to remove) vs changed
    with open(os.path.join(backup_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({
            "backup_id": backup_id, "created_at": datetime.now().isoformat(),
            "from_version": plan["from_version"], "to_version": plan["to_version"],
            "from_contract": plan["from_contract"], "to_contract": plan["to_contract"],
            "risk": plan["risk"],
            "added": plan["added"], "modified": plan["modified"], "deleted": plan["deleted"],
            "had_manifest": os.path.exists(os.path.join(backup_dir, "engine-manifest.txt")),
        }, f, indent=2)

    # 3) swap: write/overwrite added+modified, remove deleted
    for rel in plan["added"] + plan["modified"]:
        assert_inside_engine(rel)
        _copy(os.path.join(plan["src_root"], rel), os.path.join(ENGINE_DIR, rel))
    for rel in plan["deleted"]:
        assert_inside_engine(rel)
        os.remove(os.path.join(ENGINE_DIR, rel))

    # 4) record the new installed manifest
    write_manifest(MANIFEST_FILE, plan["src_manifest"])
    return backup_id


def list_backups() -> list:
    if not os.path.isdir(BACKUP_ROOT):
        return []
    out = []
    for name in sorted(os.listdir(BACKUP_ROOT)):
        mpath = os.path.join(BACKUP_ROOT, name, "manifest.json")
        if os.path.exists(mpath):
            with open(mpath, encoding="utf-8") as f:
                out.append(json.load(f))
    return out


def rollback(backup_id: str = None):
    backups = list_backups()
    if not backups:
        fail("no backups found — nothing to roll back to")
    if backup_id:
        match = [b for b in backups if b["backup_id"] == backup_id]
        if not match:
            fail(f"no backup with id {backup_id!r}. Run --list-backups.")
        b = match[0]
    else:
        b = backups[-1]  # latest

    backup_dir = os.path.join(BACKUP_ROOT, b["backup_id"])
    files_dir = os.path.join(backup_dir, "files")
    print(f"  Rolling back to v{b['from_version']} (backup {b['backup_id']}) …")

    # restore modified + deleted files from the backup
    for rel in b["modified"] + b["deleted"]:
        src = os.path.join(files_dir, rel)
        if os.path.exists(src):
            assert_inside_engine(rel)
            _copy(src, os.path.join(ENGINE_DIR, rel))
    # remove files the update had ADDED (they did not exist before)
    for rel in b["added"]:
        assert_inside_engine(rel)
        p = os.path.join(ENGINE_DIR, rel)
        if os.path.exists(p):
            os.remove(p)
    # restore the old manifest
    saved_manifest = os.path.join(backup_dir, "engine-manifest.txt")
    if os.path.exists(saved_manifest):
        shutil.copy2(saved_manifest, MANIFEST_FILE)
    elif os.path.exists(MANIFEST_FILE):
        os.remove(MANIFEST_FILE)

    print(f"[OK] Rolled back to v{b['from_version']}. Engine stamp is now: v{engine_version(ENGINE_DIR)}")


# ── CLI ──────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="Update the Arbi Flow engine (propagation model B).")
    p.add_argument("--source", default=os.environ.get("ARBI_ENGINE_SOURCE", ""),
                   help="Engine source: local dir or git URL. Env: ARBI_ENGINE_SOURCE")
    p.add_argument("--ref", default="main", help="Git ref/tag/branch when --source is a URL (default: main)")
    p.add_argument("--subdir", default=os.environ.get("ARBI_ENGINE_SUBDIR", ""),
                   help="Engine subdir within a cloned repo. Env: ARBI_ENGINE_SUBDIR")
    p.add_argument("--apply", action="store_true", help="Apply the update (default: dry-run / stage only)")
    p.add_argument("--allow-major", action="store_true", help="Permit a HIGH-risk (breaking/major) update")
    p.add_argument("--yes", action="store_true", help="Skip the interactive confirm on --apply")
    p.add_argument("--no-content", action="store_true", help="Skip per-file unified diffs (summary only)")
    p.add_argument("--rollback", nargs="?", const=True, metavar="BACKUP_ID",
                   help="Restore a backup (latest if no id given)")
    p.add_argument("--list-backups", action="store_true", help="List rollback points")
    args = p.parse_args()

    # current engine must itself be stampable, or we can't reason about risk
    try:
        engine_version(ENGINE_DIR), contract_revision(ENGINE_DIR)
    except VersionError as e:
        fail(f"this install has no readable version stamp: {e}")

    if args.list_backups:
        backups = list_backups()
        if not backups:
            print("  (no backups yet)")
            return
        print("  Rollback points (oldest → newest):")
        for b in backups:
            print(f"    {b['backup_id']}  v{b['from_version']} → v{b['to_version']}  "
                  f"risk={b['risk']}  {b.get('created_at','')}")
        return

    if args.rollback is not None:
        rollback(None if args.rollback is True else args.rollback)
        return

    if not args.source:
        fail("no --source given (and $ARBI_ENGINE_SOURCE is unset). "
             "Point it at an engine checkout or git URL.")

    src_root, cleanup = stage_source(args.source, args.ref, args.subdir)
    try:
        validate_engine_root(src_root)
        plan = compute_plan(src_root)
        print_diff(plan, show_content=not args.no_content)

        if plan["risk"] == RISK_NONE:
            print("\n  Already up to date — nothing to apply.")
            return

        if not args.apply:
            print("\n  Dry-run only. Re-run with --apply to install"
                  + ("  (HIGH risk — also pass --allow-major)." if plan["risk"] == RISK_HIGH else "."))
            return

        if plan["risk"] == RISK_HIGH and not args.allow_major:
            print("\n[REFUSED] This is a HIGH-risk update (breaking contract / major / downgrade).")
            if plan["to_contract"] > plan["from_contract"]:
                print("          The slot contract changed: after applying, re-run /setup so the")
                print("          onboarder can fill the new/changed context slots (no slot is")
                print("          written automatically). See distribution-and-versioning.md §3.")
            print("          Re-run with --apply --allow-major once you've reviewed the diff.")
            sys.exit(2)

        if not args.yes:
            ans = input(f"\n  Apply v{plan['from_version']} → v{plan['to_version']} "
                        f"(risk {plan['risk']})? Context slots, .env, tokens and data/ are untouched. [y/N] ")
            if ans.strip().lower() not in ("y", "yes"):
                print("  Aborted. Nothing changed.")
                return

        backup_id = apply_update(plan)
        print(f"\n[OK] Updated to v{plan['to_version']} (contract rev {plan['to_contract']}).")
        print(f"     Backup saved: {backup_id}")
        print(f"     Roll back with:  python3 scripts/update_engine.py --rollback {backup_id}")
        if plan["to_contract"] > plan["from_contract"]:
            print("     ACTION: contract changed — run /setup to fill new/changed slots.")
    finally:
        cleanup()


if __name__ == "__main__":
    main()

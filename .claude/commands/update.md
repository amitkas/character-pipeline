Update the Arbi Flow **engine** to a newer version, without ever touching this install's context, secrets, or data. This is propagation model **B** from `foundation/_planning/distribution-and-versioning.md`: a versioned engine + a reviewable `/update`. The mechanism is `scripts/update_engine.py`; your job is to drive it safely, GitOps-style — **stage and show the diff first, apply only after the user reviews it.**

What `/update` will NEVER change (the hard wall — reassure the user up front):
- the context slots: `brand/`, `foundation/` (host-owned, two levels up — outside the engine dir)
- `.env`, `youtube_token.json`, `client_secret.json`, `credentials/`
- `data/` (dedup + cache), `logs/`, `output/`, `artifacts/` (run history)

It only swaps engine code (`agents/`, `pipelines/`, `*.py`, `CONTEXT.md`, `VERSION`, skills, docs).

---

## Step 1 — Find the engine source

Ask the user where the new engine version is, unless `$ARBI_ENGINE_SOURCE` is already set. It can be a local directory (another engine checkout) or a git URL (a release tag). The release channel is still being decided (ADR §6) — for now, the source is whatever the user points at.

## Step 2 — Stage and review (dry run, no changes)

```bash
python3 scripts/update_engine.py --source <PATH_OR_GIT_URL>
```

(For a git URL, add `--ref <tag>`; for an engine living in a repo subdir, add `--subdir <dir>`.)

This prints: the version transition (`from → to`), the **RISK** level, and the file diff (`+ add / ~ modify / - delete`) with per-file unified diffs. It writes nothing.

Relay this to the user clearly. Explain the risk level:
- **NONE** — already up to date, nothing to do.
- **LOW** — a PATCH: engine-internal fix, slot contract unchanged. Safe.
- **MEDIUM** — a MINOR: new capability, contract still backward-compatible. Safe; new optional slots (if any) show up later as proposals, never failures.
- **HIGH** — a MAJOR, a **slot-contract change**, or a downgrade. The script will **refuse** to apply without `--allow-major`. If the contract revision went up, after applying you must run `/setup` so the onboarder can fill the new/changed context slots (no slot is ever written automatically).

## Step 3 — Apply (only after the user approves the diff)

```bash
python3 scripts/update_engine.py --source <...> --apply
```

The script backs up every file it is about to change, then swaps engine files, then prints the **backup id** and the exact rollback command. For a HIGH-risk update, add `--allow-major` (only after the user has read the diff and understands the contract change).

After applying, confirm the new stamp:

```bash
python3 version.py
```

## Step 4 — Rollback (if anything looks wrong)

```bash
python3 scripts/update_engine.py --list-backups          # see rollback points
python3 scripts/update_engine.py --rollback              # revert the latest update
python3 scripts/update_engine.py --rollback <BACKUP_ID>  # revert a specific one
```

Rollback restores the previous engine files (and removes files the update added), leaving context, secrets, and data untouched as always.

---

Report to the user: the version transition, the risk level, what changed, and — after an apply — the backup id and how to roll back. If the contract revision changed, remind them to run `/setup`.

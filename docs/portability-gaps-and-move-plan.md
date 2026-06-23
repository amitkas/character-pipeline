# Portability gaps + configurable context root + Phase-2 move plan

*CTO deliverable, 2026-06-11. Three parts: (A) the concrete portability gap list, (B) the configurable context-root design, (C) the safe `tools/new-arbi → products/new-arbi` move plan for Phase 2. Coordinated with the PM's [`archive/business-vs-product.md`](../../../archive/business-vs-product.md) and built on the line-level audit in [`context-contract-audit.md`](context-contract-audit.md). The contract this works toward is [`../CONTEXT.md`](../CONTEXT.md).*

> **✅ Part C executed 2026-06-11.** Amit chose **Option B (physical product space)**. The move `tools/new-arbi → products/new-arbi` + the cabinet-wide link sweep are **done** (this doc now lives at the new path; `tools/` is a redirect stub; `products/index.md` is the new space index). The `tools/new-arbi → products/new-arbi` strings remaining in Part C below are the **migration record**, not broken links. **Still open:** Part B (the context-root retrofit + de-baking, gaps #1–#11) is the actual portability work and is **not yet implemented** — the move relocated the folder; it did not de-bake the code.

> **Original sequencing note (for the record).** The PM doc §5 framed **Option A (reframe in place)** vs **Option B (physical `products/` space)** as open. Amit picked B. Parts (A) and (B) were needed under *both* options — the context-root retrofit and de-baking are the real portability fixes; the physical move was orthogonal to them.

> **⏩ Status update — Part B has since landed.** When this CTO deliverable was written, the gap list below (gaps #1–#11) was the *open* de-baking plan. Since then it has been implemented: the engine reads the character through the Context Layer Contract, `grep -ri "arbi\|troll\|golden-yellow\|crown" agents/` returns **clean**, and `agents/arbi_persona.py` is now the slot loader `agents/character.py` (gap #10) with no baked persona or fallback. The gap table below is the **historical work order** that produced the current standalone engine, not outstanding work — see [`../CONTEXT.md`](../CONTEXT.md) §6 for the current conformance state. (The few open items — wiring SPINE / VOICE / RELEVANCE LENS — are tracked in CONTEXT.md §6 as declared-not-yet-consumed slots, not baked Arbi values.)

---

## Part A — Portability gap list (concrete, ordered by leverage)

Each gap names the file, what's baked, and which CONTEXT.md slot it should read instead. Line-level detail is in [`context-contract-audit.md`](context-contract-audit.md) §2; this is the actionable close-out order.

| # | Gap | File(s) | Should read slot | Leverage |
|---|---|---|---|---|
| 1 | Animation Director system prompt + every few-shot example hardcodes "a character named Arbi — golden-yellow… gold crown". Reads no cabinet doc. | `agents/script_writer.py` | BRAND & VOICE | **Highest** — 100% baked, reads nothing |
| 2 | Creative Director system prompt re-hardcodes "Arbi… chaotic-neutral troll… confidently wrong" *even though it loads the persona file* — the instance leaks back in above the contract. | `agents/creative_director.py:119-144` | BRAND & VOICE (already loaded — stop overriding it) | High |
| 3 | `OFF_LIMITS_TOPICS` / `OFF_LIMITS_PROMPT` are in-code constants; `video_scout.py` imports them live. Each brand draws its own line. | `agents/arbi_persona.py`, `agents/video_scout.py` | BRAND & VOICE (off-limits section) | High |
| 4 | Character-dressing prompts are Arbi-specific throughout (heaviest concentration of baked refs). | `agents/cartoonist.py:14-115` | BRAND & VOICE + CHARACTER IMAGE | High |
| 5 | Sound identity ("troll gibberish + pitch shift", hardcoded ElevenLabs voice id) is Arbi's voice as code, not a read of `brand/voice/`. | `agents/voice_actor.py` | VOICE | Medium |
| 6 | Fixed `../../` climb + Arbi filenames resolve the only two cabinet reads. | `agents/creative_director.py:33-39` | (the context root itself — Part B) | High — unblocks "drop anywhere" |
| 7 | SPINE, VOICE, RELEVANCE LENS slots are read by nothing — dead weight in the cabinet. | (none read them) | wire SPINE→all, VOICE→TAKE, RELEVANCE→SENSE | Medium |
| 8 | Branded assets baked: `OUTRO_FILENAME = "outro.mp4"`, default title "Arbi's Latest Adventure", "#Arbi" tags, "Arbi playlist" log lines. | `agents/outro_stitcher.py:9`, `agents/youtube_uploader.py:195-221` | BRANDED ASSETS / host config; skip when absent | Medium |
| 9 | Character image resolver bypassed on two paths — `main.py --resume` and `video_x.py` hardcode `artifacts/Character - New.png`. | `main.py:139`, `pipelines/video_x.py:48-49` | CHARACTER IMAGE (route through `resolve_character_image`) | Low |
| 10 | Rename `arbi_persona.py → character.py` (a *loader*, not a baked persona) once 1–5 land, so in-code constants survive only as a last-ditch fallback. | `agents/arbi_persona.py` | — | Cleanup |
| 11 | Stale "wacky **red** furry troll" copy (Arbi is golden-yellow — see [[arbi-visual-identity]]). | `docs/BUILD_YOUR_OWN_ARBI.md:5,85` | — | Doc hygiene |

**Definition of done:** `grep -ri "arbi\|troll\|golden-yellow\|crown" agents/` returns only the fallback loader.

---

## Part B — Configurable context root (design, not yet implemented)

The single mechanism behind every "read slot, not path" gap above. One new module + a handful of config keys; the two `../../` constants in `creative_director.py` become calls into it.

### B.1 New module: `context_root.py` (tool root)

```python
# context_root.py — resolve host-cabinet context slots through one root.
import os

# Default root = the cabinet two levels above the tool dir (this cabinet,
# instance #0). Depth-stable: survives tools/ -> products/ (same depth).
def cabinet_root() -> str:
    override = os.environ.get("CABINET_CONTEXT_ROOT", "").strip()
    if override:
        return os.path.abspath(override)
    tool_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(tool_dir))

# slot name -> (env override var, default path relative to cabinet root)
_SLOTS = {
    "spine":           ("CONTEXT_SPINE",     "foundation/one-pager.md"),
    "brand":           ("CONTEXT_BRAND",     "brand/arbi-character.md"),
    "voice":           ("CONTEXT_VOICE",     "brand/voice"),
    "audience":        ("CONTEXT_AUDIENCE",  "foundation/content-icp.md"),
    "relevance":       ("CONTEXT_RELEVANCE", "foundation/keywords.md"),
}

def slot_path(name: str) -> str:
    env_var, default_rel = _SLOTS[name]
    override = os.environ.get(env_var, "").strip()
    if override:
        return override if os.path.isabs(override) else os.path.join(cabinet_root(), override)
    return os.path.join(cabinet_root(), default_rel)
```

### B.2 `config.py` additions

Add to `OPTIONAL_KEYS` (no new *required* keys — defaults preserve today's behavior):

```
"CABINET_CONTEXT_ROOT",   # host cabinet root; default = this cabinet
"CONTEXT_SPINE", "CONTEXT_BRAND", "CONTEXT_VOICE",
"CONTEXT_AUDIENCE", "CONTEXT_RELEVANCE",
"CONTEXT_CHARACTER_IMAGE", # alias of ARBI_CHARACTER_IMAGE (keep both; ARBI_* deprecated)
"CONTEXT_OUTRO", "CONTEXT_MUSIC_DIR",
```

### B.3 The retrofit (replaces gap #6)

```python
# agents/creative_director.py — before:
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARBI_CHARACTER_PATH = os.path.normpath(os.path.join(_ROOT, "..", "..", "brand", "arbi-character.md"))
CONTENT_ICP_PATH    = os.path.normpath(os.path.join(_ROOT, "..", "..", "foundation", "content-icp.md"))

# after:
from context_root import slot_path
ARBI_CHARACTER_PATH = slot_path("brand")
CONTENT_ICP_PATH    = slot_path("audience")
```

The graceful-degradation that `creative_director.py` already has (missing file → log + fallback) stays; it's exactly the §4.5 "degrade honestly" behavior the contract wants. `resolve_character_image()` in `orchestrator.py` stays as-is but gains the `CONTEXT_CHARACTER_IMAGE` alias.

> **This retrofit is independent of the physical move** and can land first under Option A. It is the change that actually makes the tool portable; the move only changes *where the folder lives*.

---

## Part C — Safe move plan: `tools/new-arbi → products/new-arbi` (Phase 2, Option B only)

### C.0 The key insight that makes this safe

`products/` and `tools/` sit at the **same depth** under the cabinet. So:

- The `../../` climb in `creative_director.py` **still resolves to the cabinet root after the move** — and once Part B lands, the root is computed/overridable anyway. **No Python import or path constant breaks.**
- What *does* break: **Markdown cross-links** that hardcode the string `tools/new-arbi`. Those are the entire link-fix surface.

This means the move is a **rename + link sweep**, not a code migration. Do it as its own reviewable commit, separate from the Part B retrofit.

### C.1 Pre-conditions

1. **Amit has chosen Option B** (or A-now/B-later with the trigger met). Until then, this plan is dormant.
2. Working tree clean except intended changes. Run from the cabinet git root: `/Users/amitcolu/Desktop/Cabinet`.
3. **Secret safety:** `.env` is gitignored (`.gitignore:2`) and **never tracked** (`git ls-files` shows only `.env.example`). The move must not read, print, commit, or alter `.env` or `youtube_token.json`. A directory `git mv` relocates `.env` *physically* (untracked, still gitignored) so the tool keeps running — that is acceptable and touches no secret *values*. If even the physical move is unwanted, copy `.env` by hand afterward and leave the original.

### C.2 The move (tracked files)

55 files are tracked under `arbi-labs/tools/new-arbi/`. From the cabinet root:

```bash
mkdir -p arbi-labs/product
git mv arbi-labs/tools/new-arbi arbi-labs/products/new-arbi
```

`git mv` on the directory renames it on disk (carrying untracked generated dirs `artifacts/`, `output/`, `logs/`, `data/`, and `.env` along physically) and stages renames for all 55 tracked files. Verify:

```bash
git status --short | grep -c '^R'        # ~55 renames staged
test -d arbi-labs/tools/new-arbi && echo "LEFTOVER — investigate" || echo "old path gone"
ls arbi-labs/products/new-arbi/.env 2>/dev/null && echo ".env carried (untracked, gitignored)"
```

If `git mv` refuses on the whole dir (untracked-file conflict), fall back to: `git mv` each tracked file, then `mv` the remaining untracked non-secret dirs. Generated dirs (`artifacts/ output/ logs/`) and dedup/cache (`data/processed_events.json`, `data/trend_cache.json`) are gitignored and disposable — they may be left to regenerate rather than moved.

### C.3 Link fixes (the real work)

Every cross-cabinet reference to the literal `tools/new-arbi`. Enumerated 2026-06-11:

**Outside the tool (13 docs) — must update `tools/new-arbi` → `products/new-arbi`:**

```
arbi-labs/index.md
arbi-la../_planning/new-arbi/index.md
arbi-labs/.agents/.memory/arbi/context.md
arbi-labs/.agents/cto/persona.md
arbi-labs/foundation/content-icp.md
arbi-labs/archive/business-vs-product.md
arbi-labs/archive/take-as-artifact-prd.md
arbi-labs/archive/social-video-format-specs.md
arbi-labs/archive/hitl-approval-gates-prd.md
arbi-labs/archive/content-engine-roadmap.md
arbi-labs/archive/content-engine-vision.md
arbi-labs/archive/content-engine-status-2026-06-11.md
arbi-labs/archive/take-as-artifact-architecture.md
```

**Inside the tool (self-references):** `BRIEF.md`, `docs/context-contract-audit.md`, plus `CONTEXT.md` and this file — sweep for `tools/new-arbi` and relative `../../../` link depth (the `business-vs-product.md` back-link in CONTEXT.md and this doc stays valid — same depth — but verify after the move).

Sweep command to drive the fix and to verify zero stragglers afterward:

```bash
grep -rln 'tools/new-arbi' arbi-labs/ --include='*.md' --include='*.py' \
  | grep -v '/.conversations/' | grep -v '/.messages/'
# fix each, then re-run — must return empty
```

> Note: `projects/new-arbi/` (the brief) **does not move** — per the PM doc, briefs stay in `projects/`; only its internal links to the code update. Likewise `.agents/cto/persona.md` and the arbi memory note are pointers to where the code lives and must follow it.

### C.4 Verification checklist

- [ ] `grep -rln 'tools/new-arbi' arbi-labs --include='*.md' --include='*.py'` (minus `.conversations`/`.messages`) returns empty.
- [ ] `python3 -c "import config; config.load_config()"` from `arbi-labs/products/new-arbi/` (with `.env` present) succeeds.
- [ ] Offline smoke: `python3 scripts/verify_take_as_artifact.py` passes from the new path (exercises `load_take`, the render-path loop, `learn.py`, path config — no paid APIs).
- [ ] `creative_director.py` resolves the brand + audience docs from the new location (log line shows the loaded char count) — confirms the `../../` / context-root resolution survived.
- [ ] No secret file changed: `git status` shows no `.env` / `youtube_token.json` in the diff.

### C.5 Rollback

The move is one commit. `git revert <sha>` (or `git mv` back) restores `tools/new-arbi`; re-run the C.3 sweep in reverse. Generated dirs are disposable, so no data loss risk.

### C.6 Recommended commit sequencing

1. **Commit 1 (Option A or B):** Part B context-root retrofit + `CONTEXT.md` — the portability fix. Ships value independent of the move.
2. **Commit 2 (Option B only):** the `git mv` + link sweep. Pure rename, trivially reviewable, trivially revertible.

Keeping them separate means the portability win is not held hostage to the open A/B decision.

# Arbi Flow — Project Guide for Claude

## What This Is

**Arbi Flow** (the `character-pipeline` runtime) is a **portable, character-driven trend-to-video engine**. It runs one job — the creative pipeline (SENSE → GROUND → TAKE → RENDER → DISTRIBUTE → LEARN) — against **whatever context layer it is installed into**. It finds trending real-world events and produces animated square videos of a **host-defined character** re-enacting them with physical comedy, signature sounds, and overlays. Videos are saved locally or optionally auto-uploaded to YouTube.

**The engine contains no character.** Who the character is, how it sounds, and what it looks like are read at runtime from the host cabinet's **context slots** (BRAND & VOICE, VOICE, CHARACTER IMAGE, AUDIENCE) through one configurable context root. Arbi Labs is just **instance #0** — the first cabinet whose slots happen to be filled in. Point the same checkout at a different `CABINET_CONTEXT_ROOT` and it runs that cabinet's character. The contract is declared in **`CONTEXT.md`** (read it before touching agent code) and resolved by `context_root.py`.

> **The portability test that governs every line of code and docs:** *Would this survive being copied, untouched, into another business's cabinet — pointed at their context root, reading their docs?* If a line hardcodes "Arbi", "golden-yellow", "troll", or "crown" in the engine, it fails — that is host content, and it belongs in the host's BRAND & VOICE slot, not in the product. See `CONTEXT.md` §5.

## Pipeline

| Pipeline | Command | Skill | What It Produces | Time | Cost |
|----------|---------|-------|-----------------|------|------|
| **Video** | `python3 main.py` | `/video` | Animated video of the character re-enacting an event (~13s, 1:1) | ~5 min | ~$0.77 |

## Tech Stack

- **Python 3.10+** — all source code
- **Google Gemini 2.5 Flash** — trend detection, video analysis, image generation, text generation
- **fal.ai (Kling 2.5 Turbo Pro)** — AI video generation from image
- **ElevenLabs** — text-to-speech character sounds
- **Serper** — video search
- **ffmpeg** — frame extraction, audio compositing, video encoding (system dep)
- **yt-dlp** — video downloading

## How to Run

```bash
pip install -r requirements.txt
cp .env.example .env                # fill in API keys
python3 main.py                     # run full video pipeline (~5 min, ~$0.77)
python3 main.py --resume <run_id>   # resume a failed run from last step
python3 main.py --upload [run_id]   # upload to YouTube (latest or specific run)
```

Or use Claude Code skill: `/video`

## Architecture

```
main.py → pipelines/video.py → orchestrator.py → 11 agents:
  1. Video Scout      (Gemini grounded → Perplexity)
  2. Video Finder     (Serper + yt-dlp)
  3. Video Analyzer   (Gemini multimodal)
  4. Creative Director (Gemini — owns the chaos angle, after the tape is seen)
  5. Character Dresser (Gemini image gen)
  6. Animation Director (Gemini)
  7. Video Producer   (fal.ai Kling 2.5 Turbo Pro)
  8. Sound Engineer (ElevenLabs + ffmpeg)
  9. Subtitle Burner  (ffmpeg)
 10. Outro Stitcher   (ffmpeg)
 11. YouTube Uploader (YouTube Data API v3, optional)
```

Every agent reads the character from the BRAND & VOICE slot via `get_character()` (`agents/character.py`) — no agent bakes a character literal.

### Video Pipeline (11 agents)

| # | Agent | File | What It Does |
|---|-------|------|-------------|
| 1 | Video Scout | `agents/video_scout.py` | Finds trending event + search query (Gemini grounded → Perplexity fallback). Applies the character's off-limits list from the slot. No longer decides the angle. |
| 2 | Video Finder | `agents/video_finder.py` | Searches + downloads source video via Serper + yt-dlp |
| 3 | Video Analyzer | `agents/video_analyzer.py` | Analyzes video with Gemini multimodal → neutral play-by-play, outfit, keywords, scene |
| 4 | Creative Director | `agents/creative_director.py` | Owns the chaos angle, decided AFTER the tape is seen, from: Analyzer description + the character's full persona (BRAND & VOICE slot) + AUDIENCE slot (the `content_icp:` block) |
| 5 | Character Dresser | `agents/cartoonist.py` | Dresses the character in the detected outfit (Gemini image gen, 3-tier fallback); preserves the identity read from the slot |
| 6 | Animation Director | `agents/script_writer.py` | Writes 15-25 word physical comedy direction (prioritizes chaos angle; rejects truncated/dangling lines) |
| 7 | Video Producer | `agents/video_producer.py` | Generates 10s animated video via Kling 2.5 Turbo Pro on fal.ai (injects chaos angle into prompt) |
| 8 | Sound Engineer | `agents/voice_actor.py` | Generates the character's signature gibberish/sound via ElevenLabs (label, voice ID, and pitch from the slot's sound spec) |
| 9 | Subtitle Burner | `agents/subtitle_burner.py` | Burns event title + keyword overlays onto video |
| 10 | Outro Stitcher | `agents/outro_stitcher.py` | Appends a host-supplied branded outro clip (skipped if no BRANDED ASSETS slot) |
| 11 | YouTube Uploader | `agents/youtube_uploader.py` | Uploads final video to YouTube (automatic when token exists, non-fatal); title/hashtags/tags from the character's distribution spec |

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point with CLI: `python main.py [--resume\|--upload <run_id>]` |
| `orchestrator.py` | Pipeline runner (config, logging, agent loop, summary, auto-cleanup) |
| `config.py` | Loads `.env`, validates required API keys; declares the `CONTEXT_*` context-slot env vars |
| `context_root.py` | Context Layer Contract resolver — `CABINET_CONTEXT_ROOT` + slot map (see `CONTEXT.md`) |
| `VERSION` | Engine semver (`MAJOR.MINOR.PATCH`). Paired with the `Contract-Revision: N` stamp in `CONTEXT.md` |
| `version.py` | Fail-loud reader for `VERSION` + contract revision; logged at run start and written into every run summary |
| `scripts/update_engine.py` | The `/update` mechanism (propagation model B): stage → reviewable diff + risk → apply (with backup) → rollback. Never touches context slots, `.env`, tokens, or `data/` |
| `.engine-manifest.txt` | The set of engine-owned files the last `/update` installed (used to compute safe deletions; never lists per-instance files) |
| `dedup.py` | Prevents reprocessing same events (with file locking for concurrent runs) |
| `logger.py` | Logging setup: console (INFO), file (DEBUG), JSON summary |
| `context/base.py` | `BaseContext` dataclass — shared pipeline state |
| `context/video.py` | `VideoContext(BaseContext)` — video-specific fields |
| `pipelines/video.py` | Video pipeline definition (agent list + context factory) |
| `agents/character.py` | Loads the BRAND & VOICE slot (`character:` block) into a `Character` via `get_character()`; agents read this, never baked literals. Validates required keys and raises `CharacterError` if any is missing — **no in-code fallback character** |
| `agents/creative_director.py` | Owns the chaos angle; reads the BRAND & VOICE slot + AUDIENCE slot |
| `utils/*.py` | Shared utilities (JSON parsing, ffmpeg wrappers, video processing) |
| `scripts/setup_youtube_auth.py` | One-time OAuth setup for YouTube uploads |
| `scripts/generate_outro.py` | Regenerate a branded outro clip |
| `CONTEXT.md` | **The Context Layer Contract** — the slots the runtime reads, how, and what must never be baked in. Read before editing agents. |

## Directory Layout

```
main.py                   # Entry point — runs video pipeline, --resume, --upload
orchestrator.py           # Pipeline runner with auto-cleanup
config.py                 # Loads .env, validates API keys, declares CONTEXT_* slots
context_root.py           # Context Layer Contract resolver (CABINET_CONTEXT_ROOT + slots)
dedup.py                  # Tracks processed events (with file locking)
logger.py                 # Logging setup
CONTEXT.md                # The Context Layer Contract (slots, read interface, no-bake rules)
context/
  base.py               # BaseContext — shared pipeline state
  video.py              # VideoContext — video-specific fields
pipelines/
  video.py              # Video pipeline (agent list + context factory)
agents/
  character.py          # Loads BRAND & VOICE slot (character: block) → Character via get_character(); fails loud if a required key is missing (no fallback)
  video_scout.py        # Finds trending events (applies the slot's off-limits list)
  video_finder.py       # Downloads source video
  video_analyzer.py     # Analyzes video (neutral play-by-play)
  creative_director.py  # Owns the chaos angle (after the tape is seen)
  cartoonist.py         # Dresses the character
  script_writer.py      # Animation direction
  video_producer.py     # Generates animated video
  voice_actor.py        # Character sounds (per the slot's sound spec)
  subtitle_burner.py    # Burns overlays (optimized ffmpeg drawtext)
  outro_stitcher.py     # Appends host-supplied outro
  youtube_uploader.py   # Uploads to YouTube (automatic when token exists)
utils/                    # Shared utilities
  json_utils.py         # LLM JSON parsing
  ffmpeg_utils.py       # ffmpeg wrappers (run, metadata, trim, etc.)
  video_utils.py        # Video processing (square conversion, concat)
scripts/                  # One-time/rare utilities
  setup_youtube_auth.py # OAuth setup for YouTube
  generate_outro.py     # Regenerate a branded outro clip
artifacts/                # Per-run working dirs (cleaned per run)
  images/               # Generated images
  audio/                # Audio files
  videos/               # Video files
data/
  processed_events.json # Dedup tracking
  trend_cache.json      # Cached trends
logs/
  {run_id}.log          # Debug log
  {run_id}_summary.json # Machine-readable run summary
output/                   # Final videos ready for upload
VERSION                   # Engine semver (paired with Contract-Revision: N in CONTEXT.md)
version.py                # Fail-loud reader for VERSION + contract revision
.engine-manifest.txt      # Engine-owned file list (written by /update; used for safe deletions)
scripts/
  update_engine.py      # /update mechanism: stage → diff+risk → apply (backup) → rollback
.claude/
  commands/
    video.md            # /video skill
    update.md           # /update skill — pull a new engine version, never touching context/.env/data
```

> Brand assets (character reference PNG, branded outro, music bed) are **host-supplied, not bundled** — they enter through the CHARACTER IMAGE / BRANDED ASSETS slots. Instance #0's assets (`arbi-king.png`, etc.) live in the host cabinet, not in tracked product files.

## Context

```
BaseContext (context/base.py) — run metadata, event discovery, media paths, errors
└── VideoContext (context/video.py) — video-specific fields (source video, analysis, animation, audio)
```

## Required Environment Variables

```
GEMINI_API_KEY, SERPER_API_KEY, FAL_KEY, ELEVENLABS_API_KEY
```

Optional:
- `PERPLEXITY_API_KEY` (fallback trend source)
- `YOUTUBE_UPLOAD_ENABLED=false` (opt-out: disable auto-upload; upload is automatic when `youtube_token.json` exists)

Context Layer Contract (all optional; defaults resolve to instance #0 — see `CONTEXT.md` §2–§3):
- `CABINET_CONTEXT_ROOT` — host cabinet root; default = this cabinet
- `CONTEXT_SPINE`, `CONTEXT_BRAND`, `CONTEXT_VOICE`, `CONTEXT_AUDIENCE`, `CONTEXT_RELEVANCE` — per-slot doc overrides
- `CONTEXT_CHARACTER_IMAGE` — canonical character reference PNG (alias: `ARBI_CHARACTER_IMAGE`, deprecated)
- `CONTEXT_OUTRO`, `CONTEXT_MUSIC_DIR` — branded outro tail + music bed (absent ⇒ step skipped)

## Conventions

- Agent functions: `agent_name(ctx, config) -> ctx`
- Output files: `{run_id}_description.ext` (e.g., `7a7d12c4_final_with_outro.mp4`)
- Final video: copied to `output/` with clean event title filename
- Cascading fallbacks everywhere (Gemini grounded → Gemini plain → Perplexity; multi-tier image gen)
- **Character comes from the BRAND & VOICE slot, never from code.** Every agent calls `get_character()` (`agents/character.py`). There is **no in-code fallback character** — if the slot is missing, unparseable, or omits a required key, `get_character()` raises `CharacterError` (fail loud) rather than silently rendering Arbi. The character's visual identity MUST be preserved across all image/video generation — for instance #0 that means golden-yellow furry monster, gold crown, googly eyes (canonical asset: `arbi-king.png` in the host cabinet) — but the engine reads that requirement from the slot, it does not hardcode it.
- Video format: MP4 H.264, 1:1 aspect ratio, 30fps, ~13s (10s + 3s outro)
- JSON responses from LLMs: strip markdown fences before parsing
- No automated tests — verify via logs and generated output
- Claude Code skill in `.claude/commands/video.md` triggers the pipeline
- **Versioning is a promise about the slot contract.** Bump `VERSION` for any engine change; bump `Contract-Revision` in `CONTEXT.md` (a MAJOR) only when the required slots / read interface change incompatibly. `/update` refuses to silently cross a contract bump. See `../../foundation/_planning/distribution-and-versioning.md`
- **Subject switch on undownloadable video**: If Video Finder cannot download any video for the chosen event, the pipeline switches to a different trending subject (up to 3 attempts). Failed events are excluded from Video Scout so we do not retry the same undownloadable event.

## Character: the BRAND & VOICE slot (instance #0 = Arbi)

The character is **not** defined in this product. It is read at runtime from the host cabinet's **BRAND & VOICE slot** — the fenced `character:` block in the doc the host maps to that slot (instance #0: `brand/arbi-character.md`), loaded by `get_character()` in `agents/character.py`. There is **no in-code fallback**: a missing or incomplete slot fails loud with `CharacterError`. See `CONTEXT.md` for the full contract.

**Example — instance #0 (Arbi):** a golden-yellow furry monster with a gold studded crown (tilted), mismatched googly eyes, cream-white fluffy belly, two tiny lower fangs, Pixar 3D style; chaotic-neutral troll energy — causes hilarious mayhem but never mean-spirited; canonical asset `arbi-king.png`. This is *how instance #0 fills the slot*, not what the engine is — another cabinet drops in its own `character:` block and the same code renders that character.

## Post-Edit Checklist

After making any code change, always check if `README.md` needs updating. Update it when:

- The agent sequence changes
- An agent is added, removed, renamed, or its behavior changes
- New environment variables or dependencies are added/removed
- The output format or cost changes
- New files/directories are introduced or existing ones moved
- Run commands, setup steps, or system requirements change
- `CLAUDE.md` itself should also be kept in sync with any structural changes
- **A character literal ("Arbi", "golden-yellow", "troll", "crown") creeps into engine code, a prompt template, a config default, or an example** — that fails the portability test (`CONTEXT.md` §5). Route it through the BRAND & VOICE slot instead.

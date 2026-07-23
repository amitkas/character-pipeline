# Arbi Flow — Project Guide for Claude

## What This Is

**Arbi Flow** (the `character-pipeline` runtime) is a **portable, character-driven video engine**: one character slot, **two engines (recipes)** built on a shared, brand-free `studio-skills` package.

- **Engine A (Reactive, existing)** — the creative pipeline (SENSE → GROUND → TAKE → RENDER → DISTRIBUTE → LEARN) run against **whatever context layer it is installed into**. It finds trending real-world events and produces animated videos of a **host-defined character** re-enacting them with physical comedy, signature sounds, and overlays. Videos are saved locally or optionally auto-uploaded to YouTube.
- **Engine B (Scripted, new)** — a human-authored **beat JSON** (M clips: reference image + visual direction + optional scripted line each) → one muxed vertical mp4. No trend-finding, no chaos angle — the human wrote the beat. A free keyframe-conform gate lets you review every clip's reference image before any paid render runs. See `docs/beat-schema.md` (the input contract) and `docs/character-lock.md` (how a character identity stays on-model across both engines).

Both engines are **recipes** — deterministic compositions of shared skills with no LLM in the locked render chain — and neither depends on the other; they both depend *down* on `studio-skills`.

**Neither engine contains a character.** Who the character is, how it sounds, and what it looks like are read at runtime from the host cabinet's **context slots** (BRAND & VOICE, VOICE, CHARACTER IMAGE, AUDIENCE) through one configurable context root. Arbi Labs is just **instance #0** — the first cabinet whose slots happen to be filled in. Point the same checkout at a different `STUDIO_CONTEXT_ROOT` (legacy `CABINET_CONTEXT_ROOT` still honored as a fallback for one version) and it runs that cabinet's character. The contract is declared in **`CONTEXT.md`** (read it before touching agent code) and resolved by `context_root.py`.

> **The portability test that governs every line of code and docs:** *Would this survive being copied, untouched, into another business's cabinet — pointed at their context root, reading their docs?* If a line hardcodes "Arbi", "golden-yellow", "troll", or "crown" in the engine, it fails — that is host content, and it belongs in the host's BRAND & VOICE slot, not in the product. This includes render **style**: the art theme (e.g. "Pixar 3D") is not a constant either engine bakes in — it is instance #0's *value* for the BRAND & VOICE slot's optional `animation_style` key (see `CONTEXT.md` §3, §5).

## Pipeline

| Pipeline | Command | Skill | What It Produces | Time | Cost |
|----------|---------|-------|-----------------|------|------|
| **Video (Engine A)** | `python3 main.py` | `/video` | Animated video of the character re-enacting an event (~13s, 1:1) | ~5 min | ~$0.77 |
| **Scripted (Engine B)** | `python3 main.py scripted <beat.json>` | the `scripted` CLI verb | One muxed vertical mp4 from a beat (M clips, image-to-video + optional voice + captions). Free keyframe gate first (`--keyframe-only`, zero spend) before any paid render. | varies with clip count | ~$0.35–0.70/clip (Kling) + ElevenLabs cents/clip |

## Tech Stack

- **Python 3.10+** — all source code
- **Google Gemini 2.5 Flash** — trend detection, video analysis, image generation, text generation (Engine A)
- **fal.ai (Kling 2.5 Turbo Pro)** — AI video generation from image (both engines)
- **ElevenLabs** — text-to-speech character sounds (both engines)
- **Serper** — video search (Engine A)
- **ffmpeg** — frame extraction, audio compositing, video encoding (system dep)
- **yt-dlp** — video downloading (Engine A)
- **`studio-skills`** — standalone, brand-free package of dual-face skills (Python core + `SKILL.md` manifest + `python3 -m ...` CLI face), pinned in `requirements.txt` to `git+https://github.com/amitkas/studio-skills.git@v0.1.0`. Engine B is built entirely on it; Engine A's producer (`agents/video_producer.py`) now shares two of its skills. Round-1 skills used here: `studio_skills.render.image_conform`, `studio_skills.render.kling_image_to_video`, `studio_skills.render.flux_kontext_scene_still`, `studio_skills.audio.scripted_tts`, `studio_skills.assembly.scene_assemble`, plus `studio_skills.common.ffmpeg` helpers. Engines depend **down** on skills only — they never depend on each other.

## How to Run

```bash
pip install -r requirements.txt
cp .env.example .env                # fill in API keys
python3 main.py                     # run full video pipeline (Engine A, ~5 min, ~$0.77)
python3 main.py --resume <run_id>   # resume a failed run from last step
python3 main.py --upload [run_id]   # upload to YouTube (latest or specific run)
```

Or use Claude Code skill: `/video`

**Engine B (scripted):**

```bash
python3 main.py scripted beats/X.json --keyframe-only   # FREE gate: conform each clip's reference keyframe, zero API spend
python3 main.py scripted beats/X.json                    # full render (image-to-video + voice spend)
python3 main.py scripted beats/X.json --clip <clip_id>    # only run one clip from the beat
python3 main.py scripted beats/X.json --concat-preview    # after a full render, stitch a local pacing-check preview mp4
```

Author a beat against `docs/beat-schema.md` (worked examples in `beats/_examples/`); always run `--keyframe-only` first — it costs nothing and catches a bad reference-image path before any paid clip renders.

## Two Engines

Both engines are **recipes** — deterministic compositions of `studio-skills` calls with zero runtime judgment/LLM in the locked render chain — and each depends **down** on `studio-skills` only, never on the other engine:

- **Engine A (Reactive)** — 11-agent recipe, `python3 main.py`. Trend → chaos angle (Creative Director) → animated video. See "Architecture — Engine A" below.
- **Engine B (Scripted)** — 4-agent recipe, `python3 main.py scripted <beat.json>`: **Keyframe Conformer → Scripted Video Producer → Scripted Voice → Scene Assembler**, driven entirely by a human-authored beat JSON (`docs/beat-schema.md`). No trend-finding, no angle-deciding agent — the human already decided what the video is. See "Architecture — Engine B" below.

## Architecture — Engine A

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

## Architecture — Engine B

```
main.py scripted <beat.json> → pipelines/scripted.py → orchestrator.py → 4 agents:
  1. Keyframe Conformer      (studio_skills.render.image_conform — FREE gate)
  2. Scripted Video Producer (studio_skills.render.kling_image_to_video — the $ step)
  3. Scripted Voice          (studio_skills.audio.scripted_tts)
  4. Scene Assembler         (studio_skills.assembly.scene_assemble — concat → outro → music)
```

All four agents are **thin loops over the beat's clips** — the real transform/render/synthesis/assembly work lives in `studio-skills`; each agent's own job is resolving a slot read (character style, caption style, voice fallback) and passing explicit values into the skill. `--keyframe-only` runs step 1 only (zero spend); a full render runs all four.

### Scripted Pipeline (4 agents)

| # | Agent | File | What It Does |
|---|-------|------|-------------|
| 1 | Keyframe Conformer | `agents/keyframe_conformer.py` | Free/local/pure: center-crop + resize each clip's reference image to its target aspect ratio via `studio_skills.render.image_conform`. Missing/unresolvable reference image → that clip is skipped (logged), not a run-aborting error. |
| 2 | Scripted Video Producer | `agents/scripted_video_producer.py` | Renders each clip's conformed keyframe + prompt into an mp4 via Kling 2.5 Turbo Pro (`studio_skills.render.kling_image_to_video`). The prompt's **style** words come from `video_style_prefix(get_character())` (BRAND slot's `animation_style`, fallback `visual_short`) — never baked; the beat's `animation_direction` supplies motion/camera only. |
| 3 | Scripted Voice | `agents/scripted_voice.py` | Synthesizes each clip's `script_line` via ElevenLabs (`studio_skills.audio.scripted_tts`). `voice_id` falls back to the BRAND slot's `sound.voice_id`. Deliberate cost guard: an empty or `[PLACEHOLDER...]` `script_line` refuses to spend and ships that clip silent. |
| 4 | Scene Assembler | `agents/scene_assembler.py` | Resolves caption style (neutral defaults ← BRAND slot's `caption_style` ← beat's `assembly.subtitle_style`) and host-relative asset paths, then calls `studio_skills.assembly.scene_assemble` to build each clip's segment and concat → append outro → mix music into one finished mp4. |

## Key Files

| File | Purpose |
|------|---------|
| `main.py` | Entry point with CLI: `python main.py [--resume\|--upload <run_id>]` |
| `orchestrator.py` | Pipeline runner (config, logging, agent loop, summary, auto-cleanup) |
| `config.py` | Loads `.env`, validates required API keys; declares the `CONTEXT_*` context-slot env vars |
| `context_root.py` | Context Layer Contract resolver — `STUDIO_CONTEXT_ROOT` + slot map (see `CONTEXT.md`) |
| `VERSION` | Engine semver (`MAJOR.MINOR.PATCH`). Paired with the `Contract-Revision: N` stamp in `CONTEXT.md` |
| `version.py` | Fail-loud reader for `VERSION` + contract revision; logged at run start and written into every run summary |
| `scripts/update_engine.py` | The `/update` mechanism (propagation model B): stage → reviewable diff + risk → apply (with backup) → rollback. Never touches context slots, `.env`, tokens, or `data/` |
| `.engine-manifest.txt` | The set of engine-owned files the last `/update` installed (used to compute safe deletions; never lists per-instance files) |
| `dedup.py` | Prevents reprocessing same events (with file locking for concurrent runs) |
| `logger.py` | Logging setup: console (INFO), file (DEBUG), JSON summary |
| `context/base.py` | `BaseContext` dataclass — shared pipeline state |
| `context/video.py` | `VideoContext(BaseContext)` — video-specific fields (Engine A) |
| `context/scripted.py` | `ScriptedContext(BaseContext)` — Engine B fields: parsed `beat`, `beat_dir`, `clip_filter`, `keyframe_only`, and per-clip artifact maps (`keyframe_paths`, `clip_video_paths`, `clip_audio_paths`) keyed by `clip_id` |
| `pipelines/video.py` | Video pipeline definition (Engine A — agent list + context factory) |
| `pipelines/scripted.py` | Scripted pipeline definition (Engine B — `SCRIPTED_AGENTS` list + `make_context()`; `--keyframe-only` runs just agent 1; `--concat-preview` stitches a local pacing-check mp4 after a full render) |
| `agents/character.py` | Loads the BRAND & VOICE slot (`character:` block) into a `Character` via `get_character()`; agents read this, never baked literals. Validates required keys and raises `CharacterError` if any is missing — **no in-code fallback character**. Also defines `video_style_prefix()` (returns `animation_style` if set, else `visual_short`) — the one path either engine's producer reads render style through. |
| `agents/creative_director.py` | Owns the chaos angle (Engine A only); reads the BRAND & VOICE slot + AUDIENCE slot |
| `agents/keyframe_conformer.py` | Engine B, step 1 — the free keyframe-conform gate (`studio_skills.render.image_conform`) |
| `agents/scripted_video_producer.py` | Engine B, step 2 — Kling image-to-video render per clip (`studio_skills.render.kling_image_to_video`); reads render style via `video_style_prefix()` |
| `agents/scripted_voice.py` | Engine B, step 3 — ElevenLabs voice-over per clip (`studio_skills.audio.scripted_tts`); refuses to spend on placeholder/empty `script_line` |
| `agents/scene_assembler.py` | Engine B, step 4 — resolves caption style + host-relative asset paths, then concat → outro → music via `studio_skills.assembly.scene_assemble` |
| `beats/_examples/` | Worked beat-JSON examples for Engine B (`example_two_clip.json`, `example_realworld_cut.json`) |
| `utils/*.py` | Shared utilities (JSON parsing, ffmpeg wrappers, video processing) |
| `scripts/setup_youtube_auth.py` | One-time OAuth setup for YouTube uploads |
| `scripts/generate_outro.py` | Regenerate a branded outro clip |
| `CONTEXT.md` | **The Context Layer Contract** — the slots the runtime reads, how, and what must never be baked in. Read before editing agents. |
| `docs/beat-schema.md` | Engine B's input contract — every beat-JSON key, its type, and how paths resolve. Read before authoring a beat. |
| `docs/character-lock.md` | Character-authoring canon — how a locked character identity (hero image, DNA block, proof sheet, provenance manifest) stays on-model across both engines and feeds the BRAND & VOICE / CHARACTER IMAGE slots. |

## Directory Layout

```
main.py                   # Entry point — runs video pipeline, --resume, --upload
orchestrator.py           # Pipeline runner with auto-cleanup
config.py                 # Loads .env, validates API keys, declares CONTEXT_* slots
context_root.py           # Context Layer Contract resolver (STUDIO_CONTEXT_ROOT + slots)
dedup.py                  # Tracks processed events (with file locking)
logger.py                 # Logging setup
CONTEXT.md                # The Context Layer Contract (slots, read interface, no-bake rules)
context/
  base.py               # BaseContext — shared pipeline state
  video.py              # VideoContext — video-specific fields (Engine A)
  scripted.py           # ScriptedContext — beat + per-clip artifact maps (Engine B)
pipelines/
  video.py              # Video pipeline (Engine A — agent list + context factory)
  scripted.py           # Scripted pipeline (Engine B — SCRIPTED_AGENTS + make_context())
agents/
  character.py          # Loads BRAND & VOICE slot (character: block) → Character via get_character(); fails loud if a required key is missing (no fallback); also video_style_prefix()
  video_scout.py        # Finds trending events (applies the slot's off-limits list)
  video_finder.py       # Downloads source video
  video_analyzer.py     # Analyzes video (neutral play-by-play)
  creative_director.py  # Owns the chaos angle (after the tape is seen)
  cartoonist.py         # Dresses the character
  script_writer.py      # Animation direction
  video_producer.py     # Generates animated video (Engine A; shares studio_skills.render skills)
  voice_actor.py        # Character sounds (per the slot's sound spec)
  subtitle_burner.py    # Burns overlays (optimized ffmpeg drawtext)
  outro_stitcher.py     # Appends host-supplied outro
  youtube_uploader.py   # Uploads to YouTube (automatic when token exists)
  keyframe_conformer.py     # Engine B, step 1 — free keyframe-conform gate
  scripted_video_producer.py # Engine B, step 2 — Kling image-to-video per clip
  scripted_voice.py         # Engine B, step 3 — ElevenLabs voice-over per clip
  scene_assembler.py        # Engine B, step 4 — concat → outro → music
utils/                    # Shared utilities
  json_utils.py         # LLM JSON parsing
  ffmpeg_utils.py       # ffmpeg wrappers (run, metadata, trim, etc.)
  video_utils.py        # Video processing (square conversion, concat)
beats/
  _examples/             # Worked beat-JSON examples for Engine B
scripts/                  # One-time/rare utilities
  setup_youtube_auth.py # OAuth setup for YouTube
  generate_outro.py     # Regenerate a branded outro clip
artifacts/                # Per-run working dirs (cleaned per run)
  images/               # Generated images
  audio/                # Audio files
  videos/               # Video files
  keyframes/{run_id}/   # Engine B — conformed keyframes from the free gate
  scripted/{run_id}/    # Engine B — per-clip renders + assembled output
data/
  processed_events.json # Dedup tracking
  trend_cache.json      # Cached trends
logs/
  {run_id}.log          # Debug log
  {run_id}_summary.json # Machine-readable run summary
output/                   # Final videos ready for upload
docs/
  beat-schema.md        # Engine B's input contract
  character-lock.md     # Character-authoring canon (both engines)
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
├── VideoContext (context/video.py) — video-specific fields (source video, analysis, animation, audio) — Engine A
└── ScriptedContext (context/scripted.py) — beat + beat_dir, clip_filter, keyframe_only, and per-clip
    artifact maps (keyframe_paths, clip_video_paths, clip_audio_paths) keyed by clip_id — Engine B
```

## Required Environment Variables

```
GEMINI_API_KEY, SERPER_API_KEY, FAL_KEY, ELEVENLABS_API_KEY
```

Optional:
- `PERPLEXITY_API_KEY` (fallback trend source)
- `YOUTUBE_UPLOAD_ENABLED=false` (opt-out: disable auto-upload; upload is automatic when `youtube_token.json` exists)

Context Layer Contract (all optional; defaults resolve to instance #0 — see `CONTEXT.md` §2–§3):
- `STUDIO_CONTEXT_ROOT` — host cabinet root; default = this cabinet
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
- **Sandbox must be OFF for fal.ai and ElevenLabs calls** (both engines) — fal.ai's HTTP/2 usage and ElevenLabs' streaming both break through a sandbox proxy. Full detail lives in the relevant `studio-skills` `SKILL.md` (`render/kling_image_to_video`, `render/flux_kontext_scene_still`, `audio/scripted_tts`), not duplicated here.
- **Kling has a ~1–1.5s ease-in** at the start of a rendered clip. Engine B's beat schema accounts for this via `assembly.vo_offset_sec` (delays every clip's voice-over to clear it) — see `docs/beat-schema.md`. A caller muxing a Kling clip against voice-over directly, without that offset, will hear the VO start before the motion does.

## Character: the BRAND & VOICE slot (instance #0 = Arbi)

The character is **not** defined in this product. It is read at runtime from the host cabinet's **BRAND & VOICE slot** — the fenced `character:` block in the doc the host maps to that slot (instance #0: `brand/arbi-character.md`), loaded by `get_character()` in `agents/character.py`. There is **no in-code fallback**: a missing or incomplete slot fails loud with `CharacterError`. See `CONTEXT.md` for the full contract.

**Example — instance #0 (Arbi):** a golden-yellow furry monster with a gold studded crown (tilted), mismatched googly eyes, cream-white fluffy belly, two tiny lower fangs; chaotic-neutral troll energy — causes hilarious mayhem but never mean-spirited; canonical asset `arbi-king.png`. This is *how instance #0 fills the slot*, not what the engine is — another cabinet drops in its own `character:` block and the same code renders that character.

**Render style is a slot value too, not an engine constant.** *(2026-07-23.)* The old baked "Pixar 3D" style literal was removed from `video_producer.py`, `video_producer_grok.py`, and `cartoonist.py`; both engines now read render-style/art-theme language exclusively from `video_style_prefix()` (`agents/character.py`), which returns the BRAND & VOICE slot's optional `animation_style` key if set, else falls back to `visual_short`. **"Pixar 3D" is instance #0's example fill for `animation_style`** — a host-content example, not engine behavior — and instance #0 sets it as a host-side follow-up (a slot fill, not a code change). See `docs/character-lock.md` §2 for the full prompt-contract rule ("style language comes only from the DNA block — never from engine code") and `CONTEXT.md` §3/§5 for the contract stamp.

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

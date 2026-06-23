# Arbi Flow

A **portable, character-driven trend-to-video engine**. It finds trending real-world events and produces animated square videos of a **host-defined character** re-enacting them with physical comedy, signature sounds, and overlays. The engine ships with **no character of its own** — who the character is, how it sounds, and what it looks like are read at runtime from the host's context slots (see [`CONTEXT.md`](CONTEXT.md)). **Arbi** — the golden-yellow furry troll — is just **instance #0**, the first cabinet whose slots are filled in. Point the same checkout at a different context root and it runs that cabinet's character.

**Output:** ~13-second MP4 (1:1 square, H.264, 30fps) — 10s video + 3s outro — saved locally or optionally auto-uploaded to YouTube.

**Want to create your own character-driven trend-to-video pipeline?** See **[How to Create Your Own Arbi](docs/BUILD_YOUR_OWN_ARBI.md)** — a guide for growth marketers (organic, community, social, paid) at startups, with Arbi as the worked example.

---

## Get Started with Cursor / Claude Code

The easiest way to run Arbi — no terminal experience needed. Claude guides you through every step.

**Prerequisites:** [Cursor](https://cursor.com) or [Claude Code](https://claude.ai/code) installed.

1. **Clone or use this template** on GitHub → open the folder in Cursor
2. **Type `/setup`** in the Cursor chat — Claude walks you through installing dependencies and getting your 4 API keys (~5 min)
3. **Type `/video`** — Claude runs the full pipeline and reports back when your video is ready

That's it. Each run takes ~5 minutes and costs ~$0.77.

**Other commands:**
- `/video-pick` — Scout finds 3 trending events, you choose which one the character re-enacts
- `/video-custom` — You name a specific event for the character to re-enact
- `/update` — Pull a newer engine version into your install (staged, reviewable, reversible — see [Versioning & updates](#versioning--updates))

---

## Quick Start (CLI)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env
# Open .env and fill in your keys (see "API Keys" below)

# 3. Run the pipeline
python3 main.py                     # Full pipeline
python3 main.py --resume <run_id>   # Resume a failed run
python3 main.py --upload [run_id]   # Upload to YouTube (latest or specific run)
```

---

## Versioning & updates

This engine ships as a **pinned version**. The current version lives in the [`VERSION`](VERSION) file (semver `MAJOR.MINOR.PATCH`) and the slot-contract revision it requires is stamped in [`CONTEXT.md`](CONTEXT.md) (`Contract-Revision: N`). Every run logs the stamp and writes it into the run summary (`logs/{run_id}_summary.json`), so you can always tell what produced a video.

```bash
python3 version.py        # print the engine version + contract revision
```

**Staying current — propagation model B** (the engineering rationale is in [`../../archive/distribution-and-versioning.md`](../../archive/distribution-and-versioning.md)): your install is your own; a new engine version arrives via the `/update` skill, which swaps **engine code only** and **never touches** your context (`brand/`, `foundation/`), your `.env`, `youtube_token.json`, or your `data/`/`logs/`/`output/`. It stages a reviewable diff with a risk level before changing anything, and every apply is reversible.

```bash
# stage & review (no changes) — shows version transition, RISK, and the file diff
python3 scripts/update_engine.py --source <engine-dir-or-git-url>
# apply after reviewing (HIGH risk also needs --allow-major)
python3 scripts/update_engine.py --source <...> --apply
# roll back
python3 scripts/update_engine.py --list-backups
python3 scripts/update_engine.py --rollback [BACKUP_ID]
```

| Risk | Meaning | Behavior |
|------|---------|----------|
| **LOW** | PATCH — internal fix, contract unchanged | Safe to apply |
| **MEDIUM** | MINOR — new capability, contract backward-compatible | Safe to apply |
| **HIGH** | MAJOR, slot-contract change, or downgrade | Refused without `--allow-major`; a contract bump means re-running `/setup` to fill new/changed slots |

The easiest path is the **`/update`** skill, which runs the stage→review→apply→rollback flow for you.

---

## How the character works

The engine reads its character from the host's **BRAND & VOICE slot** — the fenced `character:` block in the doc the host maps to that slot — via `get_character()` in `agents/character.py`. Every agent reads that one source; no agent bakes a character in. The canonical reference image comes from the **CHARACTER IMAGE slot** (`CONTEXT_CHARACTER_IMAGE`, alias `ARBI_CHARACTER_IMAGE`), and the branded outro/music come from the **BRANDED ASSETS slots** (skipped if unset). See [`CONTEXT.md`](CONTEXT.md) for the full contract.

When the pipeline finds a trending event, the character gets dressed in whatever the main person was wearing (suit, dress, jersey — you name it) and re-enacts the event with over-the-top physical comedy. Instead of narration, it makes its signature sounds (for instance #0: gibberish troll noises, maniacal laughter).

### Meet Arbi (instance #0 — the example)

Arbi is how **instance #0** fills the BRAND & VOICE slot: a wacky golden-yellow shaggy furry monster with a cream-white fluffy belly, a gold studded crown (slightly tilted), mismatched googly greenish eyes under thick brows, a small pink nose, and two tiny lower fangs on a round chubby body, rendered in Pixar 3D style — an internet troll personality, chaotic, mischievous, and hilariously unhinged (canonical asset: `arbi-king.png`). This is one cabinet's answer, not the engine — another cabinet drops in its own `character:` block.

### Using your own character

The engine itself is character-free, so you don't edit Python to swap the character. Point it at your cabinet and fill the slots:

| Slot | Env var | Provide |
|------|---------|---------|
| **BRAND & VOICE** | `CONTEXT_BRAND` | A doc with a fenced `character:` block: name, tagline, voice, visual identity, personality, off-limits topics, sound spec, distribution metadata |
| **CHARACTER IMAGE** | `CONTEXT_CHARACTER_IMAGE` | One canonical reference PNG of your character (same pose/style works best) |
| **BRANDED ASSETS** | `CONTEXT_OUTRO`, `CONTEXT_MUSIC_DIR` | A branded outro clip and/or music bed — omit either to skip that step (never substitutes another brand's) |
| **AUDIENCE** | `CONTEXT_AUDIENCE` | A doc with a `content_icp:` block — who the video is for and what it should do |

Set `CABINET_CONTEXT_ROOT` to your cabinet root and the same checkout runs your character. No prompt edits — `get_character()` feeds every agent.

---

## Video Pipeline (11 agents)

```
Video Scout → Video Finder → Video Analyzer → Creative Director →
Character Dresser → Animation Director → Video Producer → Sound Engineer →
Subtitle Burner → Outro Stitcher → YouTube Uploader (optional)
```

~5 minutes | ~$0.77 per run

### What Each Agent Does

| # | Agent | What It Does | API / Tool |
|---|-------|-------------|------------|
| 1 | **Video Scout** | Finds the most notable real-world event from the last 24 hours in mainstream media (event + search query only — no longer decides the angle) | Gemini (Google Search grounding) |
| 2 | **Video Finder** | Searches for the video URL, downloads it, extracts first frame | Serper + yt-dlp + ffmpeg |
| 3 | **Video Analyzer** | Watches the video, gives a neutral play-by-play, detects outfit & gender | Gemini 2.0 Flash (multimodal) |
| 4 | **Creative Director** | Decides the **chaos angle** AFTER watching the tape, from the Analyzer's description + the character's full persona (BRAND & VOICE slot) + the AUDIENCE slot's `content_icp:` block | Gemini 2.5 Flash |
| 5 | **Character Dresser** | Dresses the character in the main subject's outfit, places it in the scene | Gemini Image Generation |
| 6 | **Animation Director** | Writes physical comedy animation direction for the character's behavior, prioritizing the chaos angle | Gemini 2.0 Flash |
| 7 | **Video Producer** | Animates the dressed character, injecting chaos angle into Kling prompt | Kling 2.5 Turbo Pro (fal.ai) |
| 8 | **Sound Engineer** | Generates the character's signature gibberish/sound (label, voice ID, pitch from the slot's sound spec) with real keywords, composites onto video | ElevenLabs + ffmpeg |
| 9 | **Subtitle Burner** | Burns event title overlay at the top + timed keyword subtitles at the bottom | ffmpeg drawtext filter (optimized, 5-10x faster than old approach) |
| 10 | **Outro Stitcher** | Appends a host-supplied branded outro clip to the end of the video (skipped if no BRANDED ASSETS slot) | ffmpeg |
| 11 | **YouTube Uploader** | (Optional) Uploads final video to YouTube as a public Short | YouTube Data API v3 |

Each agent is a standalone Python function: `agent(ctx, config) -> ctx`. They communicate through a shared context dataclass. If any agent fails, the pipeline aborts immediately (except YouTube Uploader, which is non-fatal). **Exception:** if Video Finder cannot download any video for the chosen event, the pipeline switches to a different trending subject (up to 3 attempts) instead of failing.

---

## TAKE-as-Artifact (one take → N render paths)

The video pipeline is split at **the seam**: a **TAKE phase** that decides *what* the
video is (the POV, the line, the visual direction), and a **RENDER phase** that produces
*how* it looks. The TAKE phase runs **once** and persists a flat take file; each render
path then hydrates a fresh context from that file. This makes "one take, two render
techniques" a loop instead of an impossibility.

```
── TAKE phase (runs once) ───────────────────────────────────────
  Video Scout → Video Finder → Video Analyzer → Creative Director → Animation Director → Take Emitter
                                                                       └─ writes data/takes/{take_id}.json
── RENDER phase (once per selected path, from the same take) ─────
  fal+elevenlabs (9:16):  Character Dresser → Video Producer (Kling) → Sound
                          Engineer → Subtitle → YouTube (optional)
  grok (9:16):            Character Dresser → Video Producer (Grok, video+narration
                          in one) → Subtitle → YouTube (optional)
                                                   └─ each appends a row to data/learn_log.jsonl (only when a real asset is produced)
```

Both render paths target **9:16** (vertical-feed native — YouTube Shorts / TikTok / Reels;
see `foundation/_planning/social-video-format-specs.md`). The branded outro is paused for now.

- **`take.py`** — `Take` dataclass + `emit_take` / `write_take` / `load_take`. The take is
  six fields (`take_id`, `schema_version`, `created_at`, `voice_tag`, `event`, `angle`,
  `line`, `visual_direction`). `voice_tag` is a **pointer** to the character bible, never
  the voice itself; the cartoon image is **not** in the take (it's a render artifact).
- **`agents/take_emitter.py`** — the seam agent: builds the take from ctx, writes the file,
  sets `ctx.take_id`. Terminal step of the TAKE phase.
- **`pipelines/video.py`** — `TAKE_AGENTS` + a `RENDER_PATHS` dict. Aspect ratio is lifted
  into each path's config (the free second axis), so the aspect ratio varies with no code edit.
- **`orchestrator.py`** — `run_take_and_render(...)` runs the TAKE phase once, then loops the
  selected paths via `run_render_path(...)`, each starting from `load_take(take_id)`.
- **`learn.py`** — `append_learn(...)` → `data/learn_log.jsonl`, one append-only row per
  asset, keyed by `take_id`. `control_of_script` is `true` for fal+elevenlabs (we keep the
  script) and `false` for grok (the technique takes it). `engagement_rate` / `impressions`
  stay `null` until channel data connects.

Run it with a human in the loop (the phase commands map to the approval gates):

```bash
python3 main.py take --pick                              # TAKE phase → persist → STOP (review the take)
#   ↳ review/edit data/takes/{take_id}.json (angle, line, visual direction)
python3 main.py render <take_id> --paths fal+elevenlabs,grok   # render approved take → stage in output/
python3 main.py publish <take_id>                        # HELD — requires manual sign-off (T9)
```

The all-in-one `python3 main.py` still runs take + render in one shot (no human gate).
The **character image** comes from the CHARACTER IMAGE slot — `CONTEXT_CHARACTER_IMAGE` in
`.env` (absolute or cabinet-relative path; alias `ARBI_CHARACTER_IMAGE` is deprecated but
still honored). Instance #0 points it at Arbi's reference PNG.

Verify the architecture end-to-end with no API credentials (placeholder render, real
take/seam/loop/learn mechanics):

```bash
python3 scripts/verify_take_as_artifact.py   # checks PRD §3 acceptance criteria A–D
```

---

## How It Works

### 1. Video Scout (`agents/video_scout.py`)

Searches for the most notable real-world event covered by mainstream media using Gemini with Google Search grounding. Covers all major categories: politics, entertainment, sports, tech, science, business, culture, weather, and more. Excludes social media-native content. Falls back through a cascade: **Gemini grounded** → Gemini plain → Perplexity.

Deduplication: checks `data/processed_events.json` to avoid covering the same event twice. When retrying after an undownloadable video, also excludes events we already tried.

### 2. Video Finder (`agents/video_finder.py`)

Uses Serper's video search API to find the actual video URL, then downloads it using yt-dlp. Extracts the first frame using ffmpeg. Downloads at max 720p, skips videos longer than 2 minutes, tries up to 10 candidate URLs. If no video can be downloaded, the pipeline switches to a different trending subject (up to 3 attempts).

### 3. Video Analyzer (`agents/video_analyzer.py`)

Uploads the downloaded video to Gemini's File API for multimodal analysis. Returns a neutral play-by-play, scene prompt, outfit description, gender, people count, and audio keywords for subtitle timing. It describes the tape; it does **not** decide the angle.

### 4. Creative Director (`agents/creative_director.py`)

Owns the **chaos angle** — the comedic POV the whole video hangs on — and decides it *after* the clip has been watched (the fix from `docs/creative-director-proposal.md`). Fed three inputs: the Analyzer's video description (what literally happened on screen), the character's **full persona** (the BRAND & VOICE slot, not just the off-limits guardrails), and the **AUDIENCE** slot (the `content_icp:` block — who the video is for and what it should do). Emits the angle only; it does **not** write scripted voice lines (that voice call is a separate open design decision). The Scout no longer produces an angle.

### 5. Character Dresser (`agents/cartoonist.py`)

Uses Gemini image generation to create the character wearing the detected outfit. 3-tier fallback: full prompt with reference image → simplified prompt → text-only → raw character reference. Preserves the character's identity as read from the BRAND & VOICE slot (for instance #0: golden-yellow fur, gold crown, googly eyes).

### 6. Animation Director (`agents/script_writer.py`)

Writes a single physical comedy animation direction (15-25 words) describing what the character does. Prioritizes the chaos angle over scene context. Validated with retries for word count **and** for truncation — a direction that ends mid-sentence (no terminal punctuation, or dangling on a comma/connective word) is rejected and regenerated, not just one that is the wrong length.

### 7. Video Producer (`agents/video_producer.py`)

Generates a 10-second animated video from the dressed character image using Kling 2.5 Turbo Pro on fal.ai. Injects chaos angle into the Kling prompt for tone alignment. 1:1 square format.

### 8. Sound Engineer (`agents/voice_actor.py`)

Generates the character's signature sound via ElevenLabs with real keywords inserted, using the `sound` spec (label, voice ID, pitch, gibberish templates) read entirely from the BRAND & VOICE slot — for instance #0 that's gibberish troll noises, pitch-shifted +30% for a goblin effect. The file bakes no voice or pitch default; `get_character()` fails loud if the slot omits a required sound key. Optional background music from the `CONTEXT_MUSIC_DIR` slot at 25% volume. Composites audio onto video.

### 9. Subtitle Burner (`agents/subtitle_burner.py`)

Burns persistent event title (white, top) and timed keyword subtitles (yellow, bottom) onto every frame using PIL + ffmpeg.

### 10. Outro Stitcher (`agents/outro_stitcher.py`)

Appends a pre-rendered 3-second branded outro clip. Uses ffmpeg concat filter, normalizes to 1080x1080 @ 30fps.

### 11. YouTube Uploader (`agents/youtube_uploader.py`)

Uploads the final video to YouTube as a public Short. **Automatic:** runs on every pipeline run once `youtube_token.json` exists (no env var needed). Set `YOUTUBE_UPLOAD_ENABLED=false` in `.env` to disable. Non-fatal errors: pipeline continues even if upload fails. Includes retry logic with exponential backoff for transient API errors.

**Channel playlist:** Set `YOUTUBE_ARBI_PLAYLIST_ID` in `.env` to add every uploaded video to one playlist. Create the playlist on YouTube, then copy its ID from the URL (`youtube.com/playlist?list=PLxxxxxx`). (The env var keeps its `ARBI` name for instance #0 compatibility; any playlist ID works.)

**One-time setup:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or use an existing one
3. Enable "YouTube Data API v3"
4. Go to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Application type: "Desktop app"
6. Download the JSON credentials file and save as `client_secret.json` in the project root
7. Run: `python3 scripts/setup_youtube_auth.py`
8. A browser will open — sign in with your YouTube account and grant permissions
9. A `youtube_token.json` file will be created

After that, every pipeline run will automatically upload to YouTube. To opt out, add `YOUTUBE_UPLOAD_ENABLED=false` to `.env`.

**If you previously ran setup:** Re-run `python3 scripts/setup_youtube_auth.py` to grant playlist access (needed for the channel playlist).

---

## API Keys

### Required

| Key | Service | What It Does | Get It At |
|-----|---------|-------------|-----------|
| `GEMINI_API_KEY` | Google Gemini | Trends + video analysis + character dressing + animation direction | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `SERPER_API_KEY` | Serper | Video search | [serper.dev](https://serper.dev) |
| `FAL_KEY` | fal.ai | Kling 2.5 Turbo Pro video generation | [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys) |
| `ELEVENLABS_API_KEY` | ElevenLabs | Character sound generation (instance #0: troll gibberish) | [elevenlabs.io](https://elevenlabs.io) |

### Optional (extra trend sources)

| Key | Service | Get It At |
|-----|---------|-----------|
| `PERPLEXITY_API_KEY` | Perplexity (fallback trend detection) | [perplexity.ai](https://perplexity.ai) |

---

## Cost Per Run (~$0.77)

| Service | Purpose | Cost |
|---------|---------|------|
| Gemini 2.5 Flash (grounded) | Video Scout — find trending event | ~$0.005 |
| Serper | Video Finder — search for video URL | ~$0.002 |
| Gemini 2.5 Flash (multimodal) | Video Analyzer — understand video + detect outfit | ~$0.006 |
| Gemini 2.5 Flash Image | Character Dresser — dress the character in the outfit | ~$0.04 |
| Gemini 2.5 Flash (text) | Animation Director — write animation direction | ~$0.001 |
| ElevenLabs (eleven_v3) | Sound Engineer — signature character sound | ~$0.02 |
| fal.ai (Kling 2.5 Turbo Pro) | Video Producer — animate the character (10s × $0.07/s) | ~$0.70 |
| Local tools | Subtitle Burner, Outro Stitcher | $0.00 |

---

## Where Outputs Go

| What | Location |
|------|----------|
| **Final video (ready to upload)** | `output/{Event_Title}_{run_id}.mp4` |
| **YouTube upload (if enabled)** | Auto-uploaded to your YouTube channel as a public video |
| YouTube video URL | Logged in `logs/{run_id}_summary.json` (`youtube_video_url` field) |
| Run log (human-readable) | `logs/{run_id}.log` |
| Run summary (JSON) | `logs/{run_id}_summary.json` |
| Processed events log | `data/processed_events.json` |

Intermediate artifacts (source video, dressed image, audio) are cleaned up after each run.

### Recovering failed runs

If the pipeline fails partway (e.g. Sound Engineer times out), resume from the last completed step instead of paying for the whole run again:

```bash
python3 main.py --resume <run_id>
```

The orchestrator reloads the run's persisted context and picks up from where it stopped. For the split TAKE/RENDER flow, re-run `python3 main.py render <take_id>` — the approved take is already on disk, so only the render path re-executes.

---

## System Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| **ffmpeg** | Frame extraction, audio composite, video re-encoding | `brew install ffmpeg` (macOS) |
| **Python 3.10+** | Runtime | [python.org](https://python.org) |

---

## FAQ

### How do I customize the Character Dresser prompt?

Edit the `_build_dresser_prompt()` function in `agents/cartoonist.py`.

### How do I change the animation style?

Edit the `SYSTEM_PROMPT` in `agents/script_writer.py`.

### How do I change the character's voice?

The voice ID and label come from the `sound` spec in your **BRAND & VOICE slot** (the `character:` block) — set them there, not in code. The ElevenLabs delivery knobs in `agents/voice_actor.py` still tune *how* that voice is rendered:
- `stability` — lower = more chaotic (current: 0.0)
- `similarity_boost` — lower = more distorted (current: 0.3)
- `style` — higher = more exaggerated personality (current: 1.0)
- `speed` — higher = more manic (current: 1.4)
- `sound.pitch_shift` (in the slot) — >1.0 = higher goblin pitch, <1.0 = deeper ogre pitch (instance #0: 1.3)

The voice, label, pitch, and gibberish all come from the slot's `sound:` block — the file bakes none of them.

### How do I customize the background music?

Point the **BRANDED ASSETS** music slot (`CONTEXT_MUSIC_DIR`) at a directory of `.mp3`, `.wav`, or `.m4a` files. The pipeline randomly picks one per run, trims it to video length, and mixes it at 25% volume. Leave the slot unset to skip background music entirely (it never substitutes another brand's bed).

### How do I use a different character instead of Arbi?

You don't edit Python — the engine is character-free. Fill your cabinet's context slots and point the runtime at them (see [How the character works](#how-the-character-works) and [`CONTEXT.md`](CONTEXT.md)):

1. **BRAND & VOICE** (`CONTEXT_BRAND`) — a doc with a fenced `character:` block: name, tagline, voice, visual identity, personality, off-limits topics, sound spec, distribution metadata.
2. **CHARACTER IMAGE** (`CONTEXT_CHARACTER_IMAGE`) — one canonical reference PNG of your character.
3. **BRANDED ASSETS** (`CONTEXT_OUTRO`, `CONTEXT_MUSIC_DIR`) — optional outro clip / music bed.
4. Set `CABINET_CONTEXT_ROOT` to your cabinet root.

`get_character()` (`agents/character.py`) feeds that one source to every agent. Arbi is just instance #0's answer; another cabinet drops in its own `character:` block and the same checkout renders that character.

### What if an agent fails?

The pipeline aborts immediately. Common failures:
- **Rate limits (429):** Video Scout has built-in retry. Wait and retry.
- **yt-dlp download fails:** Video Finder tries up to 5 candidate URLs.
- **Content safety blocks:** Character Dresser falls back through 3 tiers.
- **fal.ai timeout:** Transient network issue. Retry the pipeline.

### How do I reset the processed events list?

```bash
echo '{"processed": []}' > data/processed_events.json
```

### How do I change the video duration or aspect ratio?

Edit `agents/video_producer.py`:
- **Duration:** Change `KLING_DURATION` in `video_producer.py` to `"5"` or `"10"` (Kling 2.5 Turbo Pro supports 5–10s)
- **Aspect ratio:** Change `"aspect_ratio": "1:1"` to `"9:16"` or `"16:9"` for vertical/landscape

---

## Project Structure

```
character-pipeline/
├── main.py                     # Entry point — full run, --resume, --upload, take/render/publish
├── orchestrator.py             # Pipeline runner (config, logging, agent loop, TAKE/RENDER loop)
├── config.py                   # Loads .env, validates API keys, declares CONTEXT_* slot vars
├── context_root.py             # Context Layer Contract resolver (CABINET_CONTEXT_ROOT + slot map)
├── dedup.py                    # Tracks processed events (avoid repeats, file-locked)
├── logger.py                   # Logging setup
├── take.py                     # Take dataclass + emit/write/load (the TAKE↔RENDER seam)
├── learn.py                    # append_learn → data/learn_log.jsonl (one row per asset)
├── CONTEXT.md                  # The Context Layer Contract — slots, read interface, no-bake rules
├── CLAUDE.md                   # Project guide for Claude
├── context/
│   ├── base.py                 # BaseContext — shared pipeline state
│   └── video.py                # VideoContext — video-specific fields
├── pipelines/
│   ├── video.py                # Video pipeline: TAKE_AGENTS + RENDER_PATHS (fal+elevenlabs)
│   └── video_x.py              # Grok render path (video + narration in one)
├── agents/
│   ├── character.py            # Loads BRAND & VOICE slot (character: block) → get_character(); fails loud, no fallback
│   ├── video_scout.py          # Find trending real-world event (applies slot's off-limits list)
│   ├── video_finder.py         # Download video + extract first frame
│   ├── video_analyzer.py       # Analyze video + detect outfit (neutral play-by-play)
│   ├── creative_director.py    # Decide the chaos angle (after the tape is seen)
│   ├── cartoonist.py           # Dress the character in the detected outfit
│   ├── script_writer.py        # Write animation direction
│   ├── take_emitter.py         # Seam agent — persists the take, ends the TAKE phase
│   ├── video_producer.py       # Animate the character (Kling 2.5 Turbo Pro)
│   ├── video_producer_grok.py  # Animate the character (Grok render path)
│   ├── voice_actor.py          # Generate the character's signature sound (ElevenLabs)
│   ├── subtitle_burner.py      # Add event title + keyword overlays
│   ├── outro_stitcher.py       # Append host-supplied outro (skipped if no slot)
│   └── youtube_uploader.py     # Upload to YouTube (automatic when token exists)
├── utils/                      # Shared utilities (JSON parsing, ffmpeg/video wrappers)
├── scripts/
│   ├── setup_youtube_auth.py   # One-time OAuth setup for YouTube uploads
│   ├── generate_outro.py       # Regenerate a branded outro clip
│   └── verify_take_as_artifact.py  # Offline architecture check (PRD §3 criteria A–D)
├── .claude/
│   └── commands/
│       ├── setup.md            # /setup skill — first-time onboarding
│       ├── video.md            # /video skill — auto-pick trending event
│       ├── video-pick.md       # /video-pick skill — choose from 3 events
│       ├── video-custom.md     # /video-custom skill — pin your own event
│       └── video-x.md          # /video-x skill — Grok render path
├── docs/
│   └── BUILD_YOUR_OWN_ARBI.md  # Worked example (Arbi = instance #0): build your own character pipeline
├── artifacts/                  # Per-run working dirs (cleaned per run)
│   ├── images/                 # Generated images
│   ├── audio/                  # Audio files
│   └── videos/                 # Video files
├── data/
│   ├── processed_events.json   # Dedup tracking
│   ├── trend_cache.json        # Cached trends
│   ├── takes/                  # Persisted take files ({take_id}.json)
│   └── learn_log.jsonl         # Append-only learn log (one row per asset)
├── logs/                       # Run logs and summaries
├── output/                     # Final videos ready for upload
├── .env                        # Your API keys (not committed)
├── .env.example                # Template
├── .gitignore
└── requirements.txt
```

> Brand assets (the character reference PNG, branded outro, music bed) are **host-supplied through the CHARACTER IMAGE / BRANDED ASSETS slots, not bundled** in the product. Instance #0's assets (`arbi-king.png`, etc.) live in the host cabinet.

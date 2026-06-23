# Arbi Flow (the `character-pipeline` runtime) — BRIEF

*Last updated: 2026-06-08; reframed 2026-06-13 to separate the standalone engine from its instance-#0 fill (and to fix stale `arbi_persona.py` / "red troll" references).*

## What it is

A **portable, character-driven trend-to-video engine**. Finds a real-world trending event from the last 24 hours, then generates a ~13-second animated square video of a **host-defined character** re-enacting that event with physical comedy, signature sounds, and burned-in overlays. Optionally auto-uploads to YouTube. Each run takes ~5 minutes and costs ~$0.77.

The engine ships with **no character of its own** — who the character is, how it sounds, and what it looks like are read at runtime from the host cabinet's context slots (see [`CONTEXT.md`](CONTEXT.md)). **Arbi Labs is instance #0** — the first cabinet whose slots are filled in. Instance #0's character is **Arbi**: a golden-yellow furry troll with a gold crown and googly eyes — one cabinet's fill of the BRAND & VOICE slot, never the engine's identity. (Within Arbi Labs, PlayArbi gives that character a stage; Arbi Flow gives it a feed — but that's how instance #0 uses the engine, not what the engine is.)

## Current state — what's built and working

- **Full 10-agent Python pipeline** running end-to-end: Video Scout → Video Finder → Video Analyzer → Character Dresser → Animation Director → Video Producer → Sound Engineer → Subtitle Burner → Outro Stitcher → YouTube Uploader.
- **Tool stack:** Gemini 2.5 Flash (trends, analysis, image gen, text), fal.ai Kling 2.5 Turbo Pro (video gen), ElevenLabs (troll sounds), Serper (video search), yt-dlp (video download), ffmpeg (compositing).
- **Claude Code skills installed** (`/setup`, `/video`, `/video-pick`, `/video-custom`) — anyone with Cursor or Claude Code can run it without touching the terminal.
- **Robust failure handling:** dedup tracking (`data/processed_events.json`), file locking for concurrent runs, 3-tier image-gen fallback, subject switching on undownloadable videos (up to 3 retries), non-fatal YouTube upload, resumable runs.
- **Dogfooded on instance #0:** Arbi Labs' character is authored in the host cabinet's BRAND & VOICE slot (`brand/arbi-character.md`) — visual identity, persona, content boundaries — and read at runtime via `agents/character.py`. No character is baked into the engine. Outro clip is pre-rendered (a host-supplied branded asset, not bundled).
- **Distribution-ready public guide:** `docs/BUILD_YOUR_OWN_ARBI.md` walks a reader through the engine using Arbi as the named instance-#0 worked example — the pipeline is a *generalized character-pipeline product*, not an Arbi-specific tool.
- **OAuth setup for YouTube** working (`scripts/setup_youtube_auth.py`), auto-uploads to a host-configured channel playlist (instance #0 points it at Arbi's).

## Open threads — what's incomplete or worth improving

- **Scout is not 100% trustworthy — keep a human in the loop, then add a fact-checker.** The Scout (Gemini grounded search) can surface fabricated or distorted "trending" events. On the first live test (2026-06-11) it returned two real events (Taylor Swift courtside, Trump on inflation) and one fabricated one ("Apple Vision Pro 2"). **Near-term:** a human reviews scouted events before any take is rendered or published — never trust a scouted headline as fact. **Later experiment worth testing:** a dedicated fact-checker agent that verifies each scouted event against independent sources before it enters the pipeline. Related taste note: Amit finds dry consumer-tech announcements beige; AI news and culturally-charged moments are the more interesting lane.
- **Creative Director agent (own the angle, after the video is seen).** The chaos angle is currently decided by the Scout, blind, from event text before the clip is analyzed — and with no persona depth or ICP awareness. Parked design decision to split this into a dedicated Creative Director placed after the Analyzer. Full write-up: `docs/creative-director-proposal.md`. Revisit after the first full cycle is tested.
- **Real-time trend-hunting.** Today the Scout finds "trending in the last 24 hours." The bigger bet: detect a trend the *moment* it spikes and ship matching creative inside the same news cycle. This is a top-priority hypothesis (see foundation doc section 7). World Cup 2026 is the live test.
- **Output cadence + scheduling.** Currently a manual `python3 main.py`. No scheduler, no daily/hourly auto-run, no queue. Cabinet's scheduled jobs solve this cleanly.
- **Multi-character / multi-style support — largely resolved since this brief was first written.** The engine is now character-free: it reads the character from the host cabinet's BRAND & VOICE slot at runtime (the Context Layer Contract — see `CONTEXT.md`), so pointing it at a different cabinet swaps the character with no code edit. Remaining nicety: a single typed `character.yaml` authoring format to make filling the slot even easier.
- **No measurement loop.** No tracking of which videos performed on YouTube, which trends converted to views, which chaos angles landed. Adding a results-back-into-Scout loop would let the system learn what's working.
- **No formats other than YouTube Shorts.** Square 1:1, ~13s. Doesn't yet output for TikTok, IG Reels, X/Twitter video, vertical 9:16. The Kling config supports it (aspect ratio is a parameter) — just not wired into the pipeline yet.
- **No "publish to X/TikTok/IG" agent** to match the YouTube Uploader. Half the distribution surface is missing.
- **Cost ceiling.** ~$0.77/run × N runs/day adds up fast. No budget guardrails or per-channel cost reporting.

## Cabinet role — what it looks like as an embedded app

Inside the Arbi Labs Cabinet workspace, this becomes `products/character-pipeline/`:

- The Python pipeline runs as-is, exposed via a thin HTML control panel at `products/character-pipeline/index.html` — "Run now," "View last 10 runs," "Schedule daily."
- Cabinet's **scheduled jobs** layer drives auto-runs (daily, hourly, or triggered by a trend-detection job).
- The character bible and chaos angles live as markdown in the KB at `brand/arbi-character.md` (instance #0's BRAND & VOICE slot), read at runtime by the engine's loader (`agents/character.py`), so the pipeline reads from the same source of truth as everything else in the cabinet.
- Run logs and processed-events tracking land in `products/character-pipeline/data/` — version-controlled with the KB, queryable by other agents.
- Other Cabinet agents can read the pipeline's output and act on it (e.g., a Social Distribution agent reads `output/` and posts to X with on-brand copy).

**The bigger move:** once it's a Cabinet app inside the studio, it ports to *any* other Cabinet workspace as a templated tool. A solo founder installs PixelDrop's twin app into their Cabinet, swaps `brand/character.md` for their own persona, and they have a character-driven content engine in 30 minutes. That's the productization path.

## Next experiment

**Real-time trend-hunting around World Cup 2026.** Build a "trend spike" detector that runs every 15 minutes during the tournament, watches for surges in sports news mentions, and triggers a pipeline run within the same hour the event happens. Goal: be the first character account on YouTube/X commenting on a goal, a controversy, or a result. Measure: time-to-publish (target: under 60 minutes from event), views, follower growth.

## Key files for anyone reading the code

| File | Purpose |
|---|---|
| `CLAUDE.md` | Full project guide for any Claude session working in this repo |
| `README.md` | Public-facing readme |
| `main.py` | Entry point, CLI |
| `orchestrator.py` | Pipeline runner with auto-cleanup |
| `pipelines/video.py` | Video pipeline definition |
| `agents/character.py` | Loads the host's BRAND & VOICE slot (the `character:` block) via `get_character()` — no character baked into the engine; fails loud if a required slot key is missing |
| `agents/*.py` | One file per pipeline step |
| `docs/BUILD_YOUR_OWN_ARBI.md` | Public guide for marketers building their own version |
| `.claude/commands/` | Claude Code / Cursor skills (`/setup`, `/video`, etc.) |
| `data/processed_events.json` | Dedup tracking |
| `output/` | Final videos ready for upload |

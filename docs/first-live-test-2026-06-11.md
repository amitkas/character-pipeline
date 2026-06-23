# First live test of the Arbi Flow — 2026-06-11

*Working session: Amit + Arbi (partner). First time the pipeline ran against real APIs.*

## What we ran

- **Scout (live):** Gemini grounded returned 3 events. Amit's read: Swift + Trump real, "Apple Vision Pro 2" fabricated; dry tech announcements are beige, AI news is the more interesting lane. (See `BRIEF.md` open threads + memory.)
- **Take (pinned):** `python3 main.py take --event "Taylor Swift Courtside at NBA Finals Game 4" --description "..."` → `tk_57b5b57c`. Pulled a real Instagram source clip, analyzed it, persisted the take. ~22s.
- **Human review gate:** caught a truncated `line` (Animation Director output ended mid-clause on a stray quote). Fixed in the take file by hand before rendering.
- **Render (both paths):** `python3 main.py render tk_57b5b57c --paths fal+elevenlabs,grok` (publish held; no YouTube token present).

## Result

| Path | Outcome | Asset |
|---|---|---|
| **fal+elevenlabs** | ✅ Real video, but **silent** | `output/tk_57b5b57c__fal-elevenlabs__9x16.mp4` — 1080×1920, 10.0s, 16MB, H.264 |
| **grok** | ❌ Crashed, no asset | none |

**Character quality (fal path):** Arbi on-model — red fur, gold crown, mismatched googly eyes, white belly; correctly dressed in the detected Knicks tee + ripped denim + crossbody bag. Composited into an arena crowd. Looks good for a first render.

## Bugs found (fix later)

1. **ElevenLabs 402 — troll audio failed.** `paid_plan_required`: "Free users cannot use library voices via the API." The account is free-tier and the configured voice (Patrick, a *library* voice in `agents/voice_actor.py`) is paywalled. Result: silent video. **Fix options:** (a) upgrade the ElevenLabs plan, or (b) switch `TROLL_VOICE` to a premade/default voice usable on the free tier. Also note: the render path treated this failure as **non-fatal** and continued — acceptable for staging, but means a "successful" render can be silently audio-less.
2. **Grok render path is wired wrong.** `Video Producer (Grok)` failed with `No such file or directory: ''` — it base64-encodes an input image, but the `grok` path in `RENDER_PATHS` (`pipelines/video.py`) has **no Character Dresser**, so no image is ever produced/passed. The grok path needs either its own dresser step or to feed off the source first-frame / dressed image. Until fixed, grok produces nothing.

## Character color bug — FOUND & FIXED (the big one)

The rendered Arbi came out **red**. Root cause: the canonical asset `arbi-king.png` is **golden-yellow**, but the codebase described Arbi as a "red furry monster" in ~6 places — including the Character Dresser prompt (`cartoonist.py`) which said "RED FURRY MONSTER" six times. At render time the *text* prompt overrode the *reference image*, recoloring him red — off-brand.

Fixed (golden-yellow now): `agents/arbi_persona.py` (ARBI_VISUAL source of truth + personality line), `agents/cartoonist.py` (all 3 generation prompts), `agents/script_writer.py`, `agents/video_analyzer.py`, `CLAUDE.md`. **Still to propagate:** `README.md` (lines ~3, ~49) and the vault `brand/arbi-character.md`.

Canonical look: golden-yellow shaggy fur, cream-white belly, gold studded crown (tilted), mismatched googly greenish eyes, small pink nose, two tiny lower fangs, round chubby body, Pixar 3D. A re-render is needed to confirm the fix produces a gold Arbi.

## Note on the spoken script

There is **no spoken script** — by design. Arbi is non-verbal: the Animation Director's `line` is what he *does* (physical gag, dialogue forbidden), and `voice_actor.py` generates gibberish troll onomatopoeia with real video keywords sprinkled in. Open creative question: keep Arbi non-verbal, or give him an actual voice/script? Ties into the Creative Director + ICP work.

## Data-quality note

`data/learn_log.jsonl` appended a row for **both** paths, including grok — whose `asset_path` points to a file that was never created. Learn-log rows should probably only be written on a real asset, or carry a success/failure flag.

## Quality-gate note (carried from the take review)

The Animation Director's only validation is `10 <= word_count <= 30` (`agents/script_writer.py`) — length only. It can't detect an incomplete/dangling sentence (it accepted the truncated 14-word line). Fix alongside the Creative Director work (`docs/creative-director-proposal.md`).

## Suggested next steps

1. Fix ElevenLabs voice (free-tier-safe voice or upgrade), re-render the audio so we see a complete video with troll sound.
2. Fix the grok path so we can actually compare the two techniques (the whole point of one-take→N-renders).
3. Then revisit the Creative Director refactor with a real baseline in hand.

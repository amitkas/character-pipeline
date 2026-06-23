# Render paths: `fal+elevenlabs` vs `grok`

The pipeline renders one TAKE through one or more **render paths**. Two are registered today (`pipelines/video.py` → `RENDER_PATHS`). They are fundamentally different tools, and we keep both on purpose.

## `grok` — the one-stop shop

Give Grok (`grok-imagine-video`) a **first image + creative direction**, and it returns a finished **video with native audio in one shot**.

- **Agents:** Video Producer (Grok) → Subtitle Burner → (YouTube)
- **`control_of_script = False`** — the technique generates its own audio/voice; we don't author it.
- **Pros:** simplest, fastest, fewest moving parts, cheapest (~$0.20 est.).
- **Cons:** least creative control — the voice/sound is whatever Grok decides. You can't direct a specific line, voice, or sound design.
- **Best for:** quick, high-volume, "good enough" reactions where speed/cost matter more than precise control.

## `fal+elevenlabs` — the control path (more creative freedom)

A multi-stage path where each creative layer is a separate, directable step.

- **Agents:** Character Dresser (Gemini image) → Video Producer (Kling on fal.ai, **visuals only**) → Sound Engineer (ElevenLabs, **audio/voice separately**) → Subtitle Burner → (YouTube)
- **`control_of_script = True`** — **we keep the script.** fal/Kling makes the visual; ElevenLabs produces the speech/voice/sound independently.
- **Pros:** maximum creative freedom — we control the image, the motion, and the audio as separate dials. This is the path where a real scripted voice (vs. gibberish) would live, and where more complex videos are possible.
- **Cons:** more steps = more cost (~$0.70+) and more failure surface (e.g. the ElevenLabs plan issue, the silent-video bug).
- **Best for:** hero/flagship pieces where the joke, the voice, and the craft need to land precisely.

## The strategic point

`grok` optimizes for **throughput**; `fal+elevenlabs` optimizes for **control**. The TAKE-as-artifact seam exists precisely so the *same* creative idea can be pushed through both and compared — cheap-and-fast vs. crafted — and so we can learn which earns attention per dollar (`data/learn_log.jsonl`, `control_of_script` flag).

## Open question this raises

Instance #0's character (Arbi) is currently **non-verbal** (gibberish + keywords) on both paths — that's a choice in its BRAND & VOICE slot, not a property of the engine. The `fal+elevenlabs` path is the one that *could* carry a real scripted voice. Deciding non-verbal vs. scripted is a creative call tied to the Creative Director + ICP work (`docs/creative-director-proposal.md`).

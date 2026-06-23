# How to Create Your Own Arbi: A Guide for Growth Marketers

You’ve seen character-driven content win on organic, paid, and community — one recognizable “face,” a repeatable format, and a hook that ties to what’s happening in the world. The hard part isn’t the idea; it’s producing it at speed without blowing the budget or the team.

Arbi is the **worked example — instance #0** of the engine: a wacky golden-yellow furry troll who gets “dressed” for trending events and re-enacts them in short animated videos. He’s not what the engine *is*; he’s one cabinet’s answer to “who’s the character?” The engine itself ships character-free and reads the character from your cabinet at runtime — so everywhere below where you see “Arbi,” read “the example; your character goes here.” One run takes about **5 minutes** and costs about **$0.77**. This article walks you through how a system like that works and how you can get your own version — whether you have a developer, an agency, or a no-code stack.

---

## Who This Is For

This guide is for **growth marketers** — organic, community, social, and/or paid — at **B2B or B2C startups** (seed to Series A/B). You’re a **builder** and **AI explorer**, and you might be **leading a small team** (senior, head of, or director). You care about:

- Owned IP (a character + format you control)
- Content at scale without linear headcount
- Testing creative and formats quickly
- Understanding how AI can run a content pipeline so you can brief it, buy it, or build it

You don’t need to code. You need to understand the pipeline, define your character, and choose how to execute.

---

## Why a “Character + Trends” Pipeline Matters for Growth

Standout creative often has:

1. **A character** — someone (or something) the audience recognizes.
2. **A format** — same structure every time (e.g. “character reacts to X”).
3. **Timeliness** — tied to what’s trending so it feels relevant.

Doing that by hand is slow. Doing it with a **system** means: pick a trend → understand it → put your character in it → generate the video → add audio and text → publish. One pipeline, many videos.

**What you get:**

- **Organic:** Steady short-form content that’s on-trend and on-brand.
- **Community:** Relatable, timely clips that spark conversation.
- **Paid:** Cheap creative tests; same character and format, different hooks or angles.
- **Experimentation:** Own the pipeline so you can change the character, the trend source, or the channel without starting from zero.

Arbi is one implementation of that pipeline. The rest of this guide explains how it works and how you can get your own.

---

## How the Pipeline Works (No Code Required)

Think of one video as one **run**. A single “brief” (we call it *context*) carries everything from step to step: the event, the description, what the main person wore, the character image, the gag, and the file paths. Each step reads from that brief, does one job, and writes back. No step needs to know the whole system — just its input and output.

Here are the **10 steps** in plain language:

| Step | Name | What it does |
|------|------|---------------|
| 1 | **Trend discovery** | Picks one trending event (with safety filters so you never touch tragedies or harmful topics). |
| 2 | **Source video** | Finds a real video for that event and pulls a frame to analyze. |
| 3 | **Understand scene** | Watches the video and describes what happened and what the main person wore. |
| 4 | **Dress character** | Generates your character in that outfit and setting (same face and body, new costume). |
| 5 | **Write gag** | Writes one short physical gag (e.g. 15–25 words) that fits your character’s “angle” on the event. |
| 6 | **Generate video** | Animates the character image with that gag using an AI video model. |
| 7 | **Add audio** | Adds voice or sound (e.g. gibberish, branded lines, or music) and composites it onto the video. |
| 8 | **Add text** | Burns titles and keyword overlays onto the video. |
| 9 | **Branded end** | Stitches a short branded outro (e.g. 3 seconds) to the end. |
| 10 | **Publish** | Optionally uploads to YouTube (or you use the file for TikTok, Meta, etc.). |

Flow:

```
Trend discovery → Source video → Understand scene → Dress character →
Write gag → Generate video → Add audio → Add text → Branded end → Publish
```

The only thing that’s **yours** end-to-end is your **character**. Everything else is the same pipeline: different events, same steps. So the first thing to get right is the character.

---

## Defining Your Character (The One Thing You Own)

Your character is your IP. Same character across events = recognizable format. Clear personality and “angle” = consistent tone for organic and paid.

You need to define three things (no code — a one-pager or short doc is enough):

### 1. Content boundaries

What topics you **never** touch. For brand and platform safety, the system should never pick tragedies, violence, or other harmful events. In Arbi’s case we have an explicit off-limits list (e.g. shootings, terrorism, abuse, etc.) so the trend step and any filters never suggest them. You define your own list for your brand.

### 2. Visual identity

A short, bullet-style description of how the character looks: species, props, style. Examples: “golden-yellow furry monster, gold crown, mismatched googly eyes, white belly, Pixar 3D style.” This gets used every time we generate an image or a video so the character stays consistent.

### 3. Personality / angle

How the character reacts to events. Arbi is “chaotic neutral” — causes mayhem but never mean-spirited; treats every event like he was personally invited. You might want “calm expert,” “sarcastic commentator,” or “hype host.” That “angle” drives the gag and the tone of the video.

### 4. One reference image

One canonical image of the character. The pipeline “dresses” them per event (outfit, setting) but keeps face and body consistent. You supply it through the **CHARACTER IMAGE slot** (`CONTEXT_CHARACTER_IMAGE`); instance #0 points that slot at Arbi’s reference PNG. For your own character, you point it at your own reference and the same idea applies.

In the engine, **no character is baked into the code** — not even a fallback. The character is read at runtime from your cabinet’s **BRAND & VOICE slot** — a doc with a `character:` block holding boundaries, visual identity, personality, sound, and distribution. That block *is* the character brief; write your own one-pager and the engine runs on it. If the slot is missing or omits a required key, the loader (`agents/character.py`) fails loud rather than substituting anyone else’s character. Want to see a filled-in brief? Instance #0’s lives in the host cabinet at [`brand/arbi-character.md`](../../../brand/arbi-character.md) — a worked example of what your own slot should contain.

---

## Tech and Tools (Enough to Brief a Dev or Choose No-Code)

You don’t need to configure these yourself. You need to know they exist so you can (1) ask a developer to run the open-source pipeline with API keys, (2) brief an agency on “we want this pipeline with our character,” or (3) map steps to no-code tools as they become available.

High-level stack:

| Step | Role in pipeline | Typical tool (in this repo) |
|------|------------------|-----------------------------|
| Trend + analyze + character + gag | LLM for search, understanding, and text | Gemini (Google) |
| Search and download | Find video URL, download it | Serper + yt-dlp |
| Character image | Generate character in outfit/scene | Gemini image generation |
| Video | Animate character with gag | Kling 2.5 Turbo Pro on fal.ai |
| Audio | Voice/sounds and mix with video | ElevenLabs + ffmpeg |
| Text and outro | Overlays and concat | ffmpeg |
| Publish | Upload | YouTube API (optional) |

**Cost and time (this implementation):** about **$0.77** and **~5 minutes** per video. Scaling = more runs and more API cost, not more people.

---

## Three Ways to Get Your Own Arbi

### Path A — Open-source + a developer

Clone this repo. A developer (or contractor) adds API keys and runs the pipeline. You provide:

- Character brief (boundaries, visual, personality)
- One reference image of your character

They handle: running the pipeline, resume if something fails, and optional upload. Best if you have even light dev capacity (in-house or freelance).

**To run one video:** `python3 main.py` (auto-picks a trend) or `python3 main.py --event "Your event title"` to pin an event. Full details are in the [README](../README.md).

### Path B — Agency or freelancer

Use this article and the repo as a **spec**. You say: “We want a pipeline that does these 10 steps; here’s our character brief and reference image.” They build or adapt (this codebase or their own stack). You own the character and the brief; they own the implementation. Best if you have no in-house dev but want it done quickly.

### Path C — No-code / low-code

The pipeline is code-first today. You can still use the 10-step breakdown to design a no-code flow (e.g. “trend from X → send to Y → generate video with Z”) as tools mature. This article gives you the mental model to evaluate “build your own character pipeline” products when they appear.

---

## Customization for Growth Use Cases

- **Different character:** Same pipeline; swap the character brief and reference image (e.g. your mascot, your founder persona).
- **Different channels:** Same video file; you decide where it goes — organic, paid, community. The optional upload step here is YouTube; the same file can go to TikTok, Meta, etc.
- **Different trend source:** The pipeline stays the same; the “trend discovery” step can use different sources (news, social trends, niche feeds) depending on your audience.
- **Experimentation:** Run multiple events per week; A/B test hooks, thumbnails, or angles while keeping character and format consistent.

---

## Cost, Time, and Scaling

- **Per video:** ~**$0.77**, ~**5 minutes**.
- **Scaling:** More videos = more runs (and more API spend); no linear increase in headcount. Fits seed–Series A/B budgets and small teams.
- **Where the money goes:** Video generation (fal.ai Kling 2.5 Turbo Pro) is ~91% of the cost (~$0.70 of ~$0.77). The rest — LLM calls (trend, analysis, image, gag), voice (ElevenLabs), search (Serper) — is under $0.10 combined.

---

## Next Steps

- **If you have a dev (or are technical):** Clone the repo, add API keys, run one video. Then adapt the character and distribution to your brand. See the [README](../README.md) and [CLAUDE.md](../CLAUDE.md) for how it runs.
- **If you don’t:** Use this article as a brief for an agency or freelancer: “We want a pipeline that does [these 10 steps]; here’s our character brief and reference image.”
- **If you’re exploring:** Map the 10 steps to tools you already use (e.g. ChatGPT, Runway, ElevenLabs) and approximate the flow manually. Use that to justify investing in a proper pipeline later.

The reference implementation is this repo. The character is read from your cabinet’s BRAND & VOICE slot (instance #0’s filled example lives in the host cabinet at [`brand/arbi-character.md`](../../../brand/arbi-character.md)); the pipeline is defined in [`pipelines/video.py`](../pipelines/video.py). Hand those — plus your own character brief — to your dev or agency when you’re ready to build your own.

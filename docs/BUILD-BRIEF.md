# Arbi Flow — build brief (living tracker)

*Started 2026-06-11, first live test session (Amit + Arbi). This is the running source of truth for what we're doing, what's decided, and what's next. Update it as we go.*

> **Scope note.** Arbi Flow is the standalone, portable trend-to-video engine; this tracker records **instance #0's** build session — Arbi Labs filling the engine's context slots and running the first videos through it. Where it says "Arbi video" or "Arbi persona" below, that's instance #0's fill of the BRAND & VOICE slot, not the engine's identity.

## Where we are

The core engine works end to end. First live run produced a real, on-model (after the color fix), vertical 10s Arbi video via the `fal+elevenlabs` path. We're now hardening it and defining the creative layer before scaling output. **Nothing is published — publish stays HELD until Amit signs off.**

## Decisions made

- **First-test subject:** Taylor Swift courtside / NBA (real event; most visual) — for mechanics, not topic fit. Take = `tk_57b5b57c`.
- **Render both paths** to compare techniques (see `render-paths-comparison.md`).
- **Arbi is golden-yellow, not red.** Canonical asset = `arbi-king.png`. Fixed across generation code + CLAUDE.md.
- **Scout is not trusted** — human-in-loop now; fact-checker agent later. AI news > dry tech announcements.
- **Creative Director refactor is the right direction** — parked until after a clean full cycle.

## Done

- ✅ Verified env (keys, deps, ffmpeg, character image).
- ✅ Scouted live; ran TAKE phase; reviewed take at the gate; fixed truncated `line`.
- ✅ Rendered both paths (fal = real video but silent; grok = crashed).
- ✅ Fixed Arbi red→gold across generation code + CLAUDE.md.
- ✅ **CTO task — fix grok render path + render robustness nits.** (done)
- ✅ **Editor task — propagate gold to README + vault brand doc.** (done)

## Resolved (this session, after the fixes)

- ✅ **ElevenLabs upgraded** — audio works; 402 gone.
- ✅ **Full re-render of `tk_57b5b57c`, BOTH paths succeeded** — first complete side-by-side:
  - `fal+elevenlabs` — 1080×1920, 10s, gold Arbi + controlled troll audio + subtitles.
  - `grok` — 720×1280, 10s, gold Arbi + native audio + subtitles.
  - Both staged in `output/`, nothing published. Color fix + audio confirmed on screen.
- ✅ **Voice strategy decision:** do NOT decide it ad hoc — it becomes part of the **Creative Director** redesign (see next).

## Active focus — the Creative Director (rethink + rewrite)

Amit's call: the angle **and** the voice strategy belong to a re-thought Creative Director step. This is now the main work item, not parked.

1. **Define the content ICP first** (who instance #0's videos are for / what each should do) — gates everything. Likely a PM + Amit session.
2. **Design the Creative Director agent** — owns the angle, runs *after* the Analyzer (sees the footage), fed: video analysis + the host character's full persona (instance #0: Arbi's) + content ICP. Decide non-verbal vs. scripted voice here.
3. **Rewrite the step** — strip angle-generation out of the Scout; add the Creative Director; (voice) wire scripted output into the `fal+elevenlabs` path if we go that way.
4. Judge new angles/voice against this session's baseline (`tk_57b5b57c`).

Full design: `creative-director-proposal.md`.

## Assignments (proposed 2026-06-11, pending Amit's approval)

| Item | Owner | Status |
|---|---|---|
| **Content ICP** — who Arbi videos are for + what each should do + the metric (gates the Creative Director) | `product-manager` | proposed |
| **Creative Director refactor** — split angle out of the Scout into a new agent after the Analyzer (reads video analysis + full persona + an ICP doc); also fix the Animation Director length-only validation | `cto` | proposed (structure can start now; content/voice wait on ICP + voice decision) |
| **Index the new build docs** into the KB (BUILD-BRIEF, render-paths-comparison, creative-director-proposal, first-live-test) | `librarian` | proposed |
| **Chronicle run #1** as a building-journey entry (Amit-voiced, building-in-public) | `scribe` | proposed |
| **Scout fact-checker** (verify scouted events) | — | held / later, not yet assigned |
| **Voice: non-verbal vs scripted** | Amit + `product-manager` | decided inside the Creative Director work |

**Sequencing:** ICP (PM) is the gating input. CTO can build the *structural* seam in parallel using a placeholder ICP doc as the interface, but must NOT wire scripted voice until the voice strategy is decided.

## Parked (revisit after a clean full cycle)

- **Creative Director agent** — own the angle, placed after the Analyzer, fed video analysis + full persona + content ICP. See `creative-director-proposal.md`.
- **Content ICP** — not written anywhere the pipeline can read; gates the Creative Director. Likely a PM/Amit call.
- **Animation Director validation** — length-only gate (`script_writer.py`) can't catch truncated lines; fix alongside Creative Director work.

## Reference docs

- `first-live-test-2026-06-11.md` — full results + bugs from run #1
- `render-paths-comparison.md` — `fal+elevenlabs` vs `grok`
- `creative-director-proposal.md` — the parked angle-ownership refactor
- `BRIEF.md` — project brief + open threads

# Proposal: a Creative Director agent (own the angle, after the video is seen)

*Status: parked design decision — revisit after the first full take→render→review cycle is tested. Captured 2026-06-11 from a working session between Amit and Arbi (partner).*

> **Framing.** This is an engine-design proposal. Where it names "Arbi", "the persona", or "Arbi Labs' content ICP", read those as **instance #0's fill** of the BRAND & VOICE and AUDIENCE slots — the worked example. The Creative Director the engine ships reads whatever character/ICP the host cabinet provides; another cabinet's character and audience drop straight in.

## The decision (what we agreed)

The **chaos angle** — the comedic POV the whole video hangs on — should be owned by a dedicated **Creative Director** agent, **not** the Video Scout. A scout scouts; deciding the creative angle is a different job and deserves its own role.

## Why the current design is wrong

Today `chaos_angle` is set inside `agents/video_scout.py` (`_fill_pinned_event_fields` for pinned events ~L291; the grounded prompt ~L138 for auto-scouted events). Three problems:

1. **The angle is decided blind.** The Scout sets the angle from the event's **title + description text only** — *before* the Finder downloads the clip and *before* the Analyzer ever watches it. The Analyzer then runs second and merely aligns its `scene_prompt` to the already-frozen angle. That is backwards: a creative director watches the tape, *then* finds the angle.
2. **Persona is reduced to guardrails.** The angle call only pulls the off-limits list from the host character — the *don'ts* (no tragedies, nothing mean-spirited). It never sees the character's actual voice/persona. It knows what the character can't do, not who it is. *(At capture time the off-limits list was baked in `agents/arbi_persona.py`; that file has since become the BRAND & VOICE slot loader `agents/character.py`, so the persona now reaches the pipeline through the slot.)*
3. **Zero ICP awareness.** Nothing in the pipeline encodes who the output is *for* or what it should *do* for that audience. The angle is optimized for "generically funny," not "funny for this cabinet's audience, in service of its positioning."

## Proposed architecture

Split the Scout's two jobs. Add a **Creative Director** agent **after the Analyzer**:

```
Scout (finds event + clip search query)
  → Finder (downloads clip)
  → Analyzer (watches the clip, describes it)
  → Creative Director (decides the ANGLE from: video analysis + the host character's persona + the host's content ICP)
  → Animation Director (choreographs the ONE physical gag that performs the angle)
  → Take Emitter (persists the take)
```

- **Scout** goes back to pure scouting: event + `video_search_query`. It no longer emits `chaos_angle`.
- **Creative Director** owns `chaos_angle`, and decides it *with the footage actually seen*, fed three inputs:
  1. the Analyzer's video description (what literally happened on screen),
  2. the host character's **full persona** (voice + identity, not just off-limits guardrails — for instance #0, Arbi's),
  3. the **content ICP** (see open gap below).
- **Animation Director** is unchanged in role: it still turns the (now better) angle into one camera-followable gag.

## Open gap this forces (must resolve before building)

**The content ICP isn't written anywhere the pipeline can read.** We have a *product* ICP (growth marketers who'd clone the pipeline — `docs/BUILD_YOUR_OWN_ARBI.md`), but not an *audience* ICP: who watches the output (for instance #0, Arbi videos), and what each video should accomplish for them. The Creative Director is only as good as this input, so this is a host-cabinet foundation decision (for instance #0, a PM/Amit call) that gates the refactor.

## Sequencing

1. **First** finish at least one full take → render → review cycle on the current code, to establish a baseline.
2. **Then** define the content ICP (source-of-truth doc the pipeline can read).
3. **Then** build the Creative Director agent and wire it after the Analyzer; strip angle-generation out of the Scout.
4. Judge the Creative Director's angles against the baseline.

## Related

- Scout-trust / fact-checker note and topic taste: `BRIEF.md` → Open threads.
- Truncation bug surfaced same session: the Animation Director's only quality gate is `10 <= word_count <= 30` (`agents/script_writer.py` ~L83), which is length-only and cannot detect an incomplete/dangling sentence (it accepted a truncated 14-word line). Worth fixing alongside this work.

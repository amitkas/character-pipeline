# Character Lock — authoring a portable, on-model character identity

Character Lock is the method for authoring a character identity that reproduces recognizably across many generations, many scenes, and even a third party's own model — without the pipeline's code ever knowing what the character looks like. A locked character is guaranteed to stay on-model by a small set of canonical artifacts plus a strict prompt contract, never by engine logic. The character's style and visual DNA live in the character's own authored artifacts; the engine only reads them through a slot. This is the doc the Onboarder's client character-image generation step and the SociaLoops character-asset layer both point back to — it is the one place the method is written down, and it carries no character of its own.

---

## 1. The four canonical artifacts

Every locked character is backed by exactly four artifacts. Nothing else is required to reproduce the character; nothing else should be treated as load-bearing.

**Canonical hero.** One reference image, blank background, no scene or pose noise. This is the character's sticky identity anchor — every re-pose, every new scene, every outfit change is conditioned on this single image. It is the only artifact the runtime reads directly (via the pipeline's CHARACTER IMAGE context slot).

**Portable DNA block.** One prompt-able paragraph that fully describes the character — copyable verbatim into any model call, on this pipeline or a completely different one — plus a "locked constants" table (palette, signature prop, off-limits colors, build, attitude). This is where the character's style and art-theme language lives, and it is the *only* place it lives. If the style words aren't in the DNA block, they don't exist for this character.

**Consistency proof sheet.** A handful of hard re-poses that demonstrate the identity actually holds under pressure: silhouette, palette, and signature prop should all survive a pose the hero image doesn't show. This is the evidence artifact — it is what lets you claim "locked" rather than "drawn once and hoped."

**Provenance manifest (`_gen-manifest.json`).** Records, per canonical asset, exactly how it was generated: model, endpoint, the exact prompt used, guidance scale, any seed or other params, and the date. Every canonical asset should be reproducible from its manifest entry alone.

These four artifacts are authoring/canon artifacts, not runtime-read files — see §4 for what the pipeline actually reads.

---

## 2. The prompt contract

Every render of a locked character follows the same prompt shape:

```
[LOCKED STYLE] + [LOCKED DNA] + SCENE + POSE
```

Two rules govern it, and both exist because violating them is how a character silently drifts off-model:

- **Style language comes only from the DNA block — never from engine code, an agent, or a config default.** The cautionary tale: a style prefix hardcoded into engine code (a generic "premium 3D" or generic-CGI line baked in as a default) will silently override the character's actual look on every render, the same failure class as a hardcoded brand color baked into a template. That is exactly the corruption this method exists to prevent. In this pipeline the only two paths a style can travel are: the BRAND & VOICE slot's optional `animation_style` field, read by `video_style_prefix()` in `agents/character.py`; or the DNA paragraph passed directly into a still-generation call. If a style word shows up anywhere else, it's a bug.
- **POSE leads the prompt for hard re-poses**, and the prompt should state limb and head direction explicitly and negate the hero's default pose (e.g. "arms raised overhead, NOT the resting arms-down pose"). Left implicit, a strong reference image dominates the generation and the new pose simply won't take — the model reproduces the hero's original pose instead of the one asked for.

---

## 3. The model split

Two models cover the two things a locked character needs to do, and they are not interchangeable:

**FLUX Kontext** locks the hero and re-poses it into new scenes and poses. It is invoked through the studio skill `studio_skills.render.flux_kontext_scene_still`, whose CLI face is the still-author's day-to-day tool for producing a new canonical or scene still. Guidance around 4.5 pushes prompt adherence for hard re-poses; raise it from whatever lower default the skill ships with when a pose is resisting. The skill's own `SKILL.md` points back to this doc for the prompt contract — this doc is the source of truth for *why* the prompt is shaped the way it is, the skill just executes it.

**Nano Banana (multi-reference image edit)** is the tool for re-dressing a character or placing an exact logo or mark onto it, because FLUX Kontext will redraw or simplify embedded marks rather than preserve them pixel-for-pixel — asking it to hold a precise logo is asking it to do something it doesn't do. Nano Banana takes the character and the mark as separate reference images and edits them together; run one edit per pass rather than compounding multiple changes in a single call. Nano Banana is inventoried as a future studio skill and is not required for Character Lock to function — note it here so it isn't reinvented later, not as a hard dependency.

---

## 4. How Character Lock feeds this pipeline

Of the four canonical artifacts, only two are ever read at runtime, and both arrive through slots rather than direct file paths:

- The **canonical hero** feeds the pipeline's **CHARACTER IMAGE** context slot.
- The DNA block's **style words** feed the **BRAND & VOICE** slot's optional `animation_style` field. Both Engine A and Engine B read it exclusively through `video_style_prefix()` — never a baked literal (see `CONTEXT.md` §5, "What must NEVER be baked in").
- **Engine B** beats condition Kling's first frame on a Kontext **scene still** generated from the hero — never the raw hero image itself. See `docs/beat-schema.md` for the beat's `character_image` and `animation_direction` fields, and the flux skill referenced in §3 above for how that scene still gets produced.

The **portable DNA block**, the **consistency proof sheet**, and the **provenance manifest** are authoring and canon artifacts. The pipeline never reads them directly; they exist so a human (or another model) can reproduce or extend the character correctly.

---

## 5. Cross-links

- **Onboarder §6** consumes this doc for client character-image generation at onboarding time.
- The **SociaLoops character-asset layer** references this doc as its method for authoring a client's locked character.
- Companion in-repo docs: `CONTEXT.md` (the full slot contract this pipeline reads through) and `docs/beat-schema.md` (Engine B's beat input, including how a beat's `character_image` and `animation_direction` fields relate to the hero and the prompt contract above).

---

## 6. Fill-in templates

These are brand-free starting points. Copy them into a character's own authoring folder — where that folder lives is the author's choice; the pipeline never looks for it by path, only through the slots described in §4.

### `character-lock/<character>/dna-block.md` template

```markdown
---
title: "<character> — DNA block (portable character description)"
status: "<LOCKED | DRAFT> — v<n>, approved <date>. This DNA block is the
  reusable, prompt-able description for every future render of <character>."
character_pick: "<which explored option this locks, if more than one was tried>"
tested: "<what portability/consistency test this has passed, and where the
  evidence lives>"
use: "Paste this paragraph as the base of any prompt to generate a new
  pose/scene of <character>. Add a pose/action/scene on top — never change
  the description below."
---

# <character> — DNA block

**The one paragraph.** Copy this verbatim as the character description in
any generation:

> [LOCKED DNA — a single dense paragraph: body shape/build, linework or
> render style, primary and secondary palette, distinguishing facial
> features, the ONE signature prop and how it's worn, limb/hand treatment,
> the palette's hard boundaries ("never X, never Y"), background treatment,
> and the attitude/expression the character reads as. Style language lives
> here and only here — see §2 of docs/character-lock.md.]

## Locked constants (never vary)

| Element | Value |
|---|---|
| Body / primary color | `<hex>` |
| Secondary color | `<hex>` |
| Background | `<hex>` |
| Accent | `<hex>` |
| Off-limits | `<colors or treatments this character never uses>` |
| Signature prop | `<the one prop, how it's worn, never swapped>` |
| Build | `<body proportions / construction>` |
| Attitude | `<the one expression/posture this character defaults to>` |

## What's proven so far

- **Consistency** — <which hard re-poses have been tried and held identity;
  where the evidence lives>.
- **Portability** — <has this exact paragraph been tested with no reference
  image, on a fresh/different model call? what happened?>.

## Known weak spot

<the part of the description most likely to erode on a re-render or a
round-trip through a different model, and what the fix looks like if it
keeps happening>.
```

### `_gen-manifest.json` schema

```json
{
  "character": "<character>",
  "asset": "<hero | scene-still | proof-sheet-pose-N>",
  "model": "<...>",
  "endpoint": "<...>",
  "prompt": "<...>",
  "guidance_scale": "<...>",
  "aspect_ratio": "<...>",
  "params": {
    "<...>": "<...>"
  },
  "generated": "<YYYY-MM-DD>",
  "source_reference": "<path to the canonical hero this asset was conditioned on, or null for the hero itself>"
}
```

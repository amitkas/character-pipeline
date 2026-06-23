# Onboarding Agent — the context-slot component (character-pipeline)

> **This is one layer of the whole-workspace Onboarder, not the whole job.** *(Reframed 2026-06-15 — see [[about-arbi-labs]] §5 + the 2026-06-15 changelog.)* The canonical Onboarder ([[onboarder]]) stands up an entire instance #N — the AI CMO operator, the operation, and the context layer. This doc specifies the **context-slot layer for *character-pipeline specifically*** — the write-side of *this pipeline's* Context Layer Contract. The slot-by-slot output contract below stays accurate; for what the Onboarder installs end to end, read [[onboarder]] first.

*The write-side companion to the [Context Layer Contract](../CONTEXT.md). The pipeline **reads** the contract slots to make videos; the onboarding agent **writes** them from a company's raw materials. Same contract, opposite direction. Filling these slots is **one layer** of the install that turns "a company" into **instance #N** ([[onboarder]]). · 2026-06-11 (persona-spec / brain-skin composition added 2026-06-14; demoted to the context-slot component 2026-06-15) · status: spec, pre-build.*

*Companion docs: [`../CONTEXT.md`](../CONTEXT.md) (the slots, the read interface) · [`../../../archive/business-vs-product.md`](../../../archive/business-vs-product.md) (the Business/Product line this sits on) · [`BUILD_YOUR_OWN_ARBI.md`](BUILD_YOUR_OWN_ARBI.md) (the manual version this automates).*

> **Decisions locked (Amit, 2026-06-11):** **(A) Shape — Cabinet teammate now**, hardening into a shipped runtime once the slot-authoring logic is proven on instance #0. **(B) Gaps — propose-and-mark**: where a company's docs are silent on a slot, the agent drafts the slot, flags it `inferred`, and routes it for human sign-off. It never invents silently and never leaves a required slot empty without saying so.

---

## 1. What it is, in one line

A portable reader of raw company materials that writes a **conformant context layer** + a **creative brief** — everything the character-pipeline needs to run on that company instead of on Arbi.

It is the only component *allowed* to write company-specific values, because it writes them into the **host cabinet's slots** (where specifics belong), never into the runtime (where the contract forbids them). That keeps the Business/Product line clean: **the onboarding agent is product (portable, runs for any company); its output is business (one specific company's filled context).**

The test it exists to satisfy: after onboarding runs and a human approves, `grep -ri "arbi" agents/` is irrelevant — the pipeline reads only the slots onboarding wrote, and produces *that company's* video.

---

## 2. Inputs — whatever the company already has

The agent takes a pointed-at folder of **unstructured** company materials. None are required by name; the agent reads what's there and maps it to slots.

| Typical input | Feeds slot(s) |
|---|---|
| One-pager / positioning / marketing deck | SPINE, AUDIENCE |
| Brand guidelines / tone-of-voice doc | BRAND & VOICE, VOICE (detail) |
| **Archetype pick** (a persona *type* from a library — deadpan critic, hype-man, wise mentor, chaos gremlin) | BRAND & VOICE |
| **Onboarding interview answers** (how unhinged, who's the audience, what to never joke about) | BRAND & VOICE, RELEVANCE LENS |
| Mascot / logo / character art (any image) | CHARACTER IMAGE |
| ICP / persona docs / "who we sell to" | AUDIENCE |
| Content calendar / past posts / "what we talk about" | RELEVANCE LENS |
| Outro sting / brand music / jingle | BRANDED ASSETS |

The last two rows are the reframe's point ([[about-arbi-labs]] §5): the BRAND & VOICE slot isn't only *read* from an existing doc — when one is thin or absent, the agent **composes** it from an archetype pick + a short interview. The three together are the inputs to the persona spec (§3).

**For instance #0 (dogfood target):** point it at this cabinet's own `foundation/`, `brand/`, and `projects/`. That's the first run — onboarding Arbi Labs onto Arbi Labs, proving the agent reproduces the slots we hand-authored.

---

## 3. Output contract — slot by slot

Each output conforms to the typed shape the runtime already expects ([CONTEXT.md §3–4](../CONTEXT.md)). The agent does not get to invent a format; it fills the one the pipeline reads.

| Slot | Default target file | Required? | Output shape the agent must produce |
|---|---|---|---|
| **SPINE** | `foundation/one-pager.md` | Recommended | One-screen prose: positioning, what it does, who it serves, what's live. |
| **BRAND & VOICE** | `brand/<brand>.md` | **Required** | The `character:` block (visual identity, personality/angle, registers) **+ the off-limits list** (`OFF_LIMITS_*`). This is the slot the most agents read — get it right. |
| **VOICE (detail)** | `foundation/voice/` | Recommended | Register/tone detail driving script + sound. Prose. |
| **AUDIENCE** | `foundation/content-icp.md` | **Required** | The fenced ```` ```yaml content_icp: ```` block — keys: `primary_audience`, `video_jobs`, `angle_selection_rule`, `lane_weights`, `hard_bars`, `success_metric`. Typed; the pipeline parses it. |
| **RELEVANCE LENS** | `foundation/keywords.md` | Optional | What this company finds worth reacting to — scores candidate events. List/prose. |
| **CHARACTER IMAGE** | host-supplied PNG | **Required** | A pointer to one canonical reference image. If none exists → see §5. |
| **BRANDED ASSETS** | outro / music | Optional | Pointers to outro tail + music bed, or explicitly "none → skip the step." Never an Arbi default. |

Every value the agent writes is **traceable to a source line** in the input materials (cite the file), or carries the `inferred` tag (§5). No uncited, unmarked claims — same discipline as the one-pager maintenance protocol.

> **The BRAND & VOICE output is the persona spec — the instance's "skin."** *(Added 2026-06-14 — voices & instance reframe; this agent is the "Onboarder" that [[about-arbi-labs]] §5 and [`context-contract-audit.md` §5](context-contract-audit.md) name.)* In the brain/skin model, what this agent writes into BRAND & VOICE is the instance's **persona spec** — the client-cabinet equivalent of instance #0's `brand/arbi-character.md`. It is the **skin** (the variable, per-instance persona). The agent composes it from **three inputs**: (1) the company's **existing brand voice** (richest when it exists — read and cite it); (2) an **archetype pick** from a library — a persona *type*, never a named person; (3) a short **onboarding interview** that sets the unhinged-dial, the audience, and the hard "never joke about" lines. The **brain** — the marketer's judgment — is **not** this agent's to write: it stays Arbi's, in the operator layer. The Onboarder writes the skin; it never writes the brain. *(Where a company can't articulate a voice, the "who'd be your dream brand ambassador?" question is allowed only as an interview **facilitation prompt** — extract the traits, discard the name; never clone a named real person. See the §11 hypothesis + legal guardrail in [[about-arbi-labs]].)*

---

## 4. Second output — the creative brief

Distinct from the machine slots: a short, human-readable **angle primer** for the Creative Director — the "easy context" that makes per-video angle-setting sharp without re-reading the whole cabinet. It's the digest, not the raw docs.

```
CREATIVE BRIEF — <Company>
- Who they are:        <one line from SPINE>
- Their angle/voice:   <how this brand reacts to events — the generalized "chaos angle">
- Lanes to react to:   <from RELEVANCE LENS + lane_weights>
- Hard bars:           <off-limits + hard_bars — what to never touch>
- What a win is:       <success_metric, in plain words>
```

The Creative Director already consumes the AUDIENCE slot today ([CONTEXT.md §6](../CONTEXT.md)); the brief is the distilled prime that sits on top of it, so angle decisions start from one screen instead of five docs.

---

## 5. Gap behavior — propose-and-mark *(locked)*

When the input is silent on a slot:

- **Optional slot empty** (e.g. no RELEVANCE LENS) → the agent **drafts a proposal**, tags it `# inferred — from <source/reasoning>`, and lists it in the onboarding report for approval. The pipeline can run without it (documented fallback), but the company gets a starting draft, not a hole.
- **Required slot empty** (BRAND & VOICE, AUDIENCE, CHARACTER IMAGE) → the agent **drafts a best-effort proposal AND flags it loudly** as a required gap. Onboarding is **not** "complete" until a human resolves every required gap. It never silently ships a required slot, and never substitutes Arbi's answer.
- **No character image at all** → flag as a required gap; propose generating a brand-consistent reference from the visual-identity description (the pipeline already has image-gen). Human approves before it becomes canonical.

The marking is the contract with the human: every `inferred` line is a question waiting for a yes. This is the "surface a draft, human decides" rule applied to the foundation everything downstream inherits.

---

## 6. The human-approval gate

Onboarding output is the root everything else grows from — a wrong ICP or off-limits line propagates into every video. So:

1. Agent reads inputs → drafts all slots + the creative brief + an **onboarding report** (what it filled, what it inferred, what's still a gap).
2. Human reviews the report, resolves required gaps, edits any draft.
3. On approval, the slots are written to the host cabinet's context root and the pipeline is cleared to run.

No externally visible action, no autonomous "done." The agent proposes a complete draft; the human signs it. (Matches the studio's hard rule: never take the foundational action autonomously.)

---

## 7. Build shape — teammate now, runtime later

**Phase 1 — Cabinet teammate (now, the build we're greenlighting).** A new teammate agent in this cabinet (sibling to curator/librarian). You point it at a materials folder; it drafts the slots + brief + report conversationally; you approve. Mostly agent definition (system prompt, when-to-use, the slot output contract above) + light glue. **Dogfood target: run it on Arbi Labs' own `foundation/`+`brand/` and confirm it reproduces our hand-authored slots.** Ships this week (per the seven-day rule).

> Adding this teammate is the one engineering-squad addition Amit approved by choosing Fork A (see the squad-staffing note). No further team members without his sign-off.

**Phase 2 — Shipped runtime (later, once proven).** Harden the teammate's logic into a portable installer that ships next to the pipeline — the mirror of `main.py`: `onboard <materials-dir>` → writes the slots to a target `CABINET_CONTEXT_ROOT`. This is what makes "anyone can install it on their own cabinet and watch it run on *their* context" (H1) literally a command, not a manual. Don't build it until Phase 1 has produced correct slots for at least instance #0 + one real second company.

---

## 8. Definition of done (Phase 1)

- The teammate exists and, pointed at this cabinet's `foundation/`+`brand/`, produces a `content_icp:` block, a `character:` block + off-limits list, a SPINE draft, a relevance-lens draft, and a creative brief.
- Every output is source-cited or `inferred`-tagged; every required gap is flagged.
- The produced slots are conformant enough that the character-pipeline reads them through the contract and runs a video on them — the loop closes on instance #0.
- The onboarding report is reviewable in one screen.

---

## References

- [[onboarder]] — the **whole-workspace Onboarder spec** (source of truth); this doc is its character-pipeline context-slot layer
- [`../CONTEXT.md`](../CONTEXT.md) — the slots this agent writes and the read interface they must satisfy
- [`context-contract-audit.md`](context-contract-audit.md) — the line-level conformance audit (the read side)
- [`portability-gaps-and-move-plan.md`](portability-gaps-and-move-plan.md) — the de-baking gap list this agent completes from the write side
- [`BUILD_YOUR_OWN_ARBI.md`](BUILD_YOUR_OWN_ARBI.md) — the manual "define your character + one-pager" process this automates
- [`../../../archive/business-vs-product.md`](../../../archive/business-vs-product.md) — the Business/Product line: installer is product, its output is business

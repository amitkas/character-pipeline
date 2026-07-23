# CONTEXT.md — Context Layer Contract for the character-pipeline runtime

*The contract this product carries. It declares the **context slots** the runtime expects a host cabinet to fill, **how** it reads them (through one configurable context root — never a hardcoded path or a baked-in Arbi value), and **what must never be baked in**. Ships inside the product so the contract travels with the code.*

*Companion docs: [`foundation/context-layer-contract.md`](../../foundation/architecture/context-layer-contract.md) (the org-level portability **standard** this manifest instantiates) and [`foundation/context-manifest-schema.md`](../../foundation/architecture/context-manifest-schema.md) (the formal schema this `CONTEXT.md` conforms to) and [`foundation/_planning/business-vs-product.md`](../../archive/business-vs-product.md) (PM — the two spaces + why this contract exists) and [`docs/context-contract-audit.md`](docs/context-contract-audit.md) (the line-level conformance audit) and [`docs/portability-gaps-and-move-plan.md`](docs/portability-gaps-and-move-plan.md) (the gap list + Phase-2 move plan). Slot vocabulary here matches the PM doc §2 verbatim. · 2026-06-11; persona-spec / brain-skin lens added to §3 on 2026-06-14 (no contract change); context-root env var renamed `CABINET_CONTEXT_ROOT` → `STUDIO_CONTEXT_ROOT` on 2026-07-23, legacy name honored as fallback for one version (non-breaking, Contract-Revision stays 1).*

> **Status: contract enforced.** Every agent reads the host's character through `get_character()` (the BRAND & VOICE slot); the context root, character image, off-limits list, sound spec, and distribution copy all resolve through slots. The engine carries **no** in-code character and **no** fallback — a missing/incomplete required slot fails loudly (see §4.5, §6). `grep -ri "arbi\|troll\|golden-yellow\|crown" agents/` returns clean.

> **Contract-Revision: 1** — the revision of *this* slot contract. The engine version (`VERSION`) is a promise about this number: a **MAJOR** bump means this revision changed in a breaking way (a required slot added, a typed block's keys changed), and `/update` refuses to silently cross it (see [`foundation/_planning/distribution-and-versioning.md`](../../archive/distribution-and-versioning.md) §3). Bump this whenever §3's required slots or §4's read interface change incompatibly. Read by `version.py`.

---

## 1. What this product is, and the one test that governs it

A portable runtime that does one job — the creative pipeline (SENSE → GROUND → TAKE → RENDER → DISTRIBUTE → LEARN) — against **whatever context layer it is installed into**. Arbi Labs is just instance #0: the first cabinet whose slots happen to be filled in. This is **H1** made literal — the engine is an open-core asset (open recipes, closed implementation) that ports to *any* cabinet *because* it contains no copy of the business, only the contract for reading one.

**The portability test — the single question that decides whether any line is correct:**

> Would this survive being copied, untouched, into another business's cabinet — pointed at *their* context root, reading *their* docs?

If a line names "Arbi", "golden-yellow", "troll", or a `../../brand` path that only resolves in our tree, it **fails** — it is host content wearing a product's clothes, and belongs back in the host cabinet (`foundation/` / `brand/` / `projects/`), read through a slot.

---

## 2. The configurable context root

The runtime resolves **every** host doc relative to a single host-supplied root. No `os.path.join(_ROOT, "..", "..", ...)` climbs, no Arbi filenames in agent code.

| Knob | Env var | Default | Meaning |
|---|---|---|---|
| **Context root** | `STUDIO_CONTEXT_ROOT` | the cabinet two levels above the tool dir (i.e. *this* cabinet) | Absolute path to the host cabinet root. Set it, and the same checkout reads a different cabinet. (legacy `CABINET_CONTEXT_ROOT` honored as fallback for one version) |

**Default = this cabinet, by design.** When unset, the root resolves to `dirname(dirname(tool_dir))` — the behavior the code has today — so instance #0 keeps working with zero config. A second cabinet sets one env var.

> Resolution order for the root: `STUDIO_CONTEXT_ROOT` (if set, used as-is) → else the computed default. The default is *depth-stable*: it survived the `tools/new-arbi → products/new-arbi → products/character-pipeline` moves (2026-06-11, 2026-06-19) because all three locations sit two levels under the cabinet root, so `dirname(dirname(tool_dir))` resolves to the cabinet either way (see the move plan).

---

## 3. The context slots (the required host docs)

Each row is a **role**, not a filename. The product names only the slot; the host cabinet declares which of its docs fills it (via the per-slot env override, or the documented default). The "Filled here" column is how **instance #0** answers it — a product must never name that column.

| Slot | Env override | Default (relative to context root) | Required? | What the runtime needs from it | Consumed by | Spine IDs |
|---|---|---|---|---|---|---|
| **SPINE** | `CONTEXT_SPINE` | `foundation/one-pager.md` | Recommended | One-screen "what is this business": positioning, what it does, who it serves, what's live. Primes every phase. | all phases (prime) | P1, S1, H1, ICP1, M1, M2 |
| **BRAND & VOICE** | `CONTEXT_BRAND` | `brand/arbi-character.md` | **Required** | Read as the fenced `character:` block: visual identity, personality, voice, the off-limits list, the **sound spec** (`label`/`voice_name`/`voice_id`/`pitch_shift`/`gibberish_templates`/`video_audio_direction`), **distribution copy** (`title_fallback`/`description_suffix`/`hashtags`/`tags`), and two **optional** keys — `animation_style` (string) and `caption_style` (mapping), see the note below. Required keys are validated at load — a missing one fails loud (§4.5). | TAKE (voice), RENDER (look), DISTRIBUTE | BR1b, BR2, N1 |
| **VOICE (detail)** | `CONTEXT_VOICE` | `brand/voice` | Recommended | Voice DNA / register detail — drives script tone + sound design. *(Unread today.)* | TAKE, sound | BR2 |
| **AUDIENCE** | `CONTEXT_AUDIENCE` | `growth/character-pipeline-content-icp.md` | **Required** | Who the output is for. Read as the fenced `content_icp:` YAML block (§4), incl. `video_jobs`. | SENSE (filter), Creative Director (angle), DISTRIBUTE | ICP1 |
| **RELEVANCE LENS** | `CONTEXT_RELEVANCE` | `foundation/keywords.md` | Optional | What counts as worth reacting to for this business; scores candidate events. *(Unread today.)* | SENSE | — |
| **CHARACTER IMAGE** | `CONTEXT_CHARACTER_IMAGE` (alias: `ARBI_CHARACTER_IMAGE`) | host `<context root>/brand/creative/arbi-king.png` (instance #0's asset — host-supplied, not bundled) | **Required** | One canonical reference PNG. | RENDER (dress/animate) | BR1b |
| **BRANDED ASSETS** | `CONTEXT_OUTRO`, `CONTEXT_MUSIC_DIR` | none | Optional | Branded outro tail + music bed. Absent ⇒ skip the step, never substitute Arbi's. | RENDER tail | — |
| **PLANS** | `CONTEXT_PLANS` | host-declared | Optional | Operational design the runtime should respect (formats, gates). | the phase that needs it | — |

> **The BRAND & VOICE slot is the persona spec — the "skin."** *(2026-06-14 — voices & instance reframe.)* What fills this slot is the instance's **persona spec**: visual identity, personality, voice, the sound spec, the off-limits line. Instance #0's is `brand/arbi-character.md`; a client cabinet's is **composed at onboarding** from the client's own brand voice + an archetype pick (a persona *type*, never a named person) + a short interview — the "read the host, bake in nothing" rule applied to the persona itself. In the brain/skin model ([[about-arbi-labs]] §3/§5), this slot carries the **skin** — the variable, per-instance persona; the **brain** — the marketer's judgment — is Arbi's and lives in the operator layer upstream, never in a slot this engine reads. The engine renders whatever skin the slot names and carries none. **This names what BRAND & VOICE already carries — no slot is added, so Contract-Revision stays 1.** *(Note: BR2 is now "one Arbi, one personality, one memory" — a temperament-neutral professional brain + a chosen human-like identity (the skin); how publicly that personality is deployed is a separate visibility-tier choice, not the personality itself — [[one-pager]] v0.4+. That visibility dial is an upstream operator choice and does not change what this slot carries (the skin); the `BR1b/BR2/N1` dependency stands.)*

> **Two optional keys inside the `character:` block.** *(2026-07-23 — Engine B / studio-skills.)* `animation_style` (string) carries the render-style/art-theme language for image and video prompts — e.g. "Pixar 3D style" is instance #0's *value* for this key, never an engine constant; read exclusively through `video_style_prefix()` in `agents/character.py`, which returns `animation_style` if set, else falls back to `visual_short`. `caption_style` (mapping) carries Engine B's per-clip caption overrides: `font_path`, `font_px`, `weight`, `box_rgb`, `text_rgb`, `pad_x`, `pad_y`, `radius`, `line_spacing`, `max_width_frac`, `y_frac`. **Both keys are optional** — a slot that omits them loads exactly as it did before this pass (Engine A falls back to `visual_short` for style; Engine B's caption resolution falls back to its own neutral white-box default). **Because neither is required, Contract-Revision stays 1.** The art-theme/style must live here and only here — never baked into engine code, a prompt template, or a config default (§5).

---

## 4. The read interface (the stable contract)

1. **By slot, never by path.** A phase asks for "the BRAND & VOICE doc," not for `brand/arbi-character.md`. The host maps its doc to the slot; the product resolves it under `STUDIO_CONTEXT_ROOT`.
2. **Typed block where one exists; whole-file prose otherwise.** The AUDIENCE slot is read as a fenced ```` ```yaml content_icp: ... ``` ```` block whose keys are the interface (`primary_audience`, `video_jobs`, `angle_selection_rule`, `lane_weights`, `hard_bars`, `success_metric`). This same fenced-block pattern is the template to generalize to a `brand:` and `voice:` block. Bibles with no structured block are read as raw text.
3. **Spine first, then the trunk.** Load SPINE as the prime, then pull only the slot a phase needs. Cheap context, no over-reading.
4. **Cite the IDs you depend on.** A phase that consumes a spine fact names its ID (TAKE derives from BR1b/BR2/N1), so a contract change is greppable and traceable — mirrors the [[one-pager]] maintenance protocol.
5. **Degrade honestly, fail loud on required slots.** A missing **optional** slot ⇒ log + documented fallback. A missing **required** slot ⇒ fail loudly at startup. **Never** silently reach back into instance #0's docs as a substitute.

---

## 5. What must NEVER be baked in

- **No character literals in agent code.** No "Arbi", "golden-yellow", "troll", "crown", "chaotic/sharp/unhinged" — not in a prompt template, a config default, an example, or a fallback branch. These enter through BRAND & VOICE or they do not exist.
- **No instance safety list in code.** `OFF_LIMITS_*` belongs in the BRAND & VOICE doc; each brand draws its own line.
- **No baked brand assets or distribution identity.** Outro / music / playlist id / title & hashtag templates are host-supplied or skipped — never an "Arbi" default that silently brands someone else's video.
- **No hardcoded cabinet layout.** Folder names and the tool's location inside the cabinet are the host's choice, resolved through `STUDIO_CONTEXT_ROOT` + the per-slot overrides.

> The product is allowed to know the *shape* of a brand doc; it is never allowed to know *Arbi's answer*. Code and templates ship; canon, character, and copy are read from the host at runtime.

---

## 6. Current conformance (honest state)

| Slot | Read through the contract today? |
|---|---|
| AUDIENCE | ✅ Yes — `agents/creative_director.py` extracts the `content_icp:` block. The first real seam. |
| BRAND & VOICE | ✅ Yes — **every** agent in **both engines** reads the host's character via `get_character()` (`agents/character.py`), which loads the fenced `character:` block. No agent bakes a character literal; no in-code fallback. Required keys validated at load → fail loud if missing. Engine B (`pipelines/scripted.py`) reads the same slot plus its two optional keys: `agents/scripted_video_producer.py` and `agents/scene_assembler.py` (caption-style merge). The fal/Kling producer for **both** Engine A (`agents/video_producer.py`, `agents/video_producer_grok.py`) and Engine B (`agents/scripted_video_producer.py`) now sources its render-style words exclusively from `video_style_prefix()` — `animation_style` if set, else `visual_short` — no baked style literal remains in either engine. |
| CHARACTER IMAGE | ✅ Yes — resolved through `resolve_character_image()` for `main.py`, `--resume`, the `video` pipeline, and `pipelines/video_x.py`. Env-swappable via `CONTEXT_CHARACTER_IMAGE` (alias `ARBI_CHARACTER_IMAGE`); default is the host cabinet's `brand/` asset, not a bundled file. |
| BRANDED ASSETS / DISTRIBUTION | ✅ Yes — outro/music read from `CONTEXT_OUTRO` / `CONTEXT_MUSIC_DIR` (absent ⇒ step skipped, never an Arbi substitute); title/description/hashtags/tags + playlist come from the slot's `distribution` block / `YOUTUBE_PLAYLIST_ID`. |
| Context root | ✅ Yes — `context_root.py` resolves every host doc under `STUDIO_CONTEXT_ROOT`; no `../../` climbs or Arbi filenames in agent code. |
| SPINE / VOICE / RELEVANCE LENS | 🟡 Declared, not yet consumed — slots resolve but no phase reads them yet. Tracked, not baked. |

**One-line finding:** the engine is now brand-free — the character, its sound, its image, its safety line, and its distribution copy all live in the host cabinet and are read through slots. `grep -ri "arbi\|troll\|golden-yellow\|crown" agents/` returns **clean**. The remaining open work (consume SPINE / VOICE / RELEVANCE LENS) lives in [`docs/portability-gaps-and-move-plan.md`](docs/portability-gaps-and-move-plan.md).

**Definition of done — met.** `grep -ri "arbi\|troll\|golden-yellow\|crown" agents/` returns nothing: the engine carries no character, not even a fallback loader. The same checkout, pointed at a different `STUDIO_CONTEXT_ROOT`, runs that cabinet's brand — "copy the engine, you still won't win" (P1 / H1) is literally true of this tool.

# Context Contract Audit — character-pipeline

*Slug renamed from `context-layer-contract.md` → `context-contract-audit.md` on 2026-06-15 to disambiguate from the org-level standard [`foundation/architecture/context-layer-contract.md`](../../../foundation/architecture/context-layer-contract.md). This doc is the **line-level conformance audit** of how far `products/character-pipeline` honors that contract — the standard is the **why**, this is the **how-far-from-it**. Per the Librarian's basename-collision flag.*

*Engineering companion to [`archive/business-vs-product.md`](../../../archive/business-vs-product.md) (PM, 🟠 awaiting Amit). That proposal defines the two spaces — **Arbi Labs the Business** (the context layer: spine, brand, plans — we are instance #0) and **Arbi Product** (this portable runtime) — and the **Context Layer Contract** between them: five named **slots** a product reads from the host cabinet, the hard rule (a product bakes in nothing from the host), and the portability test. This doc audits how far `products/character-pipeline` is from honoring that contract today, using the PM's slot names verbatim so the two interlock.*

*Spine facts cited from [[one-pager]] / [[ai-cmo/concept]]: **H1** — the engine is copyable on purpose; **S1** — installs into a business's own context; **ICP1** — product ICP. The PM doc already quotes the exact `creative_director.py` hardcoded paths flagged in §2 below — same bug, two angles.*

*Audited: 2026-06-11 (re-cut to the 5-slot taxonomy after the PM doc landed). Scope: `products/character-pipeline`. No `.env`/secrets touched.*

> **⏩ Status since this audit (read first).** This is the **2026-06-11 snapshot** of how far the code was from the contract — it documents the *baked-Arbi debt that has since been removed*, not the engine as it stands now. The de-baking has landed: `grep -ri "arbi\|troll\|golden-yellow\|crown" agents/` now returns **clean**, every agent reads the host character through `get_character()`, and there is no in-code fallback. For the current conformance state, see [`../CONTEXT.md`](../CONTEXT.md) §6. Treat the "baked into Arbi" findings below as the historical to-do list that drove that work — instance #0 is no longer wired into the engine.

---

## The one-line finding

Of the **five contract slots** the PM doc defines, the pipeline cleanly reads **one** (AUDIENCE), partially reads **one** (BRAND & VOICE — character only, via a single agent), and reads **none** of the other three (SPINE, RELEVANCE LENS, PLANS). Every unread slot is instead **baked into Python** as Arbi constants. Net: the tool is ~1.5 of 5 slots contract-driven. The one working seam (Creative Director) is the proof the pattern works; the job is to extend it to the other four and de-bake what it displaces.

---

## 1. Slot-by-slot: is the contract honored?

PM slots in CAPS; "filled here (instance #0) by" is the host doc that *should* feed the slot.

| Contract slot (PM §2) | Host doc (instance #0) | Pipeline agent that should consume it | Read today? | Reality |
|---|---|---|---|---|
| **SPINE** | `foundation/one-pager.md` | should prime every phase | **❌ No** | No agent opens it. P1/S1/H1/ICP1 never reach a render decision. |
| **BRAND & VOICE** | `brand/arbi-character.md` + `brand/voice/` | Creative Director (voice/identity), Animation Director, Sound, Cartoonist | **🟡 Partial** | Creative Director reads `arbi-character.md` whole-file. `brand/voice/` (Voice DNA, Content Context) read by **nothing**. Every other agent uses baked Arbi prompts. |
| **AUDIENCE** | `foundation/content-icp.md` | Creative Director (TAKE/angle) | **✅ Yes** | Reads the fenced `content_icp:` YAML block; degrades cleanly if absent. **The one real seam.** |
| **RELEVANCE LENS** | `foundation/keywords.md` | Video Scout (SENSE — score candidate events) | **❌ No** | Scout imports baked `OFF_LIMITS_*` from `arbi_persona.py` and reads only `data/trend_cache.json`. `keywords.md` is never opened. |
| **PLANS** *(optional)* | `foundation/content-intelligence.md` etc. | phase that needs it | **❌ No** | Not read. |

Asset inputs the contract folds into the slots above (not separate slots, but they leak Arbi the same way): **character image** — env `ARBI_CHARACTER_IMAGE` → baked default `artifacts/Character - New.png`; **branded outro** — `OUTRO_FILENAME = "outro.mp4"` hard-coded; **distribution** — "Arbi playlist", default title `"Arbi's Latest Adventure"`.

---

## 2. The one real seam vs. the baked debt

### The seam to copy — `agents/creative_director.py`
Reads the BRAND & VOICE character bible *and* the AUDIENCE ICP block, and **degrades, never crashes** (missing file → in-code fallback, logged). This graceful-degradation read is exactly the contract behavior the PM doc §2 step 4 asks for. **But** it resolves both via the hardcoded climb the PM doc quotes as the bug:

```python
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARBI_CHARACTER_PATH = os.path.normpath(os.path.join(_ROOT, "..", "..", "brand", "arbi-character.md"))
CONTENT_ICP_PATH    = os.path.normpath(os.path.join(_ROOT, "..", "..", "foundation", "content-icp.md"))
```

Two `..` hops that assume our tree + two Arbi filenames in source. Right read behavior, wrong locator — fails the portability test on the path alone.

### Baked into Arbi (every unread slot, plus leaks above the seam)
- **`agents/arbi_persona.py`** — `OFF_LIMITS_TOPICS/PROMPT` (should be **RELEVANCE LENS** / BRAND non-negotiables), `ARBI_VISUAL`, `ARBI_PERSONALITY`. In-code. Imported live by `video_scout.py`; fallback for `creative_director.py`.
- **`agents/script_writer.py`** — `SYSTEM_PROMPT` opens *"a character named Arbi — a golden-yellow furry monster with a gold crown"*; every few-shot example is an Arbi gag. Should read **BRAND & VOICE**; reads nothing.
- **`agents/creative_director.py` system prompt** — even while loading the persona file, re-hard-codes *"Arbi, a chaotic-neutral troll… confidently wrong."* The instance leaks back in *above* the contract read.
- **`agents/cartoonist.py`** — Arbi-specific dressing prompts throughout (RENDER reading BRAND & VOICE, baked).
- **`agents/voice_actor.py`** — sound identity is "troll gibberish + pitch shift": Arbi's voice as code, not a read of `brand/voice/`.
- **`agents/youtube_uploader.py`** — "Arbi playlist", `"Arbi's Latest Adventure"`. **`agents/outro_stitcher.py`** — `outro.mp4`.

---

## 3. The contract spec (engineering form of PM §2)

What the runtime must require, how it must read, what it must never bake — restated as build targets. Slot names are the PM's; this section is the *implementation* of that interface.

### 3.1 Required slots
Same five as PM §2. **Required:** SPINE, BRAND & VOICE, AUDIENCE, RELEVANCE LENS. **Optional:** PLANS. Asset sub-inputs (character image, outro, music, playlist/title) are host-supplied via the BRAND & VOICE / distribution config — never an Arbi default.

### 3.2 Read interface (the build targets)
1. **One host-supplied context root; resolve every slot relative to it.** Kill all `os.path.join(_ROOT, "..", "..", ...)` and filename literals. A `CABINET_ROOT` + a slot→path map (env or a `cabinet.toml`/`context:` manifest) is the whole mechanism. Swap the cabinet, set the root, source unchanged. (PM §2 "by slot, never by path".)
2. **Spine first, then the specific trunk.** Load SPINE as the prime for every phase, then pull only the slot a phase needs.
3. **Typed block where one exists, whole-file prose otherwise.** The `content_icp:` fenced-YAML block is already the model — generalize it to a `brand:`/`voice:` block and a `relevance:` block so agents read documented keys, not vibes; fall back to raw text for prose bibles.
4. **Cite the IDs you depend on** (TAKE → BR1b/BR2/N1, SENSE → ICP1) so a spine change is greppable.
5. **Degrade loudly, never silently.** Missing slot → documented fallback **+ a startup warning**, exactly as Creative Director logs today — never a silent reach into Arbi's constants.

### 3.3 The hard rule (PM §2) — enforced at the file level
> No brand constant, voice sample, ICP, "golden-yellow", or "Arbi" — not in a config default, prompt template, or fallback. Every business-specific value enters through a slot at install time, or it's a bug.

**Done =** `grep -ri "arbi\|troll\|golden-yellow\|crown" agents/` returns only the last-ditch fallback loader.

---

## 4. Portability gap list (ordered by leverage)

Each gap is a baked value that fails the PM's portability test ("would this survive being copied into Acme's cabinet?").

1. **Replace the `../../` path climb with a `CABINET_ROOT` + slot map.** Unblocks every other gap and is the exact bug the PM doc names. *Do first.*
2. **De-bake `script_writer.py`** — read BRAND & VOICE; drop the Arbi system prompt + examples. (100% baked, reads nothing.)
3. **Strip Arbi literals from the Creative Director system prompt** — let the loaded persona carry voice; stop overriding the file above the read.
4. **Wire RELEVANCE LENS** — Video Scout reads `keywords.md` (+ off-limits *from the brand doc*) instead of importing `OFF_LIMITS_*`. This is the slot the re-check surfaced as wholly unwired.
5. **Wire SPINE** — prime phases with the one-pager so ICP1/moat facts inform angle selection. Dead weight in the cabinet today.
6. **Wire `brand/voice/`** into `script_writer`/`voice_actor` (incl. the open non-verbal-vs-scripted call, per PM context).
7. **De-bake `cartoonist.py` + `voice_actor.py`** — dressing + sound become functions of BRAND & VOICE.
8. **Host-supply assets** — character image / outro / music / playlist / title from config; skip cleanly when absent; remove the Arbi defaults.
9. **Rename `arbi_persona.py` → `character.py`** (a loader, not a source of truth) once 2–7 land.
10. **Fix stale "red troll" copy in `docs/BUILD_YOUR_OWN_ARBI.md`** (says "wacky red furry troll"; Arbi is golden-yellow — [[arbi-visual-identity]]).

**Note on sequencing:** gap #1 is structural and lands cleanly under **either** of the PM's open options (A reframe-in-place / B physical `products/` space) — a context root is needed regardless. Gaps #2–#10 are the same retrofit either way; Option B only adds the wall that *prevents regression*, it doesn't change this list. So this work isn't blocked on Amit's A-vs-B call.

When gaps #1–#9 land, the same checkout pointed at Acme's cabinet runs Acme's brand — and **H1** ("copy the engine, you still won't win") is literally true of this tool.

---

## 5. The persona spec — where brain/skin meets the slot machinery

*(Added 2026-06-14 — voices & instance reframe, E9 second half. Companion to [[ai-cmo/concept]] "The instance model" section and `archive/voices-and-instance-reframe-proposal.md`. The instance-model section — naming the Onboarder-composed persona spec in the studio canon — landed in the AI CMO product concept on 2026-06-14; this is the engineering-side completion that was flagged "not part of that pass.")*

The reframe splits every Arbi into a **brain** — the marketer's judgment (strategy, taste, content direction), the *constant* a client buys, Arbi's and living in the operator / cross-network layer — and a **skin** — the public persona, the *variable* the client chooses (see [[ai-cmo/concept]] "Brain and skin" and "The instance model"). That split lands exactly on the seam this contract already draws:

- **The BRAND & VOICE slot is the skin.** What fills it is an **instance-level persona spec**: visual identity, personality, voice, the sound spec, the off-limits line. `brand/arbi-character.md` is **instance #0's** persona spec; a client cabinet drops in its own. This is precisely the doc the reframe calls "the client-cabinet equivalent of `arbi-character.md`" — so the persona spec needs **no new slot**; it *is* the `character:` block §1 already audits. The reframe gives that fill a name (persona spec) and a provenance (below); it adds nothing to the read interface. **Contract-Revision is unchanged.**
- **In a client cabinet the persona spec is Onboarder-composed** — from three inputs: the client's existing brand voice + an archetype pick (a persona *type* from a library — the deadpan critic, the hype-man — not a named person) + a short onboarding interview (see [[ai-cmo/concept]] "Path A — compose a new identity" and "Path B — rent a proven identity"). The same "read the host, bake in nothing" mechanism the whole engine runs on, applied to the persona itself; nothing invented or borrowed from a real person. The Onboarder *writes* the slot's doc; this engine only ever *reads* it. *(Composing this skin is **one step** of the Onboarder's job — it's the whole-workspace installer that stands up the entire instance #N, operator + operation + context; see [[onboarder]]. Writing character-pipeline's slots specifically is the [[onboarding-agent-spec|context-slot layer]] of that install.)*
- **The brain is not in this engine.** This pipeline is part of the copyable engine (**H1**). The judgment that decides *what* to perform and *why* is Arbi's, and lives upstream in the operator layer — never in a slot here. The engine reads the skin and renders it; it never carries the brain. That's the §5 instance-model guarantee restated at the file level: a bespoke persona spec swaps the skin and leaves Arbi's edge (the brain) untouched.

**BR2 re-sync.** BR2 evolved from a flat two-register binary to **"working register always-on + performance register as a tier dial"** ([[one-pager]] v0.3, 2026-06-14). That dial is an **operator / host concern upstream of this pipeline** — it sets how loud the persona plays in public (full mascot at tier 3 → invisible at tier 1; see [[ai-cmo/concept]] "The visibility spectrum"). It does **not** change this contract: the BRAND & VOICE slot carries the persona spec regardless of the host's visibility tier, and the `BR1b/BR2/N1` citations on that slot (§3.2.4) stand as-is. The dial decides *whether and how loud* the rendered skin is performed publicly; the slot decides *what the skin is*. Two different layers.

---

*Changelog — 2026-06-14:* added §5 (above) completing E9's contract half: the BRAND & VOICE slot is named as the **persona spec** / **skin** in the brain/skin model, its client-cabinet provenance recorded (Onboarder-composed), and BR2 re-synced to the dial framing. No slot added, no read-interface change → **Contract-Revision stays 1**. **Why:** the studio canon now ties the instance model to this engine's slot machinery ([[about-arbi-labs]] §5 links here); the contract reciprocates so the seam reads the same from both sides — and so "what fills BRAND & VOICE" has a name and a source, not just a shape.

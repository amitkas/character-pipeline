---
title: "Character Pipeline Content Audience — who the video pipeline targets"
created: "2026-06-11T00:00:00.000Z"
modified: "2026-06-21T00:00:00.000Z"
tags:
  - character-pipeline
  - content
  - audience
  - video
  - living
---

# Character Pipeline Content Audience — who the video pipeline targets

*The character pipeline's content-targeting doc — the `content_icp` block (§5) the **Creative Director** agent reads to pick a per-video angle and `video_job`. This is not the AI CMO's AUDIENCE slot (that's `growth/studio-brand-audience.md`). Moved from `growth/character-pipeline-content-icp.md` on 2026-06-21 — this is a product-specific doc and belongs with the product.*

*The audience definition here is derived from canon — [[about-arbi-labs]] §3 ("the room") — the same source as [[studio-brand-audience]]. A change to the primary room flows from there, not here. The Creative Director reads the `content_icp` YAML block at §5 (incl. `video_jobs`).*

> **Scope.** This doc is the character pipeline's content-targeting doc. The AI CMO does **not** read it — its AUDIENCE slot is [[studio-brand-audience]]. Both share the same canon source (§3 of [[about-arbi-labs]]).

---

## 1. The audience

*Derived from [[about-arbi-labs]] §3 ("the room"). The single source of truth is there; this section resolves it into the content-targeting lens.*

**Primary — the room we optimize for: AI-native builders, founders, and marketers.** The people building and marketing in the current AI/startup wave. Chronically online, fluent in internet culture, allergic to corporate marketing; they reward sharp/weird/fast over polished/safe. This is the room where "an AI character runs its own organic growth" is most credibly *demonstrated*, not just claimed — every take is implicitly proof-of-craft to the people we'll one day sell the engine to.

**Secondary — the reach layer: the broad short-form-entertainment internet.** We do not optimize *for* them, but the character must stay legible and funny *to* them — a joke only a growth marketer gets can't go wide, and reach is the raw material brand recognition is built from. They're the amplifier, not the target.

**Anti-audience — who it is explicitly NOT for:** anyone who wants earnest explainers, dry products/tech-announcement coverage, or brand-safe corporate content. Standing call: **AI news > dry tech announcements.** Beige is the only sin.

## 2. What each take must DO (the content job)

Every take does **one** primary job — the Creative Director picks it per take:

1. **Recognition** *(the default, most takes)* — make the primary room recognize and remember Arbi. Win = "I know that troll."
2. **Demonstration** *(the meta-flex / building-in-public)* — be live proof of character-led growth: on-trend, same-cycle, visibly AI-made. Win = "wait — an AI made this, this fast?"
3. **Resonance** *(the insider nod)* — say the quiet thing the primary room is already thinking about a trend. Win = shares *inside* the niche.

Two hard bars every take clears regardless of job:
- **On-character** — Arbi's chaotic-neutral troll, never punches down ([[arbi-character]] governs; this doc never overrides it).
- **Earns the first 2 seconds** — short-form reality; no hook, no view.

## 3. The angle-selection rule

> Pick the angle that maximizes: **"would an AI-native builder/marketer stop, laugh, and remember Arbi?"** Overweight trends in the AI / tech / startup / creator-culture lane. Treat generic celebrity/sports/news trends as usable *vehicles* only when the angle says something the primary room actually feels — not just because the event is big.

## 4. The metric

- **North-star (brand, compounding):** follower growth + recognition/return on the publish channel.
- **Per-take:** **engagement rate (engagements ÷ impressions)** against the Arbi account baseline — **plus a right-room read:** do replies/shares come from the AI/builder/marketing crowd (resonance) or generic accounts (reach without compounding)? Reach without the right room is logged, not celebrated. *(Baseline: Recon-measured near-zero floor as of 2026-06-17.)*

## 5. Agent-readable interface

*The Creative Director reads this block as a structured input alongside the trend analysis and the full Arbi persona — including `video_jobs`, which it picks one of per video. Keep the keys stable; edit values as the audience evolves.*

```yaml
content_icp:
  audience_key: ai-builder-room
  primary_audience: "AI-native builders, founders, marketers — online, culture-fluent, anti-corporate-marketing"
  secondary_audience: "broad short-form-entertainment internet — amplifier, not target"
  anti_audience: "earnest explainers, dry tech-announcement coverage, brand-safe corporate content"
  video_jobs: [recognition, demonstration, resonance]   # pick ONE per take
  angle_selection_rule: "maximize: would an AI-native builder/marketer stop, laugh, remember Arbi? overweight AI/tech/startup/creator-culture lane; generic trends only as vehicles for an in-room angle"
  lane_weights:
    ai_tech_startup_creator: overweight
    generic_celebrity_sports_news: vehicle_only
  hard_bars:
    on_character: true            # arbi-character.md governs; never override
    first_2s_hook: true
  success_metric:
    per_video: "engagement_rate vs near-zero baseline floor (Recon-measured 2026-06-17, heist hx_2ef2c151: median 0 engagement on sampled @ArbiLabs_Studio posts at 1 follower, ~9.7 link-shares/wk) + right-room qualitative read"
    north_star: "follower growth + recognition on publish channel"
  poc_platform: "X"                # resolved 2026-06-13 — first/only POC channel
  audience_fork: "RESOLVED — primary-room-lean hybrid confirmed by Amit 2026-06-13"
  parked_unresolved:               # working assumptions only — pressure-tested via AI CMO, not locked here
    format: "native-X (text/macros/clips) vs video-repurpose — open"
    narrative_spearhead: "troll-led vs build-in-public-led — open"
```

---

## References

- [[about-arbi-labs]] — §3 "the room" is the **source of truth** the audience definition derives from.
- [[arbi-character]] — Arbi's voice/character; the `on_character` bar. Not touched by this doc.
- [[studio-brand-audience]] — the **studio's** brand presence audience slot (AI CMO reads that, not this). Both share the same canon source.
- [[context-layer-contract]] — the portability standard; this doc fills the **AUDIENCE** slot for the character pipeline.
- `products/character-pipeline/` — the video pipeline that reads this file; the Creative Director agent consumes the `content_icp:` block, incl. `video_jobs`.

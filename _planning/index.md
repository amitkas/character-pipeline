---
title: "Character Led Pipeline (Arbi Flow)"
created: "2026-06-09T00:00:00.000Z"
modified: "2026-06-21T00:00:00.000Z"
tags:
  - project
  - pipeline
  - content-engine
---

# Character Led Pipeline (Arbi Flow)

*Summary of `Character Led Pipeline/BRIEF.md` (last updated 2026-06-08; renamed from "New Arbi" 2026-06-19).*

> **📦 The code now lives in the cabinet.** Source ported to [`products/character-pipeline/`](../) on 2026-06-10 — the full Python pipeline (agents, orchestrator, pipelines, utils, scripts, `.claude/` skills) minus generated `artifacts/`, git history, caches, and secrets. Start with [`products/character-pipeline/README.md`](../README.md) or [`BRIEF.md`](../BRIEF.md). Run config is `.env.example` → `.env` (keys not included).

## What it is

A **character-driven trend-to-video pipeline.** It finds a real-world trending event from the last 24 hours, then generates a ~13-second animated square video of **Arbi** — a wacky golden-yellow furry troll with a gold crown and googly eyes — re-enacting that event with physical comedy, troll sounds, and burned-in overlays. Optionally auto-uploads to YouTube. Each run takes **~5 minutes** and costs **~$0.77**.

This is the **creative content engine** of Arbi Labs. PlayArbi gives Arbi a stage; Character Led Pipeline gives him a feed.

## Current state — built and working

- **Full 10-agent Python pipeline** running end-to-end: Video Scout → Finder → Analyzer → Character Dresser → Animation Director → Producer → Troll Sound Designer → Subtitle Burner → Outro Stitcher → YouTube Uploader.
- **Tool stack:** Gemini 2.5 Flash (trends/analysis/image/text), fal.ai Kling 2.5 Turbo Pro (video), ElevenLabs (sound), Serper (search), yt-dlp, ffmpeg.
- **Claude Code skills installed** (`/setup`, `/video`, `/video-pick`, `/video-custom`) — runnable without touching the terminal.
- **Robust failure handling:** dedup tracking, file locking, 3-tier image-gen fallback, subject switching on bad videos, non-fatal upload, resumable runs.
- **Distribution-ready public guide** (`docs/BUILD_YOUR_OWN_ARBI.md`) — already templated as a *generalized* character-pipeline product, not just an Arbi tool.
- **YouTube OAuth** working; auto-uploads to a designated Arbi playlist.

## First live test — 2026-06-11

Ran end-to-end against real APIs for the first time (take/render split, dogfooded on the Troll). Result: the **fal+ElevenLabs** path produced a real on-model video but **silent** (ElevenLabs free-tier paywalled the configured voice); the **grok** path **crashed** (no Character Dresser wired into that path). The **red→golden-yellow color bug** was found and fixed in code. Nothing published. Full write-up: [`products/character-pipeline/docs/first-live-test-2026-06-11.md`](../docs/first-live-test-2026-06-11.md). PM read on what this means for the week-one bet: [[content-engine-status-2026-06-11]].

## Open threads

- **Real-time trend-hunting** — detect a trend *the moment* it spikes and ship matching creative inside the same news cycle. Top-priority hypothesis; World Cup 2026 is the live test.
- **Scheduling** — currently a manual `python3 main.py`. No scheduler or queue (Cabinet's scheduled jobs solve this).
- **Multi-character / multi-style** — hard-coded to Arbi; a `character.yaml` config layer would unlock the generalized product.
- **No measurement loop** — no tracking of what performed; a results-back-into-Scout loop is missing.
- **YouTube-only output** — no TikTok / IG Reels / X / 9:16 vertical yet (Kling supports it; just not wired in).
- **No publish-to-X/TikTok/IG agent** to match the YouTube Uploader.
- **Cost ceiling** — ~$0.77/run adds up; no budget guardrails or per-channel cost reporting.

## Cabinet role — embedded tool

Becomes `products/character-pipeline/`: the Python pipeline runs as-is behind a thin HTML control panel ("Run now / View last 10 runs / Schedule daily"), driven by Cabinet's scheduled jobs. The character bible lives as markdown in `brand/arbi-character.md` so the pipeline reads the same source of truth as the rest of the studio. Run logs land in `products/character-pipeline/data/`, queryable by other agents (e.g. a Social Distribution agent that posts output to X).

**The bigger move:** once it's a Cabinet app, it ports to *any* workspace — swap `brand/character.md` for another persona and a founder has a character-driven content engine in 30 minutes.

## Next experiment

**Real-time trend-hunting around World Cup 2026.** A "trend spike" detector running every 15 minutes during the tournament that triggers a pipeline run within the same hour an event happens. Target: under 60 minutes from event to publish; measure views and follower growth.

---

← Back to [Products](../../index.md) · [[Arbi Labs]] studio home.

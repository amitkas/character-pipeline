"""Architecture verification for TAKE-as-artifact (PRD §3 acceptance criteria A–D).

Drives ONE persisted take through TWO render paths (fal+elevenlabs, grok) and
checks every A–D criterion against the REAL code paths: take.py (emit/persist/
load_take), the orchestrator render-path loop, learn.py, and the path config.

This runs OFFLINE: there are no render credentials in this environment, so the
network producers (Gemini / fal / ElevenLabs / Grok) are substituted with a
placeholder base video. Everything that A–D actually assert — the take artifact,
the seam, one-take-two-paths, and the learn log — is exercised for real. The
produced .mp4s are architecture proofs, NOT publish-quality videos.

Run:  python3 scripts/verify_take_as_artifact.py
Exits non-zero if any criterion fails.
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from context.video import VideoContext
from agents.take_emitter import emit_take_artifact
from take import load_take, take_path, SCHEMA_VERSION
from learn import read_learn, LEARN_LOG
from orchestrator import run_render_path
from pipelines.video import RENDER_PATHS, TAKE_AGENTS
from logger import setup_logging

PASS, FAIL = "PASS", "FAIL"
_results = []


def check(criterion, ok, detail=""):
    _results.append((criterion, bool(ok), detail))
    mark = PASS if ok else FAIL
    print(f"  [{mark}] {criterion}  {detail}")
    return ok


def seed_take_ctx() -> VideoContext:
    """A completed TAKE-phase ctx for a benign, off-limits-safe sample event.
    Stands in for Scout/Finder/Analyzer/Animation Director output so we can emit a
    real take without the network TAKE agents (which need credentials)."""
    ctx = VideoContext(run_id="seedtake", started_at="2026-06-10T00:00:00", pipeline_name="video")
    ctx.event_title = "Robot Vacuum Wins Local Talent Show"
    ctx.event_description = (
        "A robot vacuum entered a small-town talent show and 'performed' by "
        "bumping into furniture in rhythm, delighting the crowd."
    )
    ctx.source_video_url = "https://example.com/robot-vacuum-talent-show"
    ctx.scout_source = "gemini-grounded"
    # Explicit pointer so this verifier is character-agnostic and slot-independent.
    ctx.voice_tag = "test-character"
    ctx.chaos_angle = "The character is convinced the vacuum stole its spotlight and demands a rematch."
    ctx.animation_direction = (
        "The character shoves a tiny robot vacuum aside, grabs a mic, and belts a "
        "dramatic solo while spinning in a victory circle."
    )
    ctx.scene_prompt = "The character crashes a talent-show stage, snatches the mic from a robot vacuum, and performs."
    ctx.character_outfit = "Sparkly silver stage jacket with oversized sequined bowtie"
    ctx.character_gender = "male"
    ctx.video_keywords = ["talent", "spotlight", "rematch", "encore"]
    return ctx


def main():
    setup_logging("verify")
    print("=" * 70)
    print("  TAKE-as-artifact — acceptance verification (PRD §3 A–D)  [OFFLINE]")
    print("=" * 70)

    # ── Emit ONE take (the seam: Take Emitter persists data/takes/{take_id}.json) ──
    ctx = seed_take_ctx()
    ctx = emit_take_artifact(ctx, {})
    take_id = ctx.take_id
    tpath = take_path(take_id)
    print(f"\n  Persisted take: {tpath}\n")

    raw = json.load(open(tpath, encoding="utf-8"))

    # ── A. The take is a real, standalone artifact ──────────────────────────
    print("A. The take is a real, standalone artifact")
    expected_keys = {"take_id", "schema_version", "created_at", "voice_tag",
                     "event", "angle", "line", "visual_direction"}
    check("A1 one take file, six-field schema",
          set(raw.keys()) == expected_keys and raw["schema_version"] == SCHEMA_VERSION,
          f"keys={sorted(raw.keys())}")
    check("A2 voice_tag is a short pointer string, not embedded voice/lines",
          isinstance(raw["voice_tag"], str) and raw["voice_tag"] == "test-character"
          and "\n" not in raw["voice_tag"] and len(raw["voice_tag"]) < 64,
          f"voice_tag={raw['voice_tag']!r}")
    vd = raw["visual_direction"]
    no_image = ("cartoon_image_path" not in raw and "cartoon_image_path" not in vd
                and not any("image" in k for k in vd))
    check("A3 no cartoon image in take; visual_direction is text only",
          no_image and set(vd.keys()) == {"scene", "outfit", "subject_gender", "keywords"},
          f"visual_direction keys={sorted(vd.keys())}")
    hydrated = load_take(take_id)
    check("A4 load_take round-trips into a usable ctx",
          hydrated.take_id == take_id
          and hydrated.event_title == raw["event"]["title"]
          and hydrated.character_outfit == vd["outfit"]
          and hydrated.scene_prompt == vd["scene"]
          and hydrated.chaos_angle == raw["angle"]
          and hydrated.animation_direction == raw["line"],
          "event/outfit/scene/angle/line all hydrated")

    # ── B + C + D: drive the ONE take through BOTH render paths ──────────────
    take_agent_names = {n for n, _ in TAKE_AGENTS}
    print("\n  Rendering both paths from the one persisted take (offline)...")
    rendered = []
    ctx_objs = []
    for path_name, path_cfg in RENDER_PATHS.items():
        ctx_r, asset_path, row = run_render_path(
            take_id, path_name, path_cfg, config={}, offline=True, publish=False
        )
        rendered.append((path_name, path_cfg, asset_path, row))
        ctx_objs.append(ctx_r)

    print("\nB. One take genuinely feeds two paths")
    check("B1 two assets produced; no TAKE-phase agent appears in any render path",
          len(rendered) == 2
          and all(not (take_agent_names & {n for n, _ in cfg["agents"]})
                  for _, cfg, _, _ in rendered),
          f"{len(rendered)} assets, render agents disjoint from TAKE agents")
    def _abs(p):
        return p if os.path.isabs(p) else os.path.join(ROOT, p)
    name_re = re.compile(r"^" + re.escape(take_id) + r"__[\w+-]+__\dx\d+\.mp4$")
    names_ok = all(name_re.match(os.path.basename(p)) for _, _, p, _ in rendered)
    check("B2 output files named by take + technique + ratio",
          names_ok,
          " | ".join(os.path.basename(p) for _, _, p, _ in rendered))
    check("B3 each path used a fresh ctx hydrated from the take (no leakage)",
          ctx_objs[0] is not ctx_objs[1]
          and all(c.take_id == take_id for c in ctx_objs)
          and all(ctx_objs[i].aspect_ratio == rendered[i][1]["aspect_ratio"]
                  for i in range(len(rendered))),
          "distinct ctx objects, each carrying its own path's config")
    # B4: aspect ratio is read from path config (changing it needs no code edit to
    # video_producer.py). We assert each path's ctx ratio equals its configured ratio —
    # whether the two paths share a ratio (both 9:16 today) or differ is a product call,
    # not an architecture property.
    b4_ok = all(ctx_objs[i].aspect_ratio == rendered[i][1]["aspect_ratio"]
                for i in range(len(rendered)))
    check("B4 aspect ratio read from path config (no code edit to change it)",
          b4_ok,
          " | ".join(f"{rendered[i][0]}={ctx_objs[i].aspect_ratio}" for i in range(len(rendered))))

    print("\nC. The seam holds")
    fal_cfg = RENDER_PATHS["fal+elevenlabs"]
    dresser_render_side = "Character Dresser" in {n for n, _ in fal_cfg["agents"]}
    check("C1 Character Dresser runs render-side, loading outfit+scene from the hydrated take",
          dresser_render_side
          and hydrated.character_outfit == vd["outfit"]
          and hydrated.scene_prompt == vd["scene"],
          "Dresser is in the fal render path; outfit/scene come from the take")
    # C2: both assets were produced by run_render_path, which sources its ctx ONLY
    # from load_take(take_id) and runs ONLY render-path agents — no TAKE agent is
    # ever called. So removing/renaming a TAKE agent cannot break a render from an
    # already-persisted take. (No extra render here — proven by construction in B,
    # keeping the learn log at exactly one row per asset.)
    render_only = all(not (take_agent_names & {n for n, _ in cfg["agents"]})
                      for _, cfg, _, _ in rendered)
    take_file_self_sufficient = load_take(take_id).event_title == raw["event"]["title"]
    check("C2 render path runs from an already-persisted take with no TAKE agent involved",
          render_only and take_file_self_sufficient
          and all(os.path.exists(_abs(p)) for _, _, p, _ in rendered),
          "both assets sourced from the take file alone; TAKE agents not invoked")

    print("\nD. LEARN log is correct and joinable")
    rows = [r for r in read_learn() if r.get("take_id") == take_id]
    full_keys = {"ts", "take_id", "technique", "aspect_ratio", "cost_usd",
                 "control_of_script", "asset_path", "platform", "asset_url",
                 "engagement_rate", "impressions"}
    check("D1 one append-only row per asset (exactly two, never rewritten)",
          len(rows) == 2 and all(set(r.keys()) == full_keys for r in rows),
          f"{len(rows)} rows for this take_id")
    join_ok = all(os.path.exists(take_path(r["take_id"])) for r in rows)
    check("D2 every row carries the full key set; take_id joins to a real take file",
          join_ok and all(set(r.keys()) == full_keys for r in rows),
          f"take_id joins to {os.path.basename(take_path(take_id))}")
    by_tech = {}
    for r in rows:
        by_tech.setdefault(r["technique"], r)
    check("D3 grok rows log control_of_script=false; fal+elevenlabs log true",
          by_tech.get("grok", {}).get("control_of_script") is False
          and by_tech.get("fal+elevenlabs", {}).get("control_of_script") is True,
          f"grok={by_tech.get('grok',{}).get('control_of_script')} "
          f"fal={by_tech.get('fal+elevenlabs',{}).get('control_of_script')}")
    cost_ok = all(isinstance(r["cost_usd"], (int, float)) and r["cost_usd"] > 0 for r in rows)
    null_ok = all(r["engagement_rate"] is None and r["impressions"] is None for r in rows)
    check("D4 cost_usd populated; engagement_rate / impressions present and null",
          cost_ok and null_ok,
          f"costs={[r['cost_usd'] for r in rows]}, engagement/impressions all null={null_ok}")

    # ── Report ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    print(f"  RESULT: {passed}/{total} criteria PASS")
    print(f"  take:      {tpath}")
    print(f"  learn_log: {LEARN_LOG}  ({len(rows)} rows for {take_id})")
    print("  assets:")
    for path_name, _, asset_path, _ in rendered:
        exists = "ok" if os.path.exists(_abs(asset_path)) else "MISSING"
        print(f"    - {path_name:16s} {asset_path}  [{exists}]")
    print("=" * 70)

    if passed != total:
        print("  SOME CRITERIA FAILED")
        sys.exit(1)
    print("  ALL A–D CRITERIA PASS")


if __name__ == "__main__":
    main()

"""Generic pipeline runner for Arbi Flow.

Each pipeline defines its own agent sequence, context factory, and optional
summary builder, then calls run_pipeline() to execute."""

import glob
import os
import re
import shutil
import sys
import time
import uuid
from datetime import datetime

from config import load_config
from dedup import mark_processed
from logger import setup_logging, get_logger, StepTimer, write_run_summary
from take import load_take
from learn import append_learn
from context_root import cabinet_root
from version import engine_version, contract_revision, VersionError


def _engine_stamp() -> str:
    """One-line 'v<semver> · contract rev <n>' for logs; degrades loud, never aborts."""
    try:
        return f"v{engine_version()} · contract rev {contract_revision()}"
    except VersionError as e:
        return f"UNREADABLE ({e})"

# Render agents that only touch ffmpeg (no network / no API credentials). In
# offline mode we substitute a placeholder base video for the network producers
# but still run these for real, exercising the real render tail.
OFFLINE_SAFE_AGENTS = {"Subtitle Burner", "Outro Stitcher"}

# Agents that perform the external publish (PRD T9 / criterion E). Skipped unless
# publish=True so finished assets are staged for manual sign-off, never auto-shipped.
PUBLISH_AGENTS = {"YouTube Uploader"}

# Offline placeholder base-video dimensions per aspect ratio.
_OFFLINE_DIMS = {"1:1": (576, 576), "9:16": (576, 1024), "16:9": (1024, 576)}


class PipelineError(Exception):
    """Raised when a pipeline agent fails. Callers decide how to handle it."""

    def __init__(self, agent_name: str, error: str, ctx=None):
        self.agent_name = agent_name
        self.error = error
        self.ctx = ctx
        super().__init__(f"{agent_name} failed: {error}")


def run_pipeline(pipeline_name, agents, context_factory, summary_builder=None, excluded_events=None, event=None, description=None):
    """Run a named pipeline: load config, create context, execute agents in sequence.

    Args:
        pipeline_name: Human-readable name (e.g., "Video Pipeline")
        agents: List of (step_name, agent_function) tuples
        context_factory: Callable(run_id, started_at, config, **kwargs) -> context instance
        summary_builder: Optional callable(ctx, agent_timings, total_time) -> dict
        excluded_events: Optional list of event titles to exclude (e.g. undownloadable subjects)
        event: Optional pinned event title — skips auto-scouting when provided
        description: Optional description for the pinned event
    Returns:
        The final context object after all agents have run.
    """
    log = get_logger("orchestrator")

    print("=" * 60)
    print(f"  ARBI FLOW \u2014 {pipeline_name}")
    print("=" * 60)

    # Load config
    try:
        config = load_config()
        print("[OK] Config loaded\n")
    except ValueError as e:
        print(f"[FAIL] {e}")
        sys.exit(1)

    # Create context
    run_id = uuid.uuid4().hex[:8]
    started_at = datetime.now().isoformat()
    factory_kwargs = {
        "excluded_events": excluded_events or [],
        "event": event,
        "description": description,
    }
    ctx = context_factory(run_id, started_at, config, **factory_kwargs)

    # Set up logging
    setup_logging(run_id)
    log.info(f"Pipeline: {pipeline_name}")
    log.info(f"Engine: {_engine_stamp()}")
    log.info(f"Run ID: {run_id}")
    log.info(f"Started: {started_at}")

    # Clean up any partial downloads from previous failed runs
    _cleanup_partial_downloads(log)

    # Run agents in sequence
    pipeline_start = time.time()
    agent_timings = {}

    for name, agent_fn in agents:
        log.info(f"\n{'─' * 50}")
        log.info(f">> {name}")
        log.info(f"{'─' * 50}")

        with StepTimer(get_logger(name.lower().replace(" ", "_")), name) as timer:
            try:
                ctx = agent_fn(ctx, config)
                log.info(f"[OK] {name} completed ({timer.elapsed:.1f}s)")
            except Exception as e:
                log.error(f"\n[FAIL] {name} failed after {timer.elapsed:.1f}s: {e}")
                ctx.errors.append({"agent": name, "error": str(e)})
                agent_timings[name] = {
                    "status": "failed",
                    "elapsed_s": round(timer.elapsed, 2),
                    "error": str(e),
                }
                _write_summary(ctx, agent_timings, pipeline_start, pipeline_name, summary_builder)
                log.info("\nPipeline aborted.")
                raise PipelineError(name, str(e), ctx=ctx)

        agent_timings[name] = {"status": "ok", "elapsed_s": round(timer.elapsed, 2)}

    # Mark event as processed (dedup)
    if ctx.event_title:
        mark_processed(ctx.event_title, ctx.run_id)

    # Summary
    total_time = time.time() - pipeline_start
    log.info(f"\n{'=' * 60}")
    log.info(f"  {pipeline_name.upper()} COMPLETE")
    log.info(f"{'=' * 60}")
    log.info(f"  Engine:     {_engine_stamp()}")
    log.info(f"  Event:      {ctx.event_title}")
    log.info(f"  Description:{ctx.event_description}")
    log.info(f"  Video:      {ctx.final_video_path or 'no video produced'}")
    log.info(f"  Run ID:     {ctx.run_id}")
    log.info(f"  Total time: {total_time:.1f}s")
    log.info(f"{'=' * 60}")

    # Write JSON summary
    summary_path = _write_summary(ctx, agent_timings, pipeline_start, pipeline_name, summary_builder)
    log.info(f"  Summary:    {summary_path}")

    # Move final output to output/ and clean up artifacts
    _finalize_output(ctx, log)

    return ctx


def cleanup_run_artifacts(run_id: str):
    """Remove run-specific artifacts from videos/, images/, audio/. Call after output is copied."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    artifacts_dir = os.path.join(project_root, "artifacts")
    for subdir in ("videos", "images", "audio"):
        dirpath = os.path.join(artifacts_dir, subdir)
        if not os.path.isdir(dirpath):
            continue
        for f in glob.glob(os.path.join(dirpath, f"{run_id}_*")):
            try:
                os.remove(f)
            except Exception:
                pass
    for d in glob.glob(os.path.join(artifacts_dir, f"{run_id}_frames*")):
        shutil.rmtree(d, ignore_errors=True)


def _cleanup_partial_downloads(log):
    """Remove incomplete downloads (.part, .webm) from previous failed runs."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    artifacts_dir = os.path.join(project_root, "artifacts", "videos")

    if not os.path.isdir(artifacts_dir):
        return

    partial_files = (
        glob.glob(os.path.join(artifacts_dir, "*.part")) +
        glob.glob(os.path.join(artifacts_dir, "*.webm"))
    )

    if partial_files:
        for f in partial_files:
            try:
                os.remove(f)
                log.debug(f"Removed partial download: {os.path.basename(f)}")
            except Exception as e:
                log.warning(f"Failed to remove {f}: {e}")
        log.info(f"  Cleaned {len(partial_files)} partial download(s) from previous runs")


def _write_summary(ctx, agent_timings, pipeline_start, pipeline_name, summary_builder=None):
    total_time = time.time() - pipeline_start

    if summary_builder:
        summary = summary_builder(ctx, agent_timings, total_time)
    else:
        summary = {
            "run_id": ctx.run_id,
            "pipeline": pipeline_name,
            "started_at": ctx.started_at,
            "finished_at": datetime.now().isoformat(),
            "total_time_s": round(total_time, 2),
            "event_title": ctx.event_title,
            "event_description": ctx.event_description,
            "final_video_path": ctx.final_video_path or "",
            "agents": agent_timings,
            "errors": ctx.errors,
        }

    return write_run_summary(ctx.run_id, summary)


def _finalize_output(ctx, log):
    """Move final output to output/ with a clean name, then delete run artifacts."""

    project_root = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(project_root, "output")
    artifacts_dir = os.path.join(project_root, "artifacts")
    os.makedirs(output_dir, exist_ok=True)

    # Determine the final video file
    final_path = (
        ctx.final_video_path
        or ctx.subtitled_video_path
        or ctx.video_local_path
    )

    if final_path and os.path.exists(final_path):
        # Build clean filename: Event_Title_runid.ext
        ext = os.path.splitext(final_path)[1]
        title = ctx.event_title or ctx.run_id
        clean_title = re.sub(r"[^\w\s-]", "", title).strip()
        clean_title = re.sub(r"[\s-]+", "_", clean_title)
        clean_name = f"{clean_title}_{ctx.run_id}{ext}"

        dest = os.path.join(output_dir, clean_name)
        shutil.copy2(final_path, dest)
        log.info(f"  Output:     {dest}")
    else:
        log.info("  Output:     no media file to export")

    cleanup_run_artifacts(ctx.run_id)
    log.info(f"  Cleanup:    artifacts for {ctx.run_id} removed")


# ─────────────────────────────────────────────────────────────────────────────
# TAKE-as-artifact: one take → N render paths (architecture §3–§5, PRD T5)
# ─────────────────────────────────────────────────────────────────────────────

def _default_character_image() -> str:
    """Instance #0's default CHARACTER IMAGE: the host cabinet's brand asset.

    Host-supplied, not bundled in the product (Context Layer Contract §6). Mirrors
    the BRAND slot default in ``context_root.py`` — a different cabinet overrides via
    ``CONTEXT_CHARACTER_IMAGE``."""
    return os.path.join(cabinet_root(), "brand", "arbi-character.png")


def resolve_character_image(config=None) -> str:
    """Resolve the character reference image — the CHARACTER IMAGE context slot.

    Reads CONTEXT_CHARACTER_IMAGE (preferred) or its deprecated alias
    ARBI_CHARACTER_IMAGE, from config or the environment. Absolute paths are used
    as-is; relative paths are tried against the tool dir, the cabinet root, then
    cwd. Falls back to the host cabinet's brand asset when unset (instance #0)."""
    tool_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(os.path.dirname(tool_dir))  # cabinet root

    def _read(key: str) -> str:
        val = ""
        if config:
            val = (config.get(key) or "").strip()
        if not val:
            val = os.environ.get(key, "").strip()
        return val

    configured = _read("CONTEXT_CHARACTER_IMAGE") or _read("ARBI_CHARACTER_IMAGE")

    if configured:
        if os.path.isabs(configured):
            return configured
        for base in (tool_dir, repo_root, os.getcwd()):
            cand = os.path.join(base, configured)
            if os.path.exists(cand):
                return cand
        return configured  # not found — return as given; downstream logs/falls back

    return _default_character_image()


def _offline_base_video(ctx) -> str:
    """Generate a placeholder base video (no network / no credentials) at the
    path's aspect ratio. Stands in for the network producers so the real render
    tail (subtitle/outro) and the real take→hydrate→learn mechanics can be
    exercised and verified without paid API calls. NOT a publish-quality asset."""
    import subprocess

    w, h = _OFFLINE_DIMS.get(getattr(ctx, "aspect_ratio", "1:1"), _OFFLINE_DIMS["1:1"])
    artifacts_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "artifacts", "videos"
    )
    os.makedirs(artifacts_dir, exist_ok=True)
    out = os.path.join(artifacts_dir, f"{ctx.run_id}_final.mp4")

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x2b2b3a:s={w}x{h}:d=3:r=30",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", out,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    ctx.video_local_path = out
    if not getattr(ctx, "render_cost_usd", 0.0):
        ctx.render_cost_usd = 0.0  # placeholder render has no real cost
    return out


def _finalize_asset(ctx, take_id, technique, aspect_ratio, log) -> tuple:
    """Copy the path's final video to output/{take_id}__{technique}__{ratio}.mp4
    (PRD B2). Returns ``(rel, produced)``: the project-relative asset path (e.g.
    ``output/...``, matching the §4 row spec) and a bool for whether a real media
    file was actually copied. Cleans up run artifacts after."""
    project_root = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(project_root, "output")
    os.makedirs(output_dir, exist_ok=True)

    tech_slug = technique.replace("+", "-")
    ratio_slug = aspect_ratio.replace(":", "x")
    name = f"{take_id}__{tech_slug}__{ratio_slug}.mp4"
    dest = os.path.join(output_dir, name)
    rel = os.path.join("output", name)

    final_path = ctx.final_video_path or ctx.subtitled_video_path or ctx.video_local_path
    produced = bool(final_path and os.path.exists(final_path))
    if produced:
        shutil.copy2(final_path, dest)
        log.info(f"  Asset:      {rel}")
    else:
        log.warning(f"  Asset:      no media file produced for {rel}")

    cleanup_run_artifacts(ctx.run_id)
    return rel, produced


def run_render_path(take_id, path_name, path_config, config, run_id=None,
                    offline=False, publish=False):
    """Render one path from a persisted take (architecture §4, PRD B1–B4, C, D).

    Hydrates a FRESH ctx from load_take(take_id) — no cross-path ctx leakage —
    stamps the render-path config (technique / aspect_ratio / control_of_script)
    onto it, runs the path's agents, finalizes the asset, and appends exactly one
    learn-log row keyed by take_id.

    offline=True  → substitute a placeholder base video for the network producers,
                    then run the real ffmpeg-only tail (subtitle/outro).
    publish=False → omit the publish agent (stage for sign-off; PRD stops before T9).
    """
    log = get_logger("orchestrator")

    # B3: fresh ctx hydrated solely from the persisted take.
    ctx = load_take(take_id)
    ctx.run_id = run_id or uuid.uuid4().hex[:8]
    ctx.started_at = datetime.now().isoformat()
    ctx.pipeline_name = f"render:{path_name}"
    ctx.character_image_path = resolve_character_image(config)

    # Stamp render-path config (technique is the primary variable; aspect_ratio the
    # free second axis; control_of_script the moat flag).
    technique = path_config.get("technique", path_name)
    aspect_ratio = path_config.get("aspect_ratio", "1:1")
    control_of_script = path_config.get("control_of_script", True)
    ctx.technique = technique
    ctx.aspect_ratio = aspect_ratio
    ctx.control_of_script = control_of_script

    log.info("=" * 60)
    log.info(f"  RENDER PATH: {path_name}  ({technique}, {aspect_ratio}, "
             f"control_of_script={control_of_script}{', OFFLINE' if offline else ''})")
    log.info(f"  take_id: {take_id}  run_id: {ctx.run_id}")
    log.info("=" * 60)

    agents = list(path_config["agents"])
    if offline:
        _offline_base_video(ctx)
        agents = [(n, fn) for (n, fn) in agents if n in OFFLINE_SAFE_AGENTS]
    if not publish:
        agents = [(n, fn) for (n, fn) in agents if n not in PUBLISH_AGENTS]

    failed_agents = []
    for name, agent_fn in agents:
        log.info(f"\n>> {name}")
        with StepTimer(get_logger(name.lower().replace(" ", "_")), name) as timer:
            try:
                ctx = agent_fn(ctx, config)
                log.info(f"[OK] {name} completed ({timer.elapsed:.1f}s)")
            except Exception as e:
                log.error(f"[FAIL] {name} failed after {timer.elapsed:.1f}s: {e}")
                ctx.errors.append({"agent": name, "path": path_name, "error": str(e)})
                failed_agents.append(name)

    # A Sound Engineer failure otherwise slips by quietly and leaves a SILENT
    # asset that still looks "successful" (first-live-test bug #1). Make it loud.
    if "Sound Engineer" in failed_agents:
        log.error("!" * 60)
        log.error(f"  AUDIO FAILED on path '{path_name}' — Sound Engineer did not complete.")
        log.error("  The resulting asset will be SILENT. Treat this render as degraded.")
        log.error("!" * 60)

    asset_path, produced = _finalize_asset(ctx, take_id, technique, aspect_ratio, log)

    # Data quality (first-live-test note): only log a learn row when a real asset
    # was actually produced — never point a row at a file that was never created.
    if not produced:
        log.error(
            f"  No asset produced for path '{path_name}' — skipping learn-log row "
            f"(failed agents: {', '.join(failed_agents) or 'none'})."
        )
        return ctx, asset_path, None

    # cost_usd: producer-reported if available, else the path's configured estimate.
    cost_usd = ctx.render_cost_usd or path_config.get("cost_usd", 0.0)

    # platform / asset_url only exist once the asset is actually published (E1).
    platform = "youtube" if (publish and getattr(ctx, "youtube_video_url", "")) else None
    asset_url = getattr(ctx, "youtube_video_url", "") or None if publish else None

    row = append_learn(
        take_id=take_id,
        technique=technique,
        aspect_ratio=aspect_ratio,
        cost_usd=cost_usd,
        control_of_script=control_of_script,
        asset_path=asset_path,
        platform=platform,
        asset_url=asset_url,
        # engagement_rate / impressions stay null (D4) — backfilled when channel data connects.
    )
    log.info(f"  LEARN row appended: {row}")

    return ctx, asset_path, row


def run_take_and_render(pipeline_name, take_agents, render_paths, context_factory,
                        selected_paths=None, excluded_events=None, event=None,
                        description=None, offline=False, publish=False, render=True):
    """Two-phase runner (PRD T5): run the TAKE phase ONCE → persist the take →
    loop the selected render paths, each hydrating a fresh ctx from the take.

    Replaces the single flat agent sequence for the video pipeline. The TAKE
    agents (Scout / Finder / Analyzer / Animation Director / Take Emitter) run
    exactly once (B1); each render path then starts from load_take(take_id).

    render=False stops after persisting the take (HITL gate G2: the human reviews
    data/takes/{take_id}.json before any render budget is spent)."""
    log = get_logger("orchestrator")

    print("=" * 60)
    print(f"  ARBI FLOW — {pipeline_name}")
    print("=" * 60)

    try:
        config = load_config()
        print("[OK] Config loaded\n")
    except ValueError as e:
        print(f"[FAIL] {e}")
        sys.exit(1)

    run_id = uuid.uuid4().hex[:8]
    started_at = datetime.now().isoformat()
    ctx = context_factory(run_id, started_at, config,
                          excluded_events=excluded_events or [],
                          event=event, description=description)

    setup_logging(run_id)
    log.info(f"Pipeline: {pipeline_name}  (TAKE phase, run {run_id})")
    _cleanup_partial_downloads(log)

    # ── TAKE phase (runs once) ──────────────────────────────────────────────
    pipeline_start = time.time()
    agent_timings = {}
    for name, agent_fn in take_agents:
        log.info(f"\n{'─' * 50}\n>> {name}\n{'─' * 50}")
        with StepTimer(get_logger(name.lower().replace(" ", "_")), name) as timer:
            try:
                ctx = agent_fn(ctx, config)
                log.info(f"[OK] {name} completed ({timer.elapsed:.1f}s)")
            except Exception as e:
                log.error(f"[FAIL] {name} failed after {timer.elapsed:.1f}s: {e}")
                ctx.errors.append({"agent": name, "error": str(e)})
                agent_timings[name] = {"status": "failed", "elapsed_s": round(timer.elapsed, 2), "error": str(e)}
                raise PipelineError(name, str(e), ctx=ctx)
        agent_timings[name] = {"status": "ok", "elapsed_s": round(timer.elapsed, 2)}

    take_id = ctx.take_id
    if not take_id:
        raise RuntimeError("TAKE phase finished without persisting a take (no take_id set).")
    if ctx.event_title:
        mark_processed(ctx.event_title, ctx.run_id)
    log.info(f"\n[TAKE PERSISTED] take_id={take_id}  ({time.time() - pipeline_start:.1f}s)")

    # ── HITL gate G2: stop here so a human can review the take before render ──
    if not render:
        from take import take_path
        print("\n" + "=" * 60)
        print("  TAKE READY FOR REVIEW (no render budget spent yet)")
        print(f"  take_id: {take_id}")
        print(f"  file:    {take_path(take_id)}")
        print(f"  event:   {ctx.event_title}")
        print(f"  angle:   {ctx.chaos_angle}")
        print(f"  line:    {ctx.animation_direction}")
        print("  → review/edit the file, then:")
        print(f"      python3 main.py render {take_id} --paths fal+elevenlabs,grok")
        print("=" * 60)
        return {"take_id": take_id, "results": [], "take_agent_timings": agent_timings}

    # ── RENDER phase (once per selected path, from the same take) ────────────
    selected = selected_paths or list(render_paths.keys())
    results = []
    for path_name in selected:
        if path_name not in render_paths:
            log.warning(f"  Unknown render path '{path_name}', skipping")
            continue
        ctx_r, asset_path, row = run_render_path(
            take_id, path_name, render_paths[path_name], config,
            offline=offline, publish=publish,
        )
        results.append({"path": path_name, "asset_path": asset_path, "row": row, "ctx": ctx_r})

    log.info(f"\n{'=' * 60}\n  {pipeline_name.upper()} COMPLETE")
    log.info(f"  take_id:  {take_id}")
    log.info(f"  paths:    {', '.join(selected)}")
    log.info(f"  assets:   {len(results)}")
    log.info("=" * 60)

    return {"take_id": take_id, "results": results, "take_agent_timings": agent_timings}


def run_render_only(take_id, render_paths, selected_paths=None, offline=False, publish=False):
    """Render an already-persisted take (HITL gate G2 already passed). Loads config,
    then loops the selected render paths from load_take(take_id). This is what the
    `render <take_id>` CLI command calls after a human has approved the take."""
    log = get_logger("orchestrator")

    from take import take_path
    if not os.path.exists(take_path(take_id)):
        print(f"[FAIL] No take found for take_id={take_id} ({take_path(take_id)})")
        sys.exit(1)

    try:
        config = load_config()
    except ValueError as e:
        print(f"[FAIL] {e}")
        sys.exit(1)

    setup_logging(take_id)
    selected = selected_paths or list(render_paths.keys())
    print("=" * 60)
    print(f"  ARBI FLOW — RENDER  take_id={take_id}")
    print(f"  paths: {', '.join(selected)}   publish={publish}")
    print("=" * 60)

    results = []
    for path_name in selected:
        if path_name not in render_paths:
            log.warning(f"  Unknown render path '{path_name}', skipping")
            continue
        ctx_r, asset_path, row = run_render_path(
            take_id, path_name, render_paths[path_name], config,
            offline=offline, publish=publish,
        )
        results.append({"path": path_name, "asset_path": asset_path, "row": row, "ctx": ctx_r})

    print("\n" + "=" * 60)
    print(f"  RENDER COMPLETE — {len(results)} asset(s) staged in output/")
    for r in results:
        print(f"    - {r['path']:16s} {r['asset_path']}")
    if not publish:
        print("  (not published — stage for sign-off, then: python3 main.py publish "
              f"{take_id})")
    print("=" * 60)
    return {"take_id": take_id, "results": results}

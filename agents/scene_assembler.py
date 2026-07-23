"""Engine B / thin agent — resolve caption style, build each clip's segment,
then concat -> outro -> music into one finished vertical mp4.

Caption-style resolution happens HERE (neutral <- BRAND slot <- beat), and
host-relative asset paths (font, overlays, outro, music) are resolved HERE
too, before calling into studio_skills.assembly.scene_assemble — the skill
never reads context, never judges style, and has no beat_dir of its own; it
only draws/muxes whatever explicit paths and style dict it's handed."""

import os
import shutil

from studio_skills.assembly.scene_assemble import (
    build_segment, concat_segments, append_outro, mix_music,
)

from agents.character import get_character
from context_root import cabinet_root
from logger import get_logger

log = get_logger("scene_assembler")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Neutral defaults: white box, near-black text. Never brand-yellow — a
# brand's caption look comes from its own BRAND slot (caption_style),
# overridable per beat (assembly.subtitle_style). Merge order:
#   neutral <- character slot <- beat assembly.subtitle_style
NEUTRAL_CAPTION_STYLE = {
    "font_px": 60, "weight": 800,
    "box_rgb": [255, 255, 255], "text_rgb": [16, 17, 16],
    "pad_x": 34, "pad_y": 20, "radius": 24, "line_spacing": 10,
    "max_width_frac": 0.84, "y_frac": 0.80,
}


def _resolve_caption_style(ctx) -> dict:
    style = dict(NEUTRAL_CAPTION_STYLE)
    style.update(get_character().caption_style or {})
    style.update(ctx.beat.get("assembly", {}).get("subtitle_style", {}))

    # Legacy beats use key "font"; the canonical key is "font_path".
    if "font" in style and "font_path" not in style:
        style["font_path"] = style.pop("font")

    # Fonts are HOST assets: resolve a relative font_path under the cabinet
    # root (not the beat dir). No font_path => the skill falls back to
    # ImageFont.load_default, a neutral default.
    fp = style.get("font_path")
    if fp and not os.path.isabs(fp):
        style["font_path"] = os.path.join(cabinet_root(), fp)

    return style


def _resolve_beat_asset(ctx, path: str) -> str:
    """Resolve a beat-relative asset path (overlay png / outro / music) —
    these are project assets, resolved under the beat file's own dir."""
    return path if os.path.isabs(path) else os.path.normpath(os.path.join(ctx.beat_dir, path))


def assemble_scene(ctx, config):
    """Build each surviving clip's segment, concat, append outro, mix music."""
    assembly = ctx.beat.get("assembly", {})
    run_dir = os.path.join(_REPO_ROOT, "artifacts", "scripted", ctx.run_id)
    work_dir = os.path.join(run_dir, "assemble")
    os.makedirs(work_dir, exist_ok=True)

    style = _resolve_caption_style(ctx)

    # Pre-resolve graphic-overlay pngs (host-relative -> absolute) before
    # calling into the skill, which expects resolved paths.
    if assembly.get("overlays_enabled"):
        for clip in ctx.beat.get("clips", []):
            for ov in clip.get("overlays", []):
                png = ov.get("png")
                if png and not os.path.isabs(png):
                    ov["png"] = _resolve_beat_asset(ctx, png)

    segs = []
    for clip in ctx.beat.get("clips", []):
        clip_id = clip["clip_id"]
        if ctx.clip_filter and clip_id != ctx.clip_filter:
            continue

        video = ctx.clip_video_paths.get(clip_id)
        if not video:
            log.warning(f"  [scene_assembler] {clip_id}: no rendered video — skipping (upstream clip was skipped)")
            continue

        media = {"video": video, "voice": ctx.clip_audio_paths.get(clip_id)}
        seg = build_segment(clip, media, assembly, style, work_dir)
        segs.append(seg)
        log.info(f"  [scene_assembler] {clip_id} -> {seg}")

    if not segs:
        log.warning("  [scene_assembler] no segments built — nothing to assemble")
        return ctx

    scene_path = os.path.join(work_dir, "scene.mp4")
    concat_segments(segs, scene_path)
    current = scene_path

    outro = assembly.get("append_outro")
    if outro:
        outro_path = _resolve_beat_asset(ctx, outro)
        outro_out = os.path.join(work_dir, "scene_outro.mp4")
        append_outro(current, outro_path, outro_out)
        current = outro_out

    music = assembly.get("music", {})
    if music.get("enabled"):
        music_path = _resolve_beat_asset(ctx, music["path"])
        mixed_out = os.path.join(work_dir, "scene_mixed.mp4")
        mix_music(current, music_path, music.get("volume", 1.0), mixed_out)
        current = mixed_out

    final = os.path.join(run_dir, f"{ctx.run_id}_ASSEMBLED.mp4")
    shutil.copy2(current, final)

    ctx.assembled_path = final
    ctx.final_video_path = final  # so orchestrator._finalize_output stages it into output/
    log.info(f"  [scene_assembler] final -> {final}")

    return ctx

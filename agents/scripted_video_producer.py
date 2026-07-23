"""Engine B / thin agent — the $ step: Kling image-to-video render, one clip
at a time.

All render work lives in studio_skills.render.kling_image_to_video. This
agent's job is the slot read: the render-STYLE words come from the BRAND &
VOICE slot via video_style_prefix(get_character()) — never a baked style
literal — while the per-clip animation_direction (motion/camera) comes from
the beat the human wrote."""

import os

from studio_skills.render.kling_image_to_video import render_video
from studio_skills.common.ffmpeg import trim_video

from agents.character import get_character, video_style_prefix
from logger import get_logger

log = get_logger("scripted_video_producer")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def produce_clips(ctx, config):
    """Render each clip's conformed keyframe + prompt into an mp4 via Kling.

    Spends money — never runs in the keyframe-only slice. Honors
    ctx.clip_filter. A clip with no conformed keyframe (skipped at the free
    gate) is skipped here too, logged, not fatal."""
    work_dir = os.path.join(_REPO_ROOT, "artifacts", "scripted", ctx.run_id)
    os.makedirs(work_dir, exist_ok=True)

    style_prefix = video_style_prefix(get_character())

    for clip in ctx.beat.get("clips", []):
        clip_id = clip["clip_id"]
        if ctx.clip_filter and clip_id != ctx.clip_filter:
            continue

        keyframe = ctx.keyframe_paths.get(clip_id)
        if not keyframe:
            log.warning(f"  [scripted_video_producer] {clip_id}: no conformed keyframe — skipping render")
            continue

        prompt = f"{style_prefix}. {clip['animation_direction']}"
        raw_path = os.path.join(work_dir, f"{clip_id}_raw.mp4")

        log.info(f"  [scripted_video_producer] {clip_id}: rendering via Kling ({clip.get('kling_duration', '10')}s)...")
        render_video(
            keyframe, prompt, duration=clip.get("kling_duration", "10"),
            out_path=raw_path, fal_key=config["FAL_KEY"],
            on_log=lambda m: log.info(f"    [fal.ai] {m}"),
        )

        target_dur = clip.get("target_duration_sec")
        if target_dur:
            # Kling keyframes don't land on copy-safe boundaries — re-encode.
            trimmed_path = os.path.join(work_dir, f"{clip_id}_trimmed.mp4")
            trim_video(raw_path, trimmed_path, target_dur, codec_copy=False)
            clip_video = trimmed_path
        else:
            clip_video = raw_path

        ctx.clip_video_paths[clip_id] = clip_video
        log.info(f"  [scripted_video_producer] {clip_id} -> {clip_video}")

    return ctx

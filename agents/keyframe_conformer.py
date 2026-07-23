"""Engine B / thin agent — the free keyframe-conform gate for the scripted
pipeline.

Pure/local/free: for each clip, center-crop + resize its reference image to
the clip's target aspect ratio via studio_skills.render.image_conform. This
is the free gate a human can review before any paid video render is
triggered downstream (scripted_video_producer). All the real transform work
lives in the skill; this agent only resolves the per-clip reference path and
loops."""

import os

from studio_skills.render.image_conform import conform_image_to_aspect, DIMS_768

from logger import get_logger

log = get_logger("keyframe_conformer")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def conform_keyframes(ctx, config):
    """Conform each clip's reference image to its target aspect ratio.

    Honors ctx.clip_filter (run only that clip_id when set). A missing or
    unresolvable reference image is a per-clip SKIP (logged clearly) — it
    never aborts the whole run."""
    out_dir = os.path.join(_REPO_ROOT, "artifacts", "keyframes", ctx.run_id)

    for clip in ctx.beat.get("clips", []):
        clip_id = clip["clip_id"]
        if ctx.clip_filter and clip_id != ctx.clip_filter:
            continue

        ref = clip.get("character_image", "")
        if not ref:
            log.warning(f"  [keyframe_conformer] {clip_id}: no character_image set on the clip — skipping")
            continue

        ref_path = ref if os.path.isabs(ref) else os.path.normpath(os.path.join(ctx.beat_dir, ref))
        if not os.path.exists(ref_path):
            log.warning(f"  [keyframe_conformer] {clip_id}: reference image not found ({ref_path}) — skipping")
            continue

        path = conform_image_to_aspect(
            ref_path, clip.get("aspect_ratio", "1:1"), out_dir,
            dims=DIMS_768, clip_id=clip_id,
        )
        ctx.keyframe_paths[clip_id] = path
        log.info(f"  [keyframe] {clip_id} -> {path}")

    return ctx

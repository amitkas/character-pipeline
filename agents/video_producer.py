import os

from studio_skills.render.image_conform import conform_image_to_aspect, DIMS_576
from studio_skills.render.kling_image_to_video import render_video

from context import PipelineContext
from logger import get_logger, StepTimer
from agents.character import get_character, video_style_prefix

log = get_logger("video_producer")

# Kling 2.5 Turbo Pro supports 5 or 10 seconds. 10s = ~$0.70; 5s = ~$0.35.
KLING_DURATION = "10"

# Cost per asset, logged to the learn log (fal Kling 10s ~$0.70 + ElevenLabs ~$0.07).
RENDER_COST_USD = 0.77


def produce_video(ctx: PipelineContext, config: dict) -> PipelineContext:
    """Generate a 1:1 square video from the cartoon image using Kling 2.5 Turbo Pro on fal.ai."""

    # Aspect ratio comes from render-path config (PRD B4), not a hardcode.
    aspect_ratio = getattr(ctx, "aspect_ratio", "1:1") or "1:1"

    # Step 0: Conform the cartoon image to the path's aspect ratio so Kling matches it.
    image_to_upload = ctx.cartoon_image_path
    if image_to_upload and os.path.exists(image_to_upload):
        with StepTimer(log, f"Ensure image {aspect_ratio}"):
            out_dir = os.path.dirname(ctx.cartoon_image_path)
            image_to_upload = conform_image_to_aspect(
                ctx.cartoon_image_path, aspect_ratio, out_dir, dims=DIMS_576
            )

    # Step 1: Build the character-specific prompt. The animation direction already
    # incorporates the chaos angle (script writer treats it as PRIMARY input). Don't
    # dump the raw chaos_angle narrative — it's prose comedy that confuses the video
    # model. Lead with the visual direction. Art-theme style comes from the BRAND slot
    # (never baked here); the camera clause is neutral render direction, not brand style.
    animation_cue = ctx.animation_direction if ctx.animation_direction else ctx.scene_prompt
    event_context = f"Scene: {ctx.event_title}. " if ctx.event_title else ""

    video_prompt = (
        f"{video_style_prefix(get_character())}. {event_context}{animation_cue}. "
        f"Smooth continuous motion, steady camera."
    )
    log.debug(f"  Video prompt ({len(video_prompt)} chars): {video_prompt}")

    log.info("  [Video Producer] Submitting video generation job (Kling 2.5 Turbo Pro)...")
    log.info("  [Video Producer] This may take 2-5 minutes...")

    artifacts_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "artifacts", "videos"
    )
    os.makedirs(artifacts_dir, exist_ok=True)
    video_path = os.path.join(artifacts_dir, f"{ctx.run_id}_final.mp4")

    with StepTimer(log, "Kling 2.5 Turbo Pro video generation") as t:
        render_video(
            image_to_upload,
            video_prompt,
            duration=KLING_DURATION,
            out_path=video_path,
            fal_key=config["FAL_KEY"],
            on_log=lambda m: log.info(f"    [fal.ai] {m}"),
        )

    log.debug(f"  Video generation completed in {t.elapsed:.2f}s")

    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    log.info(f"  [Video Producer] Saved: {video_path} ({file_size_mb:.1f} MB)")

    ctx.video_local_path = video_path
    ctx.render_cost_usd = RENDER_COST_USD
    return ctx

import os
import time
import base64
import requests
from datetime import timedelta
from PIL import Image

import xai_sdk

from context import PipelineContext
from logger import get_logger, StepTimer
from agents.character import get_character, video_style_prefix

log = get_logger("video_producer_grok")

# Last-ditch audio direction if the host's sound spec omits one. Brand-free —
# the character's real direction comes from the BRAND slot's sound block.
DEFAULT_AUDIO_DIRECTION = (
    "The character makes only nonverbal vocal sounds — no real words, no narration, no music."
)

GROK_DURATION = 10
GROK_RESOLUTION = "720p"
GROK_MODEL = "grok-imagine-video"

# Cost per asset, logged to the learn log. Grok all-in-one (video + native audio);
# estimate pending a real billed run.
RENDER_COST_USD = 0.20

# Aspect ratio -> (width, height) for the conditioning image (Grok max 720p).
ASPECT_DIMS = {
    "1:1": (720, 720),
    "9:16": (720, 1280),
    "16:9": (1280, 720),
}


def _aspect_dims(aspect_ratio: str) -> tuple:
    return ASPECT_DIMS.get(aspect_ratio, ASPECT_DIMS["1:1"])


def _ensure_image_ratio(image_path: str, aspect_ratio: str) -> str:
    """Center-crop + resize the image to the target aspect ratio so Grok returns
    a video of that ratio. Returns the new image path."""
    target_w, target_h = _aspect_dims(aspect_ratio)
    target_ratio = target_w / target_h

    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    current_ratio = w / h

    if abs(current_ratio - target_ratio) < 0.02:
        log.debug(f"  [Video Producer Grok] Image already ~{aspect_ratio} ({w}x{h})")
    elif current_ratio > target_ratio:
        new_w = int(round(h * target_ratio))
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
        log.info(f"  [Video Producer Grok] Cropped image to {aspect_ratio} ({w}x{h} -> {new_w}x{h})")
    else:
        new_h = int(round(w / target_ratio))
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
        log.info(f"  [Video Producer Grok] Cropped image to {aspect_ratio} ({w}x{h} -> {w}x{new_h})")

    img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

    base, _ = os.path.splitext(image_path)
    ratio_slug = aspect_ratio.replace(":", "x")
    out_path = f"{base}_{ratio_slug}.jpg"
    img.save(out_path, "JPEG", quality=92)
    log.debug(f"  [Video Producer Grok] Saved {aspect_ratio} image: {out_path} ({target_w}x{target_h})")
    return out_path


def _encode_image_base64(path: str) -> str:
    """Encode image file as a base64 data URI for the Grok API."""
    with open(path, "rb") as f:
        data = f.read()
    mime = "image/jpeg" if path.lower().endswith((".jpg", ".jpeg")) else "image/png"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def produce_video(ctx: PipelineContext, config: dict) -> PipelineContext:
    """Generate a 1:1 square video from the cartoon image using Grok Imagine Video (xAI).

    Uses image-to-video with the character's audio direction (from the BRAND slot's
    sound spec) injected into the prompt — Grok generates the voice natively."""

    xai_api_key = config.get("XAI_API_KEY")
    if not xai_api_key:
        raise RuntimeError("XAI_API_KEY not configured — required for Grok video generation")

    # Aspect ratio comes from render-path config (PRD B4), not a hardcode.
    aspect_ratio = getattr(ctx, "aspect_ratio", "1:1") or "1:1"

    # Step 0: Conform the cartoon image to the path's aspect ratio. Grok is
    # image-to-video — it REQUIRES a conditioning image. If the grok render path
    # has no Character Dresser, cartoon_image_path is empty and base64-encoding it
    # blows up with "No such file or directory: ''". Fail loudly with a clear cause.
    image_to_upload = ctx.cartoon_image_path
    if not image_to_upload or not os.path.exists(image_to_upload):
        raise RuntimeError(
            "Grok video generation needs a conditioning image, but no cartoon_image_path "
            f"was produced (got {image_to_upload!r}). The grok render path must run a "
            "Character Dresser step before the Grok producer."
        )
    with StepTimer(log, f"Ensure image {aspect_ratio}"):
        image_to_upload = _ensure_image_ratio(image_to_upload, aspect_ratio)

    # Step 1: Encode image as base64 data URI (no separate upload step needed)
    log.info("  [Video Producer Grok] Encoding image as base64...")
    image_data_uri = _encode_image_base64(image_to_upload)
    log.debug(f"  Image data URI size: {len(image_data_uri) / 1024:.0f} KB")

    # Step 2: Build prompt with the character's audio direction (from the sound spec)
    animation_cue = ctx.animation_direction if ctx.animation_direction else ctx.scene_prompt
    event_context = f"Scene: {ctx.event_title}. " if ctx.event_title else ""
    audio_direction = (get_character().sound or {}).get("video_audio_direction") or DEFAULT_AUDIO_DIRECTION

    video_prompt = (
        f"{video_style_prefix(get_character())}. {event_context}{animation_cue}. "
        f"Smooth continuous motion, steady camera. "
        f"Audio: {audio_direction}"
    )
    log.debug(f"  Video prompt ({len(video_prompt)} chars): {video_prompt}")

    # Step 3: Generate video via xai_sdk
    log.info("  [Video Producer Grok] Submitting video generation job (Grok Imagine Video)...")
    log.info("  [Video Producer Grok] This typically takes 20-40 seconds...")

    client = xai_sdk.Client(api_key=xai_api_key)

    with StepTimer(log, "Grok Imagine Video generation") as t:
        response = client.video.generate(
            prompt=video_prompt,
            model=GROK_MODEL,
            image_url=image_data_uri,
            duration=GROK_DURATION,
            aspect_ratio=aspect_ratio,
            resolution=GROK_RESOLUTION,
            timeout=timedelta(minutes=10),
            interval=timedelta(seconds=5),
        )

    log.info(f"  [Video Producer Grok] Video generated in {t.elapsed:.1f}s")
    log.debug(f"  Model: {response.model}")
    log.debug(f"  Duration: {response.duration}s")
    log.debug(f"  Moderation OK: {response.respect_moderation}")

    if not response.respect_moderation:
        raise RuntimeError("Grok video generation was filtered by content moderation")

    video_url = response.url
    log.info(f"  [Video Producer Grok] Video ready: {video_url[:80]}...")

    # Step 4: Download the generated video
    artifacts_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "artifacts", "videos"
    )
    os.makedirs(artifacts_dir, exist_ok=True)

    video_path = os.path.join(artifacts_dir, f"{ctx.run_id}_final.mp4")

    log.info("  [Video Producer Grok] Downloading video...")
    with StepTimer(log, "Video download") as t:
        resp = requests.get(video_url, stream=True, timeout=120)
        resp.raise_for_status()

        with open(video_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    log.info(f"  [Video Producer Grok] Saved: {video_path} ({file_size_mb:.1f} MB)")
    log.debug(f"  Download took {t.elapsed:.2f}s, file size: {file_size_mb:.2f} MB")

    ctx.video_local_path = video_path
    ctx.render_cost_usd = RENDER_COST_USD
    return ctx

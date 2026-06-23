import os
import time
import requests
import fal_client
from PIL import Image

from context import PipelineContext
from logger import get_logger, StepTimer

log = get_logger("video_producer")

# Retry config for fal.ai upload (often hits 408 Timeout)
UPLOAD_MAX_ATTEMPTS = 3
UPLOAD_RETRY_DELAY_SEC = 10
UPLOAD_TIMEOUT_SEC = 120

# Long edge for the conditioning image. Kling follows the input image aspect ratio.
TARGET_LONG_EDGE = 576

# Aspect ratio -> (width, height) for the conditioning image. The ratio is lifted
# into render-path config (architecture §4 / PRD B4) and read off ctx.aspect_ratio;
# changing it requires no edit to this file.
ASPECT_DIMS = {
    "1:1": (576, 576),
    "9:16": (576, 1024),
    "16:9": (1024, 576),
}

# Kling 2.5 Turbo Pro supports 5 or 10 seconds. 10s = ~$0.70; 5s = ~$0.35.
KLING_DURATION = "10"

# Cost per asset, logged to the learn log (fal Kling 10s ~$0.70 + ElevenLabs ~$0.07).
RENDER_COST_USD = 0.77


def _aspect_dims(aspect_ratio: str) -> tuple:
    """Resolve an aspect-ratio string to (width, height). Defaults to 1:1."""
    return ASPECT_DIMS.get(aspect_ratio, ASPECT_DIMS["1:1"])


def _ensure_image_ratio(image_path: str, aspect_ratio: str) -> str:
    """Center-crop + resize the image to the target aspect ratio so Kling returns
    a video of that ratio (it follows the input image). Returns the new image path."""
    target_w, target_h = _aspect_dims(aspect_ratio)
    target_ratio = target_w / target_h

    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    current_ratio = w / h

    if abs(current_ratio - target_ratio) < 0.02:
        log.debug(f"  [Video Producer] Image already ~{aspect_ratio} ({w}x{h})")
    elif current_ratio > target_ratio:
        # Too wide: center-crop width
        new_w = int(round(h * target_ratio))
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
        log.info(f"  [Video Producer] Cropped image to {aspect_ratio} ({w}x{h} -> {new_w}x{h})")
    else:
        # Too tall: center-crop height
        new_h = int(round(w / target_ratio))
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))
        log.info(f"  [Video Producer] Cropped image to {aspect_ratio} ({w}x{h} -> {w}x{new_h})")

    img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

    base, _ = os.path.splitext(image_path)
    ratio_slug = aspect_ratio.replace(":", "x")
    out_path = f"{base}_{ratio_slug}.jpg"
    img.save(out_path, "JPEG", quality=92)
    log.debug(f"  [Video Producer] Saved {aspect_ratio} image: {out_path} ({target_w}x{target_h})")
    return out_path


def produce_video(ctx: PipelineContext, config: dict) -> PipelineContext:
    """Generate a 1:1 square video from the cartoon image using Kling 2.5 Turbo Pro on fal.ai."""

    os.environ["FAL_KEY"] = config["FAL_KEY"]

    # Aspect ratio comes from render-path config (PRD B4), not a hardcode.
    aspect_ratio = getattr(ctx, "aspect_ratio", "1:1") or "1:1"

    # Step 0: Conform the cartoon image to the path's aspect ratio so Kling matches it.
    image_to_upload = ctx.cartoon_image_path
    if image_to_upload and os.path.exists(image_to_upload):
        with StepTimer(log, f"Ensure image {aspect_ratio}"):
            image_to_upload = _ensure_image_ratio(image_to_upload, aspect_ratio)

    # Step 1: Upload the cartoon image to fal.ai (with retries and longer timeout)
    log.info("  [Video Producer] Uploading cartoon image to fal.ai...")
    log.debug(f"  Image path: {image_to_upload}")
    log.debug(f"  Image size: {os.path.getsize(image_to_upload)} bytes")

    client = fal_client.SyncClient(default_timeout=UPLOAD_TIMEOUT_SEC)
    image_url = None
    last_error = None
    with StepTimer(log, "fal.ai image upload"):
        for attempt in range(1, UPLOAD_MAX_ATTEMPTS + 1):
            try:
                image_url = client.upload_file(image_to_upload)
                break
            except Exception as e:
                last_error = e
                if attempt < UPLOAD_MAX_ATTEMPTS:
                    log.warning(
                        f"  [Video Producer] Upload attempt {attempt}/{UPLOAD_MAX_ATTEMPTS} failed: {e}. "
                        f"Retrying in {UPLOAD_RETRY_DELAY_SEC}s..."
                    )
                    time.sleep(UPLOAD_RETRY_DELAY_SEC)
                else:
                    raise
    if not image_url:
        raise last_error or RuntimeError("fal.ai image upload failed")
    log.info(f"  [Video Producer] Image uploaded: {image_url[:80]}...")
    log.debug(f"  Full upload URL: {image_url}")

    # Step 2: Submit video generation job with the character-specific prompt
    # The animation direction already incorporates the chaos angle (script writer
    # treats it as PRIMARY input). Don't dump the raw chaos_angle narrative — it's
    # prose comedy that confuses the video model. Lead with the visual direction.
    animation_cue = ctx.animation_direction if ctx.animation_direction else ctx.scene_prompt
    event_context = f"Scene: {ctx.event_title}. " if ctx.event_title else ""

    video_prompt = (
        f"Pixar 3D animation style. {event_context}{animation_cue}. "
        f"Smooth continuous motion, steady camera. Vibrant lighting."
    )
    log.debug(f"  Video prompt ({len(video_prompt)} chars): {video_prompt}")

    log.info("  [Video Producer] Submitting video generation job (Kling 2.5 Turbo Pro)...")
    log.info("  [Video Producer] This may take 2-5 minutes...")

    fal_arguments = {
        "image_url": image_url,
        "prompt": video_prompt,
        "duration": KLING_DURATION,
    }
    log.debug(f"  fal.ai arguments: {fal_arguments}")

    def on_queue_update(update):
        if isinstance(update, fal_client.InProgress):
            for entry in update.logs:
                log.info(f"    [fal.ai] {entry['message']}")

    with StepTimer(log, "Kling 2.5 Turbo Pro video generation") as t:
        result = fal_client.subscribe(
            "fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
            arguments=fal_arguments,
            with_logs=True,
            on_queue_update=on_queue_update,
        )

    log.debug(f"  Video generation completed in {t.elapsed:.2f}s")
    log.debug(f"  fal.ai result keys: {list(result.keys())}")

    # Step 3: Download the generated video
    video_url = result["video"]["url"]
    log.info(f"  [Video Producer] Video ready: {video_url[:80]}...")
    log.debug(f"  Full video URL: {video_url}")

    artifacts_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "artifacts", "videos"
    )
    os.makedirs(artifacts_dir, exist_ok=True)

    video_path = os.path.join(artifacts_dir, f"{ctx.run_id}_final.mp4")

    log.info("  [Video Producer] Downloading video...")
    with StepTimer(log, "Video download") as t:
        resp = requests.get(video_url, stream=True, timeout=120)
        resp.raise_for_status()

        with open(video_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

    file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
    log.info(f"  [Video Producer] Saved: {video_path} ({file_size_mb:.1f} MB)")
    log.debug(f"  Download took {t.elapsed:.2f}s, file size: {file_size_mb:.2f} MB")

    ctx.video_local_path = video_path
    ctx.render_cost_usd = RENDER_COST_USD
    return ctx

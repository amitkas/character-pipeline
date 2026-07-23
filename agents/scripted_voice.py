"""Engine B / thin agent — ElevenLabs voice-over, one clip at a time.

All synthesis work lives in studio_skills.audio.scripted_tts. This agent's
job is the slot read (voice_id falls back to the BRAND slot's
sound.voice_id) and the deliberate cost guard: a clip whose script_line is
still empty or a [PLACEHOLDER...] note refuses to spend and ships silent
instead of synthesizing throwaway copy."""

import os

from studio_skills.audio.scripted_tts import synthesize_line

from agents.character import get_character
from logger import get_logger

log = get_logger("scripted_voice")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def voice_clips(ctx, config):
    """Synthesize each clip's script_line to mp3. Honors ctx.clip_filter.

    Placeholder/empty script_line -> refuse to spend, ship silent: no entry
    is written to ctx.clip_audio_paths for that clip. Keep this cost guard —
    it is deliberate, not a gap."""
    work_dir = os.path.join(_REPO_ROOT, "artifacts", "scripted", ctx.run_id)
    os.makedirs(work_dir, exist_ok=True)

    for clip in ctx.beat.get("clips", []):
        clip_id = clip["clip_id"]
        if ctx.clip_filter and clip_id != ctx.clip_filter:
            continue

        script_line = (clip.get("script_line") or "").strip()
        if not script_line or script_line.startswith("[PLACEHOLDER"):
            log.info(
                f"  [scripted_voice] {clip_id}: no real script_line (placeholder) — "
                "shipping silent, re-run once copy is locked"
            )
            continue

        voice_id = clip.get("voice_id") or get_character().sound["voice_id"]
        out_path = os.path.join(work_dir, f"{clip_id}_voice.mp3")

        synthesize_line(
            script_line, voice_id, out_path,
            api_key=config["ELEVENLABS_API_KEY"],
            voice_settings=clip.get("voice_settings"),
        )
        ctx.clip_audio_paths[clip_id] = out_path
        log.info(f"  [scripted_voice] {clip_id} -> {out_path}")

    return ctx

import os
import json
import random
import base64
import glob

from elevenlabs.client import ElevenLabs

from context import PipelineContext
from logger import get_logger, StepTimer
from agents.character import get_character
from utils.ffmpeg_utils import run_ffmpeg, get_audio_duration, trim_audio

log = get_logger("sound_engineer")

# Background music — volume relative to the character voice (0.0-1.0)
BG_MUSIC_VOLUME = 0.25  # 25% volume so the character voice stays dominant

MAX_VOICEOVER_SECONDS = 10.0  # matches Kling 2.5 Turbo Pro duration


def _build_sound_text(templates: list[str], keywords: list[str]) -> tuple[str, list[dict]]:
    """Build a gibberish line from the character's sound templates with real keywords
    sprinkled in for comedic effect. If keywords are available, randomly insert them
    (uppercased) into a template so the character yells actual words from the original
    video.

    Returns (text, keyword_spans) where each span is
    {"keyword": str, "char_start": int, "char_end": int}."""

    base = random.choice(templates)

    if not keywords:
        return base, []

    words = base.split()
    # Insert each keyword at a random position in the gibberish
    for kw in keywords:
        pos = random.randint(0, len(words))
        words.insert(pos, kw.upper())

    text = " ".join(words)

    # Find the character positions of each keyword in the final text
    keyword_spans = []
    for kw in keywords:
        kw_upper = kw.upper()
        idx = text.find(kw_upper)
        if idx >= 0:
            keyword_spans.append({
                "keyword": kw_upper,
                "char_start": idx,
                "char_end": idx + len(kw_upper),
            })

    return text, keyword_spans


def generate_character_sounds(ctx: PipelineContext, config: dict) -> PipelineContext:
    """Generate the character's signature sound via ElevenLabs.
    Instead of narration, generates gibberish/nonverbal vocalizations per the
    character's sound spec (label, voice, pitch, templates) from the BRAND slot."""

    char = get_character()
    sound = char.sound  # get_character() guarantees these keys or raises CharacterError
    voice_id = sound["voice_id"]
    label = sound["label"]
    templates = sound["gibberish_templates"]
    pitch_shift = sound["pitch_shift"]
    log.info(f"  [Sound Engineer] Generating {char.name}'s {label}...")

    # 90s timeout — short gibberish TTS should complete in ~10–30s; fail fast if API hangs
    client = ElevenLabs(api_key=config["ELEVENLABS_API_KEY"], timeout=90)

    # Pick a random template from the character's sound spec, sprinkle in video keywords
    gibberish_text, keyword_spans = _build_sound_text(templates, ctx.video_keywords)
    log.debug(f"  Gibberish text: {gibberish_text}")
    log.debug(f"  Keyword spans: {keyword_spans}")

    with StepTimer(log, "ElevenLabs TTS generation") as t:
        response = client.text_to_speech.convert_with_timestamps(
            text=gibberish_text,
            voice_id=voice_id,
            model_id="eleven_v3",
            output_format="mp3_44100_128",
            voice_settings={
                "stability": 0.0,        # minimum stability = maximum chaos
                "similarity_boost": 0.3,  # low similarity = more distorted/monstrous
                "style": 1.0,            # maximum style exaggeration = amplified personality
                "speed": 1.4,            # faster = more manic energy
            },
        )

    log.debug(f"  TTS generation took {t.elapsed:.2f}s")

    # Decode audio from base64
    audio_bytes = base64.b64decode(response.audio_base_64)
    log.debug(f"  Audio size: {len(audio_bytes)} bytes")

    # Save audio file
    artifacts_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "artifacts", "audio"
    )
    os.makedirs(artifacts_dir, exist_ok=True)

    audio_path = os.path.join(artifacts_dir, f"{ctx.run_id}_voice.mp3")
    with open(audio_path, "wb") as f:
        f.write(audio_bytes)

    file_size_kb = os.path.getsize(audio_path) / 1024
    log.info(f"  [Sound Engineer] Saved: {audio_path} ({file_size_kb:.1f} KB)")

    # Pitch shift per the character's sound spec
    pre_shift_duration = get_audio_duration(audio_path)
    audio_path = _pitch_shift(audio_path, pitch_shift)

    # Enforce max duration
    audio_duration = get_audio_duration(audio_path)
    log.debug(f"  Audio duration: {audio_duration:.2f}s (pre-shift: {pre_shift_duration:.2f}s)")

    # Compute how much the pitch shift stretched the audio so we can scale timestamps
    time_stretch = audio_duration / pre_shift_duration if pre_shift_duration > 0 else 1.0

    if audio_duration > MAX_VOICEOVER_SECONDS:
        log.info(f"  [Sound Engineer] Audio {audio_duration:.1f}s > {MAX_VOICEOVER_SECONDS}s, trimming...")
        audio_path = _trim_audio_inplace(audio_path, MAX_VOICEOVER_SECONDS)

    ctx.voiceover_path = audio_path
    trim_limit = MAX_VOICEOVER_SECONDS if audio_duration > MAX_VOICEOVER_SECONDS else None
    ctx.word_timestamps = _extract_keyword_timestamps(
        response, keyword_spans, trim_limit, time_stretch
    )
    log.debug(f"  Keyword timestamps: {ctx.word_timestamps}")

    # Composite the character sounds onto the video
    if ctx.video_local_path and os.path.exists(ctx.video_local_path):
        ctx.video_local_path = _composite_audio(ctx, audio_path, config)

    return ctx


def _extract_keyword_timestamps(
    response, keyword_spans: list[dict], max_seconds: float | None, time_stretch: float = 1.0
) -> list[dict]:
    """Extract word-level timestamps for keywords from ElevenLabs character-level alignment.
    Scales timestamps by time_stretch to account for pitch shift duration changes."""
    alignment = getattr(response, "alignment", None)
    if not alignment or not keyword_spans:
        return []

    chars = alignment.characters
    starts = alignment.character_start_times_seconds
    ends = alignment.character_end_times_seconds

    if not chars or not starts or not ends:
        return []

    # Minimum time a keyword needs before the end to be worth showing
    end_buffer = 0.5

    timestamps = []
    for span in keyword_spans:
        cs, ce = span["char_start"], span["char_end"]
        # Bounds check against alignment data
        if cs >= len(starts) or ce - 1 >= len(ends):
            continue
        # Scale timestamps to match the actual (pitch-shifted) audio
        t_start = starts[cs] * time_stretch
        t_end = ends[ce - 1] * time_stretch
        # Skip keywords beyond the trim point
        if max_seconds and t_start >= max_seconds:
            continue
        # Skip keywords that start too close to the end (would feel cut off)
        if max_seconds and t_start >= max_seconds - end_buffer:
            continue
        # Clamp end time to trim point
        if max_seconds and t_end > max_seconds:
            t_end = max_seconds
        timestamps.append({"word": span["keyword"], "start": t_start, "end": t_end})

    return timestamps


def _pitch_shift(audio_path: str, factor: float) -> str:
    """Pitch-shift audio using ffmpeg asetrate + atempo (keeps same duration).
    factor > 1.0 = higher pitch (goblin), < 1.0 = lower pitch (ogre)."""
    shifted_path = audio_path.replace(".mp3", "_shifted.mp3")

    # asetrate raises pitch (but also speeds up), atempo compensates to keep duration
    try:
        run_ffmpeg(
            [
                "ffmpeg", "-y",
                "-i", audio_path,
                "-af", f"asetrate=44100*{factor},atempo={1/factor},aresample=44100",
                shifted_path,
            ],
            timeout=30,
            description=f"Pitch shift by {factor}x"
        )
        os.replace(shifted_path, audio_path)
        log.info(f"  [Sound Engineer] Pitch shifted by {factor}x")
    except RuntimeError as e:
        log.error(f"  [Sound Engineer] Pitch shift failed: {e}")
        # Fall back to original audio

    return audio_path


# Note: _get_audio_duration and _trim_audio now use shared utils.ffmpeg_utils

def _trim_audio_inplace(audio_path: str, max_seconds: float) -> str:
    """Trim audio file to max_seconds using ffmpeg (in-place replacement)."""
    trimmed_path = audio_path.replace(".mp3", "_trimmed.mp3")

    try:
        trim_audio(audio_path, trimmed_path, max_seconds)
        os.replace(trimmed_path, audio_path)
    except RuntimeError as e:
        log.error(f"  [Sound Engineer] Audio trim failed: {e}")
        # Fall back to untrimmed

    return audio_path


def _resolve_music_dir(config: dict) -> str | None:
    """Resolve the music bed directory — the CONTEXT_MUSIC_DIR BRANDED ASSETS slot
    (host-supplied; see CONTEXT.md). Absolute paths used as-is; relative paths resolve
    under the product's artifacts dir. Absent ⇒ None (background music is skipped)."""
    music_dir = (config.get("CONTEXT_MUSIC_DIR") or "").strip()
    if not music_dir:
        return None
    if not os.path.isabs(music_dir):
        artifacts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "artifacts")
        music_dir = os.path.join(artifacts_dir, music_dir)
    return music_dir if os.path.isdir(music_dir) else None


def _pick_background_music(config: dict) -> str | None:
    """Pick a random background music track from the host's music bed slot."""
    music_dir = _resolve_music_dir(config)
    if not music_dir:
        return None
    tracks = glob.glob(os.path.join(music_dir, "*.mp3")) + \
             glob.glob(os.path.join(music_dir, "*.wav")) + \
             glob.glob(os.path.join(music_dir, "*.m4a"))
    if not tracks:
        return None
    pick = random.choice(tracks)
    log.info(f"  [Sound Engineer] Background music: {os.path.basename(pick)}")
    return pick


def _composite_audio(ctx: PipelineContext, audio_path: str, config: dict) -> str:
    """Composite the character audio (+ optional background music) onto the video using ffmpeg."""
    log.info("  [Sound Engineer] Compositing character sounds onto video...")

    artifacts_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "artifacts", "videos"
    )
    final_path = os.path.join(artifacts_dir, f"{ctx.run_id}_final_with_audio.mp4")

    bg_music = _pick_background_music(config)

    if bg_music:
        # Get video duration so we can trim/loop the music track to match
        video_duration = get_audio_duration(ctx.video_local_path)
        log.debug(f"  Video duration for music trim: {video_duration:.2f}s")

        # Mix character voice + background music, then composite onto video
        # [1:a] = character voice, [2:a] = bg music (lowered volume, trimmed to video length)
        filter_complex = (
            f"[2:a]volume={BG_MUSIC_VOLUME},atrim=0:{video_duration},asetpts=PTS-STARTPTS[bg];"
            f"[1:a][bg]amix=inputs=2:duration=longest:dropout_transition=2[aout]"
        )
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", ctx.video_local_path,
            "-i", audio_path,
            "-i", bg_music,
            "-filter_complex", filter_complex,
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            final_path,
        ]
    else:
        log.debug("  No background music found, using character voice only")
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", ctx.video_local_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            final_path,
        ]

    log.debug(f"  ffmpeg command: {' '.join(ffmpeg_cmd)}")

    with StepTimer(log, "ffmpeg audio composite") as t:
        run_ffmpeg(ffmpeg_cmd, timeout=60, description="ffmpeg audio composite")

    final_size_mb = os.path.getsize(final_path) / (1024 * 1024)
    log.info(f"  [Sound Engineer] Final video with character audio: {final_path} ({final_size_mb:.1f} MB)")
    if bg_music:
        log.info(f"  [Sound Engineer] Background music mixed at {int(BG_MUSIC_VOLUME * 100)}% volume")
    log.debug(f"  ffmpeg took {t.elapsed:.2f}s")

    return final_path

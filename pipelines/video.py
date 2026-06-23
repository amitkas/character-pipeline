"""Video pipeline: one trending event -> one persisted TAKE -> N render paths.

TAKE-as-artifact (architecture §3-§4): the TAKE phase runs once and persists
data/takes/{take_id}.json; the orchestrator then loops the registered RENDER_PATHS,
each hydrating a fresh ctx from load_take(take_id). Same take in, two assets out.

TAKE phase:  Video Scout -> Video Finder -> Video Analyzer -> Creative Director -> Animation Director -> Take Emitter
Render paths:
  fal+elevenlabs:  Character Dresser -> Video Producer (Kling) -> Sound Engineer
                   -> Subtitle Burner -> Outro Stitcher -> YouTube Uploader
  grok:            Character Dresser -> Video Producer (Grok, all-in-one video+narration)
                   -> Subtitle Burner -> Outro Stitcher -> YouTube Uploader
"""

import os
import sys

# take.py / take_emitter live at the project root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from context.video import VideoContext
from agents.video_scout import find_trending_video
from agents.video_finder import find_and_download_video
from agents.video_analyzer import analyze_video
from agents.creative_director import direct_creative
from agents.cartoonist import dress_character
from agents.script_writer import write_animation_direction
from agents.take_emitter import emit_take_artifact
from agents.video_producer import produce_video
from agents.video_producer_grok import produce_video as produce_video_grok
from agents.voice_actor import generate_character_sounds
from agents.subtitle_burner import burn_subtitles
from agents.youtube_uploader import upload_to_youtube
from logger import get_logger
from orchestrator import (
    run_take_and_render,
    run_render_only,
    resolve_character_image,
    PipelineError,
)

log = get_logger("pipelines.video")


# ── TAKE phase: the take-forming agents, ending in the seam (Take Emitter) ──
TAKE_AGENTS = [
    ("Video Scout", find_trending_video),
    ("Video Finder", find_and_download_video),
    ("Video Analyzer", analyze_video),
    ("Creative Director", direct_creative),   # owns the chaos angle, AFTER the tape is seen
    ("Animation Director", write_animation_direction),
    ("Take Emitter", emit_take_artifact),   # terminal step — persists the take
]


# ── RENDER paths: one take -> two techniques. aspect_ratio is the free second
#    axis (roadmap §3), lifted into path config so it varies at zero code cost. ──
RENDER_PATHS = {
    "fal+elevenlabs": {
        "technique": "fal+elevenlabs",
        "aspect_ratio": "9:16",             # vertical-feed native (Shorts/TikTok/Reels) — social-video-format-specs.md
        "control_of_script": True,          # we keep the script (the moat)
        "cost_usd": 0.77,                   # fallback if producer doesn't report
        "agents": [
            ("Character Dresser", dress_character),      # moved render-side (the seam)
            ("Video Producer", produce_video),           # fal.ai Kling 2.5 Turbo Pro
            ("Sound Engineer", generate_character_sounds),  # ElevenLabs scripted audio
            ("Subtitle Burner", burn_subtitles),
            ("YouTube Uploader", upload_to_youtube),
        ],
    },
    "grok": {
        "technique": "grok",
        "aspect_ratio": "9:16",
        "control_of_script": False,         # the technique takes the script (the Grok problem)
        "cost_usd": 0.20,                   # fallback if producer doesn't report
        "agents": [
            ("Character Dresser", dress_character),          # render-side: Grok needs a conditioning image (i2v)
            ("Video Producer (Grok)", produce_video_grok),   # all-in-one video + narration
            ("Subtitle Burner", burn_subtitles),
            ("YouTube Uploader", upload_to_youtube),
        ],
    },
}


def make_context(run_id, started_at, config, excluded_events=None, event=None, description=None, **kwargs):
    ctx = VideoContext(
        run_id=run_id,
        started_at=started_at,
        pipeline_name="video",
        character_image_path=resolve_character_image(config),
    )
    if excluded_events:
        ctx.excluded_events = list(excluded_events)
    if event:
        ctx.event_title = event.strip()
    if description:
        ctx.event_description = description.strip()
    return ctx


MAX_SUBJECT_SWITCHES = 3  # Max times to switch subject when video is undownloadable


def run(event=None, description=None, selected_paths=None, offline=False,
        publish=False, render=True):
    """Run the TAKE phase once, then (if render) the selected render paths from the one take.

    selected_paths: list of RENDER_PATHS keys (default: all registered).
    render=False:   stop after persisting the take (HITL gate G2 — human reviews first).
    publish=False:  stage assets for manual sign-off (PRD stops before T9).
    offline=True:   placeholder base video (no credentials) — architecture verification.
    """
    excluded_events = []
    for attempt in range(MAX_SUBJECT_SWITCHES):
        try:
            return run_take_and_render(
                "Video Pipeline",
                TAKE_AGENTS,
                RENDER_PATHS,
                make_context,
                selected_paths=selected_paths,
                excluded_events=excluded_events if attempt > 0 else None,
                event=event,
                description=description,
                offline=offline,
                publish=publish,
                render=render,
            )
        except PipelineError as e:
            if e.agent_name != "Video Finder":
                raise
            err = str(e.error).lower()
            if "could not download" not in err and "no videos found" not in err:
                raise
            if e.ctx and e.ctx.event_title:
                excluded_events.append(e.ctx.event_title)
            if attempt >= MAX_SUBJECT_SWITCHES - 1:
                raise
            failed_title = e.ctx.event_title if e.ctx else "?"
            if event:
                log.info(
                    f"  [Pinned Event] Video undownloadable for '{failed_title}'. "
                    "Pinned events do not switch subjects — aborting."
                )
                raise
            log.info(
                f"  [Subject Switch] Video undownloadable for '{failed_title}', "
                f"switching to different event (attempt {attempt + 2}/{MAX_SUBJECT_SWITCHES})"
            )


def render_existing(take_id, selected_paths=None, offline=False, publish=False):
    """Render an already-persisted (and human-approved) take by take_id."""
    return run_render_only(
        take_id, RENDER_PATHS,
        selected_paths=selected_paths, offline=offline, publish=publish,
    )

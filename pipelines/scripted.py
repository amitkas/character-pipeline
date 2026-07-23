"""Engine B: one beat JSON (M clips) -> one muxed vertical mp4, with a free
keyframe gate before any paid render.

A recipe: a deterministic composition of studio_skills agents with zero
runtime judgment (the human wrote the beat). The four agents are THIN loops
over clips — all real work lives in studio_skills; slot reads (character
style, caption style, voice fallback) happen in the agents, which pass
explicit values into the skills.

Mirrors pipelines/video.py's make_context/run() shape, reusing the shared
runner (orchestrator.run_pipeline) and character-image resolution."""

import functools
import json
import os

from context.scripted import ScriptedContext
from agents.keyframe_conformer import conform_keyframes
from agents.scripted_video_producer import produce_clips
from agents.scripted_voice import voice_clips
from agents.scene_assembler import assemble_scene
from orchestrator import run_pipeline, resolve_character_image


SCRIPTED_AGENTS = [
    ("Keyframe Conformer",      conform_keyframes),
    ("Scripted Video Producer", produce_clips),
    ("Scripted Voice",          voice_clips),
    ("Scene Assembler",         assemble_scene),
]


def make_context(run_id, started_at, config, beat_path, clip_filter=None, keyframe_only=False, **kwargs):
    # **kwargs swallows run_pipeline's excluded_events/event/description (unused by Engine B).
    beat_path_abs = os.path.abspath(beat_path)
    with open(beat_path_abs) as f:
        beat = json.load(f)
    ctx = ScriptedContext(
        run_id=run_id, started_at=started_at, pipeline_name="scripted",
        character_image_path=resolve_character_image(config),
        beat=beat, beat_dir=os.path.dirname(beat_path_abs),
        clip_filter=clip_filter, keyframe_only=keyframe_only,
    )
    return ctx


def run(beat_path, clip_filter=None, keyframe_only=False):
    """Run the scripted pipeline for one beat file.

    keyframe_only=True runs just the free gate (Keyframe Conformer) — zero
    API spend, the headline verification for a new beat before any paid
    render is triggered downstream."""
    agents = SCRIPTED_AGENTS[:1] if keyframe_only else SCRIPTED_AGENTS
    factory = functools.partial(make_context, beat_path=beat_path,
                                clip_filter=clip_filter, keyframe_only=keyframe_only)
    return run_pipeline("Scripted Video Pipeline", agents, factory)

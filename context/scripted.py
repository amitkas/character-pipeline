from dataclasses import dataclass, field

from context.base import BaseContext


@dataclass
class ScriptedContext(BaseContext):
    """State for Engine B (scripted beats): one beat JSON -> M clips -> one muxed mp4.

    Unlike VideoContext (one trending event through N agents), a scripted run carries a
    parsed beat and per-clip artifact maps keyed by clip_id."""

    # Beat input (parsed JSON + the dir it was loaded from, for resolving relative asset paths)
    beat: dict = field(default_factory=dict)
    beat_dir: str = ""

    # Run controls
    clip_filter: str | None = None      # run only this clip_id when set
    keyframe_only: bool = False         # free gate: stop after the keyframe conform step

    # Per-clip artifact maps, keyed by clip_id
    keyframe_paths: dict = field(default_factory=dict)     # clip_id -> conformed keyframe jpg
    clip_video_paths: dict = field(default_factory=dict)   # clip_id -> rendered (+trimmed) mp4
    clip_audio_paths: dict = field(default_factory=dict)   # clip_id -> voice mp3 (absent for silent clips)

    # Final assembled output
    assembled_path: str = ""

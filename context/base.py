from dataclasses import dataclass, field


@dataclass
class BaseContext:
    """State for the video pipeline. Each agent reads what it
    needs and writes its outputs."""

    # Run metadata
    run_id: str = ""
    started_at: str = ""
    pipeline_name: str = ""

    # TAKE-as-artifact: join key to data/takes/{take_id}.json (architecture §6.3).
    # Set by the Take Emitter; read by every render path after hydration.
    take_id: str = ""

    # Character
    character_image_path: str = ""

    # Agent: Video Scout (event discovery)
    event_title: str = ""
    event_description: str = ""
    video_platform: str = ""
    video_search_query: str = ""
    chaos_angle: str = ""
    scout_source: str = ""
    scout_hours_back: int = 24

    # Subject-switch retry: events we tried but could not download (excluded from Scout)
    excluded_events: list = field(default_factory=list)

    # Media paths
    cartoon_image_path: str = ""
    final_video_path: str = ""
    subtitled_video_path: str = ""
    video_local_path: str = ""

    # Error tracking
    errors: list = field(default_factory=list)

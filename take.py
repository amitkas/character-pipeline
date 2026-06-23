"""TAKE as a first-class artifact (architecture §2 / §3).

A *take* is the moat-bearing 9% of the pipeline — the POV, the line, the visual
direction — captured *before* any render runs and persisted as a flat JSON file
under ``data/takes/{take_id}.json``. Everything downstream reads from the
persisted take by ``take_id`` (via :func:`load_take`); nothing reads take fields
off an upstream, render-fused ``ctx``. That inversion is the seam.

Two deliberate calls (architecture §2):
- ``voice_tag`` is a *pointer* to the context layer (which character bible
  produced the take), not the voice/lines themselves — the character's actual
  lines never leave the context layer. The default tag is derived from the host
  character's name (see :func:`_default_voice_tag`), never a baked literal.
- the cartoon image is NOT in the take. The take holds the *visual direction*
  (text: scene + outfit + gender + keywords); each render path generates its own
  image from that text. This is what frees Character Dresser to move render-side.
"""

import json
import os
import re
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from context.video import VideoContext

SCHEMA_VERSION = 1

TAKES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "takes")


def _default_voice_tag() -> str:
    """Default ``voice_tag`` — the take's pointer to the context layer that produced
    it (architecture §2). Derived from the host character's name (e.g. a name like
    ``"Acme Bot"`` slugifies to ``"acme-bot"``) so it stays portable: each cabinet's
    character yields its own tag, never a baked literal. It is only a provenance
    label — the voice/lines themselves stay down in the context layer. Overridable
    via ``ctx.voice_tag``."""
    from agents.character import get_character

    name = (get_character().name or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return slug or "character"


@dataclass
class Take:
    """The six-field take schema (architecture §2). Serialized verbatim to
    ``data/takes/{take_id}.json``."""

    take_id: str
    schema_version: int
    created_at: str           # ISO-8601 Z

    voice_tag: str            # POINTER to the context layer, not the voice itself
    event: dict               # {title, description, source_url, scout_source}
    angle: str                # the POV / chaos angle — the moat
    line: str                 # what the character does (animation direction)
    visual_direction: dict    # {scene, outfit, subject_gender, keywords} — TEXT only

    def to_dict(self) -> dict:
        return asdict(self)


def _now_z() -> str:
    """ISO-8601 UTC timestamp with a trailing Z (no microseconds)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def emit_take(ctx) -> Take:
    """Build a :class:`Take` from a completed TAKE-phase ctx.

    Reads only the take-forming fields (Scout / Analyzer / Animation Director
    outputs). Does NOT read or carry any render artifact (no cartoon image)."""

    take_id = f"tk_{uuid.uuid4().hex[:8]}"

    event = {
        "title": ctx.event_title,
        "description": ctx.event_description,
        "source_url": getattr(ctx, "source_video_url", ""),
        "scout_source": getattr(ctx, "scout_source", ""),
    }

    visual_direction = {
        "scene": getattr(ctx, "scene_prompt", ""),
        "outfit": getattr(ctx, "character_outfit", ""),
        "subject_gender": getattr(ctx, "character_gender", "") or "male",
        "keywords": list(getattr(ctx, "video_keywords", []) or []),
    }

    return Take(
        take_id=take_id,
        schema_version=SCHEMA_VERSION,
        created_at=_now_z(),
        voice_tag=(getattr(ctx, "voice_tag", "") or _default_voice_tag()),
        event=event,
        angle=getattr(ctx, "chaos_angle", ""),
        line=getattr(ctx, "animation_direction", ""),
        visual_direction=visual_direction,
    )


def take_path(take_id: str) -> str:
    return os.path.join(TAKES_DIR, f"{take_id}.json")


def write_take(take: Take) -> str:
    """Persist a take to ``data/takes/{take_id}.json``. Returns the file path."""
    os.makedirs(TAKES_DIR, exist_ok=True)
    path = take_path(take.take_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(take.to_dict(), f, indent=2, ensure_ascii=False)
    return path


def read_take(take_id: str) -> Take:
    """Read a persisted take file back into a :class:`Take`."""
    path = take_path(take_id)
    if not os.path.exists(path):
        raise FileNotFoundError(f"No take found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Take(
        take_id=data["take_id"],
        schema_version=data["schema_version"],
        created_at=data["created_at"],
        voice_tag=data["voice_tag"],
        event=data["event"],
        angle=data["angle"],
        line=data["line"],
        visual_direction=data["visual_direction"],
    )


def load_take(take_id: str) -> VideoContext:
    """Hydrate a *fresh* VideoContext from a persisted take (architecture §3/§4).

    The returned ctx carries no reference to how the take was produced — only the
    take's own fields, mapped onto the legacy ctx fields the render agents already
    read. This is the "smallest version" of the seam (PRD T6): the hydrate step
    populates legacy fields so render agent bodies barely change, while the *source*
    of those values is now the persisted take, never an upstream render-fused ctx."""

    take = read_take(take_id)
    vd = take.visual_direction
    ev = take.event

    ctx = VideoContext()
    ctx.take_id = take.take_id
    ctx.voice_tag = take.voice_tag

    # event
    ctx.event_title = ev.get("title", "")
    ctx.event_description = ev.get("description", "")
    ctx.source_video_url = ev.get("source_url", "")
    ctx.scout_source = ev.get("scout_source", "")

    # angle + line
    ctx.chaos_angle = take.angle
    ctx.animation_direction = take.line
    ctx.video_script = take.line  # backward compat with summary builders

    # visual direction (text only — no cartoon image in the take)
    ctx.scene_prompt = vd.get("scene", "")
    ctx.character_outfit = vd.get("outfit", "")
    ctx.character_gender = vd.get("subject_gender", "male")
    ctx.video_keywords = list(vd.get("keywords", []) or [])

    return ctx

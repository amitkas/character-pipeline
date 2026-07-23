"""Load the BRAND & VOICE context slot into a structured Character.

Reads the fenced ``character:`` YAML block from the brand doc — the slot the host
cabinet fills (see ``CONTEXT.md`` and ``context_root.py``). This is the loader that
lets every agent read the *host's* character instead of baking a character literal
into prompts.

Fail-loud, never silently brand-substitute. The engine ships with **no** in-code
character. If the BRAND & VOICE slot is missing, empty, unparseable, or omits a
required field, ``get_character()`` raises ``CharacterError`` naming the slot path
and exactly what to fix. A bare checkout does not silently render instance #0's
character — it tells you to fill the slot (Context Layer Contract §4.5 / §5 / §6:
the product is brand-free; the host supplies the character).
"""

from dataclasses import dataclass, field

import yaml

from logger import get_logger
from context_root import slot_path

log = get_logger("character")


class CharacterError(RuntimeError):
    """The BRAND & VOICE slot is missing or incomplete.

    Raised loudly: the engine carries no fallback character, so a bad/empty slot
    stops the run with a precise cause instead of silently rendering someone else's
    brand."""


@dataclass
class Character:
    name: str
    tagline: str          # who the character is + what the videos do (one line)
    voice: str            # short voice descriptors the angle must sound like
    visual_identity: str  # full bullet identity, seeded into image/video gen
    visual_short: str     # one-sentence visual used inline in prompts
    visual_preserve: str  # the non-negotiable identity to keep across generations
    visual_color_guard: str  # the recolor guard line (optional — "" if the brand has none)
    personality: str
    off_limits_prompt: str
    off_limits_topics: list
    sound: dict           # {label, voice_name, voice_id, pitch_shift, gibberish_templates, video_audio_direction}
    distribution: dict    # {title_fallback, description_suffix, hashtags, tags}
    animation_style: str = ""   # render-style language for image/video prompts; falls back to visual_short
    caption_style: dict = field(default_factory=dict)   # per-key caption style overrides for Engine B (font_path, font_px, weight, box_rgb, text_rgb, pad_x, pad_y, radius, line_spacing, max_width_frac, y_frac)


def video_style_prefix(char: "Character") -> str:
    """The render-style language for image/video prompts: the character's explicit
    animation_style if set, else its visual_short (which carries the style words for a
    well-formed persona spec). Never a baked literal — always from the BRAND & VOICE slot."""
    return char.animation_style or char.visual_short


# Fields the host's character: block MUST provide. Listed explicitly so a missing
# one fails with a precise message — never a KeyError, never a silent brand default.
_REQUIRED_SCALARS = (
    "name", "tagline", "voice", "visual_identity",
    "visual_short", "visual_preserve", "personality", "off_limits_prompt",
)
# Sound sub-keys the always-on video pipeline consumes (ElevenLabs voice + gibberish).
# ``pitch_shift`` and ``video_audio_direction`` are optional (neutral / pipeline-variant).
_REQUIRED_SOUND_KEYS = ("label", "voice_name", "voice_id", "gibberish_templates")


def _extract_character_block(doc: str) -> dict | None:
    """Pull the fenced ``character:`` YAML block out of the brand doc."""
    for seg in doc.split("```"):
        if "character:" not in seg:
            continue
        block = seg
        first_nl = block.find("\n")
        if first_nl != -1 and block[:first_nl].strip().lower() in ("yaml", "yml"):
            block = block[first_nl + 1:]
        try:
            data = yaml.safe_load(block)
        except Exception:
            # A prose segment can mention "character:" without being the block —
            # skip it and keep looking for the real fenced YAML.
            continue
        if isinstance(data, dict) and isinstance(data.get("character"), dict):
            return data["character"]
    return None


def _is_empty(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, (list, dict)):
        return len(v) == 0
    return False


_cache: "Character | None" = None


def get_character() -> Character:
    """Return the host's Character (cached) from the BRAND & VOICE slot.

    Raises ``CharacterError`` if the slot is unreadable, has no ``character:`` block,
    or omits any required field. No fallback — the engine ships no character."""
    global _cache
    if _cache is not None:
        return _cache

    path = slot_path("brand")
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = f.read()
    except Exception as e:
        raise CharacterError(
            f"BRAND & VOICE slot is unreadable: {path} ({e}). Point CONTEXT_BRAND / "
            "CABINET_CONTEXT_ROOT at a doc with a fenced `character:` block, or fill that "
            "slot. The engine ships no built-in character (CONTEXT.md §3/§5)."
        ) from e

    block = _extract_character_block(doc)
    if not block:
        raise CharacterError(
            f"BRAND & VOICE slot has no fenced `character:` block: {path}. Add one — "
            "CONTEXT.md §3 lists the required keys. The engine has no character to fall "
            "back to."
        )

    # Validate everything required up front and report ALL gaps in one message.
    missing = [k for k in _REQUIRED_SCALARS if _is_empty(block.get(k))]

    topics = block.get("off_limits_topics")
    if not isinstance(topics, list) or not topics:
        missing.append("off_limits_topics")

    sound = block.get("sound")
    if not isinstance(sound, dict):
        missing.append("sound")
        sound = {}
    else:
        missing += [f"sound.{k}" for k in _REQUIRED_SOUND_KEYS if _is_empty(sound.get(k))]

    if missing:
        raise CharacterError(
            f"BRAND & VOICE slot {path} is missing required character field(s): "
            f"{', '.join(missing)}. Fill them in the `character:` block (CONTEXT.md §3 "
            "lists every key). The engine ships no fallback values."
        )

    # distribution is optional: a cabinet that never publishes needn't supply copy.
    # Defaults are neutral and derived from the slot's own name — never a baked brand literal.
    name = str(block["name"]).strip()
    dist = block.get("distribution") if isinstance(block.get("distribution"), dict) else {}
    distribution = {
        "title_fallback": dist.get("title_fallback") or f"{name}: latest video",
        "description_suffix": dist.get("description_suffix") or "",
        "hashtags": dist.get("hashtags") or "",
        "tags": dist.get("tags") or [],
    }

    _cache = Character(
        name=name,
        tagline=str(block["tagline"]).strip(),
        voice=str(block["voice"]).strip(),
        visual_identity=str(block["visual_identity"]).strip(),
        visual_short=str(block["visual_short"]).strip(),
        visual_preserve=str(block["visual_preserve"]).strip(),
        visual_color_guard=str(block.get("visual_color_guard") or "").strip(),
        personality=str(block["personality"]).strip(),
        off_limits_prompt=str(block["off_limits_prompt"]).strip(),
        off_limits_topics=list(topics),
        sound={
            "label": sound["label"],
            "voice_name": sound["voice_name"],
            "voice_id": sound["voice_id"],
            "pitch_shift": sound.get("pitch_shift") or 1.0,  # 1.0 = no shift (neutral)
            "gibberish_templates": list(sound["gibberish_templates"]),
            "video_audio_direction": sound.get("video_audio_direction") or "",
        },
        distribution=distribution,
        animation_style=str(block.get("animation_style") or "").strip(),
        caption_style=block.get("caption_style") if isinstance(block.get("caption_style"), dict) else {},
    )
    log.debug(f"  [character] loaded '{_cache.name}' from BRAND slot ({path})")
    return _cache

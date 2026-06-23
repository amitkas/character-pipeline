"""Creative Director — owns the chaos angle, decided AFTER the tape is seen.

Architecture: see ``docs/creative-director-proposal.md``. The angle (the comedic
POV the whole video hangs on) used to be set blind inside the Video Scout, from
the event's title + description alone, BEFORE any clip was downloaded or watched.
That is backwards: a creative director watches the tape, *then* finds the angle.

This agent runs after the Video Analyzer and decides ``ctx.chaos_angle`` from
three inputs the Scout never had:
  1. the Analyzer's video description — what literally happened on screen,
  2. the character's FULL persona (voice + identity), not just the off-limits guardrails,
  3. the content ICP — who a video is for and what it should do for them.

It deliberately owns ONLY the angle. The non-verbal-vs-scripted *voice* call
(whether the character gets scripted lines) is a separate, still-open design
decision (pending Amit) — this agent does NOT emit dialogue or scripted narration.
"""

from google import genai
from google.genai import types

from context import PipelineContext
from logger import get_logger, StepTimer
from context_root import slot_path
from agents.character import get_character
from utils.json_utils import parse_llm_json

log = get_logger("creative_director")

# Resolved through the Context Layer Contract (CONTEXT.md): the BRAND & VOICE doc
# and the AUDIENCE doc live in the host cabinet, located via the configurable
# context root — never a hardcoded ../../ climb or a host-specific filename.
BRAND_SLOT_PATH = slot_path("brand")
CONTENT_ICP_PATH = slot_path("audience")

ANGLE_MAX_WORDS = 20


def _load_full_persona() -> str:
    """Return the character's FULL persona text (voice + identity), not just guardrails.

    Prefers the whole BRAND & VOICE doc (the slot — see CONTEXT.md); falls back to the
    character loader's structured fields if the doc can't be read, so the pipeline
    still runs from a bare checkout / a host that only filled the character: block."""
    try:
        with open(BRAND_SLOT_PATH, "r", encoding="utf-8") as f:
            text = f.read().strip()
        if text:
            log.debug(f"  Loaded full persona from BRAND slot {BRAND_SLOT_PATH} ({len(text)} chars)")
            return text
    except Exception as e:
        log.debug(f"  Could not read BRAND slot {BRAND_SLOT_PATH}: {e}; falling back to character constants")

    char = get_character()
    return (
        f"# {char.name} — Character Bible (fallback)\n\n"
        "## Visual identity\n" + char.visual_identity.strip() + "\n\n"
        "## Core personality\n" + char.personality.strip() + "\n\n"
        "## Off limits\n" + char.off_limits_prompt
    )


def _load_content_icp() -> str:
    """Return the agent-readable ``content_icp:`` YAML block from the Content ICP.

    The ICP doc (growth/character-pipeline-content-icp.md §8) pins a fenced ``yaml`` block whose
    keys are the stable interface for this agent. We extract that block; if the
    file or block is missing we return an empty string and the prompt degrades to
    persona-only (logged), rather than crashing the take."""
    try:
        with open(CONTENT_ICP_PATH, "r", encoding="utf-8") as f:
            doc = f.read()
    except Exception as e:
        log.warning(f"  [Creative Director] Could not read content ICP ({CONTENT_ICP_PATH}): {e}")
        return ""

    # Pull the first fenced code block that contains the content_icp: key.
    segments = doc.split("```")
    for seg in segments:
        if "content_icp:" in seg:
            block = seg
            # Drop a leading language hint (e.g. "yaml\n").
            first_nl = block.find("\n")
            if first_nl != -1 and block[:first_nl].strip().lower() in ("yaml", "yml"):
                block = block[first_nl + 1:]
            block = block.strip()
            if block:
                log.debug(f"  Loaded content_icp block ({len(block)} chars)")
                return block

    log.warning("  [Creative Director] No content_icp: block found in ICP doc")
    return ""


def _is_truncated_angle(angle: str) -> bool:
    """True if the angle looks cut off (no terminal punctuation / dangling word)."""
    a = angle.strip().rstrip('"\'')
    if not a:
        return True
    if a[-1] not in ".!?":
        return True
    return False


def direct_creative(ctx: PipelineContext, config: dict) -> PipelineContext:
    """Decide ``ctx.chaos_angle`` from the watched tape + full persona + content ICP."""

    client = genai.Client(api_key=config["GEMINI_API_KEY"])

    char = get_character()
    name = char.name
    persona = _load_full_persona()
    content_icp = _load_content_icp()
    if not content_icp:
        log.info("  [Creative Director] content ICP unavailable — directing on persona only")

    system_prompt = (
        f"You are the CREATIVE DIRECTOR for {name}, {char.tagline}.\n\n"
        "YOUR JOB: decide the CHAOS ANGLE — the single comedic point of view the whole "
        "video hangs on. You have just watched the source footage (the Analyzer's "
        "description below is your eyes). Find the angle FROM what actually happens on "
        "screen — not from the headline alone.\n\n"
        "You are fed three inputs and must honor all three:\n"
        "1. THE TAPE — what literally happens in the footage. The angle must be physically "
        f"performable from this; {name} re-enacts a real moment, he doesn't narrate an abstract idea.\n"
        f"2. {name.upper()}'S FULL PERSONA — who {name} IS (voice, identity, what he finds funny), not just "
        f"what he can't touch. The angle must sound like THIS character: {char.voice}.\n"
        "3. THE CONTENT ICP — who the video is FOR and what it should DO for them. Optimize the "
        "angle for the ICP's angle-selection rule and primary audience; clear the ICP's hard bars.\n\n"
        f"HARD CONSTRAINTS:\n{char.off_limits_prompt}\n\n"
        "OUTPUT a JSON object with exactly these fields, IN THIS ORDER:\n"
        f'- "chaos_angle": the angle itself. ONE complete sentence, max {ANGLE_MAX_WORDS} words — '
        f"punchy, visual, and physically performable. First-person {name} main-character energy. "
        "Must be a finished sentence, not a fragment. NO dialogue or scripted lines — this is the "
        "POV, not the voiceover.\n"
        '- "video_job": which ONE job this video does for the audience, chosen from the ICP\'s '
        "video_jobs (e.g. recognition / demonstration / resonance).\n"
        '- "rationale": max 15 words — why this angle wins for the ICP\'s primary audience.\n\n'
        "Return ONLY valid JSON. No markdown, no explanation. Keep it short enough to be complete."
    )

    user_prompt = (
        f"EVENT: {ctx.event_title}\n"
        f"EVENT DESCRIPTION: {ctx.event_description}\n\n"
        f"THE TAPE (what the footage actually shows):\n{ctx.video_analysis}\n\n"
        f"=== {name.upper()}'S FULL PERSONA ===\n{persona}\n\n"
        f"=== CONTENT ICP (who this is for) ===\n"
        + (content_icp if content_icp else "(unavailable — rely on persona judgement)")
    )

    log.debug(f"  System prompt ({len(system_prompt)} chars)")
    log.debug(f"  User prompt ({len(user_prompt)} chars)")

    max_attempts = 3
    angle = ""
    extra = " Make sure chaos_angle is ONE complete, finished sentence."
    for attempt in range(1, max_attempts + 1):
        log.info(f"  [Creative Director] Deciding chaos angle (attempt {attempt})...")
        with StepTimer(log, f"Gemini creative direction (attempt {attempt})") as t:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Content(role="user", parts=[
                        types.Part(text=system_prompt + (extra if attempt > 1 else "") + "\n\n" + user_prompt)
                    ]),
                ],
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=2048,
                    # Structured, low-ambiguity task — skip thinking so the whole
                    # token budget goes to a complete JSON object (a short budget
                    # was getting spent on thinking and truncating the angle).
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )

        try:
            result = parse_llm_json(response.text, ["chaos_angle"])
        except ValueError as e:
            log.warning(f"  [Creative Director] JSON parse failed (attempt {attempt}): {e}")
            continue

        angle = (result.get("chaos_angle") or "").strip()
        word_count = len(angle.split())
        log.debug(f"  Took {t.elapsed:.2f}s; angle ({word_count} words): {angle}")

        if angle and word_count <= ANGLE_MAX_WORDS and not _is_truncated_angle(angle):
            ctx.chaos_angle = angle
            log.info(f"  [Creative Director] Video job: {result.get('video_job', '?')}")
            log.info(f"  [Creative Director] Rationale: {result.get('rationale', '?')}")
            log.info(f"  [Creative Director] Chaos angle: {angle}")
            return ctx

        if word_count > ANGLE_MAX_WORDS:
            log.debug(f"  Angle too long ({word_count} > {ANGLE_MAX_WORDS}), retrying")
        else:
            log.debug("  Angle looks truncated/empty, retrying")

    # Accept the last non-empty angle rather than crash the take.
    ctx.chaos_angle = angle
    log.info(f"  [Creative Director] Accepted after {max_attempts} attempts: {angle!r}")
    return ctx

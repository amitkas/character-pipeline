from google import genai
from google.genai import types

from context import PipelineContext
from logger import get_logger, StepTimer
from agents.character import get_character


def _build_system_prompt(char) -> str:
    """Build the animation-director system prompt from the host's character.

    Character name + visual identity come from the BRAND slot (see CONTEXT.md), so
    the same code directs whatever character the host cabinet declares — never a
    baked-in character."""
    n = char.name
    return f"""You are an animation director for a 15-second video of a character named {n} — {char.visual_short}.

YOUR JOB: Write a single, focused animation direction. The video model can only handle ONE clear action smoothly.

PRIORITY ORDER:
- PRIMARY: The gag MUST embody the chaos angle. The chaos angle is the comedic spin — your direction must bring it to life physically.
- SECONDARY: Use scene context only for setting or action ideas (where is {n}, what prop/situation). Do NOT let scene context override the chaos angle.

RULES:
- Describe ONE physical gag in 1-2 short sentences (15-25 words max)
- The gag must connect to the real event through the chaos angle
- Think: what is the ONE funniest thing {n} does that embodies the chaos angle?
- Describe simple, readable motion — one main action the camera can follow
- Do NOT list multiple actions or a sequence of beats
- Do NOT describe facial expressions, eye movements, or tiny details — the model can't animate those
- Do NOT re-describe {n}'s appearance (the image already shows him)
- Do NOT write dialogue
- Return ONLY the direction, nothing else

GOOD EXAMPLES (notice: one action, clear motion):
- "{n} slides across the finish line on his belly, arms out like a plane, then pops up holding a trophy above his head"
- "{n} yanks the microphone away and screams into it while the crowd behind him freezes in shock"
- "{n} belly-flops onto the red carpet and rolls toward the camera, arms flailing like a starfish"

BAD EXAMPLES (too many actions, model can't follow):
- "{n} bursts in, eyes spinning, dodges a car, leaps onto the hood, does a dance, then strikes a pose" (6 actions = incoherent)
- "{n}'s googly eyes widen as his jaw drops, then he flails his arms" (micro-expressions don't animate well)"""


log = get_logger("animation_director")

# Words that, if a direction ends on them, mean the sentence was cut off mid-thought.
_DANGLING_TAIL_WORDS = {
    "and", "then", "but", "or", "so", "with", "while", "as", "to", "into", "onto",
    "of", "for", "at", "on", "in", "by", "from", "the", "a", "an", "his", "her",
    "its", "their", "that", "which", "who", "when", "where", "before", "after",
    "over", "under", "toward", "towards", "like", "than",
}


def _is_truncated(direction: str) -> bool:
    """True if the direction looks cut off rather than a finished thought.

    Length alone can't catch this — a 14-word line that ends mid-sentence reads as
    valid by word count but is unusable. We reject a direction that does not end on
    terminal punctuation, or that dangles on a comma or a connective/article word.
    """
    text = direction.strip()
    if not text:
        return True
    # Allow a trailing closing quote/paren after the real punctuation.
    tail = text.rstrip('"\'')
    if not tail:
        return True
    last = tail[-1]
    if last in ",:;-—":
        return True
    if last not in ".!?":
        return True
    # Ends with proper punctuation, but is the final WORD a dangling connector?
    words = tail[:-1].split()
    if words and words[-1].lower().strip('.,!?"\'') in _DANGLING_TAIL_WORDS:
        return True
    return False


def write_animation_direction(ctx: PipelineContext, config: dict) -> PipelineContext:
    """Write animation direction for the character's behavior based on the trending event."""

    client = genai.Client(api_key=config["GEMINI_API_KEY"])

    char = get_character()
    system_prompt = _build_system_prompt(char)
    name = char.name

    user_prompt = (
        f"Write ONE animation gag for {name} at this event.\n\n"
        f"EVENT: {ctx.event_title}\n\n"
        f"CHAOS ANGLE (PRIMARY — the gag MUST embody this): {ctx.chaos_angle}\n\n"
        f"SCENE CONTEXT (SECONDARY — use for setting/action ideas only, do not let it override the chaos angle): {ctx.scene_prompt}\n\n"
        f"What is the single funniest physical action {name} does that brings the chaos angle to life? "
        "1-2 sentences, 15-25 words. One clear motion the camera can follow."
    )

    log.debug(f"User prompt ({len(user_prompt)} chars):\n{user_prompt}")
    log.debug(f"System prompt ({len(system_prompt)} chars)")

    max_attempts = 3
    direction = ""
    word_count = 0

    for attempt in range(1, max_attempts + 1):
        log.info(f"  [Animation Director] Generating direction (attempt {attempt})...")

        with StepTimer(log, f"Gemini animation direction (attempt {attempt})") as t:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Content(role="user", parts=[
                        types.Part(text=system_prompt + "\n\n" + user_prompt)
                    ]),
                ],
                config=types.GenerateContentConfig(
                    temperature=0.7,
                    max_output_tokens=500,
                ),
            )

        direction = response.text.strip()
        word_count = len(direction.split())
        truncated = _is_truncated(direction)

        log.info(f"  [Animation Director] Words: {word_count}, truncated: {truncated}")
        log.debug(f"  Generation took {t.elapsed:.2f}s")
        log.debug(f"  Raw direction:\n{direction}")

        if 10 <= word_count <= 30 and not truncated:
            ctx.animation_direction = direction
            ctx.video_script = direction  # backward compat with summary
            log.info(f"  [Animation Director] Direction accepted ({word_count} words)")
            log.info(f"  --- DIRECTION ---\n{direction}\n  --- END ---")
            return ctx

        if word_count < 10:
            log.debug(f"  Direction too short ({word_count} < 10), requesting longer version")
            user_prompt += "\n\nToo short. Write 15-25 words describing one physical gag."
        elif word_count > 30:
            log.debug(f"  Direction too long ({word_count} > 30), requesting shorter version")
            user_prompt += "\n\nToo long. Cut it to ONE action in 15-25 words. No sequences."
        else:
            log.debug("  Direction truncated/dangling, requesting a complete sentence")
            user_prompt += (
                "\n\nThat was cut off mid-sentence. Rewrite as ONE complete, finished "
                "sentence (15-25 words) that ends with proper punctuation."
            )

    # Accept whatever we got on the last attempt
    ctx.animation_direction = direction
    ctx.video_script = direction  # backward compat
    log.info(f"  [Animation Director] Accepted after {max_attempts} attempts ({word_count} words)")
    log.debug("  Accepted despite not meeting word count target")
    log.info(f"  --- DIRECTION ---\n{direction}\n  --- END ---")
    return ctx

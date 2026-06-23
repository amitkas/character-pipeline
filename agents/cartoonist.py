import os
from PIL import Image
from google import genai

from context import PipelineContext
from logger import get_logger, StepTimer
from agents.character import get_character

log = get_logger("character_dresser")


def _build_dresser_prompt(outfit_description: str, scene_prompt: str) -> str:
    """Build the prompt for dressing the character in the detected outfit.

    Character name, visual identity, and the recolor guard come from the BRAND slot
    (see CONTEXT.md), so the same code dresses whatever character the host declares."""
    char = get_character()
    n = char.name
    return (
        f"You are given a reference image of a character named {n} — {char.visual_short}.\n\n"
        f"TASK: Edit this character image to dress {n} in the following outfit: "
        f"{outfit_description}\n\n"
        f"CRITICAL — The output MUST be this exact character ({n}) with the outfit on. "
        "Do NOT generate a real human or a different character. The result must be the SAME character "
        "from the reference image, just wearing the described outfit. "
        f"Preserve his exact appearance — {char.visual_color_guard}.\n\n"
        "REQUIREMENTS:\n"
        f"- The character MUST remain {n}: {char.visual_preserve}\n"
        f"- Dress {n} in the described outfit, adapted to fit his body (comically stretched)\n"
        f"- Place {n} in a scene matching this context: {scene_prompt}\n"
        "- Background should be a stylized Pixar 3D animated version of the scene\n"
        "- Overall style: Pixar 3D animation, soft lighting, vibrant colors\n"
        "- Square composition (1:1 aspect ratio)\n"
        f"- {n} should look mischievous and excited, like he just crashed the scene\n"
        "- Do NOT include any real humans in the image\n"
        f"- Do NOT replace {n} with a human or realistic figure\n"
        f"- Do NOT change {n}'s species or color — {char.visual_color_guard}"
    )


def dress_character(ctx: PipelineContext, config: dict) -> PipelineContext:
    """Generate an image of the character dressed in the detected outfit using Gemini image generation."""

    # Use an image-capable model: gemini-2.5-flash is text-only and returns 400 for response_modalities IMAGE.
    image_model = "gemini-2.5-flash-image"
    client = genai.Client(api_key=config["GEMINI_API_KEY"])

    # Load the character reference image (scene image not sent to avoid confusing the model)
    character_image = Image.open(ctx.character_image_path)

    log.debug(f"Character image: {ctx.character_image_path} ({character_image.size[0]}x{character_image.size[1]})")
    log.debug(f"Outfit: {ctx.character_outfit}")

    # Build prompt
    prompt = _build_dresser_prompt(ctx.character_outfit, ctx.scene_prompt)
    log.debug(f"Dresser prompt ({len(prompt)} chars): {prompt[:300]}...")
    log.info("  [Character Dresser] Sending character reference to Gemini Image Generation...")

    try:
        # PRIMARY: character image only + outfit/scene text description
        # (scene image omitted — sending both images makes the model edit the photo instead of the character)
        with StepTimer(log, "Gemini image generation (primary - character only)") as t:
            response = client.models.generate_content(
                model=image_model,
                contents=[prompt, character_image],
                config=genai.types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )

        log.debug(f"Gemini response received in {t.elapsed:.2f}s")
        if response.candidates:
            parts = response.candidates[0].content.parts
            log.debug(f"Response parts: {len(parts)} — types: {[('image' if p.inline_data else 'text') for p in parts]}")

        cartoon_path = _extract_image(response, ctx.run_id)
        if cartoon_path:
            ctx.cartoon_image_path = cartoon_path
            log.info(f"  [Character Dresser] Dressed image saved: {cartoon_path}")
            return ctx

        log.info("  [Character Dresser] No image in response, trying simplified fallback...")

        # FALLBACK 1: character image only + simplified outfit prompt
        char = get_character()
        n = char.name
        fallback_prompt = (
            f"Take this character ({char.visual_short}, named {n}) "
            f"and dress it in: {ctx.character_outfit}. "
            f"Place it in a Pixar 3D animated scene. Square composition (1:1). "
            f"Keep the character's appearance — {char.visual_color_guard}."
        )
        log.debug(f"Fallback prompt: {fallback_prompt}")

        with StepTimer(log, "Gemini image generation (fallback - character only)") as t:
            response = client.models.generate_content(
                model=image_model,
                contents=[fallback_prompt, character_image],
                config=genai.types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )

        cartoon_path = _extract_image(response, ctx.run_id)
        if cartoon_path:
            ctx.cartoon_image_path = cartoon_path
            log.info(f"  [Character Dresser] Image saved (fallback 1): {cartoon_path}")
            return ctx

        log.info("  [Character Dresser] Fallback 1 failed, trying text-only generation...")

        # FALLBACK 2: pure text prompt, no input images
        text_only_prompt = (
            f"Generate a Pixar 3D animated image of {char.visual_short}, a character named {n}. "
            f"{n} is wearing: {ctx.character_outfit}. "
            "The outfit is comically stretched over his body. "
            "Square composition (1:1). Vibrant colors, soft Pixar lighting. "
            f"{n} has a mischievous grin."
        )
        log.debug(f"Text-only prompt: {text_only_prompt}")

        with StepTimer(log, "Gemini image generation (fallback - text only)") as t:
            response = client.models.generate_content(
                model=image_model,
                contents=[text_only_prompt],
                config=genai.types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )

        cartoon_path = _extract_image(response, ctx.run_id)
        if cartoon_path:
            ctx.cartoon_image_path = cartoon_path
            log.info(f"  [Character Dresser] Image saved (text-only): {cartoon_path}")
            return ctx

    except Exception as e:
        log.info(f"  [Character Dresser] Gemini failed: {e}")
        log.debug(f"  Full exception: {type(e).__name__}: {e}")

    # ULTIMATE FALLBACK: use the raw character reference image
    log.info("  [Character Dresser] All generation failed. Using raw character image as fallback.")
    ctx.cartoon_image_path = ctx.character_image_path
    return ctx


def _extract_image(response, run_id: str) -> str | None:
    """Extract image from Gemini response parts and save it."""
    if not response.candidates:
        log.debug("No candidates in response")
        return None

    for part in response.candidates[0].content.parts:
        if part.inline_data and part.inline_data.mime_type.startswith("image/"):
            artifacts_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "artifacts", "images"
            )
            os.makedirs(artifacts_dir, exist_ok=True)

            ext = part.inline_data.mime_type.split("/")[-1]
            if ext == "jpeg":
                ext = "jpg"
            path = os.path.join(artifacts_dir, f"{run_id}_dressed.{ext}")

            data_size = len(part.inline_data.data)
            log.debug(f"Extracted image: mime={part.inline_data.mime_type}, size={data_size} bytes")

            with open(path, "wb") as f:
                f.write(part.inline_data.data)
            return path

    log.debug("No image parts found in response candidates")
    return None

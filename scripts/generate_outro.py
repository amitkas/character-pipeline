#!/usr/bin/env python3
"""Generate a 3-second branded outro video (character + title + subtitle) with
fade-in/fade-out.

Brand-free: the character image comes from the CHARACTER IMAGE slot and the title
defaults to the host character's name (BRAND & VOICE slot). The subtitle and output
path are supplied by the caller — nothing about a specific brand is baked in. The
result is a BRANDED ASSET the host then wires in via the `CONTEXT_OUTRO` slot.

Usage:
  python3 scripts/generate_outro.py [--title TEXT] [--subtitle TEXT] \
      [--image PATH] [--output PATH]
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from orchestrator import resolve_character_image
from agents.character import get_character

# ── Config ──────────────────────────────────────────────────────────────────
WIDTH, HEIGHT = 1080, 1080  # 1:1 square aspect ratio
FPS = 30
DURATION_S = 3.0
FADE_IN_S = 0.6
FADE_OUT_S = 0.6

BG_COLOR = (0, 0, 0)

DEFAULT_OUTPUT = os.path.join(ROOT, "artifacts", "outro.mp4")


def get_font(size: int) -> ImageFont.FreeTypeFont:
    """Load a bold system font at the given size."""
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSDisplay.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def load_character(image_path: str) -> Image.Image:
    """Load and resize the character image to fit the canvas nicely."""
    char_img = Image.open(image_path).convert("RGBA")

    # Scale character to ~45% of canvas width, keep aspect ratio
    target_w = int(WIDTH * 0.45)
    scale = target_w / char_img.width
    target_h = int(char_img.height * scale)
    char_img = char_img.resize((target_w, target_h), Image.LANCZOS)

    return char_img


def draw_text_with_outline(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    outline_color: tuple = (0, 0, 0),
    outline_width: int = 4,
    anchor: str = "mt",
):
    """Draw text with a circular outline/stroke effect."""
    for dx in range(-outline_width, outline_width + 1):
        for dy in range(-outline_width, outline_width + 1):
            if dx * dx + dy * dy <= outline_width * outline_width:
                draw.text(
                    (x + dx, y + dy), text, font=font, fill=outline_color, anchor=anchor
                )
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor)


def render_frame(char_img, title_font, subtitle_font, alpha, title, subtitle) -> Image.Image:
    """Render a single outro frame with the given opacity (0.0 – 1.0)."""
    # Start with black background
    frame = Image.new("RGBA", (WIDTH, HEIGHT), (*BG_COLOR, 255))

    # ── Composite character ─────────────────────────────────────────────
    # Center horizontally, place in upper area for square video
    char_x = (WIDTH - char_img.width) // 2
    char_y = int(HEIGHT * 0.2)  # Centered for 1:1 square

    if alpha < 1.0:
        # Apply fade to character
        faded_char = char_img.copy()
        r, g, b, a = faded_char.split()
        a = a.point(lambda p: int(p * alpha))
        faded_char = Image.merge("RGBA", (r, g, b, a))
        frame.paste(faded_char, (char_x, char_y), faded_char)
    else:
        frame.paste(char_img, (char_x, char_y), char_img)

    # ── Draw text ───────────────────────────────────────────────────────
    draw = ImageDraw.Draw(frame)

    # Compute fade colors
    title_color = tuple(int(255 * alpha) for _ in range(3))
    subtitle_color = tuple(int(200 * alpha) for _ in range(3))

    # Title — big, centered below character
    title_y = char_y + char_img.height + int(HEIGHT * 0.03)
    draw_text_with_outline(
        draw,
        title,
        WIDTH // 2,
        title_y,
        title_font,
        fill=title_color,
        outline_color=(0, 0, 0),
        outline_width=5,
        anchor="mt",
    )

    # Subtitle — smaller, centered below title (skipped if empty)
    if subtitle:
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_h = title_bbox[3] - title_bbox[1]
        subtitle_y = title_y + title_h + int(HEIGHT * 0.025)

        for i, line in enumerate(subtitle.split("\n")):
            line_y = subtitle_y + i * int(subtitle_font.size * 1.4)
            draw_text_with_outline(
                draw,
                line,
                WIDTH // 2,
                line_y,
                subtitle_font,
                fill=subtitle_color,
                outline_color=(0, 0, 0),
                outline_width=3,
                anchor="mt",
            )

    # Convert to RGB for video encoding
    return frame.convert("RGB")


def main():
    parser = argparse.ArgumentParser(description="Generate a branded outro clip.")
    parser.add_argument("--title", default=None,
                        help="Title text (default: the host character's name).")
    parser.add_argument("--subtitle", default="",
                        help="Subtitle line(s); use \\n for breaks. Default: none.")
    parser.add_argument("--image", default=None,
                        help="Character PNG (default: the CHARACTER IMAGE slot).")
    parser.add_argument("--output", default=DEFAULT_OUTPUT,
                        help=f"Output mp4 path (default: {DEFAULT_OUTPUT}).")
    args = parser.parse_args()

    title = args.title or get_character().name
    image_path = args.image or resolve_character_image()
    output_path = args.output

    print(f"🎬 Generating outro video for '{title}'...")

    # Load assets
    char_img = load_character(image_path)
    title_font = get_font(90)
    subtitle_font = get_font(38)

    total_frames = int(FPS * DURATION_S)
    fade_in_frames = int(FPS * FADE_IN_S)
    fade_out_frames = int(FPS * FADE_OUT_S)

    # Create temp directory for frames
    frames_dir = tempfile.mkdtemp(prefix="outro_frames_")

    try:
        print(f"   Rendering {total_frames} frames at {WIDTH}x{HEIGHT}...")

        for i in range(total_frames):
            # Calculate fade alpha
            if i < fade_in_frames:
                alpha = i / fade_in_frames
            elif i >= total_frames - fade_out_frames:
                alpha = (total_frames - 1 - i) / fade_out_frames
            else:
                alpha = 1.0

            alpha = max(0.0, min(1.0, alpha))

            frame = render_frame(char_img, title_font, subtitle_font, alpha,
                                 title, args.subtitle)
            frame_path = os.path.join(frames_dir, f"frame_{i:06d}.png")
            frame.save(frame_path)

        print("   Encoding video with ffmpeg...")

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(FPS),
            "-i", f"{frames_dir}/frame_%06d.png",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "18",
            "-preset", "fast",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0:
            print(f"   ❌ ffmpeg failed: {result.stderr[:500]}")
            return

        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"   ✅ Outro saved: {output_path} ({file_size_mb:.1f} MB)")

    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)


if __name__ == "__main__":
    main()

"""Quick test: Wan 2.6 image-to-video with the host character's reference image.
Generates a 10s 720p 1:1 video and saves it to artifacts/videos/.

Brand-free: the reference image and the visual prompt come from the host's context
slots (CHARACTER IMAGE + BRAND & VOICE), never a baked-in character.
Cost: 10s × $0.10/s = $1.00
"""

import os
import sys
import time
import requests
import fal_client
from PIL import Image
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

from orchestrator import resolve_character_image
from agents.character import get_character

os.environ["FAL_KEY"] = os.environ.get("FAL_KEY", "")

CHARACTER_IMAGE = resolve_character_image()  # CHARACTER IMAGE slot
OUTPUT_DIR = os.path.join(ROOT, "artifacts", "videos")
os.makedirs(OUTPUT_DIR, exist_ok=True)

TARGET_SIZE = 720  # 720p square for 1:1


def ensure_square(image_path: str) -> str:
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    if w != h:
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
    img = img.resize((TARGET_SIZE, TARGET_SIZE), Image.Resampling.LANCZOS)
    out = os.path.join(OUTPUT_DIR, "wan26_test_input.jpg")
    img.save(out, "JPEG", quality=92)
    print(f"Input image: {out} ({TARGET_SIZE}x{TARGET_SIZE})")
    return out


def main():
    char = get_character()
    print(f"=== Wan 2.6 Test: {char.name} 10s 720p ===\n")

    square_img = ensure_square(CHARACTER_IMAGE)

    print("Uploading image to fal.ai...")
    client = fal_client.SyncClient(default_timeout=120)
    image_url = client.upload_file(square_img)
    print(f"Uploaded: {image_url[:80]}...\n")

    # Visual direction comes from the BRAND slot — no baked character description.
    prompt = (
        f"Pixar 3D animation style. {char.visual_short} dances wildly on a stage, "
        "arms flailing, jumping up and down with chaotic energy. Smooth continuous "
        "motion, vibrant lighting, comedic physical comedy."
    )

    print(f"Prompt: {prompt}\n")
    print("Submitting Wan 2.6 job (10s, 720p)...")
    print("This may take 2-5 minutes...\n")

    def on_queue_update(update):
        if isinstance(update, fal_client.InProgress):
            for entry in update.logs:
                print(f"  [wan2.6] {entry['message']}")

    t0 = time.time()
    result = fal_client.subscribe(
        "wan/v2.6/image-to-video",
        arguments={
            "image_url": image_url,
            "prompt": prompt,
            "duration": "10",
            "resolution": "720p",
            "negative_prompt": "blur, distortion, low quality, realistic human",
            "enable_prompt_expansion": False,
            "enable_safety_checker": False,
        },
        with_logs=True,
        on_queue_update=on_queue_update,
    )
    elapsed = time.time() - t0
    print(f"\nGeneration completed in {elapsed:.1f}s")

    video_url = result["video"]["url"]
    print(f"Video URL: {video_url}")

    if "actual_prompt" in result and result["actual_prompt"]:
        print(f"Actual prompt used: {result['actual_prompt']}")

    out_path = os.path.join(OUTPUT_DIR, "wan26_test_output.mp4")
    print(f"Downloading to {out_path}...")
    resp = requests.get(video_url, stream=True, timeout=120)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"\nSaved: {out_path} ({size_mb:.1f} MB)")
    print(f"Cost: ~$1.00 (10s × $0.10/s at 720p)")
    print("Done! Open the video to compare quality with Kling v3.")


if __name__ == "__main__":
    main()

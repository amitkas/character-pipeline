import os
from dotenv import load_dotenv


REQUIRED_KEYS = [
    "SERPER_API_KEY",
    "GEMINI_API_KEY",
    "FAL_KEY",
    "ELEVENLABS_API_KEY",
]

OPTIONAL_KEYS = [
    "PERPLEXITY_API_KEY",
    "XAI_API_KEY",              # xAI Grok — video generation (video-x pipeline)
    # ── Context Layer Contract (see CONTEXT.md / context_root.py) ──
    # The host cabinet root + per-slot doc overrides. All optional: unset =>
    # defaults resolve to THIS cabinet, so instance #0 runs with zero config.
    "STUDIO_CONTEXT_ROOT",      # Absolute path to the host cabinet's context root
    "CABINET_CONTEXT_ROOT",     # Legacy name, still honored as a fallback for one version
    "CONTEXT_SPINE",            # Override for the SPINE slot (default foundation/one-pager.md)
    "CONTEXT_BRAND",            # Override for the BRAND & VOICE slot (default brand/arbi-character.md)
    "CONTEXT_VOICE",            # Override for the VOICE detail slot (default brand/voice)
    "CONTEXT_AUDIENCE",         # Override for the AUDIENCE slot (default growth/character-pipeline-content-icp.md)
    "CONTEXT_RELEVANCE",        # Override for the RELEVANCE LENS slot (default foundation/keywords.md)
    "CONTEXT_CHARACTER_IMAGE",  # Character reference PNG (preferred name; alias of ARBI_CHARACTER_IMAGE)
    "ARBI_CHARACTER_IMAGE",     # Deprecated alias of CONTEXT_CHARACTER_IMAGE (swappable per character/client)
    "CONTEXT_OUTRO",            # BRANDED ASSETS: host outro clip appended by the Outro Stitcher (absent => skipped)
    "CONTEXT_MUSIC_DIR",        # BRANDED ASSETS: host music-bed dir mixed by the Sound Engineer (absent => skipped)
    "YT_DLP_COOKIES",           # Path to cookies.txt for YouTube (export from browser)
    "YT_DLP_COOKIES_FROM_BROWSER",  # e.g. "chrome" or "firefox" — use browser cookies
    "YOUTUBE_UPLOAD_ENABLED",   # Set to "true" to enable auto-upload to YouTube
    "YOUTUBE_PLAYLIST_ID",      # Channel playlist ID — every video is added to this playlist
    "YOUTUBE_ARBI_PLAYLIST_ID", # Deprecated alias of YOUTUBE_PLAYLIST_ID
]


def load_config() -> dict:
    load_dotenv()

    config = {}
    missing = []

    for key in REQUIRED_KEYS:
        value = os.getenv(key, "").strip()
        if not value:
            missing.append(key)
        config[key] = value

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Copy .env.example to .env and fill in the values."
        )

    for key in OPTIONAL_KEYS:
        config[key] = os.getenv(key, "").strip()

    # Back-compat: deprecated *_ARBI_* aliases feed the brand-free keys the agents read.
    if not config.get("YOUTUBE_PLAYLIST_ID") and config.get("YOUTUBE_ARBI_PLAYLIST_ID"):
        config["YOUTUBE_PLAYLIST_ID"] = config["YOUTUBE_ARBI_PLAYLIST_ID"]
    if not config.get("CONTEXT_CHARACTER_IMAGE") and config.get("ARBI_CHARACTER_IMAGE"):
        config["CONTEXT_CHARACTER_IMAGE"] = config["ARBI_CHARACTER_IMAGE"]

    return config

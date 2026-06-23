"""LEARN as a log, not an analyst (architecture §5 / roadmap §3).

A flat append-only ``data/learn_log.jsonl`` — JSON Lines, **one row per published
asset, never rewritten**. ``take_id`` is the join key back to
``data/takes/{take_id}.json``; that join is the entire point — it lets LEARN later
ask "which *angle*, rendered which *technique*, at what *cost* and *control*,
converted?"

This is deliberately NOT an analyst: no aggregation, no scoring, no UI (PRD §2a).
``engagement_rate`` / ``impressions`` stay ``null`` now and are backfilled when
X/YouTube channel data connects (roadmap §5)."""

import json
import os
from datetime import datetime, timezone

LEARN_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "learn_log.jsonl")

# Field order matches the architecture §5 / PRD §4 row spec.
ROW_FIELDS = [
    "ts",
    "take_id",
    "technique",
    "aspect_ratio",
    "cost_usd",
    "control_of_script",
    "asset_path",
    "platform",
    "asset_url",
    "engagement_rate",
    "impressions",
]


def _now_z() -> str:
    """ISO-8601 UTC timestamp to the minute with a trailing Z (matches §4 example)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def append_learn(
    take_id: str,
    technique: str,
    aspect_ratio: str,
    cost_usd: float,
    control_of_script: bool,
    asset_path: str,
    platform=None,
    asset_url=None,
    engagement_rate=None,
    impressions=None,
    ts: str = None,
) -> dict:
    """Append exactly one row to ``data/learn_log.jsonl`` and return it.

    One row per asset, append-only, never rewritten (PRD D1). ``engagement_rate``
    and ``impressions`` are present and ``null`` until channel data connects (D4).
    ``platform`` / ``asset_url`` are ``null`` until the asset is actually published
    (E1) — they get their values from the publish step, which is out of scope this
    week (PRD T9)."""

    row = {
        "ts": ts or _now_z(),
        "take_id": take_id,
        "technique": technique,
        "aspect_ratio": aspect_ratio,
        "cost_usd": cost_usd,
        "control_of_script": bool(control_of_script),
        "asset_path": asset_path,
        "platform": platform,
        "asset_url": asset_url,
        "engagement_rate": engagement_rate,   # the one success metric — null for now (D4)
        "impressions": impressions,           # denominator — null for now (D4)
    }

    os.makedirs(os.path.dirname(LEARN_LOG), exist_ok=True)
    with open(LEARN_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return row


def read_learn() -> list:
    """Read all rows from the learn log (convenience for verification/inspection)."""
    if not os.path.exists(LEARN_LOG):
        return []
    rows = []
    with open(LEARN_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

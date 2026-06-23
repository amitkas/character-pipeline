"""Take Emitter — the seam agent (architecture §3).

Terminal step of the TAKE phase. Does three boring things:
  1. builds a Take from ctx,
  2. writes data/takes/{take_id}.json,
  3. sets ctx.take_id.

After this line the pipeline knows nothing about *how* the take was made;
everything downstream reads from the persisted take by take_id.
"""

import os
import sys

# take.py lives at the project root (one level up from agents/).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from take import emit_take, write_take
from context import PipelineContext
from logger import get_logger

log = get_logger("take_emitter")


def emit_take_artifact(ctx: PipelineContext, config: dict) -> PipelineContext:
    """Build the take from the completed TAKE-phase ctx, persist it, set ctx.take_id."""

    take = emit_take(ctx)
    path = write_take(take)
    ctx.take_id = take.take_id

    log.info(f"  [Take Emitter] Take persisted: {path}")
    log.info(f"  [Take Emitter] take_id: {take.take_id}")
    log.info(f"  [Take Emitter] voice_tag: {take.voice_tag}  (pointer, not the voice)")
    log.info(f"  [Take Emitter] angle: {take.angle}")
    log.debug(f"  [Take Emitter] event: {take.event}")
    log.debug(f"  [Take Emitter] visual_direction: {take.visual_direction}")

    return ctx

"""SSE event streaming route for live updates."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])


async def _event_generator(queue: asyncio.Queue | None) -> AsyncIterator[dict]:
    """Yield SSE-formatted events from the event queue.

    If queue is None (non-watch mode), the generator yields nothing and exits.
    """
    if queue is None:
        return

    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=30.0)
            yield {
                "event": event.get("type", "message"),
                "data": json.dumps(event.get("data", {})),
            }
        except asyncio.TimeoutError:
            # Send keepalive comment to prevent connection timeout
            yield {"comment": "keepalive"}
        except asyncio.CancelledError:
            break


@router.get("/events")
async def event_stream(request: Request):
    """SSE endpoint for real-time events (reindex_start, reindex_complete, file_changed)."""
    from sse_starlette.sse import EventSourceResponse

    event_queue = request.app.state.event_queue
    return EventSourceResponse(_event_generator(event_queue))

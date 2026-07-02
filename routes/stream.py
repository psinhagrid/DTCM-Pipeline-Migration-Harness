import json
from typing import AsyncGenerator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from event_queue import subscribe, unsubscribe

router = APIRouter()


@router.get("/stream")
async def stream():
    q = subscribe()

    async def generator() -> AsyncGenerator[dict, None]:
        try:
            while True:
                event = await q.get()
                yield {"data": json.dumps(event)}
                # Only close when the orchestrator sends the final complete — not sub-agent completions
                if event.get("type") == "complete" and event.get("agent") in ("orchestrator_agent", "orchestrator"):
                    break
        finally:
            unsubscribe(q)

    return EventSourceResponse(generator())

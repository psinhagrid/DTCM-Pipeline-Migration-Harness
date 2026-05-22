import json
from typing import AsyncGenerator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from event_queue import event_queue

router = APIRouter()


async def event_generator() -> AsyncGenerator[dict, None]:
    while True:
        event = await event_queue.get()
        yield {"data": json.dumps(event)}
        if event.get("type") == "complete":
            break


@router.get("/stream")
async def stream():
    return EventSourceResponse(event_generator())

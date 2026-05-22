import asyncio
from datetime import datetime, timezone

event_queue: asyncio.Queue = asyncio.Queue()


async def push(
    *,
    type: str,
    agent: str,
    message: str,
    target: str | None = None,
    pipeline: str = "hive_migration",
    **extra,
) -> None:
    await event_queue.put({
        "type": type,
        "agent": agent,
        "message": message,
        "target": target,
        "pipeline": pipeline,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **extra,
    })

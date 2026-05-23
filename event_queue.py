import asyncio
import anthropic
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


async def claude_with_retry(client: anthropic.Anthropic, max_attempts: int = 3, **kwargs):
    """
    Call client.messages.create with exponential backoff on transient errors.
    Raises immediately on non-retryable errors (auth, bad request).
    """
    retryable = (
        anthropic.RateLimitError,
        anthropic.APIConnectionError,
        anthropic.InternalServerError,
    )
    for attempt in range(max_attempts):
        try:
            return await asyncio.to_thread(client.messages.create, **kwargs)
        except retryable:
            if attempt == max_attempts - 1:
                raise
            await asyncio.sleep(2 ** attempt)   # 1s → 2s → 4s
        except (anthropic.AuthenticationError, anthropic.BadRequestError):
            raise

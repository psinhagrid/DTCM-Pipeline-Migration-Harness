import asyncio
import os
import anthropic
from datetime import datetime, timezone

event_queue: asyncio.Queue = asyncio.Queue()

# Set AGENT_LOG=true to print agent events to terminal as they happen.
_LOG = os.getenv("AGENT_LOG", "false").lower() == "true"

_ICONS = {
    "delegation": "→",
    "tool_call":  "  ⚙",
    "artifact":   "  ✓",
    "validation": "  ✓",
    "hook":       "  ⚡",
    "complete":   "✅",
    "error":      "  ✗",
    "status":     "  ·",
}

_AGENT_SHORT = {
    "supervisor":         "SUP",
    "assess_subagent":    "ASS",
    "convert_subagent":   "CVT",
    "reconcile_subagent": "REC",
    "deploy_subagent":    "DEP",
}

# ── User input mechanism ──────────────────────────────────────────────────────
# When the supervisor needs user input, it calls request_user_input().
# That pushes a user_input_required SSE event to the frontend,
# then waits until the frontend POSTs a choice via /user-input endpoint.

_input_event:    asyncio.Event | None = None
_input_response: dict | None = None
_pending_input:  dict | None = None   # read by /pending-input endpoint


async def request_user_input(situation: str, options: list[str], pipeline: str = "") -> dict:
    """
    Push a user_input_required event to the frontend and wait for the response.
    Returns {"choice": int, "chosen": str} when the user submits.
    Times out after 10 minutes and defaults to Halt.
    """
    global _input_event, _input_response, _pending_input

    _input_event    = asyncio.Event()
    _input_response = None
    _pending_input  = {"situation": situation, "options": options, "pipeline": pipeline}

    await push(
        type="user_input_required",
        agent="supervisor",
        message=situation,
        situation=situation,
        options=options,
        pipeline=pipeline or "system",
    )

    try:
        await asyncio.wait_for(_input_event.wait(), timeout=600)   # 10 min timeout
    except asyncio.TimeoutError:
        _input_response = {"choice": len(options), "chosen": options[-1], "timed_out": True}

    result = _input_response or {"choice": len(options), "chosen": options[-1]}
    _pending_input  = None
    _input_event    = None
    _input_response = None
    return result


def resolve_user_input(choice: int, chosen: str) -> bool:
    """Called by the /user-input endpoint when the frontend submits a choice."""
    global _input_event, _input_response
    if _input_event and not _input_event.is_set():
        _input_response = {"choice": choice, "chosen": chosen}
        _input_event.set()
        return True
    return False


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
        "type":      type,
        "agent":     agent,
        "message":   message,
        "target":    target,
        "pipeline":  pipeline,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **extra,
    })

    if _LOG:
        icon  = _ICONS.get(type, "  ·")
        short = _AGENT_SHORT.get(agent, agent[:3].upper())
        ts    = datetime.now().strftime("%H:%M:%S")
        if type == "delegation" and target:
            print(f"\033[90m{ts}\033[0m \033[1m{icon} [{short}]\033[0m → \033[1m{target}\033[0m")
        elif type == "complete":
            print(f"\033[90m{ts}\033[0m {icon} [{short}] \033[32m{message}\033[0m")
        elif type == "error":
            print(f"\033[90m{ts}\033[0m {icon} [{short}] \033[31m{message}\033[0m")
        else:
            print(f"\033[90m{ts}\033[0m {icon} [{short}] {message}")


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
            await asyncio.sleep(2 ** attempt)
        except (anthropic.AuthenticationError, anthropic.BadRequestError):
            raise

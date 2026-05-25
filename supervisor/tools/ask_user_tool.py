"""
Interactive user prompt — pauses the supervisor and asks the user for
guidance via the frontend UI (not the terminal).

Pushes a user_input_required SSE event, frontend shows a modal,
user clicks an option, frontend POSTs to /user-input, supervisor continues.
"""

from event_queue import request_user_input


async def ask_user_tool(situation: str, options: list[str], pipeline: str = "") -> dict:
    """
    Push a user_input_required event and wait for the user to respond in the frontend.
    Returns {"choice": int, "chosen": str}.
    Times out after 10 minutes — defaults to the last option (usually Halt).
    """
    return await request_user_input(situation, options, pipeline)

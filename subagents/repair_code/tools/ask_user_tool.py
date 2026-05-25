from event_queue import request_user_input


async def ask_user_tool(situation: str, options: list[str], pipeline: str = "") -> dict:
    """
    Show a proposed fix to the user and wait for their response.
    situation: describes the issue and proposed fix (before/after)
    options: e.g. ["Accept fix", "Skip this fix", "Halt repair"]
    """
    return await request_user_input(situation, options, pipeline)

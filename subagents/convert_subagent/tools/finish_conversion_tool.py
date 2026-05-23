def finish_conversion_tool(result: dict, status: str = "SUCCESS", reason: str = "") -> dict:
    """
    Signal that conversion is complete. Always the agent's final action.
    status: SUCCESS | HALTED | ERROR
    reason: required when status is HALTED or ERROR
    """
    return {
        "finished": True,
        "status":   status,
        "reason":   reason,
        "result":   result,
    }

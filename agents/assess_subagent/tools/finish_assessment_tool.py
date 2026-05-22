def finish_assessment_tool(result: dict, status: str = "SUCCESS", reason: str = "") -> dict:
    """
    Signal that assessment is complete. Always the agent's final action.
    status: SUCCESS | HALTED | ERROR
    reason: required when status is HALTED or ERROR
    """
    return {
        "finished": True,
        "status":   status,
        "reason":   reason,
        "result":   result,
    }

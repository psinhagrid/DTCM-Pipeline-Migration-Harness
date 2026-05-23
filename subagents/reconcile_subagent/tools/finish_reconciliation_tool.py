def finish_reconciliation_tool(result: dict, status: str = "SUCCESS", reason: str = "") -> dict:
    """
    Signal that reconciliation is complete. Always the agent's final action.
    status: SUCCESS | HALTED | ERROR
    """
    return {
        "finished": True,
        "status":   status,
        "reason":   reason,
        "result":   result,
    }

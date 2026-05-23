def finish_migration_tool(pipeline: str, outcome: str, summary: str) -> dict:
    """
    Signal that the migration workflow is complete. Always the supervisor's final action.
    outcome: SUCCESS | PARTIAL | HALTED | FAILED
    summary: one or two sentences — what happened and why.
    """
    return {
        "finished": True,
        "pipeline": pipeline,
        "outcome":  outcome,
        "summary":  summary,
    }

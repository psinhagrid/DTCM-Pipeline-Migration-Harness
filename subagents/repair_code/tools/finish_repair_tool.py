def finish_repair_tool(
    files_fixed: list[str],
    issues_skipped: list[str],
    status: str = "SUCCESS",
    reason: str = "",
) -> dict:
    """
    Signal that repair is complete.
    status: SUCCESS | PARTIAL | HALTED
    """
    return {
        "finished":       True,
        "status":         status,
        "reason":         reason,
        "files_fixed":    files_fixed,
        "issues_skipped": issues_skipped,
        "fix_count":      len(files_fixed),
    }

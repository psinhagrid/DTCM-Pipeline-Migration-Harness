from agents.reconcile_agent.tools_impl.utils.static_analyzer import check_workflow_parity

def workflow_parity_tool(conversion: dict) -> dict:
    """
    Check that the generated DAG matches the conversion file structure.
    Returns status (PASSED/WARNING/FAILED) and detail string.
    """
    return check_workflow_parity(conversion)

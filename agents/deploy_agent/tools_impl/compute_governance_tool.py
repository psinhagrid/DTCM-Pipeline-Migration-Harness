from agents.deploy_agent.tools_impl.utils.governance import compute_readiness_score, compute_governance

def compute_governance_tool(
    artifact_checks: dict,
    smoke_results:   dict,
    reconcile:       dict,
) -> dict:
    """
    Compute deployment readiness score and governance approval state.
    Returns readiness_score (int 0-100) and governance dict with state, label, conditions.
    """
    readiness  = compute_readiness_score(artifact_checks, smoke_results, reconcile)
    governance = compute_governance(readiness, reconcile, smoke_results, artifact_checks)
    return {
        "readiness_score": readiness,
        "governance":      governance,
    }

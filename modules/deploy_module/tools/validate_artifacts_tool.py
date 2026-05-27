from ..utils.artifact_validator import validate_artifacts

def validate_artifacts_tool(conversion: dict, reconcile: dict) -> dict:
    """
    Validate all generated migration artifacts.
    Returns file_checks, dag_check, reconciliation_check, deployment_ready flag.
    """
    return validate_artifacts(conversion, reconcile)

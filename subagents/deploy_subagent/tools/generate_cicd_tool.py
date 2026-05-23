from ..utils.cicd_generator import generate_deployment_yaml, generate_pipeline_config

def generate_cicd_tool(pipeline: str, files: list[str], assessment: dict, reconcile: dict) -> dict:
    """
    Generate CI/CD YAML and pipeline config for the deployment.
    files: list of python_filename values from conversion result.
    Returns cicd_yaml (string) and pipeline_config (dict).
    """
    cicd_yaml    = generate_deployment_yaml(pipeline, files, assessment)
    pipeline_cfg = generate_pipeline_config(pipeline, assessment, reconcile)
    return {
        "cicd_yaml":     cicd_yaml,
        "pipeline_config": pipeline_cfg,
    }

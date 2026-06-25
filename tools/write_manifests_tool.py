from .utils.manifest_builder import write_all

def write_manifests_tool(
    pipeline:       str,
    assessment:     dict,
    conversion:     dict,
    reconcile:      dict,
    artifact_checks: dict,
    smoke_results:  dict,
    governance:     dict,
    cicd_yaml:      str,
) -> dict:
    """
    Write all deployment manifests to disk under output/{pipeline}/.
    Returns output_dir and list of files_written.
    """
    return write_all(
        pipeline, assessment, conversion, reconcile,
        artifact_checks, smoke_results, governance, cicd_yaml
    )

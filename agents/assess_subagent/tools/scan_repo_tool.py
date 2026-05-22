from pathlib import Path


def scan_repo_tool(pipeline_dir: Path) -> dict:
    """
    Discover all source files in a pipeline directory.
    Returns hql_files, config_files, and total_files count.
    """
    hql_files    = sorted(pipeline_dir.glob("*.hql"))
    config_files = sorted(pipeline_dir.glob("*.xml")) + sorted(pipeline_dir.glob("*.properties"))
    total_files  = len(list(pipeline_dir.rglob("*")))
    return {
        "hql_files":    hql_files,
        "config_files": config_files,
        "total_files":  total_files,
    }

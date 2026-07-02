from pathlib import Path

PIPELINES_ROOT = Path(__file__).parents[1] / "pipelines"

def list_hql_files_tool(pipeline_name: str) -> dict:
    """
    Discover all .hql source files for a pipeline.
    Returns filenames (not full paths) — pass these to transform_hql_tool.
    """
    pipeline_dir = PIPELINES_ROOT / pipeline_name
    if not pipeline_dir.exists():
        return {"error": f"Pipeline directory not found: {pipeline_dir}"}
    files = sorted(f.name for f in pipeline_dir.glob("*.hql"))
    return {"files": files, "count": len(files)}

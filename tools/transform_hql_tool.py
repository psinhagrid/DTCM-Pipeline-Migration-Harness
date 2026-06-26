from pathlib import Path
from .utils.conversion_engine import transform_file

PIPELINES_ROOT = Path(__file__).parents[1] / "pipelines"

def transform_hql_tool(filename: str, pipeline: str, metadata: dict) -> dict:
    """
    Convert a single HiveQL file to PySpark via Claude Sonnet.
    Reads the source file, runs LLM conversion, returns structured result.
    """
    path = PIPELINES_ROOT / pipeline / filename
    if not path.exists():
        return {"error": f"File not found: {path}"}
    hql_content = path.read_text(encoding="utf-8")
    return transform_file(filename, hql_content, pipeline, metadata)

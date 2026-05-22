from pathlib import Path
from ..conversion_engine import transform_file

PIPELINES_ROOT = Path(__file__).parents[3] / "pipelines"

def transform_hql_tool(filename: str, pipeline_name: str, metadata: dict) -> dict:
    """
    Convert a single HiveQL file to PySpark via Llama 3.2 (Ollama).
    Reads the source file, runs LLM conversion, returns structured result.
    """
    path = PIPELINES_ROOT / pipeline_name / filename
    if not path.exists():
        return {"error": f"File not found: {path}"}
    hql_content = path.read_text(encoding="utf-8")
    return transform_file(filename, hql_content, pipeline_name, metadata)

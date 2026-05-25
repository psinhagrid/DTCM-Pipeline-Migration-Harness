from pathlib import Path

PIPELINES_ROOT = Path(__file__).parents[3] / "pipelines"
OUTPUT_ROOT    = Path(__file__).parents[3] / "output"


def list_files_tool(pipeline: str, target: str = "hql") -> dict:
    """
    List source files available for repair.
    target: 'hql' → lists .hql files from pipelines/
            'pyspark' → lists .py files from output/
    """
    if target == "hql":
        base = PIPELINES_ROOT / pipeline
        files = sorted(f.name for f in base.glob("*.hql")) if base.exists() else []
        root  = str(base)
    else:
        base  = OUTPUT_ROOT / pipeline
        files = sorted(f.name for f in base.glob("*.py")) if base.exists() else []
        root  = str(base)

    return {"pipeline": pipeline, "target": target, "root": root, "files": files}

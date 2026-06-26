from .utils.conversion_engine import generate_dag

def generate_dag_tool(pipeline: str, files: list[str], complexity: str) -> dict:
    """
    Generate an MWAA Airflow DAG from the list of converted PySpark files.
    complexity affects retry count: SMALL=1, MEDIUM=2, LARGE/COMPLEX=3.
    """
    metadata = {"complexity": complexity}
    dag_content  = generate_dag(pipeline, files, metadata)
    dag_filename = f"{pipeline}_dag.py"
    return {
        "dag_content":  dag_content,
        "dag_filename": dag_filename,
    }

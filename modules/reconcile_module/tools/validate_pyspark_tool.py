from ..utils.pyspark_validator import validate_pyspark


def validate_pyspark_tool(filename: str, spark_python: str, source_hql: str = "") -> dict:
    """
    Static validation of a generated PySpark file.

    Checks:
      1. Python syntax (ast.parse)
      2. SparkSession import
      3. functions as F import
      4. SparkSession.builder initialisation
      5. Write operation (.writeTo / .append)
      6. hiveconf variable parity (${hiveconf:var} → spark.conf.get())
      7. UDF reference presence
      8. Non-empty output (catches silent LLM failures)

    Returns: valid (bool), checks (dict), errors (list), warnings (list).
    """
    return validate_pyspark(filename, spark_python, source_hql)

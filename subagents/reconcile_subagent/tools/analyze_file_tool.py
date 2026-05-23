import asyncio
from ..utils.static_analyzer import analyze_hiveql, analyze_pyspark, compare

def analyze_file_tool(filename: str, hql_src: str, pyspark_src: str) -> dict:
    """
    Run full semantic comparison for one HiveQL↔PySpark file pair.
    Returns per-dimension check results, overall_similarity, and issues list.
    Skip if source or target is empty.
    """
    if not hql_src.strip() or not pyspark_src.strip():
        return {"skipped": True, "reason": "empty source or target"}
    hive_qs  = analyze_hiveql(hql_src)
    spark_qs = analyze_pyspark(pyspark_src)
    return compare(hive_qs, spark_qs)

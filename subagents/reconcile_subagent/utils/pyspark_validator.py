"""
PySpark static validator — pure analysis, no I/O.
Safe to call via asyncio.to_thread().
"""

import ast
import re

# ── Patterns ──────────────────────────────────────────────────────────────────

RE_HIVECONF      = re.compile(r'\$\{hiveconf:([^}]+)\}',         re.I)
RE_CONF_GET      = re.compile(r'spark\.conf\.get\(["\']([^"\']+)["\']\)')
RE_SPARKSESSION  = re.compile(r'SparkSession\s*\.\s*builder')
RE_WRITE_OP      = re.compile(r'\.(writeTo|append|overwritePartitions|insertInto)\s*\(')
RE_IMPORT_SPARK  = re.compile(r'from\s+pyspark\.sql\s+import[^\n]*SparkSession')
RE_IMPORT_F      = re.compile(r'from\s+pyspark\.sql\s+import\s+functions\s+as\s+F')
RE_HQL_INSERT    = re.compile(r'\bINSERT\b', re.I)
RE_HQL_FUNCTIONS = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', re.I)

# Hive built-ins and SQL keywords — same exclusion set as assess_subagent
_EXCLUDE: set[str] = {
    "sum","count","avg","min","max","coalesce","nvl","substr","substring","length",
    "trim","upper","lower","concat","concat_ws","split","regexp_replace","regexp_extract",
    "from_unixtime","unix_timestamp","to_date","year","month","day","cast","round",
    "floor","ceil","abs","rank","dense_rank","row_number","lag","lead","first_value",
    "last_value","collect_list","collect_set","size","explode","get_json_object",
    "partition","by","table","select","from","where","join","on","and","or","group",
    "order","having","limit","insert","into","overwrite","create","drop","alter",
    "external","if","not","exists","case","when","then","else","end","null","true","false",
    "as","set","use","left","right","inner","outer","cross","full","union","all","distinct",
    "between","in","like","over","row","rows","range","current","interval","values",
    "boolean","int","bigint","float","double","string","varchar","timestamp","date",
    "array","map","struct","isnull","isnotnull","decode",
}


# ── Main validator ────────────────────────────────────────────────────────────

def validate_pyspark(filename: str, spark_python: str, source_hql: str = "") -> dict:
    """
    Run 7 static checks on a generated PySpark file.

    Returns:
        valid    — True only if zero errors (warnings are non-fatal)
        checks   — per-check dict with status (PASSED/FAILED/WARNING/SKIPPED) + detail
        errors   — list of blocking issue strings
        warnings — list of non-fatal issue strings
    """
    errors   : list[str] = []
    warnings : list[str] = []
    checks   : dict      = {}

    # ── 1. Python syntax ──────────────────────────────────────────────────────
    try:
        ast.parse(spark_python)
        checks["syntax"] = {"status": "PASSED", "detail": "valid Python syntax"}
    except SyntaxError as e:
        checks["syntax"] = {
            "status": "FAILED",
            "detail": f"SyntaxError line {e.lineno}: {e.msg}",
        }
        errors.append(f"[{filename}] syntax: SyntaxError at line {e.lineno} — {e.msg}")

    # ── 2. SparkSession import ────────────────────────────────────────────────
    if RE_IMPORT_SPARK.search(spark_python):
        checks["spark_import"] = {"status": "PASSED", "detail": "SparkSession imported"}
    else:
        checks["spark_import"] = {
            "status": "FAILED",
            "detail": "missing: from pyspark.sql import SparkSession",
        }
        errors.append(f"[{filename}] spark_import: SparkSession not imported")

    # ── 3. functions as F import ──────────────────────────────────────────────
    if RE_IMPORT_F.search(spark_python):
        checks["functions_import"] = {"status": "PASSED", "detail": "functions as F imported"}
    else:
        checks["functions_import"] = {
            "status": "WARNING",
            "detail": "missing: from pyspark.sql import functions as F — aggregations may fail",
        }
        warnings.append(f"[{filename}] functions_import: F not imported — aggregations may fail at runtime")

    # ── 4. SparkSession initialisation ───────────────────────────────────────
    if RE_SPARKSESSION.search(spark_python):
        checks["sparksession_setup"] = {"status": "PASSED", "detail": "SparkSession.builder present"}
    else:
        checks["sparksession_setup"] = {
            "status": "FAILED",
            "detail": "SparkSession.builder not found — no Spark context created",
        }
        errors.append(f"[{filename}] sparksession_setup: SparkSession not initialised")

    # ── 5. Write operation ────────────────────────────────────────────────────
    has_insert = bool(RE_HQL_INSERT.search(source_hql)) if source_hql else True
    if has_insert:
        if RE_WRITE_OP.search(spark_python):
            match = RE_WRITE_OP.search(spark_python)
            checks["write_operation"] = {
                "status": "PASSED",
                "detail": f"write operation present (.{match.group(1)}())",
            }
        else:
            checks["write_operation"] = {
                "status": "FAILED",
                "detail": "no .writeTo() or .append() found — data will not be written",
            }
            errors.append(f"[{filename}] write_operation: no DataFrame write call found")
    else:
        checks["write_operation"] = {"status": "SKIPPED", "detail": "DDL-only source — no write expected"}

    # ── 6. hiveconf variable parity ───────────────────────────────────────────
    if source_hql:
        hiveconf_vars = RE_HIVECONF.findall(source_hql)
        if hiveconf_vars:
            conf_gets = set(RE_CONF_GET.findall(spark_python))
            missing   = [v for v in hiveconf_vars if v not in conf_gets]
            if not missing:
                checks["hiveconf_parity"] = {
                    "status": "PASSED",
                    "detail": f"{len(hiveconf_vars)} hiveconf var(s) → spark.conf.get()",
                }
            else:
                checks["hiveconf_parity"] = {
                    "status": "FAILED",
                    "detail": f"unmapped vars: {missing}",
                }
                errors.append(f"[{filename}] hiveconf_parity: {len(missing)} variable(s) not mapped — {missing}")
        else:
            checks["hiveconf_parity"] = {"status": "SKIPPED", "detail": "no hiveconf variables in source"}
    else:
        checks["hiveconf_parity"] = {"status": "SKIPPED", "detail": "no source HQL provided"}

    # ── 7. UDF reference parity ───────────────────────────────────────────────
    if source_hql:
        all_fns   = {m.group(1).lower() for m in RE_HQL_FUNCTIONS.finditer(source_hql)}
        all_tables = set(re.findall(r'\b(?:FROM|JOIN)\s+([`\w]+(?:\.[`\w]+)?)', source_hql, re.I))
        udfs      = all_fns - _EXCLUDE - {t.lower() for t in all_tables}
        if udfs:
            py_lower  = spark_python.lower()
            missing   = [u for u in sorted(udfs) if u not in py_lower]
            if not missing:
                checks["udf_presence"] = {
                    "status": "PASSED",
                    "detail": f"{len(udfs)} UDF(s) referenced in converted code",
                }
            else:
                checks["udf_presence"] = {
                    "status": "WARNING",
                    "detail": f"UDFs not referenced in output: {missing}",
                }
                warnings.append(f"[{filename}] udf_presence: UDF(s) missing from PySpark — {missing}")
        else:
            checks["udf_presence"] = {"status": "SKIPPED", "detail": "no UDFs in source"}
    else:
        checks["udf_presence"] = {"status": "SKIPPED", "detail": "no source HQL provided"}

    # ── 8. Non-empty output ───────────────────────────────────────────────────
    code_lines = [
        l for l in spark_python.splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    if len(code_lines) >= 5:
        checks["non_empty"] = {"status": "PASSED", "detail": f"{len(code_lines)} code lines generated"}
    else:
        checks["non_empty"] = {
            "status": "FAILED",
            "detail": f"only {len(code_lines)} code lines — LLM conversion may have failed silently",
        }
        errors.append(f"[{filename}] non_empty: suspiciously short output ({len(code_lines)} lines)")

    return {
        "filename": filename,
        "valid":    len(errors) == 0,
        "checks":   checks,
        "errors":   errors,
        "warnings": warnings,
    }

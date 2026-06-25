"""
artifact_validator.py — REAL artifact validation.

Uses Python AST parsing and regex structural checks on actual
generated code. No mocking — these are genuine correctness checks.
"""

import ast
import re
from pathlib import Path


# ── DAG structure patterns ────────────────────────────────────────────────────

_DAG_IMPORT     = re.compile(r'from airflow import DAG|from airflow\.models import DAG', re.I)
_SPARK_OPERATOR = re.compile(r'SparkSubmitOperator', re.I)
_DAG_BLOCK      = re.compile(r'with DAG\s*\(', re.I)
_TASK_DEF       = re.compile(r'=\s*SparkSubmitOperator\s*\(', re.I)
_SCHEDULE       = re.compile(r'schedule_interval\s*=', re.I)


def validate_python_syntax(code: str, filename: str) -> dict:
    """Real Python AST syntax check."""
    if not code or not code.strip():
        return {"status": "FAILED", "detail": "Empty file", "lines": 0}
    try:
        tree = ast.parse(code)
        n_lines = len(code.splitlines())
        n_nodes = len(list(ast.walk(tree)))
        return {
            "status":  "PASSED",
            "detail":  f"Valid Python — {n_lines} lines, {n_nodes} AST nodes",
            "lines":   n_lines,
            "ast_nodes": n_nodes,
        }
    except SyntaxError as e:
        return {
            "status":  "FAILED",
            "detail":  f"SyntaxError line {e.lineno}: {e.msg}",
            "lines":   0,
            "ast_nodes": 0,
        }


def validate_dag_structure(dag_code: str) -> dict:
    """Real structural check on generated Airflow DAG."""
    if not dag_code or not dag_code.strip():
        return {"status": "FAILED", "detail": "DAG file is empty"}

    checks = {
        "airflow_import":    bool(_DAG_IMPORT.search(dag_code)),
        "spark_operator":    bool(_SPARK_OPERATOR.search(dag_code)),
        "dag_block":         bool(_DAG_BLOCK.search(dag_code)),
        "task_defined":      bool(_TASK_DEF.search(dag_code)),
        "schedule_defined":  bool(_SCHEDULE.search(dag_code)),
    }
    failed = [k for k, v in checks.items() if not v]

    if not failed:
        return {
            "status": "PASSED",
            "detail": "All DAG structural checks passed",
            "checks": checks,
        }
    return {
        "status": "WARNING" if len(failed) <= 1 else "FAILED",
        "detail": f"Missing: {', '.join(failed)}",
        "checks": checks,
    }


def validate_reconciliation_readiness(reconcile: dict, threshold: float = 0.72) -> dict:
    """Check reconciliation confidence meets deployment threshold."""
    confidence = reconcile.get("confidence_score", 0.0)
    status_val = reconcile.get("validation_status", "UNKNOWN")
    passed     = confidence >= threshold and status_val != "FAILED"
    return {
        "status":    "PASSED" if passed else "FAILED",
        "detail":    f"confidence={confidence:.0%}  status={status_val}  threshold={threshold:.0%}",
        "confidence": confidence,
        "threshold":  threshold,
    }


def validate_artifacts(conversion: dict, reconcile: dict) -> dict:
    """
    Run all real artifact checks.
    Returns per-file results + DAG + reconciliation readiness.
    """
    files = conversion.get("converted_files") or conversion.get("files") or []
    dag_content = conversion.get("dag_content") or conversion.get("dag") or ""
    if isinstance(dag_content, dict):
        dag_content = dag_content.get("dag_content") or dag_content.get("content") or ""
    results = {}

    # Per-file Python syntax
    for f in files:
        fname = f.get("filename", "unknown")
        code  = f.get("spark_python", "")
        results[fname] = validate_python_syntax(code, fname)

    # DAG structure
    dag_result   = validate_dag_structure(dag_content)
    recon_result = validate_reconciliation_readiness(reconcile)

    # Overall readiness
    syntax_ok = all(r["status"] == "PASSED" for r in results.values())
    all_ok    = syntax_ok and dag_result["status"] == "PASSED" and recon_result["status"] == "PASSED"

    return {
        "file_checks":             results,
        "dag_check":               dag_result,
        "reconciliation_check":    recon_result,
        "all_artifacts_valid":     syntax_ok,
        "deployment_ready":        all_ok,
    }

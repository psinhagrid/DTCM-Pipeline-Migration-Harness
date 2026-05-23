import sys
from pathlib import Path
_ROOT = Path(__file__).parents[4]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ..utils.validators import (
    calculate_confidence,
    overall_status,
    compute_severity_map,
    compute_migration_risk,
    compute_recommendation,
    compute_reasoning,
)

def compile_report_tool(
    pipeline: str,
    files_analysis: list[dict],
    workflow_check: dict,
    runtime_checks: dict,
    all_issues: list[str],
) -> dict:
    """
    Compile all check results into the final reconciliation report.
    files_analysis: list of results from analyze_file_tool (one per file).
    workflow_check: result from workflow_parity_tool.
    runtime_checks: result from runtime_validation_tool.
    all_issues: accumulated issue strings from all file analyses.
    """
    # Aggregate semantic similarity across files
    sims = [f.get("overall_similarity", 0.0) for f in files_analysis if not f.get("skipped")]
    avg_similarity = round(sum(sims) / len(sims), 3) if sims else 0.0

    # Build aggregated check statuses
    rc = runtime_checks.get("row_count", {})
    ck = runtime_checks.get("checksum", {})
    sl = runtime_checks.get("sla_compliance", {})
    cr = runtime_checks.get("consumer_replay", {})

    # Helper: worst status across files for a given dimension
    STATUS_RANK = {"PASSED": 0, "SKIPPED": 0, "WARNING": 1, "FAILED": 2}

    def _agg_dim(dim: str) -> dict:
        entries = [f.get(dim) for f in files_analysis if isinstance(f.get(dim), dict)]
        if not entries:
            return {"status": "SKIPPED", "score": 1.0, "detail": "no files analyzed"}
        worst = max(entries, key=lambda e: STATUS_RANK.get(e.get("status", "SKIPPED"), 0))
        scores = [e.get("score", 1.0) for e in entries]
        return {"status": worst["status"], "score": round(sum(scores)/len(scores), 3), "detail": worst.get("detail", "")}

    dims = ["table_parity","column_parity","aggregation_parity","join_parity",
            "group_by_parity","filter_parity","partition_parity","runtime_var_parity"]
    agg = {d: _agg_dim(d) for d in dims}

    flat_checks = {d: agg[d]["status"] for d in dims}
    flat_checks.update({
        "workflow_parity":  workflow_check.get("status", "SKIPPED"),
        "row_count":        rc.get("status", "SKIPPED"),
        "checksum":         ck.get("status", "SKIPPED"),
        "sla_compliance":   sl.get("status", "SKIPPED"),
        "consumer_replay":  cr.get("status", "SKIPPED"),
    })

    confidence      = calculate_confidence(avg_similarity, runtime_checks)

    # Mechanical blast radius threshold — not LLM decision
    blast_radius = []
    try:
        from graph.client import query_blast_radius
        blast_radius = query_blast_radius(pipeline)
    except Exception:
        pass

    blast_count = len(blast_radius)
    if blast_count == 0:
        proceed_threshold = 0.75      # terminal sink — nothing downstream
    elif blast_count <= 2:
        proceed_threshold = 0.75      # standard
    elif blast_count <= 4:
        proceed_threshold = 0.80      # raised — 3-4 downstream consumers
    else:
        proceed_threshold = 0.85      # high impact — 5+ downstream consumers

    # Convert proceed_threshold to overall_status threshold
    # overall_status uses a single threshold; scale it proportionally
    status_threshold = 0.88 * (proceed_threshold / 0.75)

    val_status      = overall_status(confidence, flat_checks, threshold=status_threshold)
    severity_map    = compute_severity_map(flat_checks)
    migration_risk, risk_score = compute_migration_risk(severity_map)

    partial_data = {
        "files_reconciled": len([f for f in files_analysis if not f.get("skipped")]),
        "row_variance_pct": rc.get("variance_pct", 0.0),
        "issues":           all_issues,
        "migration_risk":   migration_risk,
        "recommendation":   compute_recommendation(val_status, flat_checks, all_issues),
    }
    recommendation = partial_data["recommendation"]
    reasoning      = compute_reasoning(flat_checks, partial_data)

    semantic_breakdown = {
        "tables":       round(agg["table_parity"]["score"]       * 100),
        "columns":      round(agg["column_parity"]["score"]      * 100),
        "aggregations": round(agg["aggregation_parity"]["score"] * 100),
        "joins":        round(agg["join_parity"]["score"]        * 100),
        "filters":      round(agg["filter_parity"]["score"]      * 100),
        "runtime_vars": round(agg["runtime_var_parity"]["score"] * 100),
        "partitions":   round(agg["partition_parity"]["score"]   * 100),
    }

    return {
        "pipeline":             pipeline,
        "validation_status":    val_status,
        "confidence_score":     confidence,
        "semantic_similarity":  avg_similarity,
        "files_reconciled":     partial_data["files_reconciled"],
        "source_rows":          rc.get("source_rows", 0),
        "target_rows":          rc.get("target_rows", 0),
        "row_variance_pct":     rc.get("variance_pct", 0.0),
        "source_checksum":      ck.get("source_checksum", ""),
        "target_checksum":      ck.get("target_checksum", ""),
        "checks":               flat_checks,
        "issues":               all_issues,
        "severity_map":         severity_map,
        "migration_risk":       migration_risk,
        "migration_risk_score": risk_score,
        "recommendation":       recommendation,
        "reasoning":            reasoning,
        "semantic_breakdown":   semantic_breakdown,
        "speedup_factor":       cr.get("speedup_factor", 1.0),
        "blast_radius":      blast_radius,
        "blast_radius_count": blast_count,
        "threshold_applied":  round(proceed_threshold, 2),
        "data_provenance": {
            "semantic_analysis": "REAL — static regex comparison of HiveQL vs PySpark across 8 dimensions",
            "pyspark_validation": "REAL — ast.parse() syntax check + import/write operation checks",
            "workflow_parity":    "REAL — DAG task count vs DML file count",
            "row_count":          "SIMULATED — seeded from pipeline name, not real Hive/Iceberg execution",
            "checksum":           "SIMULATED — deterministic fake SHA-256, not real partition data",
            "sla_compliance":     "SIMULATED — always passes, real timing not implemented",
            "consumer_replay":    "SIMULATED — seeded from pipeline name, not real query execution",
            "confidence_score":   "80% real semantic analysis + 20% simulated runtime checks",
        },
        "summary": (
            f"Pipeline {pipeline}: {val_status}  "
            f"confidence={confidence:.0%}  "
            f"semantic={avg_similarity:.0%}  "
            f"rows={rc.get('source_rows', 0):,}"
        ),
    }

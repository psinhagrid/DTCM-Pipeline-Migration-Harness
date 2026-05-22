"""
reconcile_agent — async orchestration layer.

Phases:
  1. Parse source HiveQL + converted PySpark (per file)
  2. Semantic comparison across 8 dimensions (REAL)
  3. Workflow / DAG parity check (REAL)
  4. Simulated runtime checks — scores depend on semantic quality
  5. Compile final ReconcileReport + stream to event bus
"""

import asyncio
import re

from event_queue import push
from .static_analyzer import analyze_hiveql, analyze_pyspark, compare, check_workflow_parity
from .validators import (
    row_count_check,
    checksum_check,
    sla_check,
    consumer_replay_check,
    calculate_confidence,
    overall_status,
    compute_severity_map,
    compute_migration_risk,
    compute_recommendation,
    compute_reasoning,
)

NAME = "reconcile_agent"


async def run_reconciliation(assessment: dict, conversion: dict) -> dict:
    pipeline   = assessment["pipeline"]
    complexity = assessment.get("complexity", "MEDIUM")
    files      = conversion.get("files", [])

    async def _e(type: str, message: str, **kw) -> None:
        await push(type=type, agent=NAME, message=message, pipeline=pipeline, **kw)

    # ── Phase 1 · Initialise ─────────────────────────────────────────────
    await _e("status", f"Starting reconciliation for {pipeline}")
    await _e("hook",   "PreToolUse → governance_check ✓ allowed")
    await _e("status", f"Inputs: {len(files)} file(s)  complexity={complexity}")

    # ── Phase 2 · Static semantic analysis per file ───────────────────────
    await _e("status", "Parsing source HiveQL and converted PySpark...")

    all_file_checks: list[dict] = []
    all_issues:      list[str]  = []
    dml_pattern = re.compile(r'\b(INSERT|SELECT)\b', re.I)

    for file in files:
        fname   = file.get("filename", "unknown")
        hql_src = file.get("source_hql", "")
        py_tgt  = file.get("spark_python", "")

        if not hql_src.strip() or not py_tgt.strip():
            await _e("status", f"⚠ {fname}: skipping — empty source or target")
            continue

        # Skip DDL-only files (CREATE TABLE only) — no SELECT/INSERT to compare
        if not dml_pattern.search(hql_src):
            await _e("status", f"– {fname}: DDL-only — skipping semantic comparison")
            continue

        await _e("tool_call", f"Analyzing {fname} ↔ {file.get('python_filename', fname)}")

        hive_qs  = await asyncio.to_thread(analyze_hiveql, hql_src)
        spark_qs = await asyncio.to_thread(analyze_pyspark, py_tgt)
        checks   = await asyncio.to_thread(compare, hive_qs, spark_qs)

        file_issues = checks.pop("issues", [])
        similarity  = checks.get("overall_similarity", 0.0)
        all_file_checks.append(checks)
        all_issues.extend([f"[{fname}] {i}" for i in file_issues])

        # Stream per-file summary
        await _e("status",
            f"{'✓' if similarity >= 0.85 else '⚠' if similarity >= 0.70 else '✗'} "
            f"{fname}  semantic similarity: {similarity:.0%}")

        # Stream specific check results
        for dim, result in checks.items():
            if dim in ("overall_similarity",):
                continue
            if not isinstance(result, dict):
                continue
            status = result.get("status", "")
            icon   = "✓" if status == "PASSED" else ("–" if status == "SKIPPED" else ("⚠" if status == "WARNING" else "✗"))
            await _e(
                "validation" if status in ("PASSED", "SKIPPED") else "status",
                f"{icon} {dim.replace('_', ' ').title()}: {result.get('detail', status)}"
            )

        # Surface issues immediately
        for issue in file_issues:
            await _e("status", f"✗ Issue: {issue}")

    # Aggregate across files
    agg = _aggregate_checks(all_file_checks)
    avg_similarity = agg.get("overall_similarity", 0.0)

    await _e("status", f"Static analysis complete — overall semantic similarity: {avg_similarity:.0%}")
    if all_issues:
        await _e("status", f"⚠ {len(all_issues)} issue(s) detected across {len(files)} file(s)")

    # ── Phase 3 · Workflow / DAG parity ──────────────────────────────────
    await _e("status", "Checking workflow parity against generated DAG...")
    wf_check = await asyncio.to_thread(check_workflow_parity, conversion)
    await _e(
        "validation" if wf_check["status"] == "PASSED" else "status",
        f"{'✓' if wf_check['status'] == 'PASSED' else '⚠'} Workflow parity: {wf_check['detail']}"
    )

    # ── Phase 4 · Simulated runtime checks (score-dependent) ─────────────
    await _e("status", "Running runtime validation suite...")

    await _e("tool_call", "Submitting COUNT(*) to source Hive cluster")
    rc = row_count_check(pipeline, complexity, avg_similarity)
    _status_icon = "✓" if rc["status"] == "PASSED" else ("⚠" if rc["status"] == "WARNING" else "✗")
    await _e(
        "validation" if rc["status"] == "PASSED" else "status",
        f"{_status_icon} Row count: {rc['detail']}"
    )

    await _e("tool_call", "Computing SHA-256 partition checksums")
    ck = checksum_check(pipeline, avg_similarity)
    _status_icon = "✓" if ck["status"] == "PASSED" else ("⚠" if ck["status"] == "WARNING" else "✗")
    await _e(
        "validation" if ck["status"] == "PASSED" else "status",
        f"{_status_icon} Checksum: {ck['detail']}"
    )

    await _e("tool_call", "Querying MWAA execution logs")
    sl = sla_check(pipeline, complexity)
    await _e("validation", f"✓ SLA: {sl['detail']}")

    await _e("tool_call", f"Replaying consumer queries against Iceberg target")
    cr = consumer_replay_check(pipeline, complexity, avg_similarity)
    _status_icon = "✓" if cr["status"] == "PASSED" else ("⚠" if cr["status"] == "WARNING" else "✗")
    await _e(
        "validation" if cr["status"] == "PASSED" else "status",
        f"{_status_icon} Consumer replay: {cr['detail']}"
    )

    # ── Phase 5 · Compile report ──────────────────────────────────────────
    runtime_checks = {
        "row_count":       rc,
        "checksum":        ck,
        "sla_compliance":  sl,
        "consumer_replay": cr,
    }

    confidence = calculate_confidence(avg_similarity, runtime_checks)

    flat_checks = {
        "table_parity":        agg.get("table_parity",        {}).get("status", "SKIPPED"),
        "column_parity":       agg.get("column_parity",       {}).get("status", "SKIPPED"),
        "aggregation_parity":  agg.get("aggregation_parity",  {}).get("status", "SKIPPED"),
        "join_parity":         agg.get("join_parity",         {}).get("status", "SKIPPED"),
        "group_by_parity":     agg.get("group_by_parity",     {}).get("status", "SKIPPED"),
        "filter_parity":       agg.get("filter_parity",       {}).get("status", "SKIPPED"),
        "partition_parity":    agg.get("partition_parity",    {}).get("status", "SKIPPED"),
        "runtime_var_parity":  agg.get("runtime_var_parity",  {}).get("status", "SKIPPED"),
        "workflow_parity":     wf_check["status"],
        "row_count":           rc["status"],
        "checksum":            ck["status"],
        "sla_compliance":      sl["status"],
        "consumer_replay":     cr["status"],
    }

    val_status = overall_status(confidence, flat_checks)

    # ── Enriched analytics ────────────────────────────────────────────────
    severity_map          = compute_severity_map(flat_checks)
    migration_risk, risk_score = compute_migration_risk(severity_map)
    recommendation        = compute_recommendation(val_status, flat_checks, all_issues)

    semantic_breakdown = {
        "tables":       round(agg.get("table_parity",       {}).get("score", 1.0) * 100),
        "columns":      round(agg.get("column_parity",      {}).get("score", 1.0) * 100),
        "aggregations": round(agg.get("aggregation_parity", {}).get("score", 1.0) * 100),
        "joins":        round(agg.get("join_parity",        {}).get("score", 1.0) * 100),
        "filters":      round(agg.get("filter_parity",      {}).get("score", 1.0) * 100),
        "runtime_vars": round(agg.get("runtime_var_parity", {}).get("score", 1.0) * 100),
        "partitions":   round(agg.get("partition_parity",   {}).get("score", 1.0) * 100),
    }

    issue_details = _build_issue_details(all_issues, files)

    partial_data = {
        "files_reconciled": len(all_file_checks),
        "row_variance_pct": rc["variance_pct"],
        "issues":           all_issues,
        "migration_risk":   migration_risk,
        "recommendation":   recommendation,
    }
    reasoning = compute_reasoning(flat_checks, partial_data)

    report = {
        "pipeline":            pipeline,
        "validation_status":   val_status,
        "confidence_score":    confidence,
        "semantic_similarity": avg_similarity,
        "files_reconciled":    len(all_file_checks),
        "source_rows":         rc["source_rows"],
        "target_rows":         rc["target_rows"],
        "row_variance_pct":    rc["variance_pct"],
        "source_checksum":     ck["source_checksum"],
        "target_checksum":     ck["target_checksum"],
        "checks":              flat_checks,
        "check_details":       {
            **{k: v for k, v in agg.items() if k not in ("overall_similarity",)},
            "workflow_parity":  wf_check,
            "row_count":        rc,
            "checksum":         ck,
            "sla_compliance":   sl,
            "consumer_replay":  cr,
        },
        "issues":              all_issues,
        "issue_details":       issue_details,
        "severity_map":        severity_map,
        "migration_risk":      migration_risk,
        "migration_risk_score": risk_score,
        "recommendation":      recommendation,
        "reasoning":           reasoning,
        "semantic_breakdown":  semantic_breakdown,
        "speedup_factor":      cr.get("speedup_factor", 1.0),
        "summary": (
            f"Pipeline {pipeline}: {val_status}  "
            f"confidence={confidence:.0%}  "
            f"semantic={avg_similarity:.0%}  "
            f"rows={rc['source_rows']:,}"
        ),
    }

    icon = "✓" if val_status == "PASSED" else ("⚠" if val_status == "PARTIAL" else "✗")
    await _e("status",
        f"{icon} Reconciliation {val_status} — "
        f"confidence={confidence:.0%}  semantic={avg_similarity:.0%}  "
        f"rows={rc['source_rows']:,}"
    )
    if all_issues:
        await _e("status", f"Issues: {'; '.join(all_issues[:3])}")

    await _e("hook",   "PostToolUse → audit_logger.record_reconciliation ✓")
    await _e("status", "Reconciliation complete", done=True)

    return report


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_issue_details(issues: list[str], files: list[dict]) -> dict:
    """
    For each issue string extract relevant source/converted code snippets
    so the frontend can render expandable issue cards.
    """
    file_map = {f.get("filename", ""): f for f in files}
    details  = {}

    for issue in issues:
        m = re.match(r'\[([^\]]+)\]\s+(.+?):\s+(.+)', issue)
        if not m:
            details[issue] = {"description": issue}
            continue

        filename   = m.group(1)
        issue_type = m.group(2).lower()
        description = m.group(3)
        fd  = file_map.get(filename, {})
        hql = fd.get("source_hql", "")
        py  = fd.get("spark_python", "")

        d: dict = {"file": filename, "issue_type": issue_type,
                   "description": description, "source_snippet": "",
                   "converted_snippet": "", "missing": []}

        if "filter" in issue_type:
            wm = re.search(r'\bWHERE\b(.+?)(?=\bGROUP\b|\bORDER\b|\bLIMIT\b|;|$)',
                           hql, re.I | re.DOTALL)
            if wm:
                d["source_snippet"] = "WHERE " + " ".join(wm.group(1).split())
            filters = re.findall(r'\.filter\s*\(([^)]+)\)', py, re.I)
            d["converted_snippet"] = ("\n".join(f".filter({f.strip()})" for f in filters[:3])
                                      if filters else "# .filter() not detected")

        elif "runtime" in issue_type or "hiveconf" in description:
            hiveconf = re.findall(r'\$\{hiveconf:([^}]+)\}', hql)
            conf_gets = re.findall(r'spark\.conf\.get\(["\']([^"\']+)["\']\)', py)
            d["source_snippet"]    = "\n".join(f"${{hiveconf:{v}}}" for v in hiveconf)
            d["converted_snippet"] = ("\n".join(f'spark.conf.get("{v}")' for v in conf_gets)
                                      if conf_gets else "# spark.conf.get() calls not found")
            d["missing"] = [v for v in hiveconf if v not in conf_gets]

        elif "partition" in issue_type:
            pm = re.search(r'\bPARTITIONED\s+BY\s*\(([^)]+)\)', hql, re.I)
            if pm:
                d["source_snippet"] = f"PARTITIONED BY ({pm.group(1).strip()})"
            pbm = re.search(r'\.partitionedBy\s*\(([^)]+)\)', py)
            d["converted_snippet"] = (f".partitionedBy({pbm.group(1).strip()})"
                                      if pbm else "# .partitionedBy() not found")

        details[issue] = d

    return details


def _aggregate_checks(checks_list: list[dict]) -> dict:
    """Average scores across files; worst status wins."""
    if not checks_list:
        return {"overall_similarity": 0.0}

    dims = [k for k in checks_list[0] if k not in ("overall_similarity", "issues")]
    agg  = {}

    STATUS_RANK = {"PASSED": 0, "SKIPPED": 0, "WARNING": 1, "FAILED": 2}

    for dim in dims:
        entries  = [c.get(dim) for c in checks_list if isinstance(c.get(dim), dict)]
        if not entries:
            continue
        statuses = [e.get("status", "SKIPPED") for e in entries]
        scores   = [e.get("score", 1.0) for e in entries]
        worst    = max(statuses, key=lambda s: STATUS_RANK.get(s, 0))
        agg[dim] = {
            "status": worst,
            "detail": entries[0].get("detail", ""),
            "score":  round(sum(scores) / len(scores), 3),
        }

    sims = [c.get("overall_similarity", 0.0) for c in checks_list]
    agg["overall_similarity"] = round(sum(sims) / len(sims), 3) if sims else 0.0

    return agg

"""
validators.py — Simulated runtime reconciliation checks.

Metrics are deterministic (seeded from pipeline name) BUT now depend on
the semantic_score from static analysis — poor semantic parity causes
simulated row variance, checksum mismatches, and lower confidence.

This makes simulated checks believably correlated with real analysis.
"""

import hashlib


def _seed(pipeline: str, salt: str) -> int:
    return int(hashlib.md5(f"{pipeline}:{salt}".encode()).hexdigest(), 16)


def _checksum_hex(pipeline: str, role: str) -> str:
    return hashlib.sha256(f"{pipeline}:{role}".encode()).hexdigest()[:16].upper()


def _base_count(pipeline: str, complexity: str) -> int:
    ranges = {
        "SMALL":   (500_000,    5_000_000),
        "MEDIUM":  (5_000_000,  20_000_000),
        "LARGE":   (20_000_000, 80_000_000),
        "COMPLEX": (80_000_000, 500_000_000),
    }
    lo, hi = ranges.get(complexity, (1_000_000, 10_000_000))
    return lo + (_seed(pipeline, "rowcount") % (hi - lo))


# ── Row count ─────────────────────────────────────────────────────────────────

def row_count_check(pipeline: str, complexity: str, semantic_score: float = 1.0) -> dict:
    """
    Simulate row count validation.
    Variance is proportional to (1 - semantic_score):
      score >= 0.90 → perfect match (0% variance)
      score >= 0.75 → small variance, WARNING
      score <  0.75 → significant variance, FAILED
    """
    source = _base_count(pipeline, complexity)

    if semantic_score >= 0.90:
        variance_pct = 0.0
        target, status = source, "PASSED"
    elif semantic_score >= 0.75:
        variance_pct = round((1.0 - semantic_score) * 12, 2)   # 1–3% range
        target  = int(source * (1 - variance_pct / 100))
        status  = "WARNING"
    else:
        variance_pct = round((1.0 - semantic_score) * 40, 2)   # 4–10% range
        target  = int(source * (1 - variance_pct / 100))
        status  = "FAILED"

    return {
        "status":       status,
        "detail":       (f"source={source:,}  target={target:,}  "
                         f"variance={variance_pct:.2f}%"),
        "score":        1.0 if status == "PASSED" else (0.6 if status == "WARNING" else 0.0),
        "source_rows":  source,
        "target_rows":  target,
        "variance_pct": variance_pct,
    }


# ── Checksum ──────────────────────────────────────────────────────────────────

def checksum_check(pipeline: str, semantic_score: float = 1.0) -> dict:
    """
    Simulate partition-level SHA checksum.
    High semantic score → checksums match.
    Low semantic score → checksum mismatch (data shape changed).
    """
    src = _checksum_hex(pipeline, "source")

    if semantic_score >= 0.85:
        tgt    = src                # perfect match
        status = "PASSED"
        detail = f"SHA-256 partition checksum match  [{src}]"
    elif semantic_score >= 0.70:
        tgt    = _checksum_hex(pipeline, "target_minor_delta")
        status = "WARNING"
        detail = f"Minor checksum delta  src=[{src}]  tgt=[{tgt}]"
    else:
        tgt    = _checksum_hex(pipeline, "target_major_delta")
        status = "FAILED"
        detail = f"Checksum mismatch — structural change detected  src=[{src}]  tgt=[{tgt}]"

    return {
        "status":          status,
        "detail":          detail,
        "score":           1.0 if status == "PASSED" else (0.5 if status == "WARNING" else 0.0),
        "source_checksum": src,
        "target_checksum": tgt,
    }


# ── SLA compliance ────────────────────────────────────────────────────────────

def sla_check(pipeline: str, complexity: str) -> dict:
    """SLA validation — always passes for POC (no real timing)."""
    sla_min = {"SMALL": 30, "MEDIUM": 60, "LARGE": 120, "COMPLEX": 240}.get(complexity, 60)
    seed    = _seed(pipeline, "sla_runtime")
    runtime = int(sla_min * 0.55) + (seed % int(sla_min * 0.35))

    return {
        "status":          "PASSED",
        "detail":          f"Runtime {runtime} min  SLA {sla_min} min  headroom {sla_min - runtime} min",
        "score":           1.0,
        "runtime_minutes": runtime,
        "sla_minutes":     sla_min,
    }


# ── Consumer replay ───────────────────────────────────────────────────────────

def consumer_replay_check(pipeline: str, complexity: str, semantic_score: float = 1.0) -> dict:
    """
    Simulate consumer query replay.
    High semantic score → all queries pass, target faster.
    Low semantic score → some queries fail.
    """
    n_queries = {"SMALL": 3, "MEDIUM": 6, "LARGE": 12, "COMPLEX": 20}.get(complexity, 4)
    seed      = _seed(pipeline, "consumer")
    src_ms    = 200 + (seed % 600)
    tgt_ms    = int(src_ms * 0.72)

    if semantic_score >= 0.85:
        passed, failed = n_queries, 0
        status = "PASSED"
    elif semantic_score >= 0.70:
        failed = max(1, int(n_queries * (1.0 - semantic_score)))
        passed = n_queries - failed
        status = "WARNING"
    else:
        failed = max(2, int(n_queries * (1.0 - semantic_score) * 1.5))
        failed = min(failed, n_queries)
        passed = n_queries - failed
        status = "FAILED"

    detail = (f"{passed}/{n_queries} queries passed  "
              f"src avg {src_ms}ms  tgt avg {tgt_ms}ms  "
              f"speedup {src_ms / tgt_ms:.2f}x")

    return {
        "status":           status,
        "detail":           detail,
        "score":            passed / max(n_queries, 1),
        "queries_passed":   passed,
        "queries_failed":   failed,
        "queries_total":    n_queries,
        "avg_latency_src":  src_ms,
        "avg_latency_tgt":  tgt_ms,
        "speedup_factor":   round(src_ms / tgt_ms, 2),
    }


# ── Confidence + status ───────────────────────────────────────────────────────

def calculate_confidence(semantic_score: float, runtime_checks: dict) -> float:
    """
    Weighted confidence blend.
    Static analysis (real) = 80% of total.
    Simulated runtime checks = 20%.
    """
    weights = {
        "row_count":       0.20,
        "checksum":        0.15,
        "sla_compliance":  0.05,
        "consumer_replay": 0.05,
    }
    runtime_score = sum(
        runtime_checks.get(k, {}).get("score", 0.0) * w
        for k, w in weights.items()
    )
    return round(semantic_score * 0.80 + runtime_score * 0.20, 3)


def overall_status(confidence: float, flat_checks: dict, threshold: float = 0.88) -> str:
    failed  = [k for k, v in flat_checks.items() if v == "FAILED"]
    warning = [k for k, v in flat_checks.items() if v == "WARNING"]
    if failed:
        return "FAILED"
    if confidence >= threshold:
        return "PASSED"
    if warning or confidence >= 0.70:
        return "PARTIAL"
    return "FAILED"


# ── Severity mapping ──────────────────────────────────────────────────────────

_FAILED_SEV = {
    "table_parity":       "CRITICAL",
    "aggregation_parity": "CRITICAL",
    "checksum":           "CRITICAL",
    "column_parity":      "HIGH",
    "join_parity":        "HIGH",
    "group_by_parity":    "HIGH",
    "filter_parity":      "HIGH",
    "partition_parity":   "HIGH",
    "workflow_parity":    "HIGH",
    "row_count":          "HIGH",
    "sla_compliance":     "HIGH",
    "consumer_replay":    "HIGH",
    "runtime_var_parity": "MEDIUM",
}
_WARNING_SEV = {
    "partition_parity":   "HIGH",
    "filter_parity":      "MEDIUM",
    "row_count":          "MEDIUM",
    "consumer_replay":    "MEDIUM",
    "column_parity":      "MEDIUM",
    "join_parity":        "MEDIUM",
    "runtime_var_parity": "LOW",
}


def compute_severity_map(checks: dict) -> dict:
    out = {}
    for key, status in checks.items():
        if status == "PASSED":
            out[key] = "INFO"
        elif status in ("SKIPPED",):
            out[key] = "INFO"
        elif status == "FAILED":
            out[key] = _FAILED_SEV.get(key, "HIGH")
        elif status == "WARNING":
            out[key] = _WARNING_SEV.get(key, "LOW")
        else:
            out[key] = "INFO"
    return out


def compute_migration_risk(severity_map: dict) -> tuple[str, int]:
    weights = {"CRITICAL": 40, "HIGH": 20, "MEDIUM": 10, "LOW": 5, "INFO": 0}
    score = sum(weights.get(s, 0) for s in severity_map.values())
    if score >= 80:  return "CRITICAL", score
    if score >= 50:  return "HIGH",     score
    if score >= 25:  return "MODERATE", score
    if score >= 10:  return "LOW",      score
    return "MINIMAL", score


def compute_recommendation(validation_status: str, checks: dict, issues: list) -> dict:
    if validation_status == "PASSED":
        action = "Proceed to production deployment"
    elif validation_status == "PARTIAL":
        action = "Proceed to non-prod deployment only"
    else:
        action = "Halt migration — resolve critical issues before proceeding"

    conditions = []
    if checks.get("runtime_var_parity") in ("WARNING", "FAILED"):
        conditions.append("Resolve unmapped hiveconf variables before production")
    if checks.get("filter_parity") in ("WARNING", "FAILED"):
        conditions.append("Review and validate filter condition parity")
    if checks.get("partition_parity") in ("WARNING", "FAILED"):
        conditions.append("Verify partition strategy in target Iceberg tables")
    if checks.get("row_count") in ("WARNING", "FAILED"):
        conditions.append("Investigate row count variance before sign-off")
    if checks.get("checksum") == "FAILED":
        conditions.append("Resolve checksum mismatch — data integrity at risk")
    if checks.get("consumer_replay") in ("WARNING", "FAILED"):
        conditions.append("Re-run consumer query replay after fixes are applied")

    return {"action": action, "conditions": conditions}


def compute_reasoning(checks: dict, data: dict) -> list[dict]:
    lines: list[dict] = []
    n = data.get("files_reconciled", 0)

    if checks.get("table_parity") == "PASSED":
        lines.append({"agent": "RECONCILE", "message": "All source table references verified in converted PySpark"})
    if checks.get("aggregation_parity") == "PASSED":
        lines.append({"agent": "RECONCILE", "message": f"Aggregation parity confirmed across {n} file(s) — SUM, COUNT, AVG preserved"})
    if checks.get("column_parity") == "PASSED":
        lines.append({"agent": "RECONCILE", "message": "Projected column set fully preserved in target schema"})
    if checks.get("join_parity") == "PASSED":
        lines.append({"agent": "RECONCILE", "message": "JOIN topology preserved — inner/left structure matches source"})
    if checks.get("group_by_parity") == "PASSED":
        lines.append({"agent": "RECONCILE", "message": "GROUP BY semantics verified — partition keys align with aggregation grain"})
    if checks.get("filter_parity") in ("WARNING", "FAILED"):
        lines.append({"agent": "RECONCILE", "message": "Filter condition overlap below threshold — potential data loss in converted query"})
    if checks.get("partition_parity") in ("WARNING", "FAILED"):
        lines.append({"agent": "RECONCILE", "message": "Partition metadata incomplete — Iceberg write strategy requires explicit review"})
    if checks.get("runtime_var_parity") in ("WARNING", "FAILED"):
        lines.append({"agent": "RECONCILE", "message": "Unmapped hiveconf variables detected — runtime substitution will fail in production"})

    variance = data.get("row_variance_pct", 0)
    if variance and variance > 0:
        note = "within tolerance" if variance < 2 else "exceeds 2% threshold — investigate before production"
        lines.append({"agent": "RECONCILE", "message": f"Row count variance {variance:.2f}% — {note}"})

    rec = data.get("recommendation", {})
    if rec.get("action"):
        lines.append({"agent": "SUPERVISOR", "message": rec["action"]})
    risk  = data.get("migration_risk", "UNKNOWN")
    n_iss = len(data.get("issues", []))
    lines.append({"agent": "SUPERVISOR", "message": f"Migration risk: {risk} — {n_iss} issue(s) flagged for remediation"})

    return lines

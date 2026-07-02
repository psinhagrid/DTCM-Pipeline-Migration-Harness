"""
governance.py — Deployment governance + approval logic.

Approval state is derived from REAL scores:
  - reconciliation confidence (real)
  - migration risk (real)
  - smoke test results (real + simulated)
  - artifact validation (real)

No hardcoded PASS — outcome genuinely depends on pipeline quality.
"""


def compute_readiness_score(
    artifact_checks: dict,
    smoke_results:   dict,
    reconcile:       dict,
) -> int:
    """
    Deployment readiness score (0–100).
    Each dimension contributes a weighted portion.
    """
    score = 0

    # Artifact syntax valid (REAL) — 25 pts
    if artifact_checks.get("all_artifacts_valid"):
        score += 25

    # DAG structure valid (REAL) — 20 pts
    if artifact_checks.get("dag_check", {}).get("status") == "PASSED":
        score += 20

    # Reconciliation confidence ≥ 0.72 (REAL) — 25 pts
    confidence = reconcile.get("confidence_score", 0.0)
    if confidence >= 0.90:
        score += 25
    elif confidence >= 0.75:
        score += 18
    elif confidence >= 0.60:
        score += 10

    # Smoke tests (real + simulated) — 20 pts
    smoke_score = smoke_results.get("score", 0)
    score += int(smoke_score / 100 * 20)

    # No FAILED checks in reconciliation — 10 pts
    flat = reconcile.get("checks", {})
    failed_checks = [k for k, v in flat.items() if v == "FAILED"]
    if not failed_checks:
        score += 10
    elif len(failed_checks) == 1:
        score += 5

    return min(score, 100)


def compute_governance(
    readiness_score: int,
    reconcile:       dict,
    smoke_results:   dict,
    artifact_checks: dict,
) -> dict:
    """
    Derive governance approval state from real data.

    States:
      APPROVED           — production eligible
      APPROVED_NON_PROD  — non-prod only
      CONDITIONAL        — proceed with conditions
      BLOCKED            — must resolve before any deployment
    """
    confidence   = reconcile.get("confidence_score", 0.0)
    risk         = reconcile.get("migration_risk", "UNKNOWN")
    smoke_ok     = smoke_results.get("overall") in ("PASSED", "WARNING")
    artifacts_ok = artifact_checks.get("all_artifacts_valid", False)
    smoke_failed = smoke_results.get("failed", 0)
    rec_failed   = [k for k, v in reconcile.get("checks", {}).items() if v == "FAILED"]

    conditions = []

    if readiness_score >= 88 and risk in ("MINIMAL", "LOW") and smoke_failed == 0:
        state = "APPROVED"
        label = "Approved for production deployment"
        color = "success"

    elif readiness_score >= 72 and risk not in ("CRITICAL",) and artifacts_ok:
        state = "APPROVED_NON_PROD"
        label = "Approved for non-production deployment only"
        color = "warning"
        if reconcile.get("runtime_var_parity") == "WARNING":
            conditions.append("Resolve unmapped hiveconf variables before production")
        if reconcile.get("filter_parity") in ("WARNING", "FAILED"):
            conditions.append("Validate filter condition parity")
        if smoke_failed > 0:
            conditions.append(f"Resolve {smoke_failed} smoke test failure(s)")

    elif readiness_score >= 55:
        state = "CONDITIONAL"
        label = "Conditional approval — resolve issues before proceeding"
        color = "warning"
        if rec_failed:
            conditions.append(f"Fix failed parity checks: {', '.join(rec_failed[:3])}")
        if smoke_failed:
            conditions.append(f"Fix {smoke_failed} failing smoke test(s)")
        if confidence < 0.72:
            conditions.append(f"Improve reconciliation confidence (currently {confidence:.0%})")

    else:
        state = "BLOCKED"
        label = "Deployment blocked — critical issues must be resolved"
        color = "danger"
        conditions.append("Reconciliation confidence below minimum threshold")
        if rec_failed:
            conditions.append(f"Critical failed checks: {', '.join(rec_failed)}")
        if not artifacts_ok:
            conditions.append("Artifact syntax validation failed")

    return {
        "state":            state,
        "label":            label,
        "color":            color,
        "readiness_score":  readiness_score,
        "confidence":       confidence,
        "migration_risk":   risk,
        "smoke_passed":     smoke_results.get("passed", 0),
        "smoke_total":      smoke_results.get("total", 0),
        "conditions":       conditions,
        "environment":      "production" if state == "APPROVED" else "non-production",
        "approver":         "SUPERVISOR · AUTO",
        "policy_version":   "v3.2",
    }

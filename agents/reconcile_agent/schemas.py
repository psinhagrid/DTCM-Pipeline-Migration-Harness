"""
Typed schemas for reconcile_agent events and reports.
Uses TypedDict — no Pydantic dependency, plain dicts on the wire.
"""

from typing import TypedDict, Literal


CheckStatus = Literal["PASSED", "FAILED", "WARNING", "SKIPPED"]


class CheckResult(TypedDict):
    status: CheckStatus
    detail: str
    score: float          # 0.0 → 1.0


class StaticAnalysis(TypedDict):
    """Result of real static comparison between HiveQL and PySpark."""
    table_coverage:      CheckResult
    aggregation_parity:  CheckResult
    join_parity:         CheckResult
    group_by_parity:     CheckResult
    filter_parity:       CheckResult
    overall_similarity:  float        # 0.0 → 1.0


class RuntimeChecks(TypedDict):
    """Deterministic simulated runtime validation results."""
    row_count:       CheckResult
    checksum:        CheckResult
    sla_compliance:  CheckResult
    consumer_replay: CheckResult


class ReconcileReport(TypedDict):
    pipeline:           str
    validation_status:  Literal["PASSED", "FAILED", "PARTIAL"]
    confidence_score:   float
    files_reconciled:   int
    source_rows:        int
    target_rows:        int
    row_variance_pct:   float
    source_checksum:    str
    target_checksum:    str
    static_analysis:    StaticAnalysis
    runtime_checks:     RuntimeChecks
    checks:             dict          # flat summary for supervisor
    summary:            str

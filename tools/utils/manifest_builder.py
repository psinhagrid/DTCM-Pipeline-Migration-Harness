"""
manifest_builder.py — Writes real deployment artifacts to disk.

Produces output/<pipeline>/ with four structured JSON files.
These are the only REAL files produced by the deploy_agent.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_ROOT = Path(__file__).parents[3] / "output"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_all(
    pipeline:        str,
    assessment:      dict,
    conversion:      dict,
    reconcile:       dict,
    artifact_checks: dict,
    smoke_results:   dict,
    governance:      dict,
    cicd_yaml:       str,
) -> dict:
    """Write all four deployment manifests to output/{pipeline}/."""
    out_dir = OUTPUT_ROOT / pipeline
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = _ts()

    # ── deployment_manifest.json ──────────────────────────────────────────────
    manifest = {
        "schema_version":   "1.0",
        "generated_at":     ts,
        "pipeline":         pipeline,
        "source_language":  "HiveQL",
        "target_language":  "PySpark / Apache Iceberg",
        "target_env":       governance.get("environment", "non-production"),
        "artifacts": {
            "spark_files":  [f["python_filename"] for f in conversion.get("files", [])],
            "dag_file":     conversion.get("dag_filename", ""),
            "artifact_path": conversion.get("artifact_path", ""),
        },
        "assessment": {
            "complexity":       assessment.get("complexity"),
            "tables":           assessment.get("tables"),
            "udfs":             assessment.get("udfs"),
            "estimated_effort": assessment.get("estimated_effort"),
        },
        "cicd_config":      cicd_yaml,
    }
    _write(out_dir / "deployment_manifest.json", manifest)

    # ── deployment_report.json ────────────────────────────────────────────────
    report = {
        "generated_at":     ts,
        "pipeline":         pipeline,
        "governance":       governance,
        "readiness_score":  governance.get("readiness_score"),
        "artifact_checks":  artifact_checks,
        "reconciliation": {
            "status":       reconcile.get("validation_status"),
            "confidence":   reconcile.get("confidence_score"),
            "risk":         reconcile.get("migration_risk"),
        },
    }
    _write(out_dir / "deployment_report.json", report)

    # ── smoke_test_report.json ────────────────────────────────────────────────
    smoke_report = {
        "generated_at": ts,
        "pipeline":     pipeline,
        "summary": {
            "passed":   smoke_results.get("passed"),
            "failed":   smoke_results.get("failed"),
            "warning":  smoke_results.get("warning"),
            "total":    smoke_results.get("total"),
            "score":    smoke_results.get("score"),
            "overall":  smoke_results.get("overall"),
        },
        "tests": smoke_results.get("tests", []),
    }
    _write(out_dir / "smoke_test_report.json", smoke_report)

    # ── rollout_summary.json ──────────────────────────────────────────────────
    rollout = {
        "generated_at":    ts,
        "pipeline":        pipeline,
        "approval_state":  governance.get("state"),
        "approval_label":  governance.get("label"),
        "environment":     governance.get("environment"),
        "readiness_score": governance.get("readiness_score"),
        "conditions":      governance.get("conditions", []),
        "next_steps": _next_steps(governance),
        "planned_capabilities": [
            "Real MWAA DAG registration",
            "EMR Serverless job submission",
            "OpenLineage lineage hooks",
            "GitOps rollout via Argo CD",
            "Canary deployment support",
            "Automated rollback on failure",
        ],
    }
    _write(out_dir / "rollout_summary.json", rollout)

    files_written = [
        str(out_dir / "deployment_manifest.json"),
        str(out_dir / "deployment_report.json"),
        str(out_dir / "smoke_test_report.json"),
        str(out_dir / "rollout_summary.json"),
    ]

    return {
        "output_dir":    str(out_dir),
        "files_written": files_written,
        "file_count":    len(files_written),
    }


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _next_steps(governance: dict) -> list[str]:
    state = governance.get("state", "BLOCKED")
    if state == "APPROVED":
        return [
            "Merge to main branch to trigger CI/CD",
            "Monitor MWAA DAG execution",
            "Validate production data output",
        ]
    elif state == "APPROVED_NON_PROD":
        return [
            "Deploy to non-prod environment",
            "Run full integration test suite",
            "Resolve open conditions before production promotion",
        ]
    elif state == "CONDITIONAL":
        return [
            "Resolve all listed conditions",
            "Re-run reconciliation after fixes",
            "Resubmit for governance review",
        ]
    return [
        "Halt deployment",
        "Fix critical issues",
        "Re-run full migration pipeline",
    ]

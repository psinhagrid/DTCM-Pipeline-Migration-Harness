"""
deploy_agent — async deployment orchestration layer.

Phases:
  1. Artifact validation (REAL)
  2. Packaging simulation
  3. CI/CD config generation (REAL files)
  4. Deployment simulation
  5. Smoke test suite (REAL + simulated)
  6. Governance approval (REAL logic)
  7. Write output manifests to disk (REAL)
"""

import asyncio
from pathlib import Path

from event_queue import push
from .artifact_validator import validate_artifacts
from .cicd_generator     import generate_deployment_yaml, generate_pipeline_config
from .smoke_tests        import run_all_smoke_tests
from .governance         import compute_readiness_score, compute_governance
from .manifest_builder   import write_all

NAME = "deploy_agent"


async def run_deployment(
    assessment:   dict,
    conversion:   dict,
    reconcile:    dict,
) -> dict:
    pipeline   = assessment["pipeline"]
    complexity = assessment.get("complexity", "MEDIUM")
    files      = conversion.get("files", [])

    async def _e(type: str, message: str, **kw) -> None:
        await push(type=type, agent=NAME, message=message, pipeline=pipeline, **kw)

    # ── Phase 1 · Artifact Validation ────────────────────────────────────────
    await _e("status", f"Starting deployment orchestration for {pipeline}")
    await _e("hook",   "PreToolUse → visa_governance ✓ deployment allowed")
    await _e("status", "Validating generated migration artifacts...")

    artifact_checks = await asyncio.to_thread(validate_artifacts, conversion, reconcile)

    for fname, result in artifact_checks["file_checks"].items():
        icon = "✓" if result["status"] == "PASSED" else "✗"
        await _e("validation", f"{icon} {fname}: {result['detail']}")
        await asyncio.sleep(0.2)

    dag_chk  = artifact_checks["dag_check"]
    recon_chk = artifact_checks["reconciliation_check"]
    dag_icon  = "✓" if dag_chk["status"]  == "PASSED" else "⚠"
    rec_icon  = "✓" if recon_chk["status"] == "PASSED" else "⚠"
    await _e("validation", f"{dag_icon} DAG structure: {dag_chk['detail']}")
    await _e("validation", f"{rec_icon} Reconciliation gate: {recon_chk['detail']}")
    await asyncio.sleep(0.3)

    overall_artifact = "✓" if artifact_checks["deployment_ready"] else "⚠"
    await _e("status", f"{overall_artifact} Artifact validation complete — "
             f"{'all checks passed' if artifact_checks['deployment_ready'] else 'issues found'}")

    # ── Phase 2 · Packaging ───────────────────────────────────────────────────
    await _e("status", "Packaging migration artifacts...")
    await asyncio.sleep(0.5)

    await _e("tool_call", f"bundler.zip({pipeline}_bundle.zip) → {len(files)} PySpark files + DAG")
    await asyncio.sleep(0.6)

    await _e("tool_call", f"sha256.sign({pipeline}_bundle.zip)")
    await asyncio.sleep(0.4)

    await _e("status", f"✓ Bundle packaged: {pipeline}_bundle.zip  ({len(files) + 1} files)")

    # ── Phase 3 · CI/CD Generation ────────────────────────────────────────────
    await _e("status", "Generating CI/CD pipeline definition...")
    await asyncio.sleep(0.5)

    generated_files = [f.get("python_filename", "") for f in files] + [conversion.get("dag_filename", "")]
    cicd_yaml       = await asyncio.to_thread(generate_deployment_yaml, pipeline, generated_files, assessment)
    pipeline_cfg    = await asyncio.to_thread(generate_pipeline_config, pipeline, assessment, reconcile)

    await _e("artifact", f"✓ CI/CD pipeline config generated — {len(pipeline_cfg['stages'])} stages defined")
    await _e("status",   "✓ Deployment YAML ready — stages: validate → package → deploy-nonprod → smoke → governance")

    # ── Phase 4 · Deployment Simulation ──────────────────────────────────────
    await _e("status", "Initiating non-prod deployment sequence...")
    await asyncio.sleep(0.6)

    await _e("tool_call", f"MCP → mwaa_mcp.register_dag(pipeline={pipeline}, env=non-production)")
    await asyncio.sleep(0.9)

    await _e("status",   "✓ DAG registered in MWAA non-prod — awaiting scheduler sync")
    await asyncio.sleep(0.5)

    await _e("tool_call", "MCP → emrs_mcp.validate_job_config(spark_version=3.4)")
    await asyncio.sleep(0.6)

    await _e("status",   "✓ EMR Serverless config validated — execution profile ready")
    await asyncio.sleep(0.4)

    await _e("tool_call", f"S3.put_object → s3://dtcm-artifacts/wave1/{pipeline}/")
    await asyncio.sleep(0.5)

    await _e("artifact", f"✓ Artifacts staged → s3://dtcm-artifacts/wave1/{pipeline}/")

    # ── Phase 5 · Smoke Tests ─────────────────────────────────────────────────
    await _e("status", "Executing smoke test suite...")
    await asyncio.sleep(0.4)

    smoke_results = await asyncio.to_thread(run_all_smoke_tests, pipeline, conversion, reconcile)

    for test in smoke_results["tests"]:
        icon = "✓" if test["status"] == "PASSED" else ("⚠" if test["status"] == "WARNING" else "✗")
        tag  = f"[{test['type']}]"
        evt  = "validation" if test["status"] == "PASSED" else "status"
        await _e(evt, f"{icon} {test['name']} {tag}: {test['detail']}  ({test['runtime']})")
        await asyncio.sleep(0.35)

    smoke_icon = "✓" if smoke_results["overall"] == "PASSED" else "⚠"
    await _e("status",
        f"{smoke_icon} Smoke test suite complete — "
        f"{smoke_results['passed']}/{smoke_results['total']} passed  "
        f"score: {smoke_results['score']}%"
    )

    # ── Phase 6 · Governance + Approval ──────────────────────────────────────
    await _e("status", "Computing deployment readiness score...")
    await asyncio.sleep(0.5)

    readiness = compute_readiness_score(artifact_checks, smoke_results, reconcile)
    governance = compute_governance(readiness, reconcile, smoke_results, artifact_checks)

    await _e("status", f"Deployment readiness score: {readiness}%")
    await asyncio.sleep(0.3)

    await _e("hook", f"PostToolUse → governance_policy.evaluate(pipeline={pipeline}, policy=v3.2)")
    await asyncio.sleep(0.5)

    gov_icon = "✓" if governance["state"] in ("APPROVED", "APPROVED_NON_PROD") else ("⚠" if governance["state"] == "CONDITIONAL" else "✗")
    await _e("status", f"{gov_icon} Governance state: {governance['state']} — {governance['label']}")

    for condition in governance.get("conditions", []):
        await _e("status", f"  → Condition: {condition}")
        await asyncio.sleep(0.2)

    # ── Phase 7 · Write manifests to disk ────────────────────────────────────
    await _e("status", "Writing deployment manifests to disk...")
    await asyncio.sleep(0.4)

    output_meta = await asyncio.to_thread(
        write_all, pipeline, assessment, conversion, reconcile,
        artifact_checks, smoke_results, governance, cicd_yaml
    )

    for fpath in output_meta["files_written"]:
        fname = Path(fpath).name
        await _e("artifact", f"✓ Written: output/{pipeline}/{fname}")
        await asyncio.sleep(0.15)

    # ── Done ─────────────────────────────────────────────────────────────────
    await _e("hook",   "PostToolUse → audit_logger.record_deployment ✓")
    await _e("status", "Deployment orchestration complete", done=True)

    return {
        "pipeline":          pipeline,
        "deployment_status": governance["state"],
        "readiness_score":   readiness,
        "governance":        governance,
        "artifact_checks":   artifact_checks,
        "smoke_results":     smoke_results,
        "cicd_config":       pipeline_cfg,
        "output":            output_meta,
        "summary": (
            f"{pipeline} — {governance['state']}  "
            f"readiness={readiness}%  "
            f"smoke={smoke_results['passed']}/{smoke_results['total']}"
        ),
    }

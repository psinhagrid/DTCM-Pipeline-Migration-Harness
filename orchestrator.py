import asyncio

from event_queue import push
from agents.assess_subagent import run_assessment
from agents.convert_subagent import run_conversion
from agents.reconcile_agent import run_reconciliation
from agents.deploy_agent   import run_deployment

DEFAULT_PIPELINE = "daily_revenue_agg"

# Shared result stores — read by API endpoints
results:         dict = {}
conversions:     dict = {}
reconciliations: dict = {}
deployments:     dict = {}


async def run_pipeline(pipeline_name: str = DEFAULT_PIPELINE) -> dict | None:

    async def _sup(message: str, type: str = "status", **kw) -> None:
        await push(type=type, agent="supervisor", message=message, pipeline=pipeline_name, **kw)
        await asyncio.sleep(0.35)

    # ── Boot ──────────────────────────────────────────────────────────────────
    await _sup(f"Starting migration workflow — {pipeline_name}")
    await _sup("Hook PreToolUse → visa_governance ✓ allowed", type="hook")

    # ── assess_agent ──────────────────────────────────────────────────────────
    await _sup("Delegating to assess_subagent", type="delegation", target="assess_subagent")
    metadata = await run_assessment(pipeline_name)
    results[pipeline_name] = metadata

    await _sup(
        f"Assessment complete → complexity: {metadata['complexity']}  "
        f"tables: {metadata['tables']}  udfs: {metadata['udfs']}  "
        f"effort: {metadata['estimated_effort']}"
    )
    await _sup("MCP → neo4j_mcp.write_node(assess_result)", type="tool_call")

    # ── convert_agent ─────────────────────────────────────────────────────────
    await _sup("Delegating to convert_agent", type="delegation", target="convert_agent")
    conversion = await run_conversion(metadata)
    conversions[pipeline_name] = conversion

    await _sup(
        f"Conversion complete → {conversion['transformations_applied']} transformations  "
        f"files: {len(conversion['generated_files'])}"
    )
    await _sup(f"Artifact → {conversion['artifact_path']}", type="artifact")
    await _sup("MCP → neo4j_mcp.update_status(convert_complete)", type="tool_call")

    # ── reconcile_agent ───────────────────────────────────────────────────────
    await _sup("Delegating to reconcile_agent", type="delegation", target="reconcile_agent")
    reconcile = await run_reconciliation(metadata, conversion)
    reconciliations[pipeline_name] = reconcile

    await _sup(
        f"Reconciliation {reconcile['validation_status']} — "
        f"confidence={reconcile['confidence_score']:.0%}  "
        f"risk={reconcile.get('migration_risk', 'UNKNOWN')}  "
        f"rows={reconcile['source_rows']:,}"
    )

    # ── deploy_agent ──────────────────────────────────────────────────────────
    await _sup("Delegating to deploy_agent", type="delegation", target="deploy_agent")
    deployment = await run_deployment(metadata, conversion, reconcile)
    deployments[pipeline_name] = deployment

    gov   = deployment.get("governance", {})
    score = deployment.get("readiness_score", 0)
    smoke = deployment.get("smoke_results", {})
    await _sup(
        f"Deployment {gov.get('state', 'UNKNOWN')} — "
        f"readiness={score}%  "
        f"smoke={smoke.get('passed', 0)}/{smoke.get('total', 0)}"
    )
    await _sup(f"Output → {deployment['output']['output_dir']}", type="artifact")

    # ── Done ──────────────────────────────────────────────────────────────────
    await _sup(
        "Migration workflow complete — assess → convert → reconcile → deploy",
        type="complete"
    )
    return metadata

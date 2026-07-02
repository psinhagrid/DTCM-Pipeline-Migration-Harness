import asyncio
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

logging.getLogger("uvicorn.access").disabled = True

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from routes import stream, graph, skills as skills_router, internal as internal_router
from event_queue import resolve_user_input, _pending_input, push
from orchestrator import (
    run_pipeline,
    results         as pipeline_results,
    conversions     as pipeline_conversions,
    reconciliations as pipeline_reconciliations,
    deployments     as pipeline_deployments,
)

app = FastAPI(title="Migration Pipeline API")


def _tool_result_summary(tool: str, data: dict) -> str | None:
    """Extract a one-line human-readable summary from a tool response."""
    if "error" in data:
        return f"✗ error: {data['error']}"
    s = {
        "scan-repo":           lambda d: f"{d.get('total_files', '?')} files found",
        "parse-hql":           lambda d: f"{d.get('file', '?')} — {len(d.get('syntax_errors', []))} syntax errors, {len(d.get('udfs', []))} UDFs",
        "lineage-extract":     lambda d: f"{len(d.get('upstream', []))} upstream, {len(d.get('downstream', []))} downstream",
        "classify-complexity": lambda d: f"complexity={d.get('complexity', '?')}  effort={d.get('estimated_effort', '?')}  score={d.get('score', '?')}",
        "neo4j-write":         lambda d: f"status={d.get('status', '?')}  nodes={d.get('nodes', '?')}  edges={d.get('edges', '?')}",
        "query-graph":         lambda d: (
            f"blast_radius={d.get('count', len(d.get('blast_radius', [])))} pipelines" if "blast_radius" in d
            else f"wave={d.get('migration_wave', '?')}" if "migration_wave" in d
            else f"complexity={d.get('complexity', '?')}  depends_on={len(d.get('depends_on', []))}  consumed_by={len(d.get('consumed_by', []))}"
        ),
        "transform-hql":       lambda d: f"{d.get('python_filename', '?')} — {d.get('transformations_applied', '?')} transformations",
        "generate-dag":        lambda d: f"DAG written → {d.get('dag_filename', '?')}",
        "validate-pyspark":    lambda d: f"valid={d.get('valid', '?')}  errors={len(d.get('errors', []))}  warnings={len(d.get('warnings', []))}",
        "analyze-file":        lambda d: (
            f"skipped — {d.get('reason', '')}" if d.get("skipped")
            else f"similarity={d.get('overall_similarity', 0):.2f}  issues={len(d.get('issues', []))}"
        ),
        "workflow-parity":     lambda d: f"status={d.get('status', '?')}  score={d.get('score', '?')}",
        "runtime-validation":  lambda d: (
            "row_count={s}  checksum={c}  sla={l}  replay={r}".format(
                s=d.get("row_count", {}).get("status", "?"),
                c=d.get("checksum", {}).get("status", "?"),
                l=d.get("sla_compliance", {}).get("status", "?"),
                r=d.get("consumer_replay", {}).get("status", "?"),
            )
        ),
        "compile-report":      lambda d: f"status={d.get('validation_status', '?')}  confidence={d.get('confidence_score', 0):.2f}  risk={d.get('migration_risk', '?')}",
        "validate-artifacts":  lambda d: f"deployment_ready={d.get('deployment_ready', '?')}  all_valid={d.get('all_artifacts_valid', '?')}",
        "generate-cicd":       lambda d: f"CI/CD YAML generated ({len(d.get('cicd_yaml', ''))} chars)",
        "run-smoke-tests":     lambda d: f"overall={d.get('overall', '?')}  passed={d.get('passed', '?')}/{d.get('total', '?')}  score={d.get('score', '?')}",
        "compute-governance":  lambda d: f"readiness={d.get('readiness_score', '?')}  state={d.get('governance', {}).get('state', '?')}",
        "write-manifests":     lambda d: f"{d.get('file_count', '?')} files written → {d.get('output_dir', '?')}",
        "run-assess-phase":    lambda d: f"assess complete — complexity={d.get('complexity', '?')}",
        "run-convert-phase":   lambda d: f"convert complete — {d.get('files_converted', '?')} files",
        "run-reconcile-phase": lambda d: f"reconcile complete — confidence={d.get('confidence_score', '?')}  risk={d.get('migration_risk', '?')}",
        "run-deploy-phase":    lambda d: f"deploy complete — state={d.get('governance_state', '?')}",
        "request-approval":    lambda d: "awaiting human decision…",
    }
    fn = s.get(tool)
    try:
        return fn(data) if fn else None
    except Exception:
        return None


_TOOL_DESCRIPTIONS: dict[str, str] = {
    "scan-repo":            "Find HQL and config files in the pipeline folder",
    "parse-hql":            "Parse SQL structure — tables, joins, UDFs, partitions",
    "lineage-extract":      "Build upstream/downstream lineage from parsed reads/writes",
    "classify-complexity":  "Score migration complexity based on SQL patterns",
    "neo4j-write":          "Persist pipeline lineage graph to Neo4j",
    "query-graph":          "Query Neo4j for blast radius, wave order, or summary",
    "transform-hql":        "Convert a HQL file to PySpark via Claude Sonnet",
    "validate-pyspark":     "Syntax-check and lint the generated PySpark code",
    "generate-dag":         "Generate an Airflow DAG for the converted pipeline",
    "analyze-file":         "Compare HQL and PySpark semantics across 8 dimensions",
    "workflow-parity":      "Check DAG task count matches number of PySpark files",
    "runtime-validation":   "Simulate row-count, checksum, SLA, and replay checks",
    "compile-report":       "Aggregate scores into a confidence report with risk rating",
    "validate-artifacts":   "Verify all output files exist and are well-formed",
    "run-smoke-tests":      "Run 7 structural smoke tests on the generated artifacts",
    "compute-governance":   "Compute readiness score and APPROVED/BLOCKED decision",
    "generate-cicd":        "Generate GitHub Actions CI/CD pipeline YAML",
    "write-manifests":      "Write all phase results as JSON files to output/",
    "run-assess-phase":     "Start the ASSESS agent for this pipeline",
    "run-convert-phase":    "Start the CONVERT agent with the assessment result",
    "run-reconcile-phase":  "Start the RECONCILE agent to validate the conversion",
    "run-deploy-phase":     "Start the DEPLOY agent to govern and package artifacts",
    "request-approval":     "Pause and wait for human approval before proceeding",
}


class ToolCallLogger(BaseHTTPMiddleware):
    """Log every /internal/* call + result summary to the SSE stream."""
    async def dispatch(self, request: Request, call_next):
        if not (request.url.path.startswith("/internal/") and request.method == "POST"):
            return await call_next(request)

        tool_name = request.url.path.removeprefix("/internal/")
        from event_queue import push
        from starlette.responses import Response as StarletteResponse

        if tool_name != "read-skill":
            description = _TOOL_DESCRIPTIONS.get(tool_name, "")
            asyncio.create_task(push(
                type="tool_call",
                agent="agent",
                message=f"⚙ {tool_name}",
                description=description,
                tool_name=tool_name,
                pipeline="",
            ))

        response = await call_next(request)

        # Buffer response so we can both read it and re-send it
        body = b"".join([chunk async for chunk in response.body_iterator])

        if tool_name != "read-skill":
            try:
                parsed = json.loads(body)
                summary = _tool_result_summary(tool_name, parsed)
                if summary:
                    asyncio.create_task(push(
                        type="tool_result",
                        agent="agent",
                        message=f"  ↳ {summary}",
                        tool_name=tool_name,
                        summary=summary,
                        ok="error" not in parsed,
                        pipeline="",
                    ))
            except Exception:
                pass

        return StarletteResponse(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )

app.add_middleware(ToolCallLogger)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stream.router)
app.include_router(graph.router)
app.include_router(skills_router.router)
app.include_router(internal_router.router)

PIPELINES_ROOT = Path("pipelines")
OUTPUT_ROOT    = Path("output")


@app.get("/pipelines")
def list_pipelines():
    if not PIPELINES_ROOT.exists():
        return {"pipelines": []}
    return {
        "pipelines": [d.name for d in sorted(PIPELINES_ROOT.iterdir()) if d.is_dir()]
    }


@app.get("/pending-input")
def get_pending_input():
    """Return the current pending user input request, if any."""
    import event_queue as eq
    return eq._pending_input or {}


@app.post("/user-input")
async def submit_user_input(choice: int, chosen: str = ""):
    """Frontend submits the user's choice for a pending ask_user prompt."""
    import event_queue as eq
    if not chosen:
        pending = eq._pending_input
        if pending and 1 <= choice <= len(pending.get("options", [])):
            chosen = pending["options"][choice - 1]
    if eq._pending_input and "request_id" in eq._pending_input:
        eq.resolve_approval(eq._pending_input["request_id"], choice, chosen)
    resolved = eq.resolve_user_input(choice, chosen)
    if resolved and chosen:
        asyncio.create_task(push(
            type="tool_result",
            agent="orchestrator",
            message=f"  ↳ chosen: \"{chosen}\" (option {choice})",
            tool_name="request-approval",
            summary=f"chosen: \"{chosen}\" (option {choice})",
            ok=True,
            pipeline="",
        ))
    return {"status": "ok" if resolved else "no_pending_input"}


@app.get("/status")
def get_status():
    """Return which pipelines are currently running."""
    from orchestrator import running as running_set
    return {"running": list(running_set)}


@app.post("/run")
async def run(pipeline: str = "daily_revenue_agg"):
    asyncio.create_task(push(
        type="status",
        agent="orchestrator",
        message="⟳ Starting migration pipeline — generating code…",
        pipeline=pipeline,
    ))
    asyncio.create_task(run_pipeline(pipeline))
    return {"status": "started", "pipeline": pipeline}


@app.get("/deployment/{pipeline}")
def get_deployment(pipeline: str):
    return pipeline_deployments.get(pipeline)


@app.post("/reset")
def reset_all():
    """Clear all in-memory results — called by the frontend Reset button."""
    pipeline_results.clear()
    pipeline_conversions.clear()
    pipeline_reconciliations.clear()
    pipeline_deployments.clear()
    return {"status": "reset"}


@app.get("/result/{pipeline}")
def get_result(pipeline: str):
    if pipeline not in pipeline_results:
        raise HTTPException(status_code=404, detail="No result yet for this pipeline")
    return pipeline_results[pipeline]


@app.get("/conversion/{pipeline}")
def get_conversion(pipeline: str):
    if pipeline not in pipeline_conversions:
        raise HTTPException(status_code=404, detail="No conversion yet for this pipeline")
    return pipeline_conversions[pipeline]


@app.get("/reconcile/{pipeline}")
def get_reconcile(pipeline: str):
    if pipeline not in pipeline_reconciliations:
        raise HTTPException(status_code=404, detail="No reconciliation yet for this pipeline")
    return pipeline_reconciliations[pipeline]


# ── Output file endpoints ─────────────────────────────────────────────────────

@app.get("/output/{pipeline}")
def list_output_files(pipeline: str):
    """List all output JSON files for a pipeline."""
    out_dir = OUTPUT_ROOT / pipeline
    if not out_dir.exists():
        raise HTTPException(status_code=404, detail="No output files yet for this pipeline")
    files = sorted(f.name for f in out_dir.glob("*.json"))
    return {"pipeline": pipeline, "files": files, "path": str(out_dir)}


@app.get("/output/{pipeline}/{filename}")
def get_output_file(pipeline: str, filename: str):
    """Return contents of a specific output JSON file."""
    if not filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files supported")
    path = OUTPUT_ROOT / pipeline / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found")
    return json.loads(path.read_text(encoding="utf-8"))

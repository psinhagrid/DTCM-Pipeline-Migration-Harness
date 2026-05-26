import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from routes import stream, graph, skills as skills_router
from event_queue import resolve_user_input, _pending_input
from subagents.assess_subagent    import run_assessment
from subagents.convert_subagent   import run_conversion
from subagents.reconcile_subagent import run_reconciliation
from subagents.deploy_subagent    import run_deployment
from subagents.repair_code        import run_repair
from orchestrator import (
    run_pipeline,
    results         as pipeline_results,
    conversions     as pipeline_conversions,
    reconciliations as pipeline_reconciliations,
    deployments     as pipeline_deployments,
)

app = FastAPI(title="DTCM Pipeline API")

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
    resolved = eq.resolve_user_input(choice, chosen)
    return {"status": "ok" if resolved else "no_pending_input"}


@app.post("/run")
async def run(pipeline: str = "daily_revenue_agg"):
    asyncio.create_task(run_pipeline(pipeline))
    return {"status": "started", "pipeline": pipeline}


# ── RLM subagent endpoints ────────────────────────────────────────────────────
# Called internally by the fast_rlm tool functions running inside Pyodide.
# Each endpoint runs the real subagent and updates the result stores so
# intermediate results are visible via GET endpoints as the pipeline progresses.

@app.post("/subagent/assess")
async def subagent_assess(pipeline: str):
    result = await run_assessment(pipeline)
    pipeline_results[pipeline] = result
    return result


@app.post("/subagent/convert")
async def subagent_convert(pipeline: str, request: Request):
    assessment = await request.json()
    result = await run_conversion(assessment)
    pipeline_conversions[pipeline] = result
    # Write generated PySpark files to disk so the /conversion fallback can recover them
    # if the agent dropped spark_python from the result dict.
    out_dir = OUTPUT_ROOT / pipeline
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in (result.get("files") or []):
        if f.get("spark_python") and f.get("python_filename"):
            (out_dir / f["python_filename"]).write_text(f["spark_python"], encoding="utf-8")
    return result


@app.post("/subagent/reconcile")
async def subagent_reconcile(pipeline: str, request: Request):
    body = await request.json()
    result = await run_reconciliation(body["assessment"], body["conversion"])
    pipeline_reconciliations[pipeline] = result
    return result


@app.post("/subagent/deploy")
async def subagent_deploy(pipeline: str, request: Request):
    try:
        body = await request.json()
        result = await run_deployment(body["assessment"], body["conversion"], body["reconcile"])
        pipeline_deployments[pipeline] = result
        return result
    except Exception as exc:
        return {"error": str(exc), "pipeline": pipeline}


@app.post("/subagent/repair")
async def subagent_repair(pipeline: str, target: str = "hql"):
    result = await run_repair(pipeline, target)
    return result


@app.get("/skills/{skill_name}", response_class=PlainTextResponse)
def get_skill(skill_name: str):
    """Serve skill markdown files to the RLM running inside Pyodide (no host FS access)."""
    skill_path = Path(__file__).parent / "skills" / f"{skill_name}.md"
    if not skill_path.exists():
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
    return skill_path.read_text(encoding="utf-8")


@app.get("/deployment/{pipeline}")
def get_deployment(pipeline: str):
    if pipeline not in pipeline_deployments:
        raise HTTPException(status_code=404, detail="No deployment yet for this pipeline")
    data = dict(pipeline_deployments[pipeline])  # shallow copy

    # Normalise: ensure governance.readiness_score is set (frontend reads it there)
    gov = data.get("governance") or {}
    if gov and "readiness_score" not in gov:
        gov = dict(gov)
        gov["readiness_score"] = data.get("readiness_score", 0)
        data["governance"] = gov

    # Normalise: ensure artifact_checks has both keys the frontend uses
    art = data.get("artifact_checks") or {}
    if art and "deployment_ready" not in art:
        art = dict(art)
        art["deployment_ready"] = art.get("all_artifacts_valid", False)
        data["artifact_checks"] = art

    # Normalise: ensure deployment_status is set (Timeline reads it)
    if not data.get("deployment_status"):
        data["deployment_status"] = gov.get("state", "BLOCKED")

    # Normalise: ensure output key exists (OutputFiles component reads output.files_written)
    if "output" not in data:
        # Try reconstructing from write_manifests_tool result if it was flattened to top level
        if data.get("output_dir") or data.get("files_written"):
            data["output"] = {
                "output_dir":    data.get("output_dir", ""),
                "files_written": data.get("files_written", []),
            }

    return data


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
    data = pipeline_conversions[pipeline]
    # Safety net: if the agent dropped source_hql / spark_python, read them from disk.
    # source_hql  → pipelines/{pipeline}/{filename}
    # spark_python → output/{pipeline}/{python_filename}
    enriched_files = []
    for f in (data.get("files") or []):
        f = dict(f)  # shallow copy — don't mutate store
        if not f.get("source_hql"):
            src = PIPELINES_ROOT / pipeline / f.get("filename", "")
            if src.exists():
                f["source_hql"] = src.read_text(encoding="utf-8")
        if not f.get("spark_python"):
            out = OUTPUT_ROOT / pipeline / f.get("python_filename", "")
            if out.exists():
                f["spark_python"] = out.read_text(encoding="utf-8")
        enriched_files.append(f)
    if enriched_files:
        data = {**data, "files": enriched_files}
    return data


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

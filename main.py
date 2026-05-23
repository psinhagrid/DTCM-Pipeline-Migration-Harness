import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from routes import stream
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

PIPELINES_ROOT = Path("pipelines")
OUTPUT_ROOT    = Path("output")


@app.get("/pipelines")
def list_pipelines():
    if not PIPELINES_ROOT.exists():
        return {"pipelines": []}
    return {
        "pipelines": [d.name for d in sorted(PIPELINES_ROOT.iterdir()) if d.is_dir()]
    }


@app.post("/run")
async def run(pipeline: str = "daily_revenue_agg"):
    asyncio.create_task(run_pipeline(pipeline))
    return {"status": "started", "pipeline": pipeline}




@app.get("/deployment/{pipeline}")
def get_deployment(pipeline: str):
    if pipeline not in pipeline_deployments:
        raise HTTPException(status_code=404, detail="No deployment yet for this pipeline")
    return pipeline_deployments[pipeline]


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


# ── Lineage graph ────────────────────────────────────────────────────────────

@app.get("/graph")
def get_graph():
    """Query Neo4j for the full pipeline lineage graph via shared graph tool."""
    from graph.client import query_all_pipelines
    try:
        return {"pipelines": query_all_pipelines(), "error": None}
    except Exception as e:
        return {"pipelines": [], "error": str(e)}


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

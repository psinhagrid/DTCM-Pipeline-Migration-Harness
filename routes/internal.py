"""
/internal — FastAPI endpoints that expose every Python tool to the RLM.

The RLM runs inside Pyodide and cannot import these modules directly.
It calls these HTTP endpoints via urllib.request instead.

All endpoints:
  - Accept POST with a JSON body
  - Call the real tool (sync tools wrapped in asyncio.to_thread)
  - Return JSON-serialisable dicts (sets converted to sorted lists)
  - Wrap failures in {"error": "<message>"}
"""

import asyncio
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/internal")

PIPELINES_ROOT = Path(__file__).parents[1] / "pipelines"
OUTPUT_ROOT    = Path(__file__).parents[1] / "output"

_ROOT = Path(__file__).parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialise(obj: Any) -> Any:
    """Recursively convert sets → sorted lists so the result is JSON-safe."""
    if isinstance(obj, set):
        return sorted(_serialise(v) for v in obj)
    if isinstance(obj, dict):
        return {k: _serialise(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialise(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj


# ===========================================================================
# ASSESS TOOLS
# ===========================================================================

# ── POST /internal/scan-repo ─────────────────────────────────────────────

class ScanRepoBody(BaseModel):
    pipeline: str


@router.post("/scan-repo")
async def scan_repo(body: ScanRepoBody):
    try:
        from modules.assess_subagent.tools.scan_repo_tool import scan_repo_tool
        pipeline_dir = PIPELINES_ROOT / body.pipeline
        result = await asyncio.to_thread(scan_repo_tool, pipeline_dir)
        return {
            "hql_files":   [str(f.name) for f in result["hql_files"]],
            "config_files": _serialise(result["config_files"]),
            "total_files":  result["total_files"],
        }
    except Exception as e:
        return {"error": str(e)}


# ── POST /internal/parse-hql ─────────────────────────────────────────────

class ParseHqlBody(BaseModel):
    pipeline: str
    filename: str


@router.post("/parse-hql")
async def parse_hql(body: ParseHqlBody):
    try:
        from modules.assess_subagent.tools.parse_hql_tool import parse_hql_tool
        path   = PIPELINES_ROOT / body.pipeline / body.filename
        result = await asyncio.to_thread(parse_hql_tool, path)
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ── POST /internal/lineage-extract ───────────────────────────────────────

class LineageExtractBody(BaseModel):
    pipeline:    str
    all_reads:   list
    all_creates: list
    all_writes:  list


@router.post("/lineage-extract")
async def lineage_extract(body: LineageExtractBody):
    try:
        from modules.assess_subagent.tools.lineage_extract_tool import lineage_extract_tool
        pipeline_dir = PIPELINES_ROOT / body.pipeline
        result = await asyncio.to_thread(
            lineage_extract_tool,
            set(body.all_reads),
            set(body.all_creates),
            set(body.all_writes),
            pipeline_dir,
        )
        return {
            "upstream":      _serialise(result["upstream"]),
            "output_tables": _serialise(result["output_tables"]),
            "downstream":    _serialise(result["downstream"]),
        }
    except Exception as e:
        return {"error": str(e)}


# ── POST /internal/classify-complexity ───────────────────────────────────

class ClassifyComplexityBody(BaseModel):
    tables:       list
    udfs:         list
    has_window:   bool
    cross_db:     list
    has_dyn_part: bool
    subqueries:   int
    downstream:   list


@router.post("/classify-complexity")
async def classify_complexity(body: ClassifyComplexityBody):
    try:
        from modules.assess_subagent.tools.classify_complexity_tool import classify_complexity_tool
        result = await asyncio.to_thread(
            classify_complexity_tool,
            set(body.tables),
            set(body.udfs),
            body.has_window,
            set(body.cross_db),
            body.has_dyn_part,
            body.subqueries,
            body.downstream,
        )
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ── POST /internal/neo4j-write ───────────────────────────────────────────

class Neo4jWriteBody(BaseModel):
    pipeline:         str
    upstream_tables:  list
    output_tables:    list
    downstream:       list
    udfs:             list
    complexity:       str
    estimated_effort: str


@router.post("/neo4j-write")
async def neo4j_write(body: Neo4jWriteBody):
    try:
        from modules.assess_subagent.tools.neo4j_write_graph_tool import neo4j_write_graph_tool
        result = await asyncio.to_thread(
            neo4j_write_graph_tool,
            body.pipeline,
            body.upstream_tables,
            body.output_tables,
            body.downstream,
            body.udfs,
            body.complexity,
            body.estimated_effort,
        )
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ── POST /internal/query-graph ───────────────────────────────────────────

class QueryGraphBody(BaseModel):
    pipeline: str
    query:    str = "summary"


@router.post("/query-graph")
async def query_graph(body: QueryGraphBody):
    try:
        from modules.assess_subagent.tools.query_graph_tool import query_graph_tool
        result = await asyncio.to_thread(query_graph_tool, body.pipeline, body.query)
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ===========================================================================
# CONVERT TOOLS
# ===========================================================================

# ── POST /internal/list-hql-files ────────────────────────────────────────

class ListHqlFilesBody(BaseModel):
    pipeline: str


@router.post("/list-hql-files")
async def list_hql_files(body: ListHqlFilesBody):
    try:
        from modules.convert_subagent.tools.list_hql_files_tool import list_hql_files_tool
        result = await asyncio.to_thread(list_hql_files_tool, body.pipeline)
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ── POST /internal/transform-hql ─────────────────────────────────────────
# NOTE: calls Claude API — may take up to 300 s

class TransformHqlBody(BaseModel):
    pipeline:  str
    filename:  str
    metadata:  dict


@router.post("/transform-hql")
async def transform_hql(body: TransformHqlBody):
    try:
        from modules.convert_subagent.tools.transform_hql_tool import transform_hql_tool
        result = await asyncio.to_thread(
            transform_hql_tool,
            body.filename,
            body.pipeline,
            body.metadata,
        )
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ── POST /internal/generate-dag ──────────────────────────────────────────

class GenerateDagBody(BaseModel):
    pipeline:   str
    files:      list
    complexity: str


@router.post("/generate-dag")
async def generate_dag(body: GenerateDagBody):
    try:
        from modules.convert_subagent.tools.generate_dag_tool import generate_dag_tool
        result = await asyncio.to_thread(
            generate_dag_tool,
            body.pipeline,
            body.files,
            body.complexity,
        )
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ===========================================================================
# RECONCILE TOOLS
# ===========================================================================

# ── POST /internal/validate-pyspark ──────────────────────────────────────

class ValidatePysparkBody(BaseModel):
    filename:     str
    spark_python: str
    source_hql:   Optional[str] = ""


@router.post("/validate-pyspark")
async def validate_pyspark(body: ValidatePysparkBody):
    try:
        from modules.reconcile_subagent.tools.validate_pyspark_tool import validate_pyspark_tool
        result = await asyncio.to_thread(
            validate_pyspark_tool,
            body.filename,
            body.spark_python,
            body.source_hql or "",
        )
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ── POST /internal/analyze-file ──────────────────────────────────────────

class AnalyzeFileBody(BaseModel):
    filename:    str
    hql_src:     str
    pyspark_src: str


@router.post("/analyze-file")
async def analyze_file(body: AnalyzeFileBody):
    try:
        from modules.reconcile_subagent.tools.analyze_file_tool import analyze_file_tool
        result = await asyncio.to_thread(
            analyze_file_tool,
            body.filename,
            body.hql_src,
            body.pyspark_src,
        )
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ── POST /internal/workflow-parity ───────────────────────────────────────

class WorkflowParityBody(BaseModel):
    conversion: dict


@router.post("/workflow-parity")
async def workflow_parity(body: WorkflowParityBody):
    try:
        from modules.reconcile_subagent.tools.workflow_parity_tool import workflow_parity_tool
        result = await asyncio.to_thread(workflow_parity_tool, body.conversion)
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ── POST /internal/runtime-validation ────────────────────────────────────

class RuntimeValidationBody(BaseModel):
    pipeline:   str
    complexity: str
    similarity: float


@router.post("/runtime-validation")
async def runtime_validation(body: RuntimeValidationBody):
    try:
        from modules.reconcile_subagent.tools.runtime_validation_tool import runtime_validation_tool
        result = await asyncio.to_thread(
            runtime_validation_tool,
            body.pipeline,
            body.complexity,
            body.similarity,
        )
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ── POST /internal/compile-report ────────────────────────────────────────

class CompileReportBody(BaseModel):
    pipeline:       str
    files_analysis: list
    workflow_check: dict
    runtime_checks: dict
    all_issues:     list


@router.post("/compile-report")
async def compile_report(body: CompileReportBody):
    try:
        from modules.reconcile_subagent.tools.compile_report_tool import compile_report_tool
        result = await asyncio.to_thread(
            compile_report_tool,
            body.pipeline,
            body.files_analysis,
            body.workflow_check,
            body.runtime_checks,
            body.all_issues,
        )
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ===========================================================================
# DEPLOY TOOLS
# ===========================================================================

# ── POST /internal/validate-artifacts ────────────────────────────────────

class ValidateArtifactsBody(BaseModel):
    conversion: dict
    reconcile:  dict


@router.post("/validate-artifacts")
async def validate_artifacts(body: ValidateArtifactsBody):
    try:
        from modules.deploy_subagent.tools.validate_artifacts_tool import validate_artifacts_tool
        result = await asyncio.to_thread(
            validate_artifacts_tool,
            body.conversion,
            body.reconcile,
        )
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ── POST /internal/generate-cicd ─────────────────────────────────────────

class GenerateCicdBody(BaseModel):
    pipeline:   str
    files:      list
    assessment: dict
    reconcile:  dict


@router.post("/generate-cicd")
async def generate_cicd(body: GenerateCicdBody):
    try:
        from modules.deploy_subagent.tools.generate_cicd_tool import generate_cicd_tool
        result = await asyncio.to_thread(
            generate_cicd_tool,
            body.pipeline,
            body.files,
            body.assessment,
            body.reconcile,
        )
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ── POST /internal/run-smoke-tests ───────────────────────────────────────

class RunSmokeTestsBody(BaseModel):
    pipeline:   str
    conversion: dict
    reconcile:  dict


@router.post("/run-smoke-tests")
async def run_smoke_tests(body: RunSmokeTestsBody):
    try:
        from modules.deploy_subagent.tools.run_smoke_tests_tool import run_smoke_tests_tool
        result = await asyncio.to_thread(
            run_smoke_tests_tool,
            body.pipeline,
            body.conversion,
            body.reconcile,
        )
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ── POST /internal/compute-governance ────────────────────────────────────

class ComputeGovernanceBody(BaseModel):
    artifact_checks: dict
    smoke_results:   dict
    reconcile:       dict


@router.post("/compute-governance")
async def compute_governance(body: ComputeGovernanceBody):
    try:
        from modules.deploy_subagent.tools.compute_governance_tool import compute_governance_tool
        result = await asyncio.to_thread(
            compute_governance_tool,
            body.artifact_checks,
            body.smoke_results,
            body.reconcile,
        )
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ── POST /internal/write-manifests ───────────────────────────────────────

class WriteManifestsBody(BaseModel):
    pipeline:        str
    assessment:      dict
    conversion:      dict
    reconcile:       dict
    artifact_checks: dict
    smoke_results:   dict
    governance:      dict
    cicd_yaml:       str


@router.post("/write-manifests")
async def write_manifests(body: WriteManifestsBody):
    try:
        from modules.deploy_subagent.tools.write_manifests_tool import write_manifests_tool
        result = await asyncio.to_thread(
            write_manifests_tool,
            body.pipeline,
            body.assessment,
            body.conversion,
            body.reconcile,
            body.artifact_checks,
            body.smoke_results,
            body.governance,
            body.cicd_yaml,
        )
        return _serialise(result)
    except Exception as e:
        return {"error": str(e)}


# ===========================================================================
# SKILLS
# ===========================================================================

# ── POST /internal/read-skill ────────────────────────────────────────────

class ReadSkillBody(BaseModel):
    name: str


_SKILL_SEARCH_PATHS: list[Path] = [
    _ROOT / "skills",
    _ROOT / "modules" / "assess_subagent"    / "skills",
    _ROOT / "modules" / "convert_subagent"   / "skills",
    _ROOT / "modules" / "reconcile_subagent" / "skills",
    _ROOT / "modules" / "deploy_subagent"    / "skills",
    _ROOT / "modules" / "repair_code"        / "skills",
]


@router.post("/read-skill")
async def read_skill(body: ReadSkillBody):
    try:
        name = body.name
        stem = name[:-3] if name.endswith(".md") else name
        filename = stem + ".md"

        for directory in _SKILL_SEARCH_PATHS:
            candidate = directory / filename
            if candidate.exists():
                content = await asyncio.to_thread(candidate.read_text, "utf-8")
                return {"name": stem, "content": content}

        return {"error": "not found"}
    except Exception as e:
        return {"error": str(e)}


# ── GET /internal/list-skills ─────────────────────────────────────────────

@router.get("/list-skills")
async def list_skills():
    try:
        names = []
        seen = set()
        for directory in _SKILL_SEARCH_PATHS:
            if directory.exists():
                for f in sorted(directory.glob("*.md")):
                    if f.stem not in seen:
                        names.append(f.stem)
                        seen.add(f.stem)
        return {"skills": names}
    except Exception as e:
        return {"error": str(e)}

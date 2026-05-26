"""
DTCM Migration Agent — RLM invocation.

The RLM reads migration_flow skill first, then uses tools to orchestrate
the full assess → convert → reconcile → deploy pipeline.

Tools:
  read_skill          load any skill from skills/
  scan_repo           list HQL files in a pipeline
  parse_hql           parse one HQL file (tables, UDFs, syntax)
  lineage_extract     derive upstream/downstream table dependencies
  classify_complexity score and classify migration complexity
  neo4j_write         persist lineage graph to Neo4j
  query_graph         query Neo4j (blast_radius, wave, summary)
  transform_hql       convert HQL → PySpark via Claude Sonnet
  generate_dag        generate MWAA Airflow DAG
  validate_pyspark    static PySpark validation (syntax, imports, write ops)
  analyze_file        8-dimension semantic comparison HQL vs PySpark
  workflow_parity     check DAG structure matches conversion
  runtime_validation  simulated runtime checks (row count, checksum, SLA)
  compile_report      compile reconciliation report with confidence score
  validate_artifacts  validate PySpark files and DAG structure
  generate_cicd       generate CI/CD pipeline YAML
  run_smoke_tests     run smoke test suite (4 real + 3 simulated)
  compute_governance  compute readiness score and governance approval
  write_manifests     write output JSON manifests to disk
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parents[1] / ".env")

import anthropic  # noqa: F401 — ensures Anthropic client is importable
from fast_rlm import run, RLMConfig
from event_queue import push

from .tools import (
    list_skills, read_skill,
    scan_repo, parse_hql, lineage_extract, classify_complexity,
    neo4j_write, query_graph,
    transform_hql, generate_dag,
    validate_pyspark, analyze_file, workflow_parity,
    runtime_validation, compile_report,
    validate_artifacts, generate_cicd, run_smoke_tests,
    compute_governance, write_manifests,
)

# Deno required by fast-rlm
_DENO = Path.home() / ".deno" / "bin"
if str(_DENO) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(_DENO) + ":" + os.environ.get("PATH", "")

TOOLS = [
    list_skills, read_skill,
    scan_repo, parse_hql, lineage_extract, classify_complexity,
    neo4j_write, query_graph,
    transform_hql, generate_dag,
    validate_pyspark, analyze_file, workflow_parity,
    runtime_validation, compile_report,
    validate_artifacts, generate_cicd, run_smoke_tests,
    compute_governance, write_manifests,
]

NAME = "rlm_agent"

CONFIG = RLMConfig(
    primary_agent          = os.getenv("RLM_PRIMARY_MODEL", "claude-sonnet-4-6"),
    max_depth              = 4,
    max_calls_per_subagent = 60,
    truncate_len           = 6000,
    max_money_spent        = 5.0,
)

ENV = {k: v for k, v in {
    "DTCM_BACKEND_URL":   os.getenv("DTCM_BACKEND_URL", "http://localhost:8001"),
    "RLM_MODEL_BASE_URL": os.getenv("RLM_MODEL_BASE_URL", ""),
    "RLM_MODEL_API_KEY":  os.getenv("RLM_MODEL_API_KEY", ""),
}.items() if v}


async def run_migration(pipeline_name: str) -> dict:
    async def _e(msg: str, etype: str = "status") -> None:
        await push(type=etype, agent=NAME, message=msg, pipeline=pipeline_name)

    await _e(f"RLM started — {pipeline_name}", "delegation")

    result = await asyncio.to_thread(
        run,
        query         = {
            "pipeline":    pipeline_name,
            "instruction": (
                "Work one tool at a time. Call one tool, observe the result, "
                "reason about what it means, then decide what to call next. "
                "Do not write multi-step scripts upfront. "
                "Start: call list_skills(), then read_skill('migration_flow'). "
                "migration_flow will tell you which skills to read for each phase — "
                "read each of those skills by their exact name before using any tools. "
                "Run the ASSESS phase only. Do not run CONVERT, RECONCILE, or DEPLOY."
            ),
        },
        tools         = TOOLS,
        config        = CONFIG,
        verbose       = True,
        env_variables = ENV,
    )

    output = result.get("results", {})
    if isinstance(output, str):
        output = {"outcome": "FAILED", "summary": output}
    outcome = output.get("outcome", "UNKNOWN") if isinstance(output, dict) else "FAILED"
    await _e(f"Migration {outcome} — {output.get('summary', '')}", "complete")
    return output

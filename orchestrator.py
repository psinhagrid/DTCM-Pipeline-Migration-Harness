"""
RLM-based orchestrator — replaces the supervisor agent loop with fast_rlm.run().

The RLM drives the full migration lifecycle (assess → convert → reconcile → deploy)
by calling subagents registered as self-contained HTTP tool functions.  Each tool
POSTs to a dedicated FastAPI endpoint on this server, which runs the real subagent
and returns the result.  The RLM reasons over the results and produces a structured
final output after reconciliation validation — no human-in-the-loop feedback loop.

Architecture:
  fast_rlm.run()
    → assess_pipeline   tool  → POST /subagent/assess
    → convert_pipeline  tool  → POST /subagent/convert
    → reconcile_pipeline tool → POST /subagent/reconcile   ← primary validation
    → deploy_pipeline   tool  → POST /subagent/deploy
    → repair_pipeline   tool  → POST /subagent/repair  (optional, on low confidence)
"""

import asyncio
import os
from pathlib import Path

import fast_rlm

DEFAULT_PIPELINE = "daily_revenue_agg"

# Result stores populated after run_pipeline() completes — read by API endpoints
results:         dict = {}
conversions:     dict = {}
reconciliations: dict = {}
deployments:     dict = {}


# ── Subagent tool functions ───────────────────────────────────────────────────
# These execute inside the fast_rlm Pyodide REPL (WebAssembly Python).
# Rules: all imports must be INSIDE the function body; no closures over
# module-level state.  The RLM sees only the signature, type hints, and docstring.

def read_migration_rules() -> str:
    """Read the full migration rules for this system.

    Call this whenever you need to plan or replan. Specifically:
      1. As the very first action — before writing any plan or calling any tool.
      2. After reconcile_pipeline returns — before deciding to deploy.
      3. After repair_pipeline returns — before deciding what to do next.
      4. Any other time you are unsure what the next step should be.

    Returns a markdown string covering all 4 parts:
      Part 1: Migration flow (step order, repair triggers)
      Part 2: Deployment decision rules (RULES 1-4, decision table)
      Part 3: Replanning rules (after repair, after exceptions)
      Part 4: FINAL output contract (required keys)
    """
    # NOTE: Pyodide runs in a WebAssembly sandbox — host filesystem is inaccessible.
    # Rules are served via HTTP from the FastAPI server instead.
    import requests, os
    base = os.environ.get("DTCM_SERVER_URL", "http://localhost:8001")
    resp = requests.get(f"{base}/skills/migration_rules", timeout=10)
    resp.raise_for_status()
    return resp.text


def assess_pipeline(pipeline_name: str) -> dict:
    """STEP 1 — Always call this first before anything else.

    Scans all HiveQL source files for the pipeline.  Extracts tables, UDFs,
    complexity classification (SMALL|MEDIUM|LARGE|COMPLEX), lineage, and writes
    the lineage graph to Neo4j.

    Args:
        pipeline_name: Name of the pipeline directory, e.g. 'daily_revenue_agg'.

    Returns dict with keys:
        pipeline (str), hql_files (list[str]), tables (list[str]),
        udfs (list[str]), has_window (bool), cross_db (list[str]),
        complexity (str: SMALL|MEDIUM|LARGE|COMPLEX), estimated_effort (str),
        upstream (list[str]), downstream (list[str]).

    Pass the full returned dict as `assessment` to convert_pipeline.
    Do NOT call convert_pipeline until this completes successfully.
    If syntax_errors are present in the result, call repair_pipeline(target='hql') first.
    """
    import requests, os, json as _json
    base = os.environ.get("DTCM_SERVER_URL", "http://localhost:8001")
    resp = requests.post(f"{base}/subagent/assess", params={"pipeline": pipeline_name}, timeout=600)
    resp.raise_for_status()
    data = resp.text
    if not data:
        raise RuntimeError("assess_pipeline: empty response from server")
    # pyodide-http may return str instead of dict from .json() — always parse from text
    return _json.JSONDecoder().raw_decode(data)[0]


def convert_pipeline(pipeline_name: str, assessment: dict) -> dict:
    """STEP 2 — Call only after assess_pipeline returns successfully.

    Converts each HiveQL file to PySpark via LLM and generates an MWAA Airflow DAG.
    Requires the full assessment dict from assess_pipeline.

    Args:
        pipeline_name: Name of the pipeline directory.
        assessment: Full dict returned by assess_pipeline.

    Returns dict with keys:
        pipeline (str), files (list[str]: python_filename values),
        dag_filename (str), dag_content (str),
        transformations_applied (int), status (str: SUCCESS|HALTED|ERROR).

    Pass the full returned dict as `conversion` to reconcile_pipeline.
    Do NOT call reconcile_pipeline until this completes successfully.
    """
    import requests, os, json as _json
    base = os.environ.get("DTCM_SERVER_URL", "http://localhost:8001")
    resp = requests.post(f"{base}/subagent/convert", params={"pipeline": pipeline_name}, json=assessment, timeout=600)
    resp.raise_for_status()
    data = resp.text
    if not data:
        raise RuntimeError("convert_pipeline: empty response from server")
    return _json.JSONDecoder().raw_decode(data)[0]


def reconcile_pipeline(pipeline_name: str, assessment: dict, conversion: dict) -> dict:
    """STEP 3 — Call only after convert_pipeline returns successfully.

    Validates the PySpark conversion against the original HiveQL across 8 semantic
    dimensions, checks workflow/DAG parity, and runs runtime validation.
    This is the PRIMARY validation gate for the migration.

    Args:
        pipeline_name: Name of the pipeline directory.
        assessment: Full dict returned by assess_pipeline.
        conversion: Full dict returned by convert_pipeline.

    Returns dict with keys:
        pipeline (str), validation_status (str: PASSED|FAILED|WARNING),
        confidence_score (float 0.0–1.0), migration_risk (str: LOW|MEDIUM|HIGH),
        issues (list[str]), files_analyzed (int).

    After this returns, call read_migration_rules() to load the full deployment
    decision rules, then apply them to determine whether to call deploy_pipeline
    and what final_status to set.

    This result is the final validation output — always include it in FINAL
    as 'reconciliation'.
    """
    import requests, os, json as _json
    base = os.environ.get("DTCM_SERVER_URL", "http://localhost:8001")
    resp = requests.post(f"{base}/subagent/reconcile", params={"pipeline": pipeline_name}, json={"assessment": assessment, "conversion": conversion}, timeout=600)
    resp.raise_for_status()
    data = resp.text
    if not data:
        raise RuntimeError("reconcile_pipeline: empty response from server")
    return _json.JSONDecoder().raw_decode(data)[0]


def deploy_pipeline(pipeline_name: str, assessment: dict, conversion: dict, reconcile: dict) -> dict:
    """STEP 4 — Call only after reconcile_pipeline passes RULES 3 or 4.
    NEVER call if reconcile_pipeline returned validation_status == 'FAILED' (RULE 1).
    NEVER call if reconcile_pipeline returned confidence_score < 0.60 (RULE 2).

    Validates artifacts, generates CI/CD YAML, stages DAG to MWAA non-prod,
    runs smoke tests, computes governance readiness score, and writes manifests.

    Args:
        pipeline_name: Name of the pipeline directory.
        assessment: Full dict returned by assess_pipeline.
        conversion: Full dict returned by convert_pipeline.
        reconcile: Full dict returned by reconcile_pipeline.

    Returns dict with keys:
        pipeline (str), readiness_score (int 0–100),
        governance (dict with keys: state APPROVED|CONDITIONAL|BLOCKED, label, conditions),
        smoke_tests (dict with keys: passed, total, score),
        output_dir (str), files_written (list[str]).
    On server error returns dict with key 'error' (str) — handle gracefully.

    Include this result in FINAL as 'deployment'.
    """
    import requests, os, json as _json
    base = os.environ.get("DTCM_SERVER_URL", "http://localhost:8001")
    resp = requests.post(f"{base}/subagent/deploy", params={"pipeline": pipeline_name}, json={"assessment": assessment, "conversion": conversion, "reconcile": reconcile}, timeout=600)
    data = resp.text
    if not data:
        return {"error": f"deploy_pipeline: empty response (HTTP {resp.status_code})"}
    return _json.JSONDecoder().raw_decode(data)[0]


def repair_pipeline(pipeline_name: str, target: str = "hql") -> dict:
    """OPTIONAL — Call when assess finds syntax_errors or reconcile confidence_score < 0.60.

    Applies LLM-driven line-level fixes to source files.  Writes accepted fixes
    back to the original file locations with automatic .bak backups.

    Args:
        pipeline_name: Name of the pipeline directory.
        target: Which files to repair — 'hql' for source HiveQL files (use when
                assess_pipeline reports syntax_errors), or 'pyspark' for generated
                PySpark files (use when reconcile_pipeline confidence_score < 0.60).

    Returns dict with keys:
        files_fixed (list[str]), issues_skipped (list[str]),
        status (str: SUCCESS|PARTIAL|HALTED).

    After repair completes, call read_migration_rules() before replanning —
    Part 3 of the rules specifies exactly what to do next for each repair target.
    """
    import requests, os, json as _json
    base = os.environ.get("DTCM_SERVER_URL", "http://localhost:8001")
    resp = requests.post(f"{base}/subagent/repair", params={"pipeline": pipeline_name, "target": target}, timeout=600)
    resp.raise_for_status()
    data = resp.text
    if not data:
        raise RuntimeError("repair_pipeline: empty response from server")
    return _json.JSONDecoder().raw_decode(data)[0]


# ── Output schema ─────────────────────────────────────────────────────────────

_MIGRATION_SCHEMA = {
    "type": "object",
    "properties": {
        "pipeline":       {"type": "string"},
        "assessment":     {"type": "object"},
        "conversion":     {"type": "object"},
        "reconciliation": {"type": "object"},
        "deployment":     {"type": "object"},
        "final_status":   {"type": "string", "enum": ["PASSED", "WARNING", "FAILED", "ERROR"]},
        "summary":        {"type": "string"},
    },
    "required": ["pipeline", "assessment", "conversion", "reconciliation", "final_status", "summary"],
}


# ── RLM runner ────────────────────────────────────────────────────────────────

async def run_pipeline(pipeline_name: str = DEFAULT_PIPELINE) -> dict | None:
    # Route fast-rlm through Anthropic's OpenAI-compatible endpoint using the
    # existing ANTHROPIC_API_KEY — avoids needing a separate OpenRouter key.
    os.environ["RLM_MODEL_API_KEY"]  = os.environ.get("ANTHROPIC_API_KEY", "")
    os.environ["RLM_MODEL_BASE_URL"] = os.environ.get("RLM_MODEL_BASE_URL", "https://api.anthropic.com/v1")

    config = fast_rlm.RLMConfig.default()
    # Anthropic-direct model names (no "anthropic/" OpenRouter prefix)
    config.primary_agent       = os.getenv("RLM_PRIMARY_AGENT", "claude-sonnet-4-6")
    config.sub_agent           = os.getenv("RLM_SUB_AGENT",     "claude-sonnet-4-6")
    config.max_depth           = 1
    config.max_calls_per_subagent = 30
    config.max_money_spent     = float(os.getenv("RLM_MAX_SPEND", "20.0"))

    query = {
        "task": (
            f"Migrate HiveQL pipeline '{pipeline_name}' to PySpark. "
            "Step 0 (mandatory): Call read_migration_rules() FIRST before writing any plan or "
            "calling any other tool. Read and internalize all 4 parts. "
            "Call read_migration_rules() again whenever you need to plan or replan — "
            "after reconcile_pipeline returns, after repair_pipeline returns, "
            "or any time you are unsure what the next step should be. "
            "Always follow the rules exactly as specified."
        ),
        "pipeline_name": pipeline_name,
    }

    data = await asyncio.to_thread(
        fast_rlm.run,
        query,
        tools=[
            read_migration_rules,
            assess_pipeline,
            convert_pipeline,
            reconcile_pipeline,
            deploy_pipeline,
            repair_pipeline,
        ],
        output_schema=_MIGRATION_SCHEMA,
        config=config,
        prefix=f"migration_{pipeline_name}",
        env_variables={
            "DTCM_SERVER_URL": os.getenv("DTCM_SERVER_URL", "http://localhost:8001"),
        },
    )

    migration = data.get("results") or {}

    results[pipeline_name]         = migration.get("assessment",     {})
    conversions[pipeline_name]     = migration.get("conversion",     {})
    reconciliations[pipeline_name] = migration.get("reconciliation", {})
    deployments[pipeline_name]     = migration.get("deployment",     {})

    return results.get(pipeline_name)

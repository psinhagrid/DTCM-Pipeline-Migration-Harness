"""
DTCM Migration Agent — RLM invocation.
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parents[1] / ".env")

import anthropic  # noqa: F401
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
    max_depth              = 3,
    max_calls_per_subagent = 25,
    truncate_len           = 1500,
    max_prompt_tokens      = 180000,
    max_money_spent        = 5.0,
)

ENV = {k: v for k, v in {
    "DTCM_BACKEND_URL":   os.getenv("DTCM_BACKEND_URL", "http://localhost:8001"),
    "RLM_MODEL_BASE_URL": os.getenv("RLM_MODEL_BASE_URL", ""),
    "RLM_MODEL_API_KEY":  os.getenv("RLM_MODEL_API_KEY", ""),
}.items() if v}

LOG_DIR = Path(__file__).parents[1] / "logs"


def _extract_plan(code: str) -> str:
    """Extract meaningful lines from agent code — comments + first tool calls."""
    if not code:
        return ""
    lines = code.splitlines()
    plan_lines = []
    tool_calls = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            text = stripped.lstrip("#").strip()
            if len(text) > 3:
                plan_lines.append(text)
        elif "(" in stripped and not stripped.startswith("print") and tool_calls < 4:
            # First few function calls show intent
            call = stripped.split("(")[0].split("=")[-1].strip()
            if call and not call.startswith("_") and len(call) > 2:
                plan_lines.append(f"→ {call}(...)")
                tool_calls += 1
    return " · ".join(plan_lines[:4]) if plan_lines else ""


async def _stream_reasoning(pipeline: str, stop_event: asyncio.Event, run_started_at: float) -> None:
    """Watch the log file created for THIS run only."""
    log_path = None
    seen_bytes = 0
    seen_steps: set = set()

    while not stop_event.is_set():
        if log_path is None:
            # Only pick up log files created AFTER this run started
            logs = sorted(LOG_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
            new_logs = [l for l in logs if l.stat().st_mtime >= run_started_at]
            if new_logs:
                log_path = new_logs[0]
                seen_bytes = 0

        if log_path and log_path.exists():
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    f.seek(seen_bytes)
                    new = f.read()
                    seen_bytes = f.tell()

                for line in new.splitlines():
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                    except Exception:
                        continue

                    event_type = entry.get("event_type")
                    step = entry.get("step")

                    if event_type in ("execution_result", "code_generated") and step not in seen_steps and step is not None:
                        seen_steps.add(step)
                        code = entry.get("code", "")
                        plan = _extract_plan(code)
                        if plan and step > 0:
                            await push(
                                type="reasoning",
                                agent=NAME,
                                message=plan,
                                step=step,
                                pipeline=pipeline,
                                code=code,
                            )
            except Exception:
                pass

        await asyncio.sleep(0.4)


async def run_migration(pipeline_name: str) -> dict:
    async def _e(msg: str, etype: str = "status") -> None:
        await push(type=etype, agent=NAME, message=msg, pipeline=pipeline_name)

    await _e(f"RLM started — {pipeline_name}", "delegation")

    import time
    run_started_at = time.time()
    stop_event = asyncio.Event()
    watcher = asyncio.create_task(_stream_reasoning(pipeline_name, stop_event, run_started_at))

    output_schema = {
        "type": "object",
        "required": ["pipeline", "outcome", "summary", "assessment"],
        "properties": {
            "pipeline":   {"type": "string"},
            "outcome":    {"type": "string", "enum": ["SUCCESS", "PARTIAL", "HALTED", "FAILED"]},
            "summary":    {"type": "string"},
            "assessment": {"type": "object"},
            "conversion":     {"type": "object"},
            "reconciliation": {"type": "object"},
            "deployment":     {"type": "object"},
        },
    }

    try:
        result = await asyncio.to_thread(
            run,
            query={
                "pipeline":    pipeline_name,
                "instruction": (
                    "Run the full migration pipeline: ASSESS → CONVERT → RECONCILE → DEPLOY. "
                    "Start by calling list_skills() then read_skill('migration_flow'). "
                    "migration_flow tells you the phase order and which skills to read for each phase — "
                    "read each skill by its exact name before using any tools in that phase. "
                    "After each phase reason about the results before proceeding to the next. "
                    "CRITICAL — ASSESS phase file rule: call scan_repo(pipeline) first and capture its result. "
                    "The result has a key 'hql_files' containing the ACTUAL list of filenames that exist. "
                    "Call parse_hql(pipeline, filename) for EACH filename in that hql_files list and no others. "
                    "NEVER guess, invent, or hardcode any filename — only use what scan_repo returned."
                ),
            },
            tools=TOOLS,
            config=CONFIG,
            output_schema=output_schema,
            verbose=True,
            env_variables=ENV,
        )
    finally:
        await asyncio.sleep(0.6)  # flush last log entries
        stop_event.set()
        watcher.cancel()

    output = result.get("results", {})
    if isinstance(output, str):
        output = {"outcome": "FAILED", "summary": output}
    if not isinstance(output, dict):
        output = {"outcome": "FAILED", "summary": str(output)}
    # Infer outcome from assessment if agent forgot to set it
    if not output.get("outcome"):
        has_assessment = bool(output.get("assessment"))
        output["outcome"] = "SUCCESS" if has_assessment else "FAILED"
    outcome = output.get("outcome", "FAILED")
    await _e(f"Migration {outcome} — {output.get('summary', '')}", "complete")
    return output

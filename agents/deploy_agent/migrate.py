"""
DEPLOY Agent — validates artifacts, runs smoke tests, computes governance,
generates CI/CD YAML, writes manifests. Receives all prior phase outputs as context.
"""

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parents[2] / ".env")

import anthropic  # noqa: F401
from fast_rlm import run, RLMConfig
from event_queue import push

from .tools import (
    read_skill,
    validate_artifacts, run_smoke_tests, compute_governance,
    generate_cicd, write_manifests,
    query_graph,
)

_DENO = Path.home() / ".deno" / "bin"
if str(_DENO) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(_DENO) + ":" + os.environ.get("PATH", "")

TOOLS = [
    read_skill,
    validate_artifacts, run_smoke_tests, compute_governance,
    generate_cicd, write_manifests,
    query_graph,
]

NAME = "deploy_agent"

CONFIG = RLMConfig(
    primary_agent          = os.getenv("RLM_PRIMARY_MODEL", "claude-sonnet-4-6"),
    max_depth              = 3,
    max_calls_per_subagent = 20,
    truncate_len           = 1500,
    max_prompt_tokens      = 180000,
    max_money_spent        = 2.0,
)

ENV = {k: v for k, v in {
    "DTCM_BACKEND_URL":   os.getenv("DTCM_BACKEND_URL", "http://localhost:8001"),
    "RLM_MODEL_BASE_URL": os.getenv("RLM_MODEL_BASE_URL", ""),
    "RLM_MODEL_API_KEY":  os.getenv("RLM_MODEL_API_KEY", ""),
}.items() if v}

LOG_DIR = Path(__file__).parents[2] / "logs"


def _extract_plan(code: str) -> str:
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
            call = stripped.split("(")[0].split("=")[-1].strip()
            if call and not call.startswith("_") and len(call) > 2:
                plan_lines.append(f"→ {call}(...)")
                tool_calls += 1
    return " · ".join(plan_lines[:4]) if plan_lines else ""


async def _stream_reasoning(pipeline: str, stop_event: asyncio.Event, run_started_at: float) -> None:
    log_path = None
    seen_bytes = 0
    seen_steps: set = set()

    while not stop_event.is_set():
        if log_path is None:
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
                    if event_type == "execution_result" and step not in seen_steps and step is not None:
                        seen_steps.add(step)
                        code = entry.get("code", "")
                        plan = _extract_plan(code)
                        if plan and step > 0:
                            await push(type="reasoning", agent=NAME, message=plan,
                                       step=step, pipeline=pipeline, code=code)
            except Exception:
                pass

        await asyncio.sleep(0.4)


async def run_deploy(pipeline_name: str, assessment: dict, conversion: dict, reconciliation: dict) -> dict:
    async def _e(msg: str, etype: str = "status") -> None:
        await push(type=etype, agent=NAME, message=msg, pipeline=pipeline_name)

    await _e(f"DEPLOY started — {pipeline_name}", "delegation")

    import time
    run_started_at = time.time()
    stop_event = asyncio.Event()
    watcher = asyncio.create_task(_stream_reasoning(pipeline_name, stop_event, run_started_at))

    output_schema = {
        "type": "object",
        "required": ["pipeline", "outcome", "summary", "deployment"],
        "properties": {
            "pipeline":   {"type": "string"},
            "outcome":    {"type": "string", "enum": ["SUCCESS", "PARTIAL", "HALTED", "FAILED"]},
            "summary":    {"type": "string"},
            "deployment": {"type": "object"},
        },
    }

    try:
        result = await asyncio.to_thread(
            run,
            query={
                "pipeline":       pipeline_name,
                "assessment":     assessment,
                "conversion":     conversion,
                "reconciliation": reconciliation,
                "instruction": (
                    "Run the DEPLOY phase for this pipeline. "
                    "Start by calling read_skill('artifact_validation') — it tells you exactly which "
                    "tools to call and in what order. Prior results are in context['assessment'], "
                    "context['conversion'], context['reconciliation']. "
                    "Call FINAL() with the full deployment result when done."
                ),
            },
            tools=TOOLS,
            config=CONFIG,
            output_schema=output_schema,
            verbose=True,
            env_variables=ENV,
        )
    finally:
        await asyncio.sleep(0.6)
        stop_event.set()
        watcher.cancel()

    output = result.get("results", {})
    if isinstance(output, str):
        output = {"outcome": "FAILED", "summary": output}
    if not isinstance(output, dict):
        output = {"outcome": "FAILED", "summary": str(output)}
    if not output.get("outcome"):
        output["outcome"] = "SUCCESS" if output.get("deployment") else "FAILED"
    outcome = output.get("outcome", "FAILED")
    await _e(f"DEPLOY {outcome} — {output.get('summary', '')}", "complete")
    return output

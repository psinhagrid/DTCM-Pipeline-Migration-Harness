"""
ORCHESTRATOR Agent — sequences ASSESS → CONVERT → RECONCILE → DEPLOY,
asking for human approval at each phase transition.
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
    run_assess_phase,
    run_convert_phase,
    run_reconcile_phase,
    run_deploy_phase,
    query_graph,
    request_human_approval,
)

_DENO = Path.home() / ".deno" / "bin"
if str(_DENO) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(_DENO) + ":" + os.environ.get("PATH", "")

TOOLS = [
    read_skill,
    run_assess_phase,
    run_convert_phase,
    run_reconcile_phase,
    run_deploy_phase,
    query_graph,
    request_human_approval,
]

NAME = "orchestrator_agent"

CONFIG = RLMConfig(
    primary_agent          = os.getenv("RLM_PRIMARY_MODEL", "claude-sonnet-4-6"),
    max_depth              = 2,
    max_calls_per_subagent = 16,
    truncate_len           = 2000,
    max_prompt_tokens      = 180000,
    max_money_spent        = 1.5,
)

ENV = {k: v for k, v in {
    "DTCM_BACKEND_URL":   os.getenv("DTCM_BACKEND_URL", "http://localhost:8001"),
    "RLM_MODEL_BASE_URL": os.getenv("RLM_MODEL_BASE_URL", ""),
    "RLM_MODEL_API_KEY":  os.getenv("RLM_MODEL_API_KEY", ""),
}.items() if v}


async def run_orchestrator(pipeline_name: str) -> dict:
    async def _e(msg: str, etype: str = "status") -> None:
        await push(type=etype, agent=NAME, message=msg, pipeline=pipeline_name)

    await _e(f"ORCHESTRATOR started — {pipeline_name}", "delegation")

    output_schema = {
        "type": "object",
        "required": ["pipeline", "outcome", "summary"],
        "properties": {
            "pipeline":       {"type": "string"},
            "outcome":        {"type": "string", "enum": ["SUCCESS", "PARTIAL", "HALTED", "FAILED"]},
            "summary":        {"type": "string"},
            "assessment":     {"type": "object"},
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
                    "You are the migration orchestrator. "
                    "Start by calling read_skill('orchestrator') — it gives you the exact code "
                    "structure to run all four phases with human approval gates. "
                    "Follow it precisely and call FINAL() with the migration outcome when done."
                ),
            },
            tools=TOOLS,
            config=CONFIG,
            output_schema=output_schema,
            verbose=True,
            env_variables=ENV,
        )
    except Exception as exc:
        await _e(f"ORCHESTRATOR error — {exc}", "complete")
        return {"pipeline": pipeline_name, "outcome": "FAILED", "summary": str(exc)}

    output = result.get("results", {})
    if isinstance(output, str):
        output = {"outcome": "FAILED", "summary": output}
    if not isinstance(output, dict):
        output = {"outcome": "FAILED", "summary": str(output)}
    if not output.get("outcome"):
        output["outcome"] = "SUCCESS" if output.get("assessment") else "FAILED"

    outcome = output.get("outcome", "FAILED")
    await _e(f"ORCHESTRATOR {outcome} — {output.get('summary', '')}", "complete")
    return output

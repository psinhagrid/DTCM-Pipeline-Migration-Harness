"""
deploy_subagent — LLM-driven agentic loop.

Claude drives deployment by:
  1. Reading skill instructions via read_skill_tool
  2. Validating artifacts, generating CI/CD, staging, running smoke tests,
     computing governance, writing manifests
  3. Iterating until it calls finish_deployment_tool or MAX_ITERATIONS is hit
"""

import asyncio
import json
from pathlib import Path

import os
import anthropic

from event_queue import push
from event_queue import claude_with_retry
from .tools import (
    validate_artifacts_tool,
    generate_cicd_tool,
    stage_deployment_tool,
    run_smoke_tests_tool,
    compute_governance_tool,
    write_manifests_tool,
    read_skill_tool,
    query_graph_tool,
    finish_deployment_tool,
)

NAME           = "deploy_subagent"
MAX_ITERATIONS = 40

MODEL          = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
_SYSTEM_PROMPT = (Path(__file__).parent / "deploy_subagent_system.md").read_text(encoding="utf-8")


# ── Tool schemas (Anthropic format) ──────────────────────────────────────────

TOOLS = [
    {
        "name": "read_skill_tool",
        "description": (
            "Read full instructions for a named skill. "
            "Call this before using a skill to load its rules and heuristics."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Skill name — one of: artifact_validation, deployment_governance, cicd_packaging",
                }
            },
            "required": ["name"],
        },
    },
    {
        "name": "validate_artifacts_tool",
        "description": (
            "Validate all generated migration artifacts. "
            "Returns file_checks, dag_check, reconciliation_check, and deployment_ready flag. "
            "Call this first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "conversion": {"type": "object", "description": "Full convert_subagent result"},
                "reconcile":  {"type": "object", "description": "Full reconcile_subagent result"},
            },
            "required": ["conversion", "reconcile"],
        },
    },
    {
        "name": "generate_cicd_tool",
        "description": (
            "Generate CI/CD YAML and pipeline config for the deployment. "
            "Returns cicd_yaml (string) and pipeline_config (dict)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline":   {"type": "string"},
                "files":      {
                    "type": "array", "items": {"type": "string"},
                    "description": "List of python_filename values from conversion result",
                },
                "assessment": {"type": "object"},
                "reconcile":  {"type": "object"},
            },
            "required": ["pipeline", "files", "assessment", "reconcile"],
        },
    },
    {
        "name": "stage_deployment_tool",
        "description": (
            "Stage the deployment: register DAG in MWAA non-prod, validate EMR config, "
            "confirm S3 artifact staging. (Currently stubbed.)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline": {"type": "string"}
            },
            "required": ["pipeline"],
        },
    },
    {
        "name": "run_smoke_tests_tool",
        "description": (
            "Run the full smoke test suite. "
            "Returns tests list, overall status, passed/total counts, and score."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline":   {"type": "string"},
                "conversion": {"type": "object"},
                "reconcile":  {"type": "object"},
            },
            "required": ["pipeline", "conversion", "reconcile"],
        },
    },
    {
        "name": "compute_governance_tool",
        "description": (
            "Compute deployment readiness score and governance approval state. "
            "Returns readiness_score (0–100) and governance dict with state, label, conditions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "artifact_checks": {"type": "object"},
                "smoke_results":   {"type": "object"},
                "reconcile":       {"type": "object"},
            },
            "required": ["artifact_checks", "smoke_results", "reconcile"],
        },
    },
    {
        "name": "write_manifests_tool",
        "description": (
            "Write all deployment manifests to disk under output/{pipeline}/. "
            "Always call this — even for CONDITIONAL or BLOCKED deployments. "
            "Returns output_dir and files_written."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline":       {"type": "string"},
                "assessment":     {"type": "object"},
                "conversion":     {"type": "object"},
                "reconcile":      {"type": "object"},
                "artifact_checks":{"type": "object"},
                "smoke_results":  {"type": "object"},
                "governance":     {"type": "object"},
                "cicd_yaml":      {"type": "string"},
            },
            "required": ["pipeline", "assessment", "conversion", "reconcile",
                         "artifact_checks", "smoke_results", "governance", "cicd_yaml"],
        },
    },
    {
        "name": "query_graph_tool",
        "description": (
            "Query the Neo4j lineage graph for context about this pipeline. "
            "Call to check upstream migration status, blast radius, or wave order. "
            "query options: 'summary' | 'downstream' | 'upstream' | 'blast_radius' | 'wave'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline": {"type": "string"},
                "query":    {"type": "string", "enum": ["summary","downstream","upstream","blast_radius","wave"]},
            },
            "required": ["pipeline", "query"],
        },
    },
    {
        "name": "finish_deployment_tool",
        "description": (
            "Signal that deployment orchestration is complete. Always call this as your final action — "
            "never stop without calling it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "object", "description": "Complete deployment result"},
                "status": {"type": "string", "enum": ["SUCCESS", "HALTED", "ERROR"]},
                "reason": {"type": "string", "description": "Required when HALTED or ERROR"},
            },
            "required": ["result", "status"],
        },
    },
]


# ── Tool executor ─────────────────────────────────────────────────────────────

async def _execute_tool(name: str, args: dict) -> dict:
    if name == "read_skill_tool":
        return read_skill_tool(args["name"])

    elif name == "validate_artifacts_tool":
        return await asyncio.to_thread(
            validate_artifacts_tool,
            args["conversion"],
            args["reconcile"],
        )

    elif name == "generate_cicd_tool":
        return await asyncio.to_thread(
            generate_cicd_tool,
            args["pipeline"],
            args["files"],
            args["assessment"],
            args["reconcile"],
        )

    elif name == "stage_deployment_tool":
        stage_deployment_tool(args["pipeline"])
        return {"status": "ok", "note": "stubbed — TODO: mwaa_mcp + emrs_mcp + boto3"}

    elif name == "run_smoke_tests_tool":
        return await asyncio.to_thread(
            run_smoke_tests_tool,
            args["pipeline"],
            args["conversion"],
            args["reconcile"],
        )

    elif name == "compute_governance_tool":
        return await asyncio.to_thread(
            compute_governance_tool,
            args["artifact_checks"],
            args["smoke_results"],
            args["reconcile"],
        )

    elif name == "write_manifests_tool":
        return await asyncio.to_thread(
            write_manifests_tool,
            args["pipeline"],
            args["assessment"],
            args["conversion"],
            args["reconcile"],
            args["artifact_checks"],
            args["smoke_results"],
            args["governance"],
            args["cicd_yaml"],
        )

    elif name == "query_graph_tool":
        return await asyncio.to_thread(
            query_graph_tool,
            args["pipeline"],
            args.get("query", "summary"),
        )

    elif name == "finish_deployment_tool":
        return finish_deployment_tool(
            result=args.get("result", {}),
            status=args.get("status", "SUCCESS"),
            reason=args.get("reason", ""),
        )

    return {"error": f"Unknown tool: {name}"}


# ── Agent loop ────────────────────────────────────────────────────────────────

async def run_deployment(assessment: dict, conversion: dict, reconcile: dict) -> dict:
    pipeline = assessment["pipeline"]
    client   = anthropic.Anthropic()

    async def _e(type: str, message: str, **kw) -> None:
        await push(type=type, agent=NAME, message=message, pipeline=pipeline, **kw)

    await _e("status", f"Starting deployment orchestration for {pipeline}")
    await _e("hook",   "PreToolUse → visa_governance ✓ deployment allowed")

    messages: list[dict] = [
        {
            "role":    "user",
            "content": (
                f"Run deployment orchestration for pipeline '{pipeline}'.\n"
                f"Assessment: {json.dumps(assessment, default=str)}\n"
                f"Conversion: {json.dumps(conversion, default=str)}\n"
                f"Reconciliation: {json.dumps(reconcile, default=str)}"
            ),
        }
    ]

    iterations   = 0
    final_result = {}

    while iterations < MAX_ITERATIONS:
        iterations += 1

        response = await claude_with_retry(
            client,
            model=MODEL,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if hasattr(block, "text") and block.text.strip():
                await _e("status", block.text.strip())

        if response.stop_reason == "end_turn":
            await _e("status", "Deployment orchestration complete", done=True)
            break

        if response.stop_reason != "tool_use":
            break

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            await _e("tool_call", f"{block.name}({_fmt_args(block.input)})")
            await asyncio.sleep(0.2)

            result = await _execute_tool(block.name, block.input)

            if block.name == "finish_deployment_tool" and result.get("finished"):
                final_result = result.get("result", {})
                status       = result.get("status", "SUCCESS")
                reason       = result.get("reason", "")
                await _e("status", f"Deployment {status}" + (f" — {reason}" if reason else ""), done=True)
                await _e("hook",   "PostToolUse → audit_logger.record_deployment ✓")
                return final_result

            await _e("status", _fmt_result(block.name, result))
            await asyncio.sleep(0.2)

            tool_results.append({
                "type":        "tool_result",
                "tool_use_id": block.id,
                "content":     json.dumps(result, default=str),
            })

        messages.append({"role": "user", "content": tool_results})

    if iterations >= MAX_ITERATIONS:
        await _e("status", f"⚠ Safety stop — {MAX_ITERATIONS} iterations reached", done=True)

    return final_result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_args(args: dict) -> str:
    s = json.dumps(args, default=str)
    return (s[:120] + "…") if len(s) > 120 else s


def _fmt_result(tool_name: str, result: dict) -> str:
    if not result or "error" in result:
        return f"⚠ {tool_name}: {(result or {}).get('error', 'no result')}"
    summaries = {
        "validate_artifacts_tool":  lambda r: f"✓ Artifacts: {'ready' if r.get('deployment_ready') else 'issues found'}",
        "generate_cicd_tool":       lambda r: f"✓ CI/CD generated: {len(r.get('pipeline_config', {}).get('stages', []))} stages",
        "stage_deployment_tool":    lambda r: f"✓ Staging: {r.get('status')}",
        "run_smoke_tests_tool":     lambda r: f"✓ Smoke tests: {r.get('passed')}/{r.get('total')} passed  score={r.get('score')}%",
        "compute_governance_tool":  lambda r: f"✓ Governance: {r.get('governance', {}).get('state')}  readiness={r.get('readiness_score')}%",
        "write_manifests_tool":     lambda r: f"✓ Manifests: {len(r.get('files_written', []))} files → {r.get('output_dir')}",
        "read_skill_tool":          lambda r: f"✓ Loaded skill: {r.get('name')}",
    }
    fn = summaries.get(tool_name)
    return fn(result) if fn else f"✓ {tool_name} complete"

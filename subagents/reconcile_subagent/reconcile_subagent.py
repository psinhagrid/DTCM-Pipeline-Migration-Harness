"""
reconcile_subagent — LLM-driven agentic loop.

Claude drives reconciliation by:
  1. Reading skill instructions via read_skill_tool
  2. Analyzing each file pair semantically, running runtime validation, compiling report
  3. Iterating until it calls finish_reconciliation_tool or MAX_ITERATIONS is hit
"""

import asyncio
import json
from pathlib import Path

import os
import anthropic

from event_queue import push
from .tools import (
    analyze_file_tool,
    validate_pyspark_tool,
    workflow_parity_tool,
    runtime_validation_tool,
    compile_report_tool,
    read_skill_tool,
    finish_reconciliation_tool,
)

NAME           = "reconcile_subagent"
MAX_ITERATIONS = 40

MODEL          = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
_SYSTEM_PROMPT = (Path(__file__).parent / "reconcile_subagent_system.md").read_text(encoding="utf-8")


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
                    "description": "Skill name — one of: semantic_comparison, runtime_validation, risk_assessment",
                }
            },
            "required": ["name"],
        },
    },
    {
        "name": "validate_pyspark_tool",
        "description": (
            "Static validation of a generated PySpark file. "
            "Checks Python syntax, required imports, SparkSession setup, write operation presence, "
            "hiveconf variable parity, UDF references, and non-empty output. "
            "Call once per file before semantic comparison. Halt if syntax check fails."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename":     {"type": "string", "description": "Python filename (e.g. load_revenue.py)"},
                "spark_python": {"type": "string", "description": "Generated PySpark file content"},
                "source_hql":   {"type": "string", "description": "Original HiveQL source (for hiveconf + UDF checks)"},
            },
            "required": ["filename", "spark_python"],
        },
    },
    {
        "name": "analyze_file_tool",
        "description": (
            "Run full semantic comparison for one HiveQL↔PySpark file pair across 8 dimensions. "
            "Call once per file after validate_pyspark_tool passes. Skip DDL-only files. "
            "Returns per-dimension checks, overall_similarity, and issues list."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename":    {"type": "string", "description": "Source .hql filename"},
                "hql_src":    {"type": "string", "description": "Source HiveQL file content"},
                "pyspark_src": {"type": "string", "description": "Converted PySpark file content"},
            },
            "required": ["filename", "hql_src", "pyspark_src"],
        },
    },
    {
        "name": "workflow_parity_tool",
        "description": (
            "Check that the generated DAG structure matches the conversion file structure. "
            "Returns status (PASSED/WARNING/FAILED) and detail."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "conversion": {"type": "object", "description": "Full conversion result from convert_subagent"},
            },
            "required": ["conversion"],
        },
    },
    {
        "name": "runtime_validation_tool",
        "description": (
            "Run all 4 runtime checks: row_count, checksum, sla_compliance, consumer_replay. "
            "Call after all file analyses are complete. "
            "similarity = average overall_similarity from all analyze_file_tool results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline":   {"type": "string"},
                "complexity": {"type": "string", "description": "SMALL | MEDIUM | LARGE | COMPLEX"},
                "similarity": {"type": "number",  "description": "Average semantic similarity (0.0–1.0)"},
            },
            "required": ["pipeline", "complexity", "similarity"],
        },
    },
    {
        "name": "compile_report_tool",
        "description": (
            "Compile all check results into the final reconciliation report. "
            "Call after all file analyses, workflow parity, and runtime validation are done."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline":       {"type": "string"},
                "files_analysis": {
                    "type": "array", "items": {"type": "object"},
                    "description": "List of analyze_file_tool results (one per file)",
                },
                "workflow_check": {"type": "object", "description": "Result from workflow_parity_tool"},
                "runtime_checks": {"type": "object", "description": "Result from runtime_validation_tool"},
                "all_issues":     {
                    "type": "array", "items": {"type": "string"},
                    "description": "All issue strings collected from file analyses",
                },
            },
            "required": ["pipeline", "files_analysis", "workflow_check", "runtime_checks", "all_issues"],
        },
    },
    {
        "name": "finish_reconciliation_tool",
        "description": (
            "Signal that reconciliation is complete. Always call this as your final action — "
            "never stop without calling it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "object", "description": "Complete reconciliation report"},
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

    elif name == "validate_pyspark_tool":
        return await asyncio.to_thread(
            validate_pyspark_tool,
            args["filename"],
            args["spark_python"],
            args.get("source_hql", ""),
        )

    elif name == "analyze_file_tool":
        return await asyncio.to_thread(
            analyze_file_tool,
            args["filename"],
            args["hql_src"],
            args["pyspark_src"],
        )

    elif name == "workflow_parity_tool":
        return await asyncio.to_thread(workflow_parity_tool, args["conversion"])

    elif name == "runtime_validation_tool":
        return await asyncio.to_thread(
            runtime_validation_tool,
            args["pipeline"],
            args["complexity"],
            float(args["similarity"]),
        )

    elif name == "compile_report_tool":
        return await asyncio.to_thread(
            compile_report_tool,
            args["pipeline"],
            args["files_analysis"],
            args["workflow_check"],
            args["runtime_checks"],
            args.get("all_issues", []),
        )

    elif name == "finish_reconciliation_tool":
        return finish_reconciliation_tool(
            result=args.get("result", {}),
            status=args.get("status", "SUCCESS"),
            reason=args.get("reason", ""),
        )

    return {"error": f"Unknown tool: {name}"}


# ── Agent loop ────────────────────────────────────────────────────────────────

async def run_reconciliation(assessment: dict, conversion: dict) -> dict:
    pipeline = assessment["pipeline"]
    client   = anthropic.Anthropic()

    async def _e(type: str, message: str, **kw) -> None:
        await push(type=type, agent=NAME, message=message, pipeline=pipeline, **kw)

    await _e("status", f"Starting reconciliation for {pipeline}")
    await _e("hook",   "PreToolUse → governance_check ✓ allowed")

    messages: list[dict] = [
        {
            "role":    "user",
            "content": (
                f"Reconcile the conversion for pipeline '{pipeline}'.\n"
                f"Assessment: {json.dumps(assessment, default=str)}\n"
                f"Conversion: {json.dumps(conversion, default=str)}"
            ),
        }
    ]

    iterations   = 0
    final_result = {}

    while iterations < MAX_ITERATIONS:
        iterations += 1

        response = await asyncio.to_thread(
            client.messages.create,
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
            await _e("status", "Reconciliation complete", done=True)
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

            if block.name == "finish_reconciliation_tool" and result.get("finished"):
                final_result = result.get("result", {})
                status       = result.get("status", "SUCCESS")
                reason       = result.get("reason", "")
                await _e("status", f"Reconciliation {status}" + (f" — {reason}" if reason else ""), done=True)
                await _e("hook",   "PostToolUse → audit_logger.record_reconciliation ✓")
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
        "validate_pyspark_tool":  lambda r: f"{'✓' if r.get('valid') else '✗'} {r.get('filename')}: {len(r.get('errors', []))} error(s), {len(r.get('warnings', []))} warning(s)",
        "analyze_file_tool":      lambda r: f"✓ {r.get('file', '?')}: similarity={r.get('overall_similarity', 0):.0%}" if not r.get("skipped") else f"– {r.get('reason', 'skipped')}",
        "workflow_parity_tool":   lambda r: f"✓ Workflow parity: {r.get('status')} — {r.get('detail', '')}",
        "runtime_validation_tool":lambda r: f"✓ Runtime checks: row_count={r.get('row_count', {}).get('status')} checksum={r.get('checksum', {}).get('status')}",
        "compile_report_tool":    lambda r: f"✓ Report: {r.get('validation_status')} confidence={r.get('confidence_score', 0):.0%} risk={r.get('migration_risk')}",
        "read_skill_tool":        lambda r: f"✓ Loaded skill: {r.get('name')}",
    }
    fn = summaries.get(tool_name)
    return fn(result) if fn else f"✓ {tool_name} complete"

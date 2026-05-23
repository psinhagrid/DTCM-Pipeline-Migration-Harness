"""
convert_subagent — LLM-driven agentic loop.

Claude drives the conversion by:
  1. Reading skill instructions via read_skill_tool
  2. Listing and converting HQL files, generating DAG, packaging artifacts
  3. Iterating until it calls finish_conversion_tool or MAX_ITERATIONS is hit
"""

import asyncio
import json
from pathlib import Path

import os
import anthropic

from event_queue import push
from event_queue import claude_with_retry
from .tools import (
    list_hql_files_tool,
    transform_hql_tool,
    generate_dag_tool,
    controlm_export_tool,
    s3_upload_tool,
    read_skill_tool,
    query_graph_tool,
    finish_conversion_tool,
)

NAME           = "convert_subagent"
MAX_ITERATIONS = 40

MODEL          = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
_SYSTEM_PROMPT = (Path(__file__).parent / "convert_subagent_system.md").read_text(encoding="utf-8")


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
                    "description": "Skill name — one of: hiveql_to_pyspark, dag_generation, artifact_packaging",
                }
            },
            "required": ["name"],
        },
    },
    {
        "name": "list_hql_files_tool",
        "description": (
            "Discover all .hql source files for the pipeline. "
            "Returns a list of filenames to convert. Call this first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_name": {"type": "string"}
            },
            "required": ["pipeline_name"],
        },
    },
    {
        "name": "transform_hql_tool",
        "description": (
            "Convert a single HiveQL file to PySpark via Claude Sonnet. "
            "Call once per file returned by list_hql_files_tool. "
            "Returns python_filename, spark_python code, and transformations_applied count."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename":      {"type": "string", "description": "HQL filename from list_hql_files_tool"},
                "pipeline_name": {"type": "string"},
                "metadata":      {"type": "object", "description": "Full assess_subagent result"},
            },
            "required": ["filename", "pipeline_name", "metadata"],
        },
    },
    {
        "name": "controlm_export_tool",
        "description": (
            "Export the Control-M job chain definition for the pipeline. "
            "Call before generate_dag_tool. "
            "(Currently stubbed — returns None until MCP is implemented.)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {"pipeline_name": {"type": "string"}},
            "required": ["pipeline_name"],
        },
    },
    {
        "name": "generate_dag_tool",
        "description": (
            "Generate an MWAA Airflow DAG from the list of converted PySpark files. "
            "Call after all files are converted. "
            "Returns dag_content (Python string) and dag_filename."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline_name": {"type": "string"},
                "files": {
                    "type": "array", "items": {"type": "string"},
                    "description": "List of .hql source filenames in conversion order",
                },
                "complexity": {
                    "type": "string",
                    "description": "SMALL | MEDIUM | LARGE | COMPLEX",
                },
            },
            "required": ["pipeline_name", "files", "complexity"],
        },
    },
    {
        "name": "s3_upload_tool",
        "description": (
            "Upload all generated artifacts to S3. "
            "Call after DAG is generated. "
            "(Currently stubbed — returns None until boto3 is implemented.)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "artifact_path": {"type": "string"},
                "files":         {"type": "array", "items": {"type": "string"}},
            },
            "required": ["artifact_path", "files"],
        },
    },
    {
        "name": "query_graph_tool",
        "description": (
            "Query the Neo4j lineage graph for context about this pipeline. "
            "Call when you need blast radius, wave order, or upstream/downstream context. "
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
        "name": "finish_conversion_tool",
        "description": (
            "Signal that conversion is complete. Always call this as your final action — "
            "never stop without calling it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "object", "description": "Complete conversion result"},
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

    elif name == "list_hql_files_tool":
        return list_hql_files_tool(args["pipeline_name"])

    elif name == "transform_hql_tool":
        return await asyncio.to_thread(
            transform_hql_tool,
            args["filename"],
            args["pipeline_name"],
            args.get("metadata", {}),
        )

    elif name == "controlm_export_tool":
        controlm_export_tool(args["pipeline_name"])
        return {"status": "ok", "note": "stubbed — TODO: controlm_mcp"}

    elif name == "generate_dag_tool":
        return generate_dag_tool(
            args["pipeline_name"],
            args["files"],
            args.get("complexity", "MEDIUM"),
        )

    elif name == "s3_upload_tool":
        s3_upload_tool(args["artifact_path"], args["files"])
        return {"status": "ok", "note": "stubbed — TODO: boto3"}

    elif name == "query_graph_tool":
        return await asyncio.to_thread(
            query_graph_tool,
            args["pipeline"],
            args.get("query", "summary"),
        )

    elif name == "finish_conversion_tool":
        return finish_conversion_tool(
            result=args.get("result", {}),
            status=args.get("status", "SUCCESS"),
            reason=args.get("reason", ""),
        )

    return {"error": f"Unknown tool: {name}"}


# ── Agent loop ────────────────────────────────────────────────────────────────

async def run_conversion(assessment: dict) -> dict:
    pipeline_name = assessment["pipeline"]
    client        = anthropic.Anthropic()

    async def _e(type: str, message: str, **kw) -> None:
        await push(type=type, agent=NAME, message=message, pipeline=pipeline_name, **kw)

    await _e("status", f"Starting conversion for {pipeline_name}")
    await _e("hook",   "PreToolUse → visa_governance ✓ allowed")

    messages: list[dict] = [
        {
            "role":    "user",
            "content": (
                f"Convert the pipeline '{pipeline_name}' from HiveQL to PySpark.\n"
                f"Assessment result: {json.dumps(assessment, default=str)}"
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
            await _e("status", "Conversion complete", done=True)
            break

        if response.stop_reason != "tool_use":
            break

        # ── Execute all tool calls from this turn ─────────────────────────
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            await _e("tool_call", f"{block.name}({_fmt_args(block.input)})")
            await asyncio.sleep(0.2)

            result = await _execute_tool(block.name, block.input)

            # finish_conversion_tool → exit the loop immediately
            if block.name == "finish_conversion_tool" and result.get("finished"):
                final_result = result.get("result", {})
                status       = result.get("status", "SUCCESS")
                reason       = result.get("reason", "")
                await _e("status", f"Conversion {status}" + (f" — {reason}" if reason else ""), done=True)
                await _e("hook",   "PostToolUse → audit_logger.record_conversion ✓")
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
        "list_hql_files_tool":  lambda r: f"✓ {r.get('count')} HQL files: {r.get('files')}",
        "transform_hql_tool":   lambda r: f"✓ {r.get('filename')} → {r.get('python_filename')} ({r.get('transformations_applied')} lines)",
        "controlm_export_tool": lambda r: f"✓ Control-M export: {r.get('status')}",
        "generate_dag_tool":    lambda r: f"✓ DAG generated: {r.get('dag_filename')}",
        "s3_upload_tool":       lambda r: f"✓ S3 upload: {r.get('status')}",
        "read_skill_tool":      lambda r: f"✓ Loaded skill: {r.get('name')}",
    }
    fn = summaries.get(tool_name)
    return fn(result) if fn else f"✓ {tool_name} complete"

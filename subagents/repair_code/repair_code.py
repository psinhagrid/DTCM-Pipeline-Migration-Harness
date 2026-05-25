"""
repair_code — LLM-driven code repair agent.

Finds syntax/structural issues in HiveQL or PySpark files, proposes
line-level fixes to the user inline in the log, and writes accepted
fixes back to the original file location.
"""

import asyncio
import json
import os
from pathlib import Path

import anthropic

from event_queue import push
from .tools import (
    read_file_tool,
    write_file_tool,
    list_files_tool,
    ask_user_tool,
    finish_repair_tool,
    read_skill_tool,
)

NAME           = "repair_code"
MAX_ITERATIONS = 40
MODEL          = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

_SYSTEM_PROMPT = (Path(__file__).parent / "repair_code_system.md").read_text(encoding="utf-8")


TOOLS = [
    {
        "name": "read_skill_tool",
        "description": "Load repair rules for 'hiveql_repair' or 'pyspark_repair'. Call first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "enum": ["hiveql_repair", "pyspark_repair"]},
            },
            "required": ["name"],
        },
    },
    {
        "name": "list_files_tool",
        "description": "List source files available to repair for a pipeline.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline": {"type": "string"},
                "target":   {"type": "string", "enum": ["hql", "pyspark"], "description": "hql or pyspark"},
            },
            "required": ["pipeline", "target"],
        },
    },
    {
        "name": "read_file_tool",
        "description": (
            "Read a source file. Returns content and 1-indexed line map. "
            "Use the full path from list_files_tool: join root + filename. "
            "Example: if root='/Users/psinha/Documents/DTCM Pipeline/pipelines/raw_events_ingest' "
            "and file='ingest_clickstream.hql', path is root+'/'+filename."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Full absolute path — use root from list_files_tool + '/' + filename"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "ask_user_tool",
        "description": (
            "Show the user a specific proposed fix and wait for their response. "
            "situation must include: filename, line number(s), BEFORE code, AFTER code, reason. "
            "options must always be: ['Accept fix', 'Skip this fix', 'Halt repair']"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "situation": {"type": "string", "description": "File, line, before/after, reason"},
                "options":   {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 4},
                "pipeline":  {"type": "string"},
            },
            "required": ["situation", "options"],
        },
    },
    {
        "name": "write_file_tool",
        "description": (
            "Write fixed content back to the original file. "
            "Only call after user accepts a fix. Creates .bak backup automatically."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path":    {"type": "string", "description": "Absolute path — same as read_file_tool path"},
                "content": {"type": "string", "description": "Complete fixed file content"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "finish_repair_tool",
        "description": "Signal repair is complete. Always call last.",
        "input_schema": {
            "type": "object",
            "properties": {
                "files_fixed":    {"type": "array", "items": {"type": "string"}},
                "issues_skipped": {"type": "array", "items": {"type": "string"}},
                "status":         {"type": "string", "enum": ["SUCCESS", "PARTIAL", "HALTED"]},
                "reason":         {"type": "string"},
            },
            "required": ["files_fixed", "issues_skipped", "status"],
        },
    },
]


async def _execute_tool(name: str, args: dict, pipeline: str) -> dict:
    if name == "read_skill_tool":
        return read_skill_tool(args["name"])

    elif name == "list_files_tool":
        return await asyncio.to_thread(list_files_tool, args["pipeline"], args.get("target", "hql"))

    elif name == "read_file_tool":
        return await asyncio.to_thread(read_file_tool, args["path"])

    elif name == "ask_user_tool":
        return await ask_user_tool(
            situation=args["situation"],
            options=args["options"],
            pipeline=args.get("pipeline", pipeline),
        )

    elif name == "write_file_tool":
        return await asyncio.to_thread(write_file_tool, args["path"], args["content"])

    elif name == "finish_repair_tool":
        return finish_repair_tool(
            files_fixed=args.get("files_fixed", []),
            issues_skipped=args.get("issues_skipped", []),
            status=args.get("status", "SUCCESS"),
            reason=args.get("reason", ""),
        )

    return {"error": f"Unknown tool: {name}"}


async def run_repair(pipeline: str, target: str = "hql") -> dict:
    """
    Run the repair agent on a pipeline's HQL or PySpark files.
    target: 'hql' | 'pyspark'
    """
    client = anthropic.Anthropic()

    async def _e(type: str, message: str, **kw) -> None:
        await push(type=type, agent=NAME, message=message, pipeline=pipeline, **kw)

    await _e("status", f"Starting {target.upper()} repair for {pipeline}")

    from pathlib import Path as _Path
    _project_root = str(_Path(__file__).parents[2])

    messages: list[dict] = [
        {
            "role":    "user",
            "content": (
                f"Repair {target.upper()} files for pipeline '{pipeline}'. "
                f"Target: {target}. Project root: {_project_root}. "
                f"Use list_files_tool to discover files — it returns the 'root' path. "
                f"Build absolute paths as: root + '/' + filename. "
                f"Find syntax/structural issues, propose each fix to the user, "
                f"and write accepted fixes back to the original file location."
            ),
        }
    ]

    iterations   = 0
    final_result = {}

    try:
        while iterations < MAX_ITERATIONS:
            iterations += 1

            from event_queue import claude_with_retry
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
                await _e("status", "Repair complete", done=True)
                break

            if response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                await _e("tool_call", f"{block.name}({_fmt_args(block.input)})")

                result = await _execute_tool(block.name, block.input, pipeline)

                if block.name == "finish_repair_tool" and result.get("finished"):
                    final_result = result
                    status = result.get("status", "SUCCESS")
                    fixed  = result.get("files_fixed", [])
                    await _e("status",
                             f"Repair {status} — {len(fixed)} fix(es) applied",
                             done=True)
                    await push(type="complete", agent=NAME,
                               message=f"Repair {status} — {pipeline}", pipeline=pipeline)
                    return final_result

                await _e("status", _fmt_result(block.name, result))

                tool_results.append({
                    "type":        "tool_result",
                    "tool_use_id": block.id,
                    "content":     json.dumps(result, default=str),
                })

            messages.append({"role": "user", "content": tool_results})

        if iterations >= MAX_ITERATIONS:
            await _e("status", f"⚠ Safety stop — {MAX_ITERATIONS} iterations reached", done=True)

    except Exception as exc:
        await _e("status", f"⚠ Repair error: {exc}", done=True)
        await push(type="complete", agent=NAME,
                   message=f"Repair FAILED — {pipeline}", pipeline=pipeline)

    return final_result


def _fmt_args(args: dict) -> str:
    s = json.dumps(args, default=str)
    return (s[:100] + "…") if len(s) > 100 else s


def _fmt_result(tool_name: str, result: dict) -> str:
    if not result or "error" in result:
        return f"⚠ {tool_name}: {(result or {}).get('error', 'no result')}"
    summaries = {
        "read_file_tool":     lambda r: f"✓ Read {r.get('filename')} ({r.get('line_count')} lines)",
        "write_file_tool":    lambda r: f"✓ Fixed {Path(r.get('written_to', '')).name} (backup: {Path(r.get('backup', '')).name})",
        "list_files_tool":    lambda r: f"✓ {len(r.get('files', []))} file(s): {r.get('files')}",
        "read_skill_tool":    lambda r: f"✓ Loaded skill: {r.get('name')}",
        "ask_user_tool":      lambda r: f"✓ User chose: {r.get('chosen')}",
    }
    fn = summaries.get(tool_name)
    return fn(result) if fn else f"✓ {tool_name} complete"

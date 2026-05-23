"""
assess_subagent — LLM-driven agentic loop.

Claude drives the assessment by:
  1. Reading skill instructions via read_skill_tool
  2. Calling assessment tools and reasoning over each result
  3. Iterating until it calls finish_assessment_tool or MAX_ITERATIONS is hit
"""

import asyncio
import json
from pathlib import Path

import os
import anthropic

from event_queue import push
from event_queue import claude_with_retry
from .tools import (
    scan_repo_tool,
    parse_hql_tool,
    lineage_extract_tool,
    classify_complexity_tool,
    neo4j_write_graph_tool,
    query_graph_tool,
    read_skill_tool,
    finish_assessment_tool,
)

NAME           = "assess_subagent"
MAX_ITERATIONS = 30
PIPELINES_ROOT = Path(__file__).parents[2] / "pipelines"

MODEL          = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
_SYSTEM_PROMPT = (Path(__file__).parent / "assess_subagent_system.md").read_text(encoding="utf-8")


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
                    "description": "Skill name — one of: repo_scan, lineage_extraction, complexity_classification",
                }
            },
            "required": ["name"],
        },
    },
    {
        "name": "scan_repo_tool",
        "description": (
            "Discover all source files in the pipeline directory. "
            "Returns hql_files (list of filenames), config_files, and total_files. "
            "Always call this first — everything else depends on knowing the files."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "parse_hql_tool",
        "description": (
            "Parse a single .hql file. "
            "Returns read_tables, created_tables, written_tables, columns, partition_keys, "
            "udfs, has_window, subqueries, has_dyn_part, cross_db_joins, syntax_errors. "
            "Call once per HQL file returned by scan_repo_tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "HQL filename as returned by scan_repo_tool, e.g. 'load_revenue.hql'",
                }
            },
            "required": ["filename"],
        },
    },
    {
        "name": "lineage_extract_tool",
        "description": (
            "Derive upstream dependencies and downstream consumers. "
            "Pass the aggregated table sets unioned across all parsed files. "
            "Call after all HQL files have been parsed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "all_reads":   {
                    "type": "array", "items": {"type": "string"},
                    "description": "Union of read_tables across all parsed files",
                },
                "all_creates": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Union of created_tables across all parsed files",
                },
                "all_writes":  {
                    "type": "array", "items": {"type": "string"},
                    "description": "Union of written_tables across all parsed files",
                },
            },
            "required": ["all_reads", "all_creates", "all_writes"],
        },
    },
    {
        "name": "classify_complexity_tool",
        "description": (
            "Score and classify pipeline migration complexity. "
            "Call after lineage is extracted — needs the full picture of tables, "
            "UDFs, and downstream consumers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "tables":       {"type": "array", "items": {"type": "string"}},
                "udfs":         {"type": "array", "items": {"type": "string"}},
                "has_window":   {"type": "boolean"},
                "cross_db":     {"type": "array", "items": {"type": "string"}},
                "has_dyn_part": {"type": "boolean"},
                "subqueries":   {"type": "integer"},
                "downstream":   {"type": "array", "items": {"type": "string"}},
            },
            "required": ["tables", "udfs", "has_window", "cross_db", "has_dyn_part", "subqueries", "downstream"],
        },
    },
    {
        "name": "neo4j_write_graph_tool",
        "description": (
            "Write the pipeline lineage graph to Neo4j. "
            "Call after lineage_extract_tool and classify_complexity_tool. "
            "Pass all lineage data collected from prior tool results."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "upstream_tables": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Tables this pipeline reads but does not create (from lineage_extract_tool)",
                },
                "output_tables": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Tables this pipeline writes or creates (from lineage_extract_tool)",
                },
                "downstream": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Pipeline names that consume this pipeline's output (from lineage_extract_tool)",
                },
                "udfs": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Custom UDF names detected in source HQL files",
                },
                "complexity": {
                    "type": "string",
                    "description": "Complexity band from classify_complexity_tool: SMALL|MEDIUM|LARGE|COMPLEX",
                },
                "estimated_effort": {
                    "type": "string",
                    "description": "Effort estimate from classify_complexity_tool",
                },
            },
            "required": ["upstream_tables", "output_tables", "downstream", "udfs", "complexity"],
        },
    },
    {
        "name": "query_graph_tool",
        "description": (
            "Query the Neo4j lineage graph for context about this pipeline. "
            "Call after lineage_extract_tool to enrich with graph data if available. "
            "Returns empty if graph not yet built — treat gracefully and proceed. "
            "query options: 'summary' | 'downstream' | 'upstream' | 'blast_radius' | 'wave'"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline": {"type": "string", "description": "Pipeline name to query"},
                "query":    {
                    "type": "string",
                    "enum": ["summary", "downstream", "upstream", "blast_radius", "wave"],
                    "description": "What to query",
                },
            },
            "required": ["pipeline", "query"],
        },
    },
    {
        "name": "finish_assessment_tool",
        "description": (
            "Signal that assessment is complete. Always call this as your final action — "
            "never stop without calling it. "
            "Pass the full structured result and the outcome status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "result": {
                    "type": "object",
                    "description": "Complete assessment result matching the output contract",
                },
                "status": {
                    "type": "string",
                    "enum": ["SUCCESS", "HALTED", "ERROR"],
                    "description": "SUCCESS=complete, HALTED=decision gate triggered, ERROR=unrecoverable",
                },
                "reason": {
                    "type": "string",
                    "description": "Required when status is HALTED or ERROR",
                },
            },
            "required": ["result", "status"],
        },
    },
]


# ── Tool executor ─────────────────────────────────────────────────────────────

async def _execute_tool(name: str, args: dict, pipeline_dir: Path) -> dict:
    if name == "read_skill_tool":
        return read_skill_tool(args["name"])

    elif name == "scan_repo_tool":
        raw = scan_repo_tool(pipeline_dir)
        return {
            "hql_files":    [f.name for f in raw["hql_files"]],
            "config_files": [f.name for f in raw["config_files"]],
            "total_files":  raw["total_files"],
        }

    elif name == "parse_hql_tool":
        path = pipeline_dir / args["filename"]
        raw  = await asyncio.to_thread(parse_hql_tool, path)
        return {k: sorted(v) if isinstance(v, set) else v for k, v in raw.items()}

    elif name == "lineage_extract_tool":
        raw = await asyncio.to_thread(
            lineage_extract_tool,
            set(args.get("all_reads",   [])),
            set(args.get("all_creates", [])),
            set(args.get("all_writes",  [])),
            pipeline_dir,
        )
        return raw

    elif name == "classify_complexity_tool":
        return classify_complexity_tool(
            set(args.get("tables",    [])),
            set(args.get("udfs",      [])),
            args.get("has_window",    False),
            set(args.get("cross_db",  [])),
            args.get("has_dyn_part",  False),
            args.get("subqueries",    0),
            args.get("downstream",    []),
        )

    elif name == "query_graph_tool":
        return await asyncio.to_thread(
            query_graph_tool,
            args["pipeline"],
            args.get("query", "summary"),
        )

    elif name == "neo4j_write_graph_tool":
        result = neo4j_write_graph_tool(
            pipeline=pipeline_dir.name,
            upstream_tables=args.get("upstream_tables", []),
            output_tables=args.get("output_tables", []),
            downstream=args.get("downstream", []),
            udfs=args.get("udfs", []),
            complexity=args.get("complexity", "UNKNOWN"),
            estimated_effort=args.get("estimated_effort", ""),
        )
        return result

    elif name == "finish_assessment_tool":
        return finish_assessment_tool(
            result=args.get("result", {}),
            status=args.get("status", "SUCCESS"),
            reason=args.get("reason", ""),
        )

    return {"error": f"Unknown tool: {name}"}


# ── Agent loop ────────────────────────────────────────────────────────────────

async def run_assessment(pipeline_name: str) -> dict:
    pipeline_dir = PIPELINES_ROOT / pipeline_name
    client       = anthropic.Anthropic()

    async def _e(type: str, message: str, **kw) -> None:
        await push(type=type, agent=NAME, message=message, pipeline=pipeline_name, **kw)

    await _e("status", f"Starting assessment for {pipeline_name}")
    await _e("hook",   "PreToolUse → governance_check ✓ allowed")

    if not pipeline_dir.exists():
        await _e("status", f"ERROR: pipeline directory not found: {pipeline_dir}", done=True)
        raise FileNotFoundError(pipeline_dir)

    messages: list[dict] = [
        {
            "role":    "user",
            "content": (
                f"Assess the pipeline named '{pipeline_name}'. "
                f"Pipeline directory: {pipeline_dir}"
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

        # Stream any LLM narration to the frontend
        for block in response.content:
            if hasattr(block, "text") and block.text.strip():
                await _e("status", block.text.strip())

        if response.stop_reason == "end_turn":
            await _e("status", "Assessment complete", done=True)
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

            result = await _execute_tool(block.name, block.input, pipeline_dir)

            # finish_assessment_tool → exit the loop immediately
            if block.name == "finish_assessment_tool" and result.get("finished"):
                final_result = result.get("result", {})
                status       = result.get("status", "SUCCESS")
                reason       = result.get("reason", "")
                await _e("status", f"Assessment {status}" + (f" — {reason}" if reason else ""), done=True)
                await _e("hook",   "PostToolUse → audit_logger.record_assessment ✓")
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
    if "error" in result:
        return f"⚠ {tool_name}: {result['error']}"
    summaries = {
        "scan_repo_tool":           lambda r: f"✓ {r.get('total_files')} files, {len(r.get('hql_files', []))} HQL",
        "parse_hql_tool":           lambda r: f"✓ {r.get('file')}: {len(r.get('all_tables', []))} tables, {len(r.get('udfs', []))} UDFs",
        "lineage_extract_tool":     lambda r: f"✓ {len(r.get('upstream', []))} upstream, {len(r.get('downstream', []))} downstream",
        "classify_complexity_tool": lambda r: f"✓ Score {r.get('score')} → {r.get('complexity')} ({r.get('estimated_effort')})",
        "neo4j_write_graph_tool":   lambda r: f"✓ Graph: {r.get('status')} ({r.get('nodes', 0)} nodes, {r.get('edges', 0)} edges)",
        "query_graph_tool":         lambda r: f"✓ Graph query: wave={r.get('migration_wave', r.get('complexity', '?'))} blast_radius={len(r.get('blast_radius', []))}",
        "read_skill_tool":          lambda r: f"✓ Loaded skill: {r.get('name')}",
    }
    fn = summaries.get(tool_name)
    return fn(result) if fn else f"✓ {tool_name} complete"

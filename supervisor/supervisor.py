"""
supervisor — LLM-driven migration orchestration loop.

Claude owns the full migration lifecycle:
  1. Delegates to 4 subagents in sequence via tool calls
  2. Reads compact result summaries and makes go/no-go decisions
  3. Exits when it calls finish_migration_tool or MAX_ITERATIONS is hit

Full subagent results accumulate in context_store (not in LLM messages)
so the supervisor's context window stays small regardless of result size.
"""

import asyncio
import json
import os
from pathlib import Path

import anthropic

from event_queue import push
from event_queue import claude_with_retry
from subagents.assess_subagent    import run_assessment
from subagents.convert_subagent   import run_conversion
from subagents.reconcile_subagent import run_reconciliation
from subagents.deploy_subagent    import run_deployment
from subagents.repair_code        import run_repair
from .tools import finish_migration_tool, query_graph_tool, ask_user_tool
from graph.client import query_blast_radius

NAME           = "supervisor"
MAX_ITERATIONS = 20
MODEL          = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
COPILOT_MODE   = os.getenv("COPILOT_MODE", "false").lower() == "true"

_SYSTEM_PROMPT = (Path(__file__).parent / "supervisor_system.md").read_text(encoding="utf-8")

if COPILOT_MODE:
    _SYSTEM_PROMPT += """

## Copilot Mode — ACTIVE

After EVERY subagent returns a result, call `ask_user` before proceeding.

For `situation`: write 1–2 sentences summarising what the subagent actually found — be factual and specific to the result, not generic.

For `options`: generate 2–4 options that a senior data engineer would genuinely want to choose from given what was just found. Options should be specific to the situation — think about what could go wrong, what the risk is, and what alternatives exist. Always include "Halt migration" as one option.

Do not use the same options every time. Reason about what matters in this specific result.
"""

# Per-pipeline result store — read by API endpoints in main.py via orchestrator.py
context_store: dict[str, dict] = {}


# ── Tool schemas ──────────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "run_assessment",
        "description": (
            "STEP 1 — Always call this first, before anything else. "
            "Scans HiveQL source files. Extracts tables, UDFs, complexity score, and lineage. "
            "run_conversion cannot be called until this returns a result."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline": {"type": "string", "description": "Pipeline name, e.g. 'daily_revenue_agg'"}
            },
            "required": ["pipeline"],
        },
    },
    {
        "name": "run_conversion",
        "description": (
            "STEP 2 — Call only after run_assessment has returned a result. "
            "Converts HiveQL source files to PySpark and generates an MWAA DAG."
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
        "name": "run_reconciliation",
        "description": (
            "STEP 3 — Call only after run_conversion has returned a result. "
            "Validates PySpark correctness — static checks, semantic comparison, runtime checks. "
            "If confidence_score < 0.60, consider re-running conversion before deploying."
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
        "name": "run_deployment",
        "description": (
            "STEP 4 — Call only after run_reconciliation has returned a result. "
            "Validates artifacts, runs smoke tests, computes governance approval. "
            "Never call if reconciliation validation_status is FAILED."
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
        "name": "query_graph",
        "description": (
            "Query the Neo4j lineage graph before or after delegating to a subagent. "
            "Use to determine migration wave ordering, blast radius priority, "
            "or check which pipelines have been assessed. "
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
        "name": "run_hql_repair",
        "description": (
            "Repair HiveQL source files for a pipeline. "
            "The repair agent reads each .hql file, identifies syntax errors, "
            "proposes each fix to the user line-by-line, and writes accepted fixes "
            "back to the original file. Call when assessment returns syntax_errors > 0. "
            "After repair completes, re-run run_assessment to verify."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline": {"type": "string"},
            },
            "required": ["pipeline"],
        },
    },
    {
        "name": "run_pyspark_repair",
        "description": (
            "Repair generated PySpark files for a pipeline. "
            "The repair agent reads each .py file, identifies issues (missing imports, "
            "wrong write ops, unmapped hiveconf vars), proposes each fix to the user, "
            "and writes accepted fixes in place. "
            "Call when reconciliation finds PySpark validation failures. "
            "After repair completes, re-run run_reconciliation to verify."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline": {"type": "string"},
            },
            "required": ["pipeline"],
        },
    },
    {
        "name": "ask_user",
        "description": (
            "Pause the migration and ask the human for guidance in the terminal. "
            "Use when a subagent returns unexpected results (confidence=0.00, empty result, "
            "all files skipped, null validation_status) or when you are unsure how to proceed. "
            "Prints numbered options to the terminal and waits for the user to choose."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "situation": {
                    "type": "string",
                    "description": "Clear description of what went wrong or why guidance is needed",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2–4 numbered options for the user to choose from",
                    "minItems": 2,
                    "maxItems": 4,
                },
            },
            "required": ["situation", "options"],
        },
    },
    {
        "name": "finish_migration",
        "description": (
            "Signal that the migration workflow is complete. "
            "Always call this as your final action — never stop without it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline": {"type": "string"},
                "outcome": {
                    "type": "string",
                    "enum": ["SUCCESS", "PARTIAL", "HALTED", "FAILED"],
                },
                "summary": {
                    "type": "string",
                    "description": "One or two sentences — what happened and why.",
                },
            },
            "required": ["pipeline", "outcome", "summary"],
        },
    },
]


# ── Tool executor ─────────────────────────────────────────────────────────────

async def _execute_tool(name: str, args: dict, context: dict, pipeline: str) -> dict:
    """
    Run the named tool. Full results are stored in context (not returned to LLM).
    Returns a compact summary so the LLM context stays small.
    """
    async def _e(type: str, message: str, **kw) -> None:
        await push(type=type, agent=NAME, message=message, pipeline=pipeline, **kw)

    if name == "run_assessment":
        result = await run_assessment(args["pipeline"])
        context["assessment"] = result

        # Auto-enrich with blast radius — mechanical, not LLM decision
        blast_radius = []
        try:
            blast_radius = await asyncio.to_thread(query_blast_radius, args["pipeline"])
        except Exception:
            pass
        context["blast_radius"] = blast_radius

        return _summarise("assessment", result, [
            f"complexity={result.get('complexity')}",
            f"tables={result.get('tables')}",
            f"udfs={result.get('udfs')}",
            f"syntax_errors={result.get('syntax_errors')}",
            f"effort={result.get('estimated_effort')}",
            f"blast_radius={len(blast_radius)} pipeline(s) affected if this fails",
        ])

    elif name == "run_conversion":
        assessment = context.get("assessment", {})
        result     = await run_conversion(assessment)
        context["conversion"] = result
        return _summarise("conversion", result, [
            f"conversion_status={result.get('conversion_status')}",
            f"transformations_applied={result.get('transformations_applied')}",
            f"files={len(result.get('generated_files', []))}",
        ])

    elif name == "run_reconciliation":
        assessment = context.get("assessment",  {})
        conversion = context.get("conversion",  {})
        result     = await run_reconciliation(assessment, conversion)
        context["reconciliation"] = result
        return _summarise("reconciliation", result, [
            f"validation_status={result.get('validation_status')}",
            f"confidence_score={result.get('confidence_score', 0):.0%}",
            f"migration_risk={result.get('migration_risk')}",
            f"issues={len(result.get('issues', []))}",
        ])

    elif name == "run_deployment":
        assessment     = context.get("assessment",     {})
        conversion     = context.get("conversion",     {})
        reconciliation = context.get("reconciliation", {})
        result         = await run_deployment(assessment, conversion, reconciliation)
        context["deployment"] = result
        gov   = result.get("governance", {})
        smoke = result.get("smoke_results", {})
        return _summarise("deployment", result, [
            f"deployment_status={gov.get('state')}",
            f"readiness_score={result.get('readiness_score')}%",
            f"smoke={smoke.get('passed')}/{smoke.get('total')}",
        ])

    elif name == "query_graph":
        return await asyncio.to_thread(
            query_graph_tool,
            args["pipeline"],
            args.get("query", "summary"),
        )

    elif name == "run_hql_repair":
        result = await run_repair(args["pipeline"], target="hql")
        return {
            "stage":      "hql_repair",
            "status":     result.get("status", "UNKNOWN"),
            "files_fixed": result.get("files_fixed", []),
            "fix_count":  result.get("fix_count", 0),
            "note":       "Re-run run_assessment to verify fixes.",
        }

    elif name == "run_pyspark_repair":
        result = await run_repair(args["pipeline"], target="pyspark")
        return {
            "stage":      "pyspark_repair",
            "status":     result.get("status", "UNKNOWN"),
            "files_fixed": result.get("files_fixed", []),
            "fix_count":  result.get("fix_count", 0),
            "note":       "Re-run run_reconciliation to verify fixes.",
        }

    elif name == "ask_user":
        await _e("status", f"⏸ Waiting for user input — {args.get('situation', '')[:80]}")
        result = await ask_user_tool(
            situation=args["situation"],
            options=args["options"],
        )
        await _e("status", f"▶ User chose: {result['chosen']}")
        return result

    elif name == "finish_migration":
        result = finish_migration_tool(
            pipeline=args["pipeline"],
            outcome=args["outcome"],
            summary=args["summary"],
        )
        context["finished"] = True
        context["outcome"]  = args["outcome"]
        context["summary"]  = args["summary"]
        return result

    return {"error": f"Unknown tool: {name}"}


# ── Agent loop ────────────────────────────────────────────────────────────────

async def run_migration(pipeline_name: str) -> dict:
    client  = anthropic.Anthropic()
    context = {}

    async def _e(type: str, message: str, **kw) -> None:
        await push(type=type, agent=NAME, message=message, pipeline=pipeline_name, **kw)

    await _e("status", f"Migration started — {pipeline_name}")
    await _e("hook",   "PreToolUse → visa_governance ✓ allowed")

    messages: list[dict] = [
        {
            "role":    "user",
            "content": f"Migrate the pipeline named '{pipeline_name}'.",
        }
    ]

    iterations = 0

    try:
        while iterations < MAX_ITERATIONS:
            iterations += 1

            response = await claude_with_retry(
                client,
                model=MODEL,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            for block in response.content:
                if hasattr(block, "text") and block.text.strip():
                    await _e("status", block.text.strip())

            if response.stop_reason == "end_turn":
                await _e("status", "Migration complete", done=True)
                break

            if response.stop_reason != "tool_use":
                break

            # ── Execute tool calls ────────────────────────────────────────────
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                await _e("delegation" if block.name.startswith("run_") else "tool_call",
                         f"→ {block.name}({_fmt_args(block.input)})",
                         target=block.name)
                await asyncio.sleep(0.2)

                result = await _execute_tool(block.name, block.input, context, pipeline_name)

                if block.name == "finish_migration" and result.get("finished"):
                    outcome = result["outcome"]
                    summary = result["summary"]
                    await _e("status", f"Migration {outcome} — {summary}")
                    await _e("hook",   "PostToolUse → audit_logger.record_migration ✓")
                    await push(type="complete", agent=NAME, message=f"Migration {outcome} — {pipeline_name}", pipeline=pipeline_name)
                    context_store[pipeline_name] = context
                    return context

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

    except Exception as exc:
        await _e("status", f"⚠ Migration crashed: {exc}", done=True)
        await push(type="complete", agent=NAME,
                   message=f"Migration FAILED — {pipeline_name}", pipeline=pipeline_name)

    finally:
        # Always save whatever partial results were collected — even on crash.
        # Ensures workbench / validation / deployment show data from completed stages.
        context_store[pipeline_name] = context

    return context


# ── Helpers ───────────────────────────────────────────────────────────────────

def _summarise(stage: str, result: dict, highlights: list[str]) -> dict:
    """Return compact summary — the LLM only sees this, not the full result dict."""
    return {
        "stage":      stage,
        "highlights": highlights,
        "status":     "ok",
    }


def _fmt_args(args: dict) -> str:
    s = json.dumps(args, default=str)
    return (s[:80] + "…") if len(s) > 80 else s


def _fmt_result(tool_name: str, result: dict) -> str:
    if "error" in result:
        return f"⚠ {tool_name}: {result['error']}"
    highlights = result.get("highlights", [])
    return f"✓ {result.get('stage', tool_name)}: {' | '.join(highlights)}"

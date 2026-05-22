"""
Tool Registry — exposes each agent as a callable tool.

Two formats are maintained in parallel:
  TOOLS_OPENAI     → works with Ollama (current) and OpenAI SDK
  TOOLS_ANTHROPIC  → ready for Claude SDK when you switch

To migrate to Claude / skills:
  1. Swap TOOLS_OPENAI → TOOLS_ANTHROPIC in the orchestrator
  2. Change the API client from OpenAI → anthropic.Anthropic
  3. Zero changes to execute_tool() or the agents themselves

execute_tool() is the single dispatch point — the orchestrator calls
this with whatever name the LLM chose and the args it provided.
"""

from agents.assess_subagent import run_assessment
from agents.convert_subagent import run_conversion
from agents.reconcile_agent import run_reconciliation
from agents.deploy_agent   import run_deployment


# ── Tool names ────────────────────────────────────────────────────────────────

TOOL_NAMES = [
    "run_assessment",
    "run_conversion",
    "run_reconciliation",
    "run_deployment",
    "finish_migration",
]


# ── OpenAI-compatible schemas (Ollama / OpenAI SDK) ───────────────────────────

TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "run_assessment",
            "description": (
                "Scan the HiveQL source files for a pipeline. "
                "Extracts tables, columns, UDFs, joins, complexity score. "
                "Always call this first — every other agent depends on its output."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pipeline": {
                        "type": "string",
                        "description": "Pipeline name matching a folder in pipelines/. e.g. 'daily_revenue_agg'",
                    }
                },
                "required": ["pipeline"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_conversion",
            "description": (
                "Convert HiveQL source files to PySpark using Llama 3.2. "
                "Generates PySpark files and an MWAA DAG. "
                "Call after run_assessment succeeds. "
                "Skip if complexity is COMPLEX and confidence in assessment is low."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pipeline": {
                        "type": "string",
                        "description": "Same pipeline name passed to run_assessment.",
                    }
                },
                "required": ["pipeline"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_reconciliation",
            "description": (
                "Validate that the converted PySpark faithfully represents the source HiveQL. "
                "Performs real semantic checks: table parity, column parity, aggregation parity, "
                "join parity, filter parity, runtime variable parity. "
                "Also runs simulated row count, checksum, SLA, and consumer replay checks. "
                "Call after run_conversion. If confidence is below 0.6, consider re-running conversion."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pipeline": {
                        "type": "string",
                        "description": "Same pipeline name used throughout.",
                    }
                },
                "required": ["pipeline"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_deployment",
            "description": (
                "Validate artifacts, run smoke tests, compute governance approval, "
                "and write deployment manifests to disk. "
                "Call after run_reconciliation. "
                "If reconciliation validation_status is FAILED, halt — do not deploy."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pipeline": {
                        "type": "string",
                        "description": "Same pipeline name used throughout.",
                    }
                },
                "required": ["pipeline"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish_migration",
            "description": (
                "Signal that the migration workflow is complete. "
                "Call this as the final step after all agents have run "
                "OR when you decide to halt early. "
                "Include a summary of what happened and the final outcome."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pipeline": {
                        "type": "string",
                        "description": "Pipeline name.",
                    },
                    "outcome": {
                        "type": "string",
                        "enum": ["SUCCESS", "PARTIAL", "HALTED", "FAILED"],
                        "description": "Overall migration outcome.",
                    },
                    "summary": {
                        "type": "string",
                        "description": "One or two sentences explaining what happened and why.",
                    },
                },
                "required": ["pipeline", "outcome", "summary"],
            },
        },
    },
]


# ── Anthropic-compatible schemas (Claude SDK — future migration) ───────────────
# Same tools, Anthropic format. Swap TOOLS_OPENAI → TOOLS_ANTHROPIC
# and change the API client to use anthropic.Anthropic().

TOOLS_ANTHROPIC = [
    {
        "name": "run_assessment",
        "description": TOOLS_OPENAI[0]["function"]["description"],
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline": {
                    "type": "string",
                    "description": "Pipeline name matching a folder in pipelines/.",
                }
            },
            "required": ["pipeline"],
        },
    },
    {
        "name": "run_conversion",
        "description": TOOLS_OPENAI[1]["function"]["description"],
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline": {"type": "string", "description": "Pipeline name."}
            },
            "required": ["pipeline"],
        },
    },
    {
        "name": "run_reconciliation",
        "description": TOOLS_OPENAI[2]["function"]["description"],
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline": {"type": "string", "description": "Pipeline name."}
            },
            "required": ["pipeline"],
        },
    },
    {
        "name": "run_deployment",
        "description": TOOLS_OPENAI[3]["function"]["description"],
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline": {"type": "string", "description": "Pipeline name."}
            },
            "required": ["pipeline"],
        },
    },
    {
        "name": "finish_migration",
        "description": TOOLS_OPENAI[4]["function"]["description"],
        "input_schema": {
            "type": "object",
            "properties": {
                "pipeline": {"type": "string"},
                "outcome":  {"type": "string", "enum": ["SUCCESS", "PARTIAL", "HALTED", "FAILED"]},
                "summary":  {"type": "string"},
            },
            "required": ["pipeline", "outcome", "summary"],
        },
    },
]


# ── Executor ──────────────────────────────────────────────────────────────────

async def execute_tool(name: str, args: dict, context: dict) -> dict:
    """
    Single dispatch point — orchestrator calls this with the tool name
    and args the LLM chose. Returns structured result stored in context.

    context accumulates results between calls so each agent has access
    to what the previous agents produced without the LLM needing to
    pass data explicitly.
    """
    pipeline = args.get("pipeline", "")

    if name == "run_assessment":
        result = await run_assessment(pipeline)
        context["assessment"] = result
        return _summarise("assessment", result, [
            f"complexity={result.get('complexity')}",
            f"tables={result.get('tables')}",
            f"udfs={result.get('udfs')}",
            f"effort={result.get('estimated_effort')}",
        ])

    elif name == "run_conversion":
        assessment = context.get("assessment", {})
        result = await run_conversion(assessment)
        context["conversion"] = result
        return _summarise("conversion", result, [
            f"status={result.get('conversion_status')}",
            f"files={len(result.get('files', []))}",
            f"transformations={result.get('transformations_applied')}",
        ])

    elif name == "run_reconciliation":
        assessment  = context.get("assessment",  {})
        conversion  = context.get("conversion",  {})
        result = await run_reconciliation(assessment, conversion)
        context["reconciliation"] = result
        return _summarise("reconciliation", result, [
            f"validation_status={result.get('validation_status')}",
            f"confidence={result.get('confidence_score', 0):.0%}",
            f"risk={result.get('migration_risk')}",
            f"issues={len(result.get('issues', []))}",
        ])

    elif name == "run_deployment":
        assessment     = context.get("assessment",     {})
        conversion     = context.get("conversion",     {})
        reconciliation = context.get("reconciliation", {})
        result = await run_deployment(assessment, conversion, reconciliation)
        context["deployment"] = result
        return _summarise("deployment", result, [
            f"status={result.get('deployment_status')}",
            f"readiness={result.get('readiness_score')}%",
            f"smoke={result.get('smoke_results', {}).get('passed')}/{result.get('smoke_results', {}).get('total')}",
        ])

    elif name == "finish_migration":
        context["finished"] = True
        context["outcome"]  = args.get("outcome")
        context["summary"]  = args.get("summary")
        return {
            "status":   "complete",
            "pipeline": pipeline,
            "outcome":  args.get("outcome"),
            "summary":  args.get("summary"),
        }

    else:
        return {"error": f"Unknown tool: {name}"}


def _summarise(stage: str, result: dict, highlights: list[str]) -> dict:
    """Return a compact result dict so the LLM context window stays small."""
    return {
        "stage":      stage,
        "highlights": highlights,
        "full_result_keys": list(result.keys()),
    }

"""
Orchestrator — delegates to the 4 phase agents via the RLM orchestrator agent.
Exposes result stores for the FastAPI endpoints in main.py.
"""

from agents.orchestrator.migrate import run_orchestrator

DEFAULT_PIPELINE = "silver_orders"

results:         dict = {}
conversions:     dict = {}
reconciliations: dict = {}
deployments:     dict = {}
running:         set  = set()   # pipelines currently being processed


async def run_pipeline(pipeline_name: str = DEFAULT_PIPELINE) -> dict | None:
    running.add(pipeline_name)
    try:
        result = await run_orchestrator(pipeline_name)
        results[pipeline_name] = result
        if isinstance(result, dict):
            conversions[pipeline_name]     = result.get("conversion", {})
            reconciliations[pipeline_name] = result.get("reconciliation", {})
            deployments[pipeline_name]     = result.get("deployment", {})
        return result
    finally:
        running.discard(pipeline_name)

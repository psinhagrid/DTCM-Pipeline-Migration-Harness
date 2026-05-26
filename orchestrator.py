"""
Orchestrator — delegates to the RLM migration agent.
Exposes result stores for the FastAPI endpoints in main.py.
"""

from rlm.migrate import run_migration

DEFAULT_PIPELINE = "silver_orders"

results:         dict = {}
conversions:     dict = {}
reconciliations: dict = {}
deployments:     dict = {}


async def run_pipeline(pipeline_name: str = DEFAULT_PIPELINE) -> dict | None:
    result = await run_migration(pipeline_name)
    results[pipeline_name] = result
    if isinstance(result, dict):
        if result.get("assessment"):
            conversions[pipeline_name]     = result.get("conversion", {})
            reconciliations[pipeline_name] = result.get("reconciliation", {})
            deployments[pipeline_name]     = result.get("deployment", {})
    return result

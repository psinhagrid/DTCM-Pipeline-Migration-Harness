"""
Thin shim — delegates to the supervisor agent and exposes result stores
for the FastAPI endpoints in main.py.
"""

from supervisor import run_migration, context_store

DEFAULT_PIPELINE = "daily_revenue_agg"

# Result stores read by API endpoints
results:         dict = {}
conversions:     dict = {}
reconciliations: dict = {}
deployments:     dict = {}


async def run_pipeline(pipeline_name: str = DEFAULT_PIPELINE) -> dict | None:
    await run_migration(pipeline_name)

    ctx = context_store.get(pipeline_name, {})
    results[pipeline_name]         = ctx.get("assessment",     {})
    conversions[pipeline_name]     = ctx.get("conversion",     {})
    reconciliations[pipeline_name] = ctx.get("reconciliation", {})
    deployments[pipeline_name]     = ctx.get("deployment",     {})

    return results.get(pipeline_name)

"""
Query the Neo4j lineage graph for context about a pipeline.
Wraps graph/client.py — the project-level Neo4j integration.
Falls back gracefully if Neo4j is unavailable or graph is empty.
"""

from graph.client import (
    query_downstream,
    query_upstream,
    query_blast_radius,
    query_migration_wave,
    query_pipeline_summary,
)


def query_graph_tool(pipeline: str, query: str = "summary") -> dict:
    """
    Query Neo4j for graph context about a pipeline.

    query options:
      "summary"      — complexity, effort, reads, writes, UDFs, deps (default)
      "downstream"   — pipelines that consume this one's output
      "upstream"     — pipelines this one depends on
      "blast_radius" — all pipelines broken if this one fails (transitive)
      "wave"         — migration wave number (0 = migrate first)

    Returns empty dict / empty list if Neo4j is unavailable.
    Treat empty results as "graph not yet built" and proceed.
    """
    try:
        if query == "downstream":
            return {"downstream": query_downstream(pipeline)}
        elif query == "upstream":
            return {"upstream": query_upstream(pipeline)}
        elif query == "blast_radius":
            affected = query_blast_radius(pipeline)
            return {"blast_radius": affected, "count": len(affected)}
        elif query == "wave":
            return {"migration_wave": query_migration_wave(pipeline)}
        else:
            return query_pipeline_summary(pipeline) or {}
    except Exception as e:
        return {"error": str(e), "note": "Neo4j unavailable — graph not yet built"}

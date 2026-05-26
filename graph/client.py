"""
Neo4j graph client — lineage queries for any subagent or endpoint.
Connection config: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in .env

Import from anywhere:
    from graph.client import query_downstream, query_blast_radius
    from graph import query_migration_wave
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[1] / ".env")

from neo4j import GraphDatabase


def _driver():
    return GraphDatabase.driver(
        os.getenv("NEO4J_URI",      "bolt://localhost:7687"),
        auth=(
            os.getenv("NEO4J_USER",     "neo4j"),
            os.getenv("NEO4J_PASSWORD", "dtcm_local"),
        ),
    )


def _run(cypher: str, **params) -> list[dict]:
    drv = _driver()
    try:
        with drv.session() as session:
            return [dict(r) for r in session.run(cypher, **params)]
    finally:
        drv.close()


def query_downstream(pipeline: str) -> list[str]:
    """Direct pipelines that consume this one's output."""
    try:
        rows = _run("""
            MATCH (consumer:Pipeline)-[:DEPENDS_ON]->(p:Pipeline {name: $name})
            RETURN consumer.name AS name
        """, name=pipeline)
        return [r["name"] for r in rows]
    except Exception:
        return []


def query_upstream(pipeline: str) -> list[str]:
    """Direct pipelines this one depends on."""
    try:
        rows = _run("""
            MATCH (p:Pipeline {name: $name})-[:DEPENDS_ON]->(dep:Pipeline)
            RETURN dep.name AS name
        """, name=pipeline)
        return [r["name"] for r in rows]
    except Exception:
        return []


def query_blast_radius(pipeline: str) -> list[str]:
    """All pipelines (direct + transitive) that break if this one fails."""
    try:
        rows = _run("""
            MATCH (p:Pipeline {name: $name})<-[:DEPENDS_ON*1..]-(affected:Pipeline)
            RETURN DISTINCT affected.name AS name
        """, name=pipeline)
        return [r["name"] for r in rows]
    except Exception:
        return []


def query_migration_wave(pipeline: str) -> int:
    """Migration wave (0 = first, no deps). Higher = must wait for earlier waves."""
    try:
        rows = _run("""
            MATCH path = (p:Pipeline {name: $name})-[:DEPENDS_ON*0..]->(root:Pipeline)
            WHERE NOT (root)-[:DEPENDS_ON]->()
            RETURN max(length(path)) AS depth
        """, name=pipeline)
        if rows and rows[0]["depth"] is not None:
            return rows[0]["depth"]
        return 0
    except Exception:
        return 0


def query_pipeline_summary(pipeline: str) -> dict:
    """Full pipeline info: complexity, effort, reads, writes, UDFs, dependencies."""
    try:
        rows = _run("""
            MATCH (p:Pipeline {name: $name})
            OPTIONAL MATCH (p)-[:READS]->(rt:Table)
            OPTIONAL MATCH (p)-[:WRITES]->(wt:Table)
            OPTIONAL MATCH (p)-[:USES_UDF]->(u:UDF)
            OPTIONAL MATCH (p)-[:DEPENDS_ON]->(dep:Pipeline)
            OPTIONAL MATCH (consumer:Pipeline)-[:DEPENDS_ON]->(p)
            RETURN
                p.complexity        AS complexity,
                p.estimated_effort  AS estimated_effort,
                p.last_assessed     AS last_assessed,
                collect(DISTINCT rt.name)       AS reads,
                collect(DISTINCT wt.name)       AS writes,
                collect(DISTINCT u.name)        AS udfs,
                collect(DISTINCT dep.name)      AS depends_on,
                collect(DISTINCT consumer.name) AS consumed_by
        """, name=pipeline)
        return rows[0] if rows else {}
    except Exception:
        return {}


def query_all_pipelines() -> list[dict]:
    """Full graph snapshot — used by /graph API endpoint."""
    try:
        rows = _run("""
            MATCH (p:Pipeline)
            OPTIONAL MATCH (p)-[:READS]->(rt:Table)
            OPTIONAL MATCH (p)-[:WRITES]->(wt:Table)
            OPTIONAL MATCH (p)-[:USES_UDF]->(u:UDF)
            OPTIONAL MATCH (p)-[:DEPENDS_ON]->(dep:Pipeline)
            OPTIONAL MATCH (consumer:Pipeline)-[:DEPENDS_ON]->(p)
            RETURN
                p.name              AS name,
                p.complexity        AS complexity,
                p.estimated_effort  AS estimated_effort,
                collect(DISTINCT rt.name)       AS reads,
                collect(DISTINCT wt.name)       AS writes,
                collect(DISTINCT u.name)        AS udfs,
                collect(DISTINCT dep.name)      AS depends_on,
                collect(DISTINCT consumer.name) AS consumed_by
            ORDER BY p.name
        """)
        return rows
    except Exception:
        return []


def query_full_graph() -> dict:
    """
    Fetch the complete 5-tier hierarchy from Neo4j.

    Returns:
        {
          "nodes": [{"id": str, "type": str, "label": str, "properties": dict}, ...],
          "edges": [{"id": str, "source": str, "target": str, "type": str}, ...]
        }

    Node types: Pipeline, Workflow, Job, Query, Table, UDF
    Edge types: CONTAINS, HAS_JOB, HAS_QUERY, READS, WRITES,
                DEPENDS_ON, USES_UDF
    """
    try:
        node_rows = _run("""
            MATCH (n)
            WHERE n:Pipeline OR n:Workflow OR n:Job OR n:Query
               OR n:Table    OR n:UDF
            RETURN
                elementId(n)    AS eid,
                labels(n)[0]    AS type,
                properties(n)   AS props
        """)

        edge_rows = _run("""
            MATCH (a)-[r]->(b)
            WHERE (a:Pipeline OR a:Workflow OR a:Job OR a:Query OR a:Table OR a:UDF)
              AND (b:Pipeline OR b:Workflow OR b:Job OR b:Query OR b:Table OR b:UDF)
            RETURN
                elementId(r)    AS eid,
                elementId(a)    AS source,
                elementId(b)    AS target,
                type(r)         AS type
        """)

        def _label(node_type: str, props: dict) -> str:
            """Human-readable label for each node type."""
            if node_type == "Pipeline":
                return props.get("name", "")
            if node_type == "Workflow":
                return props.get("name", "").replace("_workflow", "")
            if node_type == "Job":
                return props.get("job_name", props.get("filename", ""))
            if node_type == "Query":
                return props.get("query_type", "Query")
            if node_type == "Table":
                return props.get("name", "")
            if node_type == "UDF":
                return props.get("name", "")
            return props.get("name", node_type)

        nodes = [
            {
                "id":         r["eid"],
                "type":       r["type"],
                "label":      _label(r["type"], r["props"]),
                "properties": dict(r["props"]),
            }
            for r in node_rows
        ]

        edges = [
            {
                "id":     r["eid"],
                "source": r["source"],
                "target": r["target"],
                "type":   r["type"],
            }
            for r in edge_rows
        ]

        return {"nodes": nodes, "edges": edges}
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}


def compute_migration_plan(pipelines: list[dict] | None = None) -> list[dict]:
    """
    Compute the recommended migration wave order from the pipeline graph.
    Pure topological sort — no business logic, no LLM.

    Returns a list of waves, each with:
      wave              int — 0 = no dependencies (migrate first)
      can_run_parallel  bool — multiple pipelines in this wave can run simultaneously
      pipelines         list — sorted by direct consumer count descending within wave
    """
    if pipelines is None:
        pipelines = query_all_pipelines()
    if not pipelines:
        return []

    name_set = {p["name"] for p in pipelines}

    # Assign tier 0 to pipelines with no in-graph dependencies
    tiers: dict[str, int] = {}
    for p in pipelines:
        if not any(d in name_set for d in (p.get("depends_on") or [])):
            tiers[p["name"]] = 0

    # Propagate: tier = max(upstream tiers) + 1
    changed = True
    while changed:
        changed = False
        for p in pipelines:
            if p["name"] in tiers:
                continue
            deps = [d for d in (p.get("depends_on") or []) if d in name_set]
            if all(d in tiers for d in deps):
                tiers[p["name"]] = max((tiers[d] for d in deps), default=0) + 1
                changed = True

    for p in pipelines:
        tiers.setdefault(p["name"], 0)   # unresolved cycles fall to wave 0

    max_tier = max(tiers.values(), default=0)

    waves = []
    for ti in range(max_tier + 1):
        wave_pl = [p for p in pipelines if tiers[p["name"]] == ti]
        # Within a wave: highest direct consumer count first (most impactful pipeline visible first)
        wave_pl.sort(key=lambda p: len(p.get("consumed_by") or []), reverse=True)
        waves.append({
            "wave":             ti,
            "can_run_parallel": len(wave_pl) > 1,
            "pipelines": [
                {
                    "name":             p["name"],
                    "complexity":       p.get("complexity"),
                    "estimated_effort": p.get("estimated_effort"),
                    "depends_on":       [d for d in (p.get("depends_on") or []) if d in name_set],
                    "blast_radius":     len(p.get("consumed_by") or []),
                    "writes":           len(p.get("writes") or []),
                    "udfs":             len(p.get("udfs") or []),
                }
                for p in wave_pl
            ],
        })
    return waves

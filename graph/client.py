"""
Neo4j graph client — lineage queries for any module or endpoint.
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
        if not rows:
            return {}
        row = dict(rows[0])
        if row.get("last_assessed") is not None:
            try:
                row["last_assessed"] = row["last_assessed"].iso_format()
            except Exception:
                row["last_assessed"] = str(row["last_assessed"])
        return row
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

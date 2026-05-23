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

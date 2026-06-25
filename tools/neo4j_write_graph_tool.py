"""
Neo4j lineage graph writer.
Writes pipeline, table, and UDF nodes + READS/WRITES/DEPENDS_ON/USES_UDF relationships.
Connection config via env: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[4] / ".env")

from neo4j import GraphDatabase


def neo4j_write_graph_tool(
    pipeline: str,
    upstream_tables: list[str],
    output_tables: list[str],
    downstream: list[str],
    udfs: list[str],
    complexity: str,
    estimated_effort: str = "",
) -> dict:
    """
    Write pipeline lineage graph to Neo4j.
    Creates Pipeline + Table + UDF nodes and their relationships.
    MERGE is used throughout so re-running is safe (idempotent).
    """
    uri      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
    user     = os.getenv("NEO4J_USER",     "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "dtcm_local")

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            session.execute_write(
                _write_graph,
                pipeline, complexity, estimated_effort,
                upstream_tables, output_tables, udfs, downstream,
            )
        driver.close()
        return {
            "status":   "ok",
            "pipeline": pipeline,
            "nodes":    1 + len(set(upstream_tables + output_tables)) + len(udfs),
            "edges":    len(upstream_tables) + len(output_tables) + len(udfs) + len(downstream),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _write_graph(
    tx,
    pipeline: str,
    complexity: str,
    estimated_effort: str,
    upstream_tables: list[str],
    output_tables: list[str],
    udfs: list[str],
    downstream: list[str],
) -> None:
    # Only delete READS/WRITES/USES_UDF — relationships this pipeline owns.
    # Do NOT delete DEPENDS_ON (those are created by upstream pipelines and
    # deleting them here causes a race condition in parallel builds).
    tx.run("""
        MATCH (p:Pipeline {name: $name})
        OPTIONAL MATCH (p)-[r:READS|WRITES|USES_UDF]->() DELETE r
    """, name=pipeline)

    # Upsert Pipeline node
    tx.run("""
        MERGE (p:Pipeline {name: $name})
        SET p.complexity       = $complexity,
            p.estimated_effort = $effort,
            p.last_assessed    = datetime()
    """, name=pipeline, complexity=complexity, effort=estimated_effort)

    # Upstream tables (sources — this pipeline reads but doesn't own)
    for table in upstream_tables:
        tx.run("""
            MERGE (t:Table {name: $table})
            ON CREATE SET t.type = 'source'
            WITH t
            MATCH (p:Pipeline {name: $pipeline})
            MERGE (p)-[:READS]->(t)
        """, table=table, pipeline=pipeline)

    # Output tables (sinks — this pipeline produces)
    for table in output_tables:
        tx.run("""
            MERGE (t:Table {name: $table})
            SET t.type = 'sink'
            WITH t
            MATCH (p:Pipeline {name: $pipeline})
            MERGE (p)-[:WRITES]->(t)
        """, table=table, pipeline=pipeline)

    # UDFs
    for udf in udfs:
        tx.run("""
            MERGE (u:UDF {name: $udf})
            WITH u
            MATCH (p:Pipeline {name: $pipeline})
            MERGE (p)-[:USES_UDF]->(u)
        """, udf=udf, pipeline=pipeline)

    # Downstream consumers (other pipelines that read this pipeline's output tables)
    for consumer in downstream:
        tx.run("""
            MERGE (c:Pipeline {name: $consumer})
            WITH c
            MATCH (p:Pipeline {name: $pipeline})
            MERGE (c)-[:DEPENDS_ON]->(p)
        """, consumer=consumer, pipeline=pipeline)

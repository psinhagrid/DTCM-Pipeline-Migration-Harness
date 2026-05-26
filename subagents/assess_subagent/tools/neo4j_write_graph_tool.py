"""
Neo4j lineage graph writer.

Writes the full 5-tier hierarchy:
    Pipeline → Workflow → Job → Query → Table

Also writes aggregate Pipeline-[:READS/WRITES]->Table edges for backward-compatible
graph queries, cross-pipeline DEPENDS_ON, intra-pipeline Job-[:DEPENDS_ON]->Job edges,
and Pipeline-[:USES_UDF]->UDF edges.

Connection config via env: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[4] / ".env")

from neo4j import GraphDatabase


def neo4j_write_graph_tool(
    pipeline: str,
    jobs: list[dict],
    upstream_tables: list[str],
    output_tables: list[str],
    downstream: list[str],
    udfs: list[str],
    complexity: str,
    estimated_effort: str = "",
) -> dict:
    """
    Write the full pipeline lineage graph to Neo4j.

    Hierarchy created:
        Pipeline -[:CONTAINS]-> Workflow
        Workflow -[:HAS_JOB]->  Job          (one per HQL file)
        Job      -[:HAS_QUERY]-> Query        (one per DML statement)
        Query    -[:READS]->    Table
        Query    -[:WRITES]->   Table

    Cross-links:
        Job      -[:DEPENDS_ON]-> Job         (intra-pipeline: JobB reads what JobA writes)
        Pipeline -[:DEPENDS_ON]-> Pipeline    (inter-pipeline consumers)
        Pipeline -[:READS]->    Table         (aggregate, backward-compat)
        Pipeline -[:WRITES]->   Table         (aggregate, backward-compat)
        Pipeline -[:USES_UDF]-> UDF

    jobs format:
        [{
            "filename":       str,             # e.g. "load_revenue.hql"
            "read_tables":    list[str],
            "written_tables": list[str],
            "created_tables": list[str],
            "queries": [{
                "query_index":    int,
                "query_type":     str,          # INSERT_OVERWRITE | INSERT_INTO | ...
                "query_text":     str,
                "read_tables":    list[str],
                "written_tables": list[str],
                "join_count":     int,
                "subquery_count": int,
                "uses_window":    bool,
                "uses_udf":       bool,
            }]
        }]

    MERGE is used throughout — re-running is idempotent.
    """
    uri      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
    user     = os.getenv("NEO4J_USER",     "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "dtcm_local")

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            node_count, edge_count = session.execute_write(
                _write_graph,
                pipeline, complexity, estimated_effort,
                jobs, upstream_tables, output_tables, udfs, downstream,
            )
        driver.close()
        return {
            "status":     "ok",
            "pipeline":   pipeline,
            "nodes":      node_count,
            "edges":      edge_count,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _write_graph(
    tx,
    pipeline: str,
    complexity: str,
    estimated_effort: str,
    jobs: list[dict],
    upstream_tables: list[str],
    output_tables: list[str],
    udfs: list[str],
    downstream: list[str],
) -> tuple[int, int]:
    """Write all nodes and relationships; return (node_count, edge_count)."""

    nodes = 0
    edges = 0

    # ── 1. Clean up owned relationships so re-runs stay idempotent ──────────
    # Delete only relationships owned by this pipeline; leave DEPENDS_ON
    # (written by *downstream* pipelines) intact to avoid race conditions.
    tx.run("""
        MATCH (p:Pipeline {name: $name})
        OPTIONAL MATCH (p)-[r:READS|WRITES|USES_UDF|CONTAINS]->() DELETE r
    """, name=pipeline)
    tx.run("""
        MATCH (wf:Workflow {pipeline: $name})
        OPTIONAL MATCH (wf)-[r:HAS_JOB]->() DELETE r
    """, name=pipeline)
    tx.run("""
        MATCH (j:Job {pipeline: $name})
        OPTIONAL MATCH (j)-[r:HAS_QUERY|DEPENDS_ON]->() DELETE r
    """, name=pipeline)

    # ── 2. Pipeline node ─────────────────────────────────────────────────────
    tx.run("""
        MERGE (p:Pipeline {name: $name})
        SET p.complexity       = $complexity,
            p.estimated_effort = $effort,
            p.last_assessed    = datetime()
    """, name=pipeline, complexity=complexity, effort=estimated_effort)
    nodes += 1

    # ── 3. Workflow node (one per pipeline) ──────────────────────────────────
    workflow_name = f"{pipeline}_workflow"
    tx.run("""
        MERGE (wf:Workflow {name: $wf_name})
        SET wf.pipeline       = $pipeline,
            wf.scheduler_type = 'oozie',
            wf.last_assessed  = datetime()
        WITH wf
        MATCH (p:Pipeline {name: $pipeline})
        MERGE (p)-[:CONTAINS]->(wf)
    """, wf_name=workflow_name, pipeline=pipeline)
    nodes += 1
    edges += 1

    # ── 4. Job nodes (one per HQL file) ─────────────────────────────────────
    for job in jobs:
        filename  = job.get("filename", "")
        job_name  = filename.replace(".hql", "")
        job_id    = f"{pipeline}.{job_name}"

        tx.run("""
            MERGE (j:Job {job_id: $job_id})
            SET j.job_name         = $job_name,
                j.filename         = $filename,
                j.pipeline         = $pipeline,
                j.job_type         = 'HIVE',
                j.execution_engine = 'MAPREDUCE',
                j.migration_status = 'NOT_STARTED'
            WITH j
            MATCH (wf:Workflow {name: $wf_name})
            MERGE (wf)-[:HAS_JOB]->(j)
        """, job_id=job_id, job_name=job_name, filename=filename,
             pipeline=pipeline, wf_name=workflow_name)
        nodes += 1
        edges += 1

        # ── 5. Query nodes (one per DML statement) ───────────────────────────
        for q in job.get("queries", []):
            query_id = f"{job_id}.q{q.get('query_index', 0)}"
            tx.run("""
                MERGE (qn:Query {query_id: $query_id})
                SET qn.query_type     = $query_type,
                    qn.query_text     = $query_text,
                    qn.pipeline       = $pipeline,
                    qn.job_id         = $job_id,
                    qn.join_count     = $join_count,
                    qn.subquery_count = $subquery_count,
                    qn.uses_window    = $uses_window,
                    qn.uses_udf       = $uses_udf
                WITH qn
                MATCH (j:Job {job_id: $job_id})
                MERGE (j)-[:HAS_QUERY]->(qn)
            """,
            query_id=query_id,
            query_type=q.get("query_type", "OTHER"),
            query_text=q.get("query_text", "")[:2000],
            pipeline=pipeline,
            job_id=job_id,
            join_count=q.get("join_count", 0),
            subquery_count=q.get("subquery_count", 0),
            uses_window=q.get("uses_window", False),
            uses_udf=q.get("uses_udf", False))
            nodes += 1
            edges += 1

            # Query reads tables
            for tbl in q.get("read_tables", []):
                tx.run("""
                    MERGE (t:Table {name: $table})
                    ON CREATE SET t.type = 'source'
                    WITH t
                    MATCH (qn:Query {query_id: $query_id})
                    MERGE (qn)-[:READS]->(t)
                """, table=tbl, query_id=query_id)
                nodes += 1
                edges += 1

            # Query writes tables
            for tbl in q.get("written_tables", []):
                tx.run("""
                    MERGE (t:Table {name: $table})
                    SET t.type = 'sink'
                    WITH t
                    MATCH (qn:Query {query_id: $query_id})
                    MERGE (qn)-[:WRITES]->(t)
                """, table=tbl, query_id=query_id)
                nodes += 1
                edges += 1

    # ── 6. Intra-pipeline Job dependencies ──────────────────────────────────
    # JobB DEPENDS_ON JobA when JobA writes a table that JobB reads.
    table_written_by: dict[str, str] = {}
    for job in jobs:
        job_id = f"{pipeline}.{job.get('filename', '').replace('.hql', '')}"
        for tbl in list(job.get("written_tables", [])) + list(job.get("created_tables", [])):
            table_written_by[tbl] = job_id

    for job in jobs:
        job_b_id = f"{pipeline}.{job.get('filename', '').replace('.hql', '')}"
        for tbl in job.get("read_tables", []):
            job_a_id = table_written_by.get(tbl)
            if job_a_id and job_a_id != job_b_id:
                tx.run("""
                    MATCH (b:Job {job_id: $b_id})
                    MATCH (a:Job {job_id: $a_id})
                    MERGE (b)-[:DEPENDS_ON]->(a)
                """, b_id=job_b_id, a_id=job_a_id)
                edges += 1

    # ── 7. Aggregate Pipeline reads/writes (backward-compat) ─────────────────
    for tbl in upstream_tables:
        tx.run("""
            MERGE (t:Table {name: $table})
            ON CREATE SET t.type = 'source'
            WITH t
            MATCH (p:Pipeline {name: $pipeline})
            MERGE (p)-[:READS]->(t)
        """, table=tbl, pipeline=pipeline)
        edges += 1

    for tbl in output_tables:
        tx.run("""
            MERGE (t:Table {name: $table})
            SET t.type = 'sink'
            WITH t
            MATCH (p:Pipeline {name: $pipeline})
            MERGE (p)-[:WRITES]->(t)
        """, table=tbl, pipeline=pipeline)
        edges += 1

    # ── 8. UDFs ──────────────────────────────────────────────────────────────
    for udf in udfs:
        tx.run("""
            MERGE (u:UDF {name: $udf})
            WITH u
            MATCH (p:Pipeline {name: $pipeline})
            MERGE (p)-[:USES_UDF]->(u)
        """, udf=udf, pipeline=pipeline)
        nodes += 1
        edges += 1

    # ── 9. Cross-pipeline DEPENDS_ON ─────────────────────────────────────────
    for consumer in downstream:
        tx.run("""
            MERGE (c:Pipeline {name: $consumer})
            WITH c
            MATCH (p:Pipeline {name: $pipeline})
            MERGE (c)-[:DEPENDS_ON]->(p)
        """, consumer=consumer, pipeline=pipeline)
        edges += 1

    return nodes, edges

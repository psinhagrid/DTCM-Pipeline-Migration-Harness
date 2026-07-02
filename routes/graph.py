import asyncio
import os
from pathlib import Path
from fastapi import APIRouter
from graph.client import query_all_pipelines, compute_migration_plan

router = APIRouter()

_PIPELINES_ROOT = Path(__file__).parents[1] / "pipelines"


@router.post("/build-graph")
async def build_graph():
    """
    Populate Neo4j by calling assessment tools directly — no LLM, no API cost.
    Runs all pipelines sequentially to avoid Neo4j race conditions.
    """
    from neo4j import GraphDatabase
    from agents.assess_agent.tools_impl.utils.hql_utils import parse_file, compute_score, classify, EFFORT
    from agents.assess_agent.tools_impl.scan_repo_tool import scan_repo_tool
    from agents.assess_agent.tools_impl.lineage_extract_tool import lineage_extract_tool
    from agents.assess_agent.tools_impl.neo4j_write_graph_tool import neo4j_write_graph_tool

    if not _PIPELINES_ROOT.exists():
        return {"status": "error", "error": "pipelines/ directory not found"}

    # Wipe existing graph first
    try:
        drv = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "dtcm_local")),
        )
        with drv.session() as s:
            s.run("MATCH (n) DETACH DELETE n")
        drv.close()
    except Exception as e:
        return {"status": "error", "error": f"Neo4j wipe failed: {e}"}

    pipeline_dirs = [d for d in sorted(_PIPELINES_ROOT.iterdir()) if d.is_dir()]

    async def _assess(pipeline_dir: Path) -> dict:
        name = pipeline_dir.name
        scan = scan_repo_tool(pipeline_dir)
        hql_files = scan["hql_files"]

        all_reads = set(); all_creates = set(); all_writes = set()
        all_udfs = set(); has_window = False; total_subq = 0
        has_dyn_part = False; cross_db = set()

        for hql in hql_files:
            f = await asyncio.to_thread(parse_file, hql)
            all_reads    |= f["read_tables"];   all_creates |= f["created_tables"]
            all_writes   |= f["written_tables"]; all_udfs   |= set(f["udfs"])
            has_window    = has_window or f["has_window"]
            total_subq   += f["subqueries"];    has_dyn_part = has_dyn_part or f["has_dyn_part"]
            cross_db     |= set(f["cross_db_joins"])

        all_tables = all_reads | all_creates | all_writes
        lineage = await asyncio.to_thread(lineage_extract_tool, all_reads, all_creates, all_writes, pipeline_dir)
        score = compute_score(all_tables, all_udfs, has_window, cross_db, has_dyn_part, total_subq, lineage["downstream"])
        complexity = classify(score)

        neo = neo4j_write_graph_tool(
            pipeline=name,
            upstream_tables=lineage["upstream"],
            output_tables=lineage["output_tables"],
            downstream=lineage["downstream"],
            udfs=sorted(all_udfs),
            complexity=complexity,
            estimated_effort=EFFORT[complexity],
        )
        return {"pipeline": name, "complexity": complexity, "tables": len(all_tables),
                "neo4j": neo.get("status", "error") if neo else "error"}

    results = []
    for d in pipeline_dirs:
        results.append(await _assess(d))

    return {"status": "done", "pipelines": results}


@router.get("/graph")
def get_graph():
    """Full pipeline lineage graph from Neo4j."""
    try:
        return {"pipelines": query_all_pipelines(), "error": None}
    except Exception as e:
        return {"pipelines": [], "error": str(e)}


@router.get("/migration-plan")
def get_migration_plan():
    """
    Recommended pipeline migration order from the Neo4j lineage graph.
    Waves are topologically sorted — Wave 0 has no dependencies and migrates first.
    Within each wave, pipelines are ordered by direct consumer count descending.
    """
    try:
        waves = compute_migration_plan()
        return {
            "waves":            waves,
            "total_pipelines":  sum(len(w["pipelines"]) for w in waves),
            "error":            None,
        }
    except Exception as e:
        return {"waves": [], "total_pipelines": 0, "error": str(e)}

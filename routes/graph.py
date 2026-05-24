from fastapi import APIRouter
from graph.client import query_all_pipelines, compute_migration_plan

router = APIRouter()


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

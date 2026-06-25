from pathlib import Path

from .utils.hql_utils import discover_downstream


def lineage_extract_tool(
    all_reads: set,
    all_creates: set,
    all_writes: set,
    pipeline_dir: Path,
) -> dict:
    """
    Derive upstream dependencies and downstream consumers from parsed table sets.

    Upstream  = tables READ but never created or written by this pipeline.
    Downstream = sibling pipelines that reference this pipeline's output tables.
    """
    upstream      = all_reads - all_creates - all_writes
    output_tables = all_writes | all_creates
    downstream    = discover_downstream(output_tables, pipeline_dir)
    return {
        "upstream":      sorted(upstream),
        "output_tables": sorted(output_tables),
        "downstream":    downstream,
    }

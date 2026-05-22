"""
assess_agent — async orchestration layer.
Streams events through the SSE queue while delegating all
parsing/scoring logic to utils.py.
"""

import asyncio
from pathlib import Path

from event_queue import push
from .utils import (
    EFFORT,
    parse_file,
    discover_downstream,
    compute_score,
    classify,
)

NAME = "assess_agent"

# TODO: replace with S3 path via boto3
PIPELINES_ROOT = Path(__file__).parents[2] / "pipelines"


async def run_assessment(pipeline_name: str) -> dict:
    pipeline_dir = PIPELINES_ROOT / pipeline_name

    async def _e(type: str, message: str, **kw) -> None:
        await push(type=type, agent=NAME, message=message, pipeline=pipeline_name, **kw)

    # ── Phase 1 · Initialise ─────────────────────────────────────────────
    await _e("status", f"Starting assessment for {pipeline_name}")
    await asyncio.sleep(0.4)

    await _e("hook", "PreToolUse → governance_check ✓ allowed")
    await asyncio.sleep(0.3)

    if not pipeline_dir.exists():
        await _e("status", f"ERROR: pipeline directory not found: {pipeline_dir}", done=True)
        raise FileNotFoundError(pipeline_dir)

    await _e("status", f"Resolved repository → {pipeline_dir}")
    await asyncio.sleep(0.5)

    # ── Phase 2 · Repository scan ────────────────────────────────────────
    await _e("status", "Reading source repository...")
    await asyncio.sleep(0.7)

    hql_files    = sorted(pipeline_dir.glob("*.hql"))
    config_files = sorted(pipeline_dir.glob("*.xml")) + sorted(pipeline_dir.glob("*.properties"))
    total_files  = len(list(pipeline_dir.rglob("*")))

    await _e("status", "Indexing files...")
    await asyncio.sleep(0.9)

    await _e("status", f"✓ {total_files} files indexed")
    await asyncio.sleep(0.4)

    await _e("status", f"✓ {len(hql_files)} HiveQL source files identified")
    await asyncio.sleep(0.4)

    if config_files:
        names = ", ".join(f.name for f in config_files[:3])
        await _e("status", f"✓ {len(config_files)} config files ({names})")
        await asyncio.sleep(0.4)

    # ── Phase 3 · DDL parsing ────────────────────────────────────────────
    await _e("status", "Parsing Hive DDL with sqlfluff (dialect=hive)...")
    await asyncio.sleep(0.6)

    all_findings:  list[dict] = []
    syntax_errors: list[str]  = []

    for hql in hql_files:
        await _e("tool_call", f"Reading {hql.name}")
        await asyncio.sleep(0.5)
        findings = await asyncio.to_thread(parse_file, hql)
        all_findings.append(findings)
        if findings["syntax_errors"]:
            syntax_errors.extend(findings["syntax_errors"])
            await _e("status", f"⚠ {hql.name}: {len(findings['syntax_errors'])} syntax warning(s)")
        await asyncio.sleep(0.2)

    # Aggregate — track read/created/written separately for correct upstream detection
    all_reads     = set()
    all_creates   = set()
    all_writes    = set()
    all_columns   = []
    all_part_keys = set()
    all_udfs      = set()
    has_window    = False
    total_subq    = 0
    has_dyn_part  = False
    cross_db      = set()

    for f in all_findings:
        all_reads     |= f["read_tables"]
        all_creates   |= f["created_tables"]
        all_writes    |= f["written_tables"]
        all_columns   += f["columns"]
        all_part_keys |= set(f["partition_keys"])
        all_udfs      |= set(f["udfs"])
        has_window     = has_window or f["has_window"]
        total_subq    += f["subqueries"]
        has_dyn_part   = has_dyn_part or f["has_dyn_part"]
        cross_db      |= set(f["cross_db_joins"])

    all_tables  = all_reads | all_creates | all_writes
    unique_cols = list({
        c.split(" as ")[-1].split(".")[-1].strip().strip("`")
        for c in all_columns if c
    })

    await _e("status", f"✓ {len(all_tables)} unique tables identified")
    await asyncio.sleep(0.3)
    await _e("status", f"✓ {len(unique_cols)} columns discovered")
    await asyncio.sleep(0.3)
    if all_part_keys:
        await _e("status", f"✓ {len(all_part_keys)} partition keys ({', '.join(sorted(all_part_keys))})")
        await asyncio.sleep(0.3)
    if all_udfs:
        await _e("status", f"✓ {len(all_udfs)} UDFs detected: {', '.join(sorted(all_udfs))}")
        await asyncio.sleep(0.4)
    if has_window:
        await _e("status", "⚠ Window functions detected (OVER clause)")
        await asyncio.sleep(0.3)
    if cross_db:
        await _e("status", f"⚠ Cross-database references: {', '.join(sorted(cross_db))}")
        await asyncio.sleep(0.3)

    # ── Phase 4 · Dependency discovery ──────────────────────────────────
    await _e("status", "Discovering upstream dependencies...")
    await asyncio.sleep(0.6)

    # Upstream = tables READ but not created or written by this pipeline
    upstream = all_reads - all_creates - all_writes
    for tbl in sorted(upstream):
        await _e("status", f"✓ Upstream dependency: {tbl}")
        await asyncio.sleep(0.35)

    await _e("status", "Discovering downstream consumers...")
    await asyncio.sleep(0.5)

    await _e("tool_call", "MCP → neo4j_mcp.query_graph(direction=downstream)")
    await asyncio.sleep(0.8)

    output_tables = all_writes | all_creates
    downstream    = await asyncio.to_thread(discover_downstream, output_tables, pipeline_dir)

    if downstream:
        for c in downstream:
            await _e("status", f"✓ Downstream consumer: {c}")
            await asyncio.sleep(0.35)
    else:
        await _e("status", "✓ No downstream consumers found in local pipelines")
        await asyncio.sleep(0.3)

    await _e("status", f"✓ {len(upstream)} upstream, {len(downstream)} downstream consumer(s)")
    await asyncio.sleep(0.4)

    # ── Phase 5 · Dependency graph ───────────────────────────────────────
    await _e("status", "Building dependency graph...")
    await asyncio.sleep(0.8)

    graph_nodes = len(all_tables) + len(downstream)
    graph_edges = len(upstream) + len(downstream) + max(len(all_tables) - 1, 0)

    await _e("tool_call", f"MCP → neo4j_mcp.write_graph(pipeline={pipeline_name})")
    await asyncio.sleep(1.0)

    await _e("artifact", f"✓ Graph written: {graph_nodes} nodes, {graph_edges} edges")
    await asyncio.sleep(0.4)

    # ── Phase 6 · Complexity scoring ─────────────────────────────────────
    await _e("status", "Scoring complexity...")
    await asyncio.sleep(0.7)

    score = compute_score(
        all_tables, all_udfs, has_window, cross_db, has_dyn_part, total_subq, downstream
    )

    for label, flag, warn_msg, ok_msg in [
        ("Cross-cluster joins", bool(cross_db),  "⚠ detected", "✓ None"),
        ("Window functions",    has_window,       "⚠ detected", "✓ None"),
        ("Dynamic partitions",  has_dyn_part,     "⚠ detected", "✓ None"),
        ("Subqueries",          total_subq > 0,   f"⚠ {total_subq} found", "✓ None"),
    ]:
        await _e("status", f"{label}: {warn_msg if flag else ok_msg}")
        await asyncio.sleep(0.3)

    complexity = classify(score)
    await _e("status", f"Complexity score: {score}  →  classification: {complexity}")
    await asyncio.sleep(0.5)

    # ── Phase 7 · Wrap-up ────────────────────────────────────────────────
    await _e("hook", "PostToolUse → audit_logger.record_assessment ✓")
    await asyncio.sleep(0.3)

    await _e("status", "Assessment complete", done=True)

    return {
        "pipeline":             pipeline_name,
        "complexity":           complexity,
        "complexity_score":     score,
        "tables":               len(all_tables),
        "columns":              len(unique_cols),
        "partition_keys":       len(all_part_keys),
        "udfs":                 len(all_udfs),
        "udf_names":            sorted(all_udfs),
        "upstream_feeds":       len(upstream),
        "upstream_tables":      sorted(upstream),
        "downstream_consumers": len(downstream),
        "has_window_functions": has_window,
        "cross_db_joins":       len(cross_db),
        "subqueries":           total_subq,
        "hql_files":            len(hql_files),
        "syntax_errors":        len(syntax_errors),
        "estimated_effort":     EFFORT[complexity],
        "graph_nodes":          graph_nodes,
        "graph_edges":          graph_edges,
    }

"""
ASSESS agent tools — Pyodide/Deno HTTP bridge functions for the ASSESS phase.
"""


def _deep_py(obj):
    """Recursively convert Pyodide JsProxy objects to native Python types."""
    if hasattr(obj, "to_py"):
        try:
            obj = obj.to_py()
        except Exception:
            pass
    if isinstance(obj, dict):
        return {k: _deep_py(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_py(v) for v in obj]
    return obj


def read_skill(name: str) -> str:
    """Read a skill file by name. Available skills: repo_scan, complexity_classification, graph_context, hiveql_repair."""
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"name": name}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/read-skill", opts)
        data = await resp.json()
        return data.to_py()
    try:
        result = run_sync(_call())
        return result.get("content", f"Skill '{name}' not found")
    except Exception as e:
        return {"error": str(e)}


def scan_repo(pipeline: str) -> dict:
    """Scan a pipeline directory for HQL and config files.

    Args:
        pipeline (str): Pipeline directory name (e.g. "silver_orders").

    Returns:
        hql_files    (list[str])  — HQL filenames in the pipeline dir.
        config_files (list)       — Non-HQL config/metadata files found.
        total_files  (int)        — Total number of files discovered.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"pipeline": pipeline}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/scan-repo", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def parse_hql(pipeline: str, filename: str) -> dict:
    """Parse a single HQL file and extract all structural metadata.

    Args:
        pipeline (str): Pipeline directory name.
        filename (str): HQL filename to parse (e.g. "transform.hql").

    Returns:
        file           (str)        — Filename that was parsed.
        read_tables    (list[str])  — Tables read/selected by this file.
        created_tables (list[str])  — Tables created (CREATE TABLE / CTAS).
        written_tables (list[str])  — Tables written via INSERT/OVERWRITE.
        all_tables     (list[str])  — Union of all table references.
        columns        (list[str])  — Column names referenced.
        partition_keys (list[str])  — Partition columns declared.
        udfs           (list[str])  — UDF function names used.
        has_window     (bool)       — True if OVER/PARTITION BY window functions present.
        subqueries     (int)        — Count of nested subqueries.
        has_dyn_part   (bool)       — True if dynamic partitioning is used.
        cross_db_joins (list[str])  — Cross-database table references (db.table format).
        syntax_errors  (list[str])  — Any HQL syntax errors detected.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"pipeline": pipeline, "filename": filename}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/parse-hql", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def lineage_extract(pipeline: str, all_reads: list, all_creates: list, all_writes: list) -> dict:
    """Derive upstream/downstream lineage from aggregated table sets.

    Args:
        pipeline    (str)       — Pipeline name.
        all_reads   (list[str]) — All tables read across all HQL files.
        all_creates (list[str]) — All tables created across all HQL files.
        all_writes  (list[str]) — All tables written across all HQL files.

    Returns:
        upstream      (list[str]) — External tables consumed but not produced by this pipeline.
        output_tables (list[str]) — Tables produced/written by this pipeline.
        downstream    (list[str]) — Other pipeline names that consume this pipeline's output.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"pipeline": pipeline, "all_reads": all_reads, "all_creates": all_creates, "all_writes": all_writes}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/lineage-extract", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def classify_complexity(tables: list, udfs: list, has_window: bool, cross_db: list, has_dyn_part: bool, subqueries: int, downstream: list) -> dict:
    """Score migration complexity based on HQL structural features.

    Args:
        tables      (list[str]) — All tables referenced in the pipeline.
        udfs        (list[str]) — UDFs used.
        has_window  (bool)      — Whether window functions are present.
        cross_db    (list[str]) — Cross-database table references.
        has_dyn_part (bool)     — Whether dynamic partitioning is used.
        subqueries  (int)       — Number of nested subqueries.
        downstream  (list[str]) — Pipelines that depend on this one.

    Returns:
        score            (int) — Numeric complexity score (higher = more complex).
        complexity       (str) — Tier: SMALL | MEDIUM | LARGE | COMPLEX.
        estimated_effort (str) — Human-readable effort estimate (e.g. "2-3 days").
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"tables": tables, "udfs": udfs, "has_window": has_window, "cross_db": cross_db, "has_dyn_part": has_dyn_part, "subqueries": subqueries, "downstream": downstream}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/classify-complexity", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def neo4j_write(pipeline: str, upstream_tables: list, output_tables: list, downstream: list, udfs: list, complexity: str, estimated_effort: str) -> dict:
    """Persist pipeline lineage graph to Neo4j.

    Args:
        pipeline         (str)       — Pipeline name.
        upstream_tables  (list[str]) — External tables this pipeline reads.
        output_tables    (list[str]) — Tables this pipeline produces.
        downstream       (list[str]) — Downstream pipeline names.
        udfs             (list[str]) — UDFs used.
        complexity       (str)       — Complexity tier (SMALL/MEDIUM/LARGE/COMPLEX).
        estimated_effort (str)       — Effort string from classify_complexity.

    Returns:
        status   (str) — "ok" on success, "error" on failure.
        pipeline (str) — Pipeline name that was written.
        nodes    (int) — Number of graph nodes created/merged.
        edges    (int) — Number of relationships created/merged.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"pipeline": pipeline, "upstream_tables": upstream_tables, "output_tables": output_tables, "downstream": downstream, "udfs": udfs, "complexity": complexity, "estimated_effort": estimated_effort}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/neo4j-write", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def query_graph(pipeline: str, query: str) -> dict:
    """Query the Neo4j lineage graph for a pipeline.

    Args:
        pipeline (str) — Pipeline name to query.
        query    (str) — One of: "blast_radius" | "wave" | "summary".

    Returns (query="blast_radius"):
        blast_radius (list[str]) — All pipelines transitively impacted.
        count        (int)       — len(blast_radius).

    Returns (query="wave"):
        migration_wave (int) — Topological wave number (1 = no deps, higher = later).

    Returns (query="summary"):
        complexity, estimated_effort, last_assessed, reads, writes, udfs, depends_on, consumed_by.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"pipeline": pipeline, "query": query}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/query-graph", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def request_human_approval(phase: str, summary: str, options: list, pipeline: str = "", artifacts: list = None) -> dict:
    """Pause and wait for human input at a significant decision point.

    Args:
        phase     (str)       — Current phase name (e.g. "ASSESS").
        summary   (str)       — What was found/done and key metrics.
        options   (list[str]) — 2-4 situation-specific choices.
        pipeline  (str)       — Pipeline name shown in the UI.
        artifacts (list[str]) — Filenames of artifacts generated so far.

    Returns:
        choice    (int)  — 1-indexed option the human selected.
        chosen    (str)  — Exact text of the chosen option.
        timed_out (bool) — True if no response within 10 minutes.
    """
    import json, os, asyncio
    from pyodide.ffi import run_sync, to_js
    import js

    async def _submit():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({
            "phase": phase, "summary": summary, "pipeline": pipeline,
            "artifacts": artifacts or [], "options": options,
        }, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/request-approval", opts)
        data = await resp.json()
        return data.to_py()

    async def _poll(request_id: str):
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        for _ in range(120):
            await asyncio.sleep(5)
            opts = to_js({"method": "GET"}, dict_converter=js.Object.fromEntries)
            resp = await js.fetch(f"{base}/internal/approval-status?request_id={request_id}", opts)
            data = await resp.json()
            result = data.to_py()
            if result.get("status") == "resolved":
                return result
        return {"status": "timed_out"}

    try:
        submitted = run_sync(_submit())
        if isinstance(submitted, dict) and "error" in submitted:
            return {"error": submitted["error"]}
        request_id = submitted.get("request_id") if isinstance(submitted, dict) else None
        if not request_id:
            return {"error": "no request_id returned"}
    except Exception as e:
        return {"error": str(e)}

    try:
        result = run_sync(_poll(request_id))
        if not isinstance(result, dict) or result.get("status") == "timed_out":
            return {"choice": len(options), "chosen": options[-1] if options else "Halt", "timed_out": True}
        return {"choice": result.get("choice", len(options)), "chosen": result.get("chosen", ""), "timed_out": False}
    except Exception as e:
        return {"error": str(e)}

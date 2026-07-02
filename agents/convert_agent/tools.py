"""
CONVERT agent tools — Pyodide/Deno HTTP bridge functions for the CONVERT phase.
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
    """Read a skill file by name. Available skills: hiveql_to_pyspark, dag_generation, hiveql_repair, pyspark_repair."""
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


def transform_hql(pipeline: str, filename: str, metadata: dict) -> dict:
    """Convert a HQL file to PySpark using Claude Sonnet. Writes the .py file to disk.

    Args:
        pipeline (str)  — Pipeline directory name.
        filename (str)  — HQL filename to convert (e.g. "load_silver.hql").
        metadata (dict) — Assessment metadata: tables, udfs, complexity, estimated_effort, etc.

    Returns:
        filename              (str)       — Original HQL filename.
        python_filename       (str)       — Output .py filename written to disk.
        source_hql            (str)       — Original HQL source text.
        spark_python          (str)       — Generated PySpark source text.
        transformations_applied (int)     — Number of HQL→Spark transformations performed.
        transformation_log    (list[str]) — Human-readable log of each transformation step.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"pipeline": pipeline, "filename": filename, "metadata": metadata}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/transform-hql", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def validate_pyspark(filename: str, spark_python: str, source_hql: str = "") -> dict:
    """Run static validation checks on generated PySpark code.

    Args:
        filename     (str) — PySpark filename (for labeling results).
        spark_python (str) — PySpark source code to validate.
        source_hql   (str) — Original HQL source (optional, for cross-reference checks).

    Returns:
        filename (str)       — Filename that was validated.
        valid    (bool)      — True if no blocking errors found.
        checks   (dict)      — Per-check results (syntax, imports, write_ops, etc.).
        errors   (list[str]) — Blocking validation errors.
        warnings (list[str]) — Non-blocking warnings.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"filename": filename, "spark_python": spark_python, "source_hql": source_hql}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/validate-pyspark", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def generate_dag(pipeline: str, files: list, complexity: str) -> dict:
    """Generate an MWAA Airflow DAG Python file for the pipeline.

    Args:
        pipeline   (str)       — Pipeline name (used as DAG ID).
        files      (list[str]) — HQL filenames in order (determines task order in DAG).
        complexity (str)       — Complexity tier: SMALL | MEDIUM | LARGE | COMPLEX.

    Returns:
        dag_content  (str) — Full DAG Python source code.
        dag_filename (str) — Filename the DAG was written to (e.g. "silver_orders_dag.py").
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"pipeline": pipeline, "files": files, "complexity": complexity}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/generate-dag", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def request_human_approval(phase: str, summary: str, options: list, pipeline: str = "", artifacts: list = None) -> dict:
    """Pause and wait for human input at a significant decision point.

    Args:
        phase     (str)       — Current phase name (e.g. "CONVERT").
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

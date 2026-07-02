"""
RECONCILE agent tools — Pyodide/Deno HTTP bridge functions for the RECONCILE phase.
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
    """Read a skill file by name. Available skills: semantic_comparison, runtime_validation, risk_assessment."""
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


def analyze_file(filename: str, hql_src: str, pyspark_src: str) -> dict:
    """8-dimension semantic comparison between HQL source and PySpark output.

    Args:
        filename    (str) — Filename label for this comparison.
        hql_src     (str) — Original HQL source text.
        pyspark_src (str) — Generated PySpark source text.

    Returns (normal case):
        table_parity, column_parity, aggregation_parity, join_parity,
        group_by_parity, filter_parity, partition_parity, runtime_var_parity
        (each: {status: PASS/WARN/FAIL, score: float}),
        overall_similarity (float), issues (list[str]).

    Returns (if either source is empty):
        skipped (bool) — True.
        reason  (str)  — Why the comparison was skipped.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"filename": filename, "hql_src": hql_src, "pyspark_src": pyspark_src}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/analyze-file", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def workflow_parity(conversion: dict) -> dict:
    """Verify the generated DAG structure matches the set of converted PySpark files.

    Args:
        conversion (dict) — Result of the CONVERT phase, containing converted file metadata.

    Returns:
        status (str)   — PASSED | WARNING | FAILED.
        detail (str)   — Human-readable explanation.
        score  (float) — Numeric parity score 0.0–1.0.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"conversion": conversion}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/workflow-parity", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def runtime_validation(pipeline: str, complexity: str, similarity: float) -> dict:
    """Run simulated runtime validation checks (row count, checksum, SLA, consumer replay).

    Args:
        pipeline   (str)   — Pipeline name.
        complexity (str)   — Complexity tier used to calibrate thresholds.
        similarity (float) — Overall similarity score from analyze_file (0.0–1.0).

    Returns:
        row_count       (dict) — {status: PASSED/WARNING/FAILED, source_rows, target_rows, variance_pct}.
        checksum        (dict) — {status, source_checksum, target_checksum, match}.
        sla_compliance  (dict) — {status, expected_minutes, actual_minutes}.
        consumer_replay (dict) — {status, replayed, consumers}.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"pipeline": pipeline, "complexity": complexity, "similarity": similarity}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/runtime-validation", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def compile_report(pipeline: str, files_analysis: list, workflow_check: dict, runtime_checks: dict, all_issues: list) -> dict:
    """Compile the full reconciliation report from all validation results.

    Args:
        pipeline       (str)        — Pipeline name.
        files_analysis (list[dict]) — One analyze_file result dict per converted file.
        workflow_check (dict)       — Result from workflow_parity.
        runtime_checks (dict)       — Result from runtime_validation.
        all_issues     (list[str])  — Aggregated issue strings from all prior checks.

    Returns:
        pipeline, validation_status, confidence_score, semantic_similarity,
        files_reconciled, migration_risk, migration_risk_score, recommendation,
        reasoning, issues, blast_radius_count, threshold_applied, data_provenance, summary.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"pipeline": pipeline, "files_analysis": files_analysis, "workflow_check": workflow_check, "runtime_checks": runtime_checks, "all_issues": all_issues}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/compile-report", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def request_human_approval(phase: str, summary: str, options: list, pipeline: str = "", artifacts: list = None) -> dict:
    """Pause and wait for human input at a significant decision point.

    Args:
        phase     (str)       — Current phase name (e.g. "RECONCILE").
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

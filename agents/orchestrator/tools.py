"""
ORCHESTRATOR agent tools — Pyodide/Deno HTTP bridge.
Calls each phase agent via /internal/run-*-phase endpoints.
"""


def _deep_py(obj):
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
    """Read a skill file by name. Available skills: orchestrator."""
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


def run_assess_phase(pipeline: str) -> dict:
    """Run the full ASSESS phase agent for the given pipeline.

    Args:
        pipeline (str): Pipeline directory name (e.g. "silver_orders").

    Returns:
        pipeline   (str)  — Pipeline name.
        outcome    (str)  — SUCCESS | PARTIAL | HALTED | FAILED.
        summary    (str)  — One-paragraph description of what was found.
        assessment (dict) — Full assessment result: hql_files, complexity,
                            complexity_score, estimated_effort, udfs,
                            upstream_tables, output_tables, downstream_pipelines,
                            blast_radius_count, migration_wave, neo4j_nodes,
                            neo4j_edges.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"pipeline": pipeline}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/run-assess-phase", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def run_convert_phase(pipeline: str, assessment: dict) -> dict:
    """Run the full CONVERT phase agent for the given pipeline.

    Args:
        pipeline   (str)  — Pipeline directory name.
        assessment (dict) — Full assessment dict returned by run_assess_phase.

    Returns:
        pipeline   (str)  — Pipeline name.
        outcome    (str)  — SUCCESS | PARTIAL | HALTED | FAILED.
        summary    (str)  — Conversion summary.
        conversion (dict) — files (list of converted file dicts), dag_filename,
                            dag_content, transformations_applied,
                            source_language, target_language.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"pipeline": pipeline, "assessment": assessment}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/run-convert-phase", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def run_reconcile_phase(pipeline: str, assessment: dict, conversion: dict) -> dict:
    """Run the full RECONCILE phase agent for the given pipeline.

    Args:
        pipeline   (str)  — Pipeline directory name.
        assessment (dict) — Result from run_assess_phase.
        conversion (dict) — Result from run_convert_phase.

    Returns:
        pipeline       (str)  — Pipeline name.
        outcome        (str)  — SUCCESS | PARTIAL | HALTED | FAILED.
        summary        (str)  — Reconciliation summary.
        reconciliation (dict) — confidence_score, migration_risk,
                                migration_risk_score, validation_status,
                                recommendation, issues, files_reconciled.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"pipeline": pipeline, "assessment": assessment, "conversion": conversion}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/run-reconcile-phase", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def run_deploy_phase(pipeline: str, assessment: dict, conversion: dict, reconciliation: dict) -> dict:
    """Run the full DEPLOY phase agent for the given pipeline.

    Args:
        pipeline       (str)  — Pipeline directory name.
        assessment     (dict) — Result from run_assess_phase.
        conversion     (dict) — Result from run_convert_phase.
        reconciliation (dict) — Result from run_reconcile_phase.

    Returns:
        pipeline   (str)  — Pipeline name.
        outcome    (str)  — SUCCESS | PARTIAL | HALTED | FAILED.
        summary    (str)  — Deployment summary.
        deployment (dict) — readiness_score, governance_state, manifests,
                            smoke_tests, cicd_yaml, files_written.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({
            "pipeline": pipeline,
            "assessment": assessment,
            "conversion": conversion,
            "reconciliation": reconciliation,
        }, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/run-deploy-phase", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def request_human_approval(phase: str, summary: str, options: list, pipeline: str = "", artifacts: list = None) -> dict:
    """Pause and wait for human input at a phase transition.

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

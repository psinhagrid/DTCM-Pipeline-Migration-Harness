"""
DEPLOY agent tools — Pyodide/Deno HTTP bridge functions for the DEPLOY phase.
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
    """Read a skill file by name. Available skills: artifact_validation, deployment_governance."""
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


def validate_artifacts(conversion: dict, reconcile: dict) -> dict:
    """Validate all generated artifacts before deployment.

    Args:
        conversion (dict) — Result of the CONVERT phase (file metadata, dag_filename, etc.).
        reconcile  (dict) — Result of the RECONCILE phase (compile_report output).

    Returns:
        file_checks          (dict) — Per-file validation results keyed by filename.
        dag_check            (dict) — DAG file validation result {status, detail}.
        reconciliation_check (dict) — Reconciliation threshold check {status, confidence_score}.
        all_artifacts_valid  (bool) — True only if all individual checks passed.
        deployment_ready     (bool) — True if the pipeline is safe to deploy.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"conversion": conversion, "reconcile": reconcile}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/validate-artifacts", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def run_smoke_tests(pipeline: str, conversion: dict, reconcile: dict) -> dict:
    """Run a smoke test suite against the converted pipeline artifacts.

    Args:
        pipeline   (str)  — Pipeline name.
        conversion (dict) — CONVERT phase result (filenames, dag, etc.).
        reconcile  (dict) — RECONCILE phase result (confidence, issues, etc.).

    Returns:
        tests   (list[dict]) — Individual test results {name, status, detail}.
        passed  (int), failed (int), warning (int), total (int).
        score   (int)        — Percentage score 0–100.
        overall (str)        — PASSED | FAILED.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"pipeline": pipeline, "conversion": conversion, "reconcile": reconcile}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/run-smoke-tests", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def compute_governance(artifact_checks: dict, smoke_results: dict, reconcile: dict) -> dict:
    """Compute deployment readiness score and governance approval decision.

    Args:
        artifact_checks (dict) — Result from validate_artifacts.
        smoke_results   (dict) — Result from run_smoke_tests.
        reconcile       (dict) — RECONCILE phase result (confidence, risk, etc.).

    Returns:
        readiness_score (int)  — Overall readiness score 0–100.
        governance      (dict) — {state: APPROVED|APPROVED_NON_PROD|CONDITIONAL|BLOCKED,
                                   label: str, conditions: list[str]}.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"artifact_checks": artifact_checks, "smoke_results": smoke_results, "reconcile": reconcile}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/compute-governance", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def generate_cicd(pipeline: str, files: list, assessment: dict, reconcile: dict) -> dict:
    """Generate a CI/CD pipeline YAML (GitHub Actions / MWAA deploy workflow).

    Args:
        pipeline   (str)       — Pipeline name.
        files      (list[str]) — PySpark filenames to include in the pipeline.
        assessment (dict)      — ASSESS phase result (complexity, effort, lineage).
        reconcile  (dict)      — RECONCILE phase result (confidence, risk, recommendation).

    Returns:
        cicd_yaml       (str)  — Full CI/CD YAML file content.
        pipeline_config (dict) — Structured config used to generate the YAML.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"pipeline": pipeline, "files": files, "assessment": assessment, "reconcile": reconcile}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/generate-cicd", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def write_manifests(pipeline: str, assessment: dict, conversion: dict, reconcile: dict, artifact_checks: dict, smoke_results: dict, governance: dict, cicd_yaml: str) -> dict:
    """Write all migration output manifests (JSON files) to the output directory.

    Args:
        pipeline        (str)  — Pipeline name (determines output subdirectory).
        assessment      (dict) — ASSESS phase result.
        conversion      (dict) — CONVERT phase result.
        reconcile       (dict) — RECONCILE phase result.
        artifact_checks (dict) — validate_artifacts result.
        smoke_results   (dict) — run_smoke_tests result.
        governance      (dict) — compute_governance result.
        cicd_yaml       (str)  — CI/CD YAML string from generate_cicd.

    Returns:
        output_dir    (str)       — Absolute path to the output directory.
        files_written (list[str]) — List of filenames written.
        file_count    (int)       — Total number of files written.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8000")
        body = json.dumps({"pipeline": pipeline, "assessment": assessment, "conversion": conversion, "reconcile": reconcile, "artifact_checks": artifact_checks, "smoke_results": smoke_results, "governance": governance, "cicd_yaml": cicd_yaml}, default=str)
        opts = to_js({"method": "POST", "body": body, "headers": {"Content-Type": "application/json"}},
                     dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/write-manifests", opts)
        data = await resp.json()
        return data.to_py()
    try:
        return run_sync(_call())
    except Exception as e:
        return {"error": str(e)}


def request_human_approval(phase: str, summary: str, options: list, pipeline: str = "", artifacts: list = None) -> dict:
    """Pause and wait for human input at a significant decision point.

    Args:
        phase     (str)       — Current phase name (e.g. "DEPLOY").
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

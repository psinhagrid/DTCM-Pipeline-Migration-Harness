def list_skills() -> list:
    """List all available skill names. Call this first to discover what skills exist before calling read_skill."""
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
        opts = to_js({"method": "GET"}, dict_converter=js.Object.fromEntries)
        resp = await js.fetch(f"{base}/internal/list-skills", opts)
        data = await resp.json()
        return data.to_py()
    try:
        result = run_sync(_call())
        return result.get("skills", [])
    except Exception as e:
        return {"error": str(e)}


def read_skill(name: str) -> str:
    """Read a skill file by name. Call list_skills() first to see what's available. Always read migration_flow first."""
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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
    """Query the Neo4j lineage graph for a pipeline. Result shape depends on query type.

    Args:
        pipeline (str) — Pipeline name to query.
        query    (str) — One of: "blast_radius" | "wave" | "summary".

    Returns (query="blast_radius"):
        blast_radius (list[str]) — All pipelines transitively impacted. Use len() for count.
        count        (int)       — len(blast_radius).

    Returns (query="wave"):
        migration_wave (int) — Topological wave number (1 = no dependencies, higher = later).

    Returns (query="summary"):
        complexity       (str)       — Complexity tier stored in Neo4j.
        estimated_effort (str)       — Effort string stored in Neo4j.
        last_assessed    (str)       — ISO timestamp of last assessment.
        reads            (list[str]) — Upstream tables this pipeline reads.
        writes           (list[str]) — Output tables this pipeline writes.
        udfs             (list[str]) — UDFs used.
        depends_on       (list[str]) — Immediate upstream pipeline dependencies.
        consumed_by      (list[str]) — Immediate downstream pipeline dependents.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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


def validate_pyspark(filename: str, spark_python: str, source_hql: str = "") -> dict:
    """Run static validation checks on generated PySpark code.

    Args:
        filename     (str) — PySpark filename (for labeling results).
        spark_python (str) — PySpark source code to validate.
        source_hql   (str) — Original HQL source (optional, for cross-reference checks).

    Returns:
        filename (str)       — Filename that was validated.
        valid    (bool)      — True if no blocking errors found.
        checks   (dict)      — Per-check results (syntax, imports, write_ops, iceberg_format, etc.).
        errors   (list[str]) — Blocking validation errors.
        warnings (list[str]) — Non-blocking warnings.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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


def analyze_file(filename: str, hql_src: str, pyspark_src: str) -> dict:
    """8-dimension semantic comparison between HQL source and PySpark output.

    Args:
        filename    (str) — Filename label for this comparison.
        hql_src     (str) — Original HQL source text.
        pyspark_src (str) — Generated PySpark source text.

    Returns (normal case):
        table_parity       (dict) — {status: PASS/WARN/FAIL, score: float} — table references match.
        column_parity      (dict) — {status, score} — column references match.
        aggregation_parity (dict) — {status, score} — GROUP BY / aggregations match.
        join_parity        (dict) — {status, score} — JOIN logic match.
        group_by_parity    (dict) — {status, score} — GROUP BY columns match.
        filter_parity      (dict) — {status, score} — WHERE / HAVING filters match.
        partition_parity   (dict) — {status, score} — partition columns match.
        runtime_var_parity (dict) — {status, score} — runtime variables match.
        overall_similarity (float) — Weighted average score 0.0–1.0.
        issues             (list[str]) — Specific mismatches found.

    Returns (if either source is empty):
        skipped (bool) — True.
        reason  (str)  — Why the comparison was skipped.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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
        detail (str)   — Human-readable explanation of what was checked and any mismatches.
        score  (float) — Numeric parity score 0.0–1.0.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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
        pipeline           (str)   — Pipeline name.
        validation_status  (str)   — PASSED | WARNING | FAILED.
        confidence_score   (float) — Overall confidence 0.0–1.0.
        semantic_similarity (float) — Average semantic similarity across files.
        files_reconciled   (int)   — Number of files included in reconciliation.
        migration_risk     (str)   — LOW | MEDIUM | HIGH | CRITICAL.
        migration_risk_score (int) — Numeric risk score.
        recommendation     (str)   — Proceed | Proceed with caution | Halt.
        reasoning          (str)   — Explanation of the recommendation.
        issues             (list)  — All issues found across all checks.
        blast_radius_count (int)   — Number of downstream pipelines impacted.
        threshold_applied  (float) — Similarity threshold used for PASS/FAIL.
        data_provenance    (str)   — Data lineage provenance summary.
        summary            (str)   — One-sentence human-readable summary.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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


def validate_artifacts(conversion: dict, reconcile: dict) -> dict:
    """Validate all generated artifacts (PySpark files, DAG, reconciliation) before deployment.

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
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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


def run_smoke_tests(pipeline: str, conversion: dict, reconcile: dict) -> dict:
    """Run a smoke test suite against the converted pipeline artifacts.

    Args:
        pipeline   (str)  — Pipeline name.
        conversion (dict) — CONVERT phase result (filenames, dag, etc.).
        reconcile  (dict) — RECONCILE phase result (confidence, issues, etc.).

    Returns:
        tests   (list[dict]) — Individual test results, each with {name, status, detail}.
        passed  (int)        — Number of tests that passed.
        failed  (int)        — Number of tests that failed.
        warning (int)        — Number of tests with warnings.
        total   (int)        — Total number of tests run.
        score   (int)        — Percentage score 0–100.
        overall (str)        — PASSED | FAILED.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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
        governance      (dict) — Approval decision:
                                   state:      APPROVED | APPROVED_NON_PROD | CONDITIONAL | BLOCKED
                                   label:      Human-readable status label.
                                   conditions: list[str] of conditions that must be met before deploy.
    """
    import json, os
    from pyodide.ffi import run_sync, to_js
    import js
    async def _call():
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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
        base = os.environ.get("DTCM_BACKEND_URL", "http://localhost:8001")
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

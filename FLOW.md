# Execution Flow

Step-by-step sequence of what happens when a migration runs.

---

## 1. User triggers a run

```
Browser → POST http://localhost:8001/run?pipeline=silver_customers
```

`main.py` receives the request and fires:
```python
asyncio.create_task(run_pipeline("silver_customers"))
```
Returns `{"status": "started"}` immediately — run happens in background.

---

## 2. Orchestrator hands off to RLM

`orchestrator.py → run_migration("silver_customers")`

Wraps the fast-rlm call and stores results in memory dicts when done:
```python
results[pipeline]         = full result
conversions[pipeline]     = result["conversion"]
reconciliations[pipeline] = result["reconciliation"]
deployments[pipeline]     = result["deployment"]
```

---

## 3. fast-rlm engine starts (Deno)

`rlm/migrate.py` calls `run(query, tools, config, output_schema, env_variables)`

The Deno engine receives:
- `query` → `{pipeline: "silver_customers", instruction: "Run ASSESS → CONVERT → RECONCILE → DEPLOY..."}`
- `tools` → 20 Python functions (exposed as callable in Deno via Pyodide bridge)
- `config` → model, max 25 tool calls, $5 cost cap, 180k token limit
- `env_variables` → DTCM_BACKEND_URL, RLM_MODEL_BASE_URL, RLM_MODEL_API_KEY

---

## 4. Agent bootstrap (Step 0)

Deno prints the full tool list + context to the agent as its first prompt.
Agent sees all 20 tools with their signatures and docstrings.

First thing the agent does, as instructed:

```
list_skills()
→ GET http://localhost:8001/internal/list-skills
→ returns: ["orchestrator", "repo_scan", "complexity_classification", ...]

read_skill("orchestrator")
→ POST http://localhost:8001/internal/read-skill  {name: "orchestrator"}
→ returns: content of skills/orchestrator.md
```

Agent now knows: ASSESS → CONVERT → RECONCILE → DEPLOY, and which skills to read per phase.

---

## 5. ASSESS phase

Agent reads phase skills first:
```
read_skill("repo_scan")             → skills/repo_scan.md
read_skill("complexity_classification") → skills/complexity_classification.md
read_skill("graph_context")         → skills/graph_context.md
```

Then calls tools (each tool = HTTP POST to backend → Python logic):

```
scan_repo("silver_customers")
→ POST /internal/scan-repo
→ tools/scan_repo_tool.py
→ returns: {hql_files: ["mask_customer_pii.hql", "curate_customer_segments.hql"], total_files: 2}

parse_hql("silver_customers", "mask_customer_pii.hql")
→ POST /internal/parse-hql
→ tools/parse_hql_tool.py → tools/utils/hql_utils.py (sqlfluff + regex)
→ returns: {read_tables, written_tables, udfs, has_window, subqueries, ...}

parse_hql("silver_customers", "curate_customer_segments.hql")
→ same as above for second file

lineage_extract("silver_customers", all_reads, all_creates, all_writes)
→ POST /internal/lineage-extract
→ tools/lineage_extract_tool.py
→ returns: {upstream: [...], output_tables: [...], downstream: [...]}

classify_complexity(tables, udfs, has_window, cross_db, has_dyn_part, subqueries, downstream)
→ POST /internal/classify-complexity
→ tools/classify_complexity_tool.py → tools/utils/hql_utils.py
→ returns: {score: 42, complexity: "MEDIUM", estimated_effort: "2-3 days"}

neo4j_write("silver_customers", upstream_tables, output_tables, downstream, udfs, complexity, effort)
→ POST /internal/neo4j-write
→ tools/neo4j_write_graph_tool.py → Neo4j bolt://localhost:7687
→ writes Pipeline + Table + UDF nodes and READS/WRITES/DEPENDS_ON/USES_UDF edges
→ returns: {status: "ok", nodes: 8, edges: 12}

query_graph("silver_customers", "blast_radius")
→ POST /internal/query-graph
→ tools/query_graph_tool.py → graph/client.py → Neo4j
→ returns: {blast_radius: ["ecomm_sales_mart"], count: 1}

query_graph("silver_customers", "wave")
→ returns: {migration_wave: 2}
```

Agent reasons about ASSESS results, then proceeds.

---

## 6. CONVERT phase

Agent reads phase skills:
```
read_skill("hiveql_to_pyspark")   → skills/hiveql_to_pyspark.md
read_skill("dag_generation")      → skills/dag_generation.md
```

Then calls tools per HQL file:

```
transform_hql("silver_customers", "mask_customer_pii.hql", metadata)
→ POST /internal/transform-hql
→ tools/transform_hql_tool.py → tools/utils/conversion_engine.py
→ conversion_engine calls Anthropic API directly (claude-sonnet-4-6)
   with ANTHROPIC_API_KEY (NOT via LiteLLM)
→ writes output/silver_customers/mask_customer_pii.py to disk
→ returns: {python_filename, spark_python, transformations_applied, ...}

transform_hql("silver_customers", "curate_customer_segments.hql", metadata)
→ same for second file

validate_pyspark("mask_customer_pii.py", spark_python, source_hql)
→ POST /internal/validate-pyspark
→ tools/validate_pyspark_tool.py → tools/utils/pyspark_validator.py
→ ast.parse() syntax check, import scan, write-op check
→ returns: {valid: true, errors: [], warnings: [...]}

generate_dag("silver_customers", ["mask_customer_pii.hql", "curate_customer_segments.hql"], "MEDIUM")
→ POST /internal/generate-dag
→ tools/generate_dag_tool.py → tools/utils/conversion_engine.py
→ Claude Sonnet generates Airflow DAG
→ writes output/silver_customers/silver_customers_dag.py to disk
→ returns: {dag_filename: "silver_customers_dag.py", dag_content}
```

---

## 7. RECONCILE phase

Agent reads phase skills:
```
read_skill("semantic_comparison")  → skills/semantic_comparison.md
read_skill("runtime_validation")   → skills/runtime_validation.md
read_skill("risk_assessment")      → skills/risk_assessment.md
```

Then calls tools:

```
analyze_file("mask_customer_pii.hql", hql_src, pyspark_src)
→ POST /internal/analyze-file
→ tools/analyze_file_tool.py → tools/utils/static_analyzer.py
→ 8-dimension regex comparison (table, column, join, filter, partition parity...)
→ returns: {overall_similarity: 0.91, issues: [...]}

analyze_file("curate_customer_segments.hql", ...)
→ same for second file

workflow_parity(conversion_result)
→ POST /internal/workflow-parity
→ tools/workflow_parity_tool.py → tools/utils/static_analyzer.py
→ checks DAG task count matches number of converted PySpark files
→ returns: {status: "PASSED", score: 1.0}

runtime_validation("silver_customers", "MEDIUM", 0.91)
→ POST /internal/runtime-validation
→ tools/runtime_validation_tool.py → tools/utils/validators.py
→ simulated: row_count, checksum, SLA, consumer_replay checks
→ returns: {row_count: {status: "PASSED"}, checksum: {status: "PASSED"}, ...}

compile_report("silver_customers", files_analysis, workflow_check, runtime_checks, issues)
→ POST /internal/compile-report
→ tools/compile_report_tool.py → tools/utils/validators.py
→ aggregates all scores, applies blast_radius threshold adjustment
→ returns: {confidence_score: 0.88, migration_risk: "LOW", recommendation: "Proceed"}
```

---

## 8. DEPLOY phase

Agent reads phase skills:
```
read_skill("artifact_validation")    → skills/artifact_validation.md
read_skill("deployment_governance")  → skills/deployment_governance.md
```

Then calls tools:

```
validate_artifacts(conversion, reconcile)
→ POST /internal/validate-artifacts
→ tools/validate_artifacts_tool.py → tools/utils/artifact_validator.py
→ checks each .py file exists + parseable, DAG file valid, confidence above threshold
→ returns: {all_artifacts_valid: true, deployment_ready: true}

run_smoke_tests("silver_customers", conversion, reconcile)
→ POST /internal/run-smoke-tests
→ tools/run_smoke_tests_tool.py → tools/utils/smoke_tests.py
→ 7 tests: file existence, syntax, import check, write ops, DAG structure, schema, lineage
→ returns: {passed: 6, failed: 0, warning: 1, total: 7, score: 92, overall: "PASSED"}

compute_governance(artifact_checks, smoke_results, reconcile)
→ POST /internal/compute-governance
→ tools/compute_governance_tool.py → tools/utils/governance.py
→ weighted formula: confidence + smoke score + blast_radius penalty
→ returns: {readiness_score: 89, governance: {state: "APPROVED", conditions: []}}

generate_cicd("silver_customers", pyspark_files, assessment, reconcile)
→ POST /internal/generate-cicd
→ tools/generate_cicd_tool.py → tools/utils/cicd_generator.py
→ builds GitHub Actions YAML for S3 upload + MWAA DAG registration
→ returns: {cicd_yaml: "...", pipeline_config: {...}}

write_manifests("silver_customers", assessment, conversion, reconcile,
                artifact_checks, smoke_results, governance, cicd_yaml)
→ POST /internal/write-manifests
→ tools/write_manifests_tool.py → tools/utils/manifest_builder.py
→ writes JSON files to output/silver_customers/
→ returns: {output_dir: "...", files_written: [...], file_count: 7}
```

---

## 9. Agent returns final result

Agent calls `FINAL(...)` with the structured output schema:
```json
{
    "pipeline":   "silver_customers",
    "outcome":    "SUCCESS",
    "summary":    "Migrated 2 HQL files to PySpark. MEDIUM complexity. Confidence 0.88. Governance APPROVED.",
    "assessment":     { complexity, lineage, blast_radius, wave, ... },
    "conversion":     { files_converted, dag_filename, ... },
    "reconciliation": { confidence_score, migration_risk, recommendation, ... },
    "deployment":     { readiness_score, governance_state, manifests_written, ... }
}
```

---

## 10. Results stored + SSE stream closes

`orchestrator.py` stores result in memory dicts.
Frontend polling `/result/silver_customers`, `/conversion/silver_customers`, etc. now returns data.
SSE stream sends `complete` event — frontend updates all panels.

---

## Event stream (parallel to steps 5–9)

Throughout the run, `ToolCallLogger` middleware intercepts every `/internal/*` POST:
```
tool called  → pushes "tool_call"   event to event_queue
tool returns → pushes "tool_result" event with one-line summary
```

`_stream_reasoning()` watches the fast-rlm `.jsonl` log file and pushes `reasoning` events
when the agent generates new code steps.

Frontend's `/stream/silver_customers` SSE connection receives all of these in real time
→ Orchestration page renders the live agent trace.

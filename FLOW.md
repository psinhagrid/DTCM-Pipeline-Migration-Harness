# Execution Flow

Step-by-step sequence of what happens when a migration runs.

---

## 1. User triggers a run

```
Browser → POST http://localhost:8000/run?pipeline=silver_customers
```

`main.py` receives the request and fires:
```python
asyncio.create_task(run_pipeline("silver_customers"))
```
Returns `{"status": "started"}` immediately — run happens in background.

---

## 2. Orchestrator starts the RLM agent

`orchestrator.py → run_orchestrator("silver_customers")`

Calls `agents/orchestrator/migrate.py` which starts the fast-rlm Deno engine with the orchestrator agent config (max_depth=2, max_calls=16, $1.50 budget).

When done, stores results in memory dicts:
```python
results[pipeline]         = full result
conversions[pipeline]     = result["conversion"]
reconciliations[pipeline] = result["reconciliation"]
deployments[pipeline]     = result["deployment"]
```

---

## 3. Orchestrator agent bootstrap

`agents/orchestrator/tools.py` Pyodide functions are registered as the agent's tool set.

First thing the agent does:
```
read_skill("orchestrator")
→ POST http://localhost:8000/internal/read-skill  {name: "orchestrator"}
→ returns: agents/orchestrator/skills/orchestrator.md
```

Agent now knows: ASSESS → CONVERT → RECONCILE → DEPLOY, human approval gates, and which skills to read per phase.

---

## 4. ASSESS phase

Orchestrator calls:
```
run_assess_phase("silver_customers")
→ POST /internal/run-assess-phase
→ agents/assess_agent/migrate.py: run_assess("silver_customers")
```

This starts a **new fast-rlm agent** (assess_agent, max_calls=20, $2.00 budget) that:

1. Reads skills: `repo_scan`, `complexity_classification`, `graph_context`
2. Calls tools (each → HTTP POST → `agents/assess_agent/tools_impl/`):

```
scan_repo("silver_customers")
→ POST /internal/scan-repo
→ agents/assess_agent/tools_impl/scan_repo.py
→ returns: {hql_files: ["mask_customer_pii.hql", ...], total_files: 2}

parse_hql("silver_customers", "mask_customer_pii.hql")
→ POST /internal/parse-hql
→ agents/assess_agent/tools_impl/parse_hql.py → tools_impl/utils/hql_utils.py
→ returns: {read_tables, written_tables, udfs, has_window, ...}

lineage_extract("silver_customers", all_reads, all_creates, all_writes)
→ POST /internal/lineage-extract
→ agents/assess_agent/tools_impl/lineage_extract.py
→ returns: {upstream: [...], output_tables: [...], downstream: [...]}

classify_complexity(tables, udfs, has_window, ...)
→ POST /internal/classify-complexity
→ agents/assess_agent/tools_impl/classify_complexity.py → tools_impl/utils/hql_utils.py
→ returns: {score: 42, complexity: "MEDIUM", estimated_effort: "2-3 days"}

neo4j_write("silver_customers", upstream_tables, output_tables, downstream, udfs, ...)
→ POST /internal/neo4j-write
→ agents/assess_agent/tools_impl/neo4j_write.py → Neo4j bolt://localhost:7687
→ returns: {status: "ok", nodes: 8, edges: 12}

query_graph("silver_customers", "blast_radius")
→ POST /internal/query-graph
→ agents/assess_agent/tools_impl/query_graph.py → graph/client.py → Neo4j
→ returns: {blast_radius: ["ecomm_sales_mart"], count: 1}
```

Returns the assessment dict to the orchestrator.

---

## 5. Human approval gate

Orchestrator calls `request_human_approval` before proceeding to CONVERT:
```
→ POST /internal/request-human-approval
→ pauses until frontend POST /user-input submits the human's choice
→ returns: {chosen: "Proceed to CONVERT", timed_out: false}
```

---

## 6. CONVERT phase

Orchestrator calls:
```
run_convert_phase("silver_customers", assessment)
→ POST /internal/run-convert-phase
→ agents/convert_agent/migrate.py: run_convert("silver_customers", assessment)
```

The convert_agent reads skills `hiveql_to_pyspark`, `dag_generation`, then:

```
transform_hql("silver_customers", "mask_customer_pii.hql", metadata)
→ POST /internal/transform-hql
→ agents/convert_agent/tools_impl/transform_hql.py → tools_impl/utils/conversion_engine.py
→ conversion_engine calls Anthropic API directly (claude-sonnet-4-6, ANTHROPIC_API_KEY)
→ writes output/silver_customers/mask_customer_pii.py to disk
→ returns: {python_filename, spark_python, transformations_applied, ...}

validate_pyspark("mask_customer_pii.py", spark_python, source_hql)
→ POST /internal/validate-pyspark
→ agents/convert_agent/tools_impl/validate_pyspark.py → tools_impl/utils/pyspark_validator.py
→ ast.parse() syntax check, import scan, write-op check
→ returns: {valid: true, errors: [], warnings: [...]}

generate_dag("silver_customers", ["mask_customer_pii.hql", ...], "MEDIUM")
→ POST /internal/generate-dag
→ agents/convert_agent/tools_impl/generate_dag.py → tools_impl/utils/conversion_engine.py
→ Claude Sonnet generates Airflow DAG
→ writes output/silver_customers/silver_customers_dag.py to disk
→ returns: {dag_filename: "silver_customers_dag.py", dag_content}
```

---

## 7. RECONCILE phase

Orchestrator calls:
```
run_reconcile_phase("silver_customers", assessment, conversion)
→ POST /internal/run-reconcile-phase
→ agents/reconcile_agent/migrate.py: run_reconcile(...)
```

The reconcile_agent reads skills `semantic_comparison`, `runtime_validation`, `risk_assessment`, then:

```
analyze_file("mask_customer_pii.hql", hql_src, pyspark_src)
→ POST /internal/analyze-file
→ agents/reconcile_agent/tools_impl/analyze_file.py → tools_impl/utils/static_analyzer.py
→ 8-dimension regex comparison (table, column, join, filter, partition parity...)
→ returns: {overall_similarity: 0.91, issues: [...]}

workflow_parity(conversion_result)
→ POST /internal/workflow-parity
→ agents/reconcile_agent/tools_impl/workflow_parity.py
→ checks DAG task count matches number of converted PySpark files
→ returns: {status: "PASSED", score: 1.0}

runtime_validation("silver_customers", "MEDIUM", 0.91)
→ POST /internal/runtime-validation
→ agents/reconcile_agent/tools_impl/runtime_validation.py → tools_impl/utils/validators.py
→ simulated: row_count, checksum, SLA, consumer_replay checks
→ returns: {row_count: {status: "PASSED"}, ...}

compile_report("silver_customers", files_analysis, workflow_check, runtime_checks, issues)
→ POST /internal/compile-report
→ agents/reconcile_agent/tools_impl/compile_report.py → tools_impl/utils/validators.py
→ aggregates all scores, applies blast_radius threshold adjustment
→ returns: {confidence_score: 0.88, migration_risk: "LOW", recommendation: "Proceed"}
```

---

## 8. DEPLOY phase

Orchestrator calls:
```
run_deploy_phase("silver_customers", assessment, conversion, reconciliation)
→ POST /internal/run-deploy-phase
→ agents/deploy_agent/migrate.py: run_deploy(...)
```

The deploy_agent reads skills `artifact_validation`, `deployment_governance`, then:

```
validate_artifacts(conversion, reconcile)
→ POST /internal/validate-artifacts
→ agents/deploy_agent/tools_impl/validate_artifacts.py → tools_impl/utils/artifact_validator.py
→ checks each .py file exists + parseable, DAG file valid, confidence above threshold
→ returns: {all_artifacts_valid: true, deployment_ready: true}

run_smoke_tests("silver_customers", conversion, reconcile)
→ POST /internal/run-smoke-tests
→ agents/deploy_agent/tools_impl/run_smoke_tests.py → tools_impl/utils/smoke_tests.py
→ 7 tests: file existence, syntax, import check, write ops, DAG structure, schema, lineage
→ returns: {passed: 6, failed: 0, warning: 1, total: 7, score: 92, overall: "PASSED"}

compute_governance(artifact_checks, smoke_results, reconcile)
→ POST /internal/compute-governance
→ agents/deploy_agent/tools_impl/compute_governance.py → tools_impl/utils/governance.py
→ weighted formula: confidence + smoke score + blast_radius penalty
→ returns: {readiness_score: 89, governance: {state: "APPROVED", conditions: []}}

# Human approval gate before writing artifacts
request_human_approval(phase="DEPLOY", summary="...", options=[...], pipeline=pipeline)

generate_cicd("silver_customers", pyspark_files, assessment, reconcile)
→ POST /internal/generate-cicd
→ agents/deploy_agent/tools_impl/generate_cicd.py → tools_impl/utils/cicd_generator.py
→ builds GitHub Actions YAML
→ returns: {cicd_yaml: "...", pipeline_config: {...}}

write_manifests("silver_customers", assessment, conversion, reconcile, ...)
→ POST /internal/write-manifests
→ agents/deploy_agent/tools_impl/write_manifests.py → tools_impl/utils/manifest_builder.py
→ writes JSON files to output/silver_customers/
→ returns: {output_dir: "...", files_written: [...], file_count: 7}
```

---

## 9. Orchestrator returns final result

Orchestrator agent calls `FINAL(...)`:
```json
{
    "pipeline":   "silver_customers",
    "outcome":    "SUCCESS",
    "summary":    "Migrated 2 HQL files to PySpark. MEDIUM complexity. Confidence 0.88. Governance APPROVED.",
    "assessment":     { "complexity": "MEDIUM", "lineage": {...}, "blast_radius": [...], "wave": 2 },
    "conversion":     { "files_converted": 2, "dag_filename": "silver_customers_dag.py" },
    "reconciliation": { "confidence_score": 0.88, "migration_risk": "LOW", "recommendation": "Proceed" },
    "deployment":     { "readiness_score": 89, "governance_state": "APPROVED", "manifests_written": 7 }
}
```

---

## 10. Results stored + SSE stream closes

`orchestrator.py` stores result in memory dicts.
Frontend polling `/result/silver_customers`, `/conversion/silver_customers`, etc. now returns data.
SSE stream sends `complete` event — frontend updates all panels.

---

## Event stream (parallel to steps 4–9)

Throughout the run, `ToolCallLogger` middleware intercepts every `/internal/*` POST:
```
tool called  → pushes "tool_call"   event to event_queue
tool returns → pushes "tool_result" event with one-line summary
```

`_stream_reasoning()` watches the fast-rlm `.jsonl` log and pushes `reasoning` events
when agents generate new code steps.

Frontend `/stream/silver_customers` SSE receives all events in real time
→ Orchestration page renders the live agent trace.

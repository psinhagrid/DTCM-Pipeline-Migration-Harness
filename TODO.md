# TODO — Known Gaps & Next Steps

Priority: **P0** = blocks real usage · **P1** = meaningful capability · **P2** = production hardening

---

## P0 — Blocks Real Usage

### Real runtime validation (reconcile_subagent)
**Files:** `subagents/reconcile_subagent/utils/validators.py`
**Now:** row count, checksum, SLA, and consumer replay are all simulated — seeded numbers, not real execution. Confidence score is 80% real + 20% simulated.
**TODO:**
- Connect to Hive source cluster — run real `COUNT(*)` queries
- Connect to Iceberg target — compute real partition checksums
- Measure actual DAG runtime for SLA compliance
- Replay saved consumer queries against both clusters and diff results
**Why:** Without this, the reconciliation confidence score is partially fictional. Documented in `data_provenance` field of every report.

### S3 artifact upload (convert_subagent)
**File:** `subagents/convert_subagent/tools/s3_upload_tool.py`
**Now:** `pass` stub — generated PySpark files and DAG never leave local disk
**TODO:** Implement with boto3. Add `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` to `.env`

### MWAA/EMR deployment staging (deploy_subagent)
**File:** `subagents/deploy_subagent/tools/stage_deployment_tool.py`
**Now:** `pass` stub — DAG never registered in MWAA, EMR config never validated
**TODO:** Wire `mwaa_mcp.register_dag()` + `emrs_mcp.validate_job_config()`

---

## P1 — Meaningful Capability Gaps

### Write migration status back to Neo4j
**File:** `graph/client.py` + `subagents/deploy_subagent/tools/`
**Now:** Neo4j is read-only — pipeline status (MIGRATED, IN_PROGRESS, FAILED) never written back
**TODO:**
1. Add `write_pipeline_status(pipeline, status)` to `graph/client.py`
2. `deploy_subagent` calls it at finish (APPROVED → MIGRATED, BLOCKED → FAILED)
3. Supervisor queries status before running downstream wave
**Why:** Without this, wave-ordered "Run All" cannot verify prerequisites are met before starting the next wave

### Control-M job chain export (convert_subagent)
**File:** `subagents/convert_subagent/tools/controlm_export_tool.py`
**Now:** `pass` stub — DAG task ordering is assumed linear
**TODO:** Wire Control-M REST API or MCP server. Feed job chain XML to DAG generator for accurate task dependencies and retry policies

### MWAA DAG validation (convert_subagent)
**Now:** Generated DAG files are never syntax-checked before deployment
**TODO:** Option A — run `airflow dags list` locally. Option B — wire MWAA MCP `POST /dags/validate`

### UDF target validation (convert_subagent)
**Now:** UDFs detected in source, but never verified against the target Spark environment
**TODO:** Query target cluster to confirm each UDF is registered before conversion

### Run All — true wave-parallel execution (Frontend)
**File:** `frontend/src/routes/index.tsx`
**Now:** Wave ordering implemented and used by Run All. Individual pipelines within a wave still run sequentially.
**TODO:** Run all pipelines in the same wave simultaneously using `Promise.all`. Wait for entire wave before starting the next.

### Migration Plan — upgrade from static to intelligent
**File:** `graph/client.py` — `compute_migration_plan()`
**Now:** Pure topological sort — correct wave order but no prioritisation intelligence
**TODO:**
- Factor in team capacity (don't schedule all COMPLEX pipelines in same wave if team is small)
- Factor in historical failure rates when available
- Let migration team annotate pipelines with priority/risk in Neo4j, incorporate into ordering
**Why:** Currently produces the mathematically correct order. Future: produces the practically optimal order.

---

## P2 — Production Hardening

### S3 source file reading (assess_subagent)
**File:** `subagents/assess_subagent/assess_subagent.py` — `PIPELINES_ROOT`
**Now:** Reads `.hql` files from local `pipelines/` directory
**TODO:** Replace with boto3 S3 client reading from `s3://dtcm-source/hive/pipelines/<name>/`

### Complexity thresholds — calibration
**File:** `subagents/assess_subagent/utils/hql_utils.py` — `WEIGHTS`, `BANDS`
**Now:** Scoring weights and band cutoffs are assumed. Not validated against real migration history.
**TODO:** Calibrate with migration team against actual completed migrations

### UDF registry
**File:** `subagents/assess_subagent/utils/hql_utils.py` — `HIVE_BUILTINS`
**Now:** Hand-curated built-in list. Anything not on it is flagged as UDF.
**TODO:** Query Hive metastore (`SHOW FUNCTIONS`) or a central UDF registry API

### HQL parser — CTE and subquery support
**File:** `subagents/assess_subagent/utils/hql_utils.py`
**Now:** Regex-based parsing misses CTEs (`WITH ... AS`), subquery aliases, LATERAL VIEW
**TODO:** Use sqlfluff parse tree for table/column extraction instead of regex. Affects ~20% of complex real pipelines.

### Governance hooks — real interceptors
**Now:** `PreToolUse` / `PostToolUse` events logged as SSE strings only
**TODO:** Implement as Python interceptors wrapping every tool call — governance hook raises to block; audit hook POSTs to compliance store

### Session persistence
**File:** `orchestrator.py`
**Now:** All results in-memory dicts — lost on process restart. Concurrent runs interleave in shared SSE queue.
**TODO:**
1. Per-run event queue keyed by `run_id`
2. Persistent store (Redis or DB) for multi-day migration sessions
3. Session forking for parallel validation runs

### MCP Servers — none wired
| Server | Purpose | Status |
|---|---|---|
| `neo4j_mcp` | Lineage graph via MCP protocol | Direct driver used instead |
| `vdc_mcp` | Data catalog registration | Not built |
| `oneflow_mcp` | CI/CD pipeline trigger | Not built |
| `openlineage_mcp` | Lineage event emission | Not built |

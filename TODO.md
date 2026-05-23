# TODO — Known Gaps & Next Steps

Tracks every stub, simplification, and missing capability.
Architecture reference: Agent → Subagent → Tools → Utils → Skills

---

## assess_subagent

### S3 file source
**File:** `agents/assess_subagent/assess_subagent.py` — `PIPELINES_ROOT`
**Now:** reads `.hql` files from local `pipelines/<name>/` directory
**TODO:** replace with boto3 S3 client → `s3://dtcm-source/hive/pipelines/<name>/`

### Complexity thresholds
**File:** `agents/assess_subagent/utils/hql_utils.py` — `WEIGHTS`, `BANDS`
**Now:** scoring weights and band cutoffs are assumed, not data-driven
**TODO:** verify thresholds with migration team; calibrate against real migration history

### UDF registry
**File:** `agents/assess_subagent/utils/hql_utils.py` — `HIVE_BUILTINS`
**Now:** anything not in a hand-curated built-in list is flagged as a UDF
**TODO:** query Hive metastore (`SHOW FUNCTIONS`) or a central UDF registry API

### Downstream consumer discovery
**File:** `agents/assess_subagent/utils/hql_utils.py` — `discover_downstream()`
**Now:** greps sibling `pipelines/` directories for output table name references
**TODO:** replace with Neo4j lineage query or data catalog API (Amundsen / DataHub)

### Neo4j graph write
**File:** `agents/assess_subagent/tools/neo4j_write_graph_tool.py`
**Now:** stub — `pass`, no graph is written
**TODO:** wire real Neo4j instance via MCP server (`neo4j_mcp`)

---

## convert_subagent

### DAG generation — Control-M dependency
**File:** `agents/convert_subagent/utils/conversion_engine.py` — `generate_dag()`
**Now:** template-based DAG from pipeline metadata; task order assumed linear
**Why not LLM yet:** requires real Control-M XML job chain export as input —
without it the LLM would hallucinate task dependencies
**TODO:**
  1. Wire `controlm_export_tool` via Control-M REST API or MCP server
  2. Export job chain XML per pipeline
  3. Feed XML to DAG generator → accurate task ordering + retry policies

### S3 artifact write
**File:** `agents/convert_subagent/tools/s3_upload_tool.py`
**Now:** stub — `pass`, artifacts never written to S3
**TODO:**
  1. Add boto3 + IAM credentials in `.env`
  2. `s3.put_object()` for each generated `.py` file and DAG

### MWAA DAG validation
**Now:** no validation — a broken DAG would not be caught until deployed
**TODO:**
  - Option A: run `airflow dags list` locally against generated file
  - Option B: wire MWAA MCP server `POST /dags/validate`

### UDF target validation
**Now:** UDFs are detected in source but never checked against target environment
**TODO:** verify each detected UDF exists in the target Spark/Iceberg cluster
before conversion to avoid silent runtime failures

---

## reconcile_subagent

### PySpark syntax validation  ← IN PROGRESS
**File:** `agents/reconcile_subagent/tools/` — to be added
**Now:** no syntax check on generated `.py` files — broken code passes reconciliation
**TODO:** add `validate_pyspark_tool` — parse each `.py` for syntax errors,
undefined imports, missing SparkSession, missing writeTo/append calls

### Real row count validation
**File:** `agents/reconcile_subagent/utils/validators.py` — `row_count_check()`
**Now:** simulated — generates plausible numbers based on similarity score
**TODO:** run real `COUNT(*)` against Hive source cluster and Iceberg target

### Real checksum validation
**File:** `agents/reconcile_subagent/utils/validators.py` — `checksum_check()`
**Now:** simulated — fake SHA-256 values
**TODO:** compute SHA-256 on partition data and compare source vs target

### Real consumer replay
**File:** `agents/reconcile_subagent/utils/validators.py` — `consumer_replay_check()`
**Now:** simulated — hardcoded speedup factor
**TODO:** replay saved downstream consumer queries against both clusters and diff results

---

## deploy_subagent

### Deployment staging
**File:** `agents/deploy_subagent/tools/stage_deployment_tool.py`
**Now:** stub — `pass`, MWAA/EMR never touched
**TODO:** wire `mwaa_mcp.register_dag()` + `emrs_mcp.validate_job_config()`

### Governance hooks
**Now:** hook events (`visa_governance`, `audit_logger`) are logged as SSE strings only —
no real interceptor blocks anything
**TODO:**
  1. Wire real governance API — `PreToolUse` hook checks approval before tool runs
  2. `PostToolUse` hook POSTs audit metadata to compliance service
  3. Denied tools raise exception and halt the subagent loop

---

## Infrastructure

### MCP Servers — none wired
The design calls for four MCP servers. All are currently stubs or missing:

| Server | Purpose | Status |
|---|---|---|
| `neo4j_mcp` | Dependency graph read/write | stub (`pass`) |
| `vdc_mcp` | Data catalog registration | not built |
| `oneflow_mcp` | CI/CD pipeline trigger | not built (YAML written locally instead) |
| `openlineage_mcp` | Lineage event emission | not built |

### Hooks — not real interceptors
**Now:** `PreToolUse` / `PostToolUse` events are emitted as SSE log strings
**TODO:** implement as actual Python interceptors that wrap every tool call —
governance hook can raise to block execution; audit hook writes to compliance store

### Sessions — no persistence
**File:** `orchestrator.py` — `results`, `conversions`, `reconciliations`, `deployments`
**Now:** in-memory dicts, wiped on server restart; concurrent runs interleave in SSE queue
**TODO:**
  1. Per-run queue keyed by `run_id` in `event_queue.py`
  2. Persistent session store (Redis or DB) so multi-day migrations resume
  3. Session forking for parallel validation runs across environments

### Prompt caching
**Now:** every Claude API call sends full context cold
**TODO:** add `cache_control` breakpoints on system prompts and skill content —
skills are read-only and perfect candidates for prompt caching

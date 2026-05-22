# TODO — Known Simplifications & Gaps

Tracks every deliberate shortcut and what needs to replace it.

---

## assess_agent

### S3 file source
**File:** `agents/assess_agent/assess_agent.py` — `PIPELINES_ROOT`
**Now:** reads `.hql` files from local `pipelines/<name>/` directory
**TODO:** replace with boto3 S3 client reading from `s3://dtcm-source/hive/pipelines/<name>/`

### Complexity thresholds
**File:** `agents/assess_agent/utils.py` — `_WEIGHTS`, `_BANDS`
**Now:** scoring weights and band cutoffs are assumed (not data-driven)
**TODO:** verify thresholds with migration team; calibrate against real migration history

### UDF registry
**File:** `agents/assess_agent/utils.py` — `HIVE_BUILTINS`, `SQL_KEYWORDS`
**Now:** anything not in a hand-curated built-in list is flagged as a UDF
**TODO:** query Hive metastore (`SHOW FUNCTIONS`) or a central UDF registry API

### Downstream consumer discovery
**File:** `agents/assess_agent/utils.py` — `discover_downstream()`
**Now:** grep sibling `pipelines/` directories for output table name references
**TODO:** replace with Neo4j lineage query or data catalog API (Amundsen / DataHub)

---

## convert_agent

### HiveQL → PySpark conversion
**File:** `agents/convert_agent/future_llm_transformer.py`
**Now:** REAL — Llama 3.2 Vision (10.7B, Ollama local) converts each .hql file
**Model config:** `OLLAMA_MODEL`, `OLLAMA_BASE_URL`, `OLLAMA_TEMPERATURE` in `.env`
**TODO:** swap `OLLAMA_BASE_URL` → Claude API when moving to production LLM

### DAG generation — kept as template (intentional)
**File:** `agents/convert_agent/conversion_engine.py` — `generate_dag()`
**Now:** Python template generates Airflow DAG from pipeline metadata
**Why NOT LLM yet:** Real DAG generation requires Control-M XML job chain export as input.
Until `controlm_mcp.export_job_chain()` is real, the LLM has insufficient input data
to produce a correct DAG — it would hallucinate task dependencies.
**TODO:**
  1. Wire real Control-M MCP server (`controlm_mcp`)
  2. Export job chain XML for each pipeline
  3. Feed XML to LLM prompt as context → generate accurate Airflow DAG

### S3 artifact write — simulated event
**File:** `agents/convert_agent/convert_agent.py` — Phase 5
**Now:** `S3.put_object` events are emitted but no real write occurs
**Issues now:** none — artifacts exist in memory only (conversion results in `orchestrator.conversions`)
**TODO:**
  1. Add boto3: `pip install boto3`
  2. IAM role / credentials in `.env` (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`)
  3. Replace simulated events with real `s3.put_object(Bucket=..., Key=..., Body=spark_python)`

### MWAA DAG validation — simulated event
**File:** `agents/convert_agent/convert_agent.py` — Phase 4
**Now:** `MCP → mwaa_mcp.validate_dag` is emitted but no real validation occurs
**Issues now:** none — a broken DAG would not be caught until deployed
**TODO:**
  1. Option A: Install airflow locally, run `airflow dags list` against generated file
  2. Option B: Wire MWAA MCP server with `POST /dags/validate` endpoint

### Control-M job chain export — simulated event
**File:** `agents/convert_agent/convert_agent.py` — Phase 4
**Now:** `MCP → controlm_mcp.export_job_chain` is emitted but no export occurs
**Issues now:** DAG is generated from pipeline metadata, not actual Control-M definition.
Task order, retry policies, and SLAs may differ from real Control-M config.
**TODO:**
  1. Stand up Control-M MCP server or use Control-M REST API
  2. `GET /run/jobs?folder=<pipeline>` → returns job chain XML
  3. Pass XML to DAG generator as structured input

### Governance hooks — simulated
**File:** `agents/convert_agent/convert_agent.py` — Phase 1 & 5
**Now:** `visa_governance` and `audit_logger` hook events are emitted with no real check
**Issues now:** none for demo — a real governance deny would not be caught
**TODO:**
  1. Wire real governance API (internal approval workflow)
  2. If denied → raise exception and emit error event, halt pipeline
  3. Audit logger → POST to real audit service with pipeline run metadata

---

## reconcile_agent

### Row count validation
**File:** `agents/reconcile_agent.py`
**Now:** mocked — always passes
**TODO:** run actual `COUNT(*)` queries against Hive source and Spark/Iceberg target

### Checksum validation
**File:** `agents/reconcile_agent.py`
**Now:** mocked — hardcoded PASS
**TODO:** compute MD5/SHA on partition data and compare source vs target

### Consumer query replay
**File:** `agents/reconcile_agent.py`
**Now:** mocked — hardcoded PASS
**TODO:** replay saved consumer queries against both clusters and diff results

---

## Infrastructure

### Neo4j graph
**Files:** `orchestrator.py`, `agents/assess_agent/assess_agent.py`
**Now:** `MCP → neo4j_mcp.*` calls are emitted — no graph is written
**TODO:** connect real Neo4j instance; wire via MCP server

### Sessions / run isolation
**File:** `event_queue.py`
**Now:** single global queue — concurrent runs would interleave events
**TODO:** per-run queue keyed by `run_id`; SSE endpoint subscribes to specific run

### LLM — production upgrade path
**File:** `agents/convert_agent/future_llm_transformer.py`
**Now:** Ollama local (Llama 3.2 Vision, 10.7B, GGUF Q4_K_M)
**TODO:** when moving to production, swap `OLLAMA_BASE_URL` + `OLLAMA_MODEL` in `.env`
to point at Claude API (`api.anthropic.com`) or hosted inference endpoint

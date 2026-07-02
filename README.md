# HiveQL → PySpark Migration Pipeline — Fast RLM

Migrates Hadoop/Hive pipelines to Airflow + Spark, driven by a multi-agent fast-rlm system backed by Claude Sonnet.

---

## Architecture

```
Browser (port 8080)
    │  SSE stream / REST
    ▼
FastAPI Backend (port 8000)         ← main.py
    │
    ├─ /run                         → orchestrator.py → orchestrator agent
    ├─ /stream/{pipeline}           → SSE event stream  (routes/stream.py)
    ├─ /graph, /migration-plan      → Neo4j queries     (routes/graph.py)
    ├─ /skills-api                  → skill CRUD        (routes/skills.py)
    └─ /internal/*                  → tool HTTP bridge  (routes/internal.py)
             ▲
             │  HTTP (tool calls from Deno/Pyodide)
             │
    5 fast-rlm Agents (Deno/Pyodide)
      orchestrator_agent  ← sequences the 4 phase agents
      assess_agent
      convert_agent
      reconcile_agent
      deploy_agent
             │
             └─ LiteLLM Proxy (port 4000)
                     │
                     └─ Anthropic API (claude-sonnet-4-6)

Neo4j (port 7687)  ← graph/client.py
```

### Migration Phases

```
HiveQL source files (pipelines/)
         │
    [ASSESS]    scan_repo → parse_hql → lineage_extract → classify_complexity → neo4j_write
         │
    [CONVERT]   transform_hql (Claude) → validate_pyspark → generate_dag
         │
    [RECONCILE] analyze_file → workflow_parity → runtime_validation → compile_report
         │
    [DEPLOY]    validate_artifacts → run_smoke_tests → compute_governance → generate_cicd → write_manifests
         │
    output/{pipeline}/  (JSON manifests + PySpark files + DAG)
```

Human approval gates between phases — the orchestrator calls `request_human_approval` before each transition. The human's decision is final.

### Module Layout

```
Fast_RLM/
├── starter.py                  # Launch script (Neo4j + LiteLLM + backend + frontend)
├── main.py                     # FastAPI app, middleware, REST endpoints
├── orchestrator.py             # Thin wrapper — calls run_orchestrator(), stores results
├── event_queue.py              # Async SSE queue + user-input mechanism
├── litellm_config.yaml         # LiteLLM proxy: claude-sonnet-4-6 → Anthropic
│
├── agents/
│   ├── assess_agent/
│   │   ├── migrate.py          # RLM runner: run_assess(pipeline) → dict
│   │   ├── tools.py            # Pyodide HTTP bridge (fetch /internal/*)
│   │   ├── tools_impl/         # Python logic: scan_repo, parse_hql, lineage_extract,
│   │   │                       #   classify_complexity, neo4j_write, query_graph
│   │   │   └── utils/          # hql_utils.py
│   │   └── skills/             # repo_scan, complexity_classification, graph_context, hiveql_repair
│   │
│   ├── convert_agent/
│   │   ├── migrate.py          # run_convert(pipeline, assessment) → dict
│   │   ├── tools.py
│   │   ├── tools_impl/         # transform_hql, validate_pyspark, generate_dag
│   │   │   └── utils/          # conversion_engine.py, pyspark_validator.py
│   │   └── skills/             # hiveql_to_pyspark, dag_generation, hiveql_repair, pyspark_repair
│   │
│   ├── reconcile_agent/
│   │   ├── migrate.py          # run_reconcile(pipeline, assessment, conversion) → dict
│   │   ├── tools.py
│   │   ├── tools_impl/         # analyze_file, workflow_parity, runtime_validation, compile_report, query_graph
│   │   │   └── utils/          # static_analyzer.py, validators.py
│   │   └── skills/             # semantic_comparison, runtime_validation, risk_assessment
│   │
│   ├── deploy_agent/
│   │   ├── migrate.py          # run_deploy(pipeline, assessment, conversion, reconciliation) → dict
│   │   ├── tools.py
│   │   ├── tools_impl/         # validate_artifacts, run_smoke_tests, compute_governance,
│   │   │                       #   generate_cicd, write_manifests, query_graph
│   │   │   └── utils/          # artifact_validator, smoke_tests, governance, cicd_generator, ...
│   │   └── skills/             # artifact_validation, deployment_governance
│   │
│   └── orchestrator/
│       ├── migrate.py          # run_orchestrator(pipeline) → dict
│       ├── tools.py            # run_*_phase + query_graph + read_skill + request_human_approval
│       └── skills/             # orchestrator, graph_interrelations
│
├── routes/
│   ├── stream.py               # GET /stream/{pipeline} — SSE
│   ├── graph.py                # GET /graph, /migration-plan — Neo4j
│   ├── skills.py               # GET/PUT/DELETE /skills-api — markdown CRUD per agent
│   └── internal.py             # POST /internal/* — HTTP bridge + phase-runner endpoints
│
├── graph/client.py             # Neo4j driver: blast_radius, wave, summary queries
├── pipelines/*/  *.hql         # Source HiveQL files
├── output/*/                   # Generated PySpark, DAGs, JSON manifests
└── frontend/                   # React + TanStack Router (Vite, port 8080)
```

---

## Setup

### Prerequisites

- Python 3.12
- Node.js 18+
- [Deno](https://deno.land) — `brew install deno`
- [Neo4j](https://neo4j.com) — `brew install neo4j`

### 1. Neo4j

```bash
brew services start neo4j
# First run: open http://localhost:7474, login neo4j/neo4j, set password to dtcm_local
```

### 2. Python environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment variables

```bash
cp .env.sample .env
# Fill in ANTHROPIC_API_KEY
```

Required variables:

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key — used by LiteLLM proxy and transform_hql directly |
| `RLM_MODEL_API_KEY` | Same key — used by fast-rlm Deno engine to authenticate with LiteLLM |
| `RLM_MODEL_BASE_URL` | `http://localhost:4000` — LiteLLM proxy URL |
| `RLM_PRIMARY_MODEL` | `claude-sonnet-4-6` (default) |
| `NEO4J_URI` | `bolt://localhost:7687` |
| `NEO4J_USER` | `neo4j` |
| `NEO4J_PASSWORD` | your Neo4j password |

### 4. Frontend

```bash
cd frontend && npm install
```

### 5. Run everything

```bash
python starter.py
```

Starts: **LiteLLM** → `:4000` · **Backend** → `:8000` · **Frontend** → `:8080`

---

## Frontend Pages

| Route | Purpose |
|---|---|
| `/` | Dashboard — trigger migrations per pipeline or Run All in wave order |
| `/orchestration` | Live SSE stream — watch agent reasoning and tool calls in real time |
| `/validation` | Reconciliation report — semantic similarity scores per file |
| `/deployments` | Governance approval + smoke test results |
| `/context-graph` | Interactive pipeline dependency graph + migration plan waves |
| `/skills` | View, create, and delete agent skill files (all 5 agents) |
| `/observability` | System metrics and run log viewer |

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/run` | POST | Start migration (`?pipeline=silver_orders`) |
| `/stream/{pipeline}` | GET | SSE stream of live agent events |
| `/result/{pipeline}` | GET | Full migration result |
| `/conversion/{pipeline}` | GET | CONVERT phase output |
| `/reconcile/{pipeline}` | GET | RECONCILE phase output |
| `/deployment/{pipeline}` | GET | DEPLOY phase output |
| `/graph` | GET | Full Neo4j lineage graph |
| `/migration-plan` | GET | Wave-ordered migration sequence |
| `/pipelines` | GET | List source pipelines |
| `/skills-api` | GET | List skill files per agent |
| `/output/{pipeline}` | GET | List generated output files |
| `/reset` | POST | Clear in-memory results |
| `/pending-input` | GET | Current human approval prompt |
| `/user-input` | POST | Submit a human approval response |

---

## How It Works

1. The **orchestrator agent** reads `orchestrator.md` to understand the phase sequence
2. It calls `run_assess_phase` → `run_convert_phase` → `run_reconcile_phase` → `run_deploy_phase` via HTTP, with human approval gates between each
3. Each **phase agent** is an independent RLM agent with its own tools and skills
4. Tool calls flow: **Deno (fast-rlm) → HTTP → `/internal/*` (FastAPI) → Python in `agents/<phase>/tools_impl/`**
5. All agents can call `query_graph` at any time to inspect Neo4j pipeline dependencies
6. Results accumulate in `orchestrator.py` dicts, served via REST to the frontend
7. The frontend receives live agent events via SSE on `/stream/{pipeline}`

---

## Notes

- **Runtime validation** (row count, checksum, SLA) is **simulated** — no live Hive/Iceberg cluster. Documented in the `data_provenance` field of every reconciliation report.
- **S3 upload** and **MWAA deployment** are stubbed — generated artifacts stay on local disk under `output/`.
- `transform_hql` calls Anthropic directly (not via LiteLLM) — both `ANTHROPIC_API_KEY` and `RLM_MODEL_API_KEY` must be set to the same value.

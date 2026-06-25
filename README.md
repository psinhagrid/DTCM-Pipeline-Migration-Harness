# DTCM Migration Pipeline — Fast RLM

Migrates Hadoop/Hive pipelines to AWS MWAA (Airflow) + Apache Iceberg on Spark, driven by a single fast-rlm agent loop backed by Claude Sonnet.

---

## Architecture

```
Browser (port 8080)
    │  SSE stream / REST
    ▼
FastAPI Backend (port 8001)         ← main.py
    │
    ├─ /run/{pipeline}              → orchestrator.py → rlm/migrate.py
    ├─ /stream/{pipeline}           → SSE event stream (routes/stream.py)
    ├─ /graph, /migration-plan      → Neo4j queries   (routes/graph.py)
    ├─ /skills                      → skill CRUD       (routes/skills.py)
    └─ /internal/*                  → tool HTTP bridge (routes/internal.py)
             ▲
             │  HTTP (tool calls)
             │
    fast-rlm Agent (Deno/Pyodide)   ← rlm/migrate.py
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

### Module Layout

```
Fast_RLM/
├── starter.py                  # Launch script (Neo4j + LiteLLM + backend + frontend)
├── main.py                     # FastAPI app, middleware, REST endpoints
├── orchestrator.py             # Thin wrapper — calls run_migration(), stores results
├── event_queue.py              # Async SSE queue + user-input mechanism
│
├── rlm/
│   ├── migrate.py              # fast-rlm engine config, 20 tools wired, ENV passthrough
│   ├── tools.py                # Pyodide tool implementations (HTTP calls to /internal/*)
│   └── litellm_config.yaml     # LiteLLM proxy: claude-sonnet-4-6 → Anthropic
│
├── tools/
│   ├── scan_repo_tool.py / parse_hql_tool.py / lineage_extract_tool.py
│   ├── classify_complexity_tool.py / neo4j_write_graph_tool.py / query_graph_tool.py
│   ├── transform_hql_tool.py / generate_dag_tool.py / validate_pyspark_tool.py
│   ├── analyze_file_tool.py / workflow_parity_tool.py / runtime_validation_tool.py
│   ├── compile_report_tool.py / validate_artifacts_tool.py / run_smoke_tests_tool.py
│   ├── compute_governance_tool.py / generate_cicd_tool.py / write_manifests_tool.py
│   └── utils/                  # hql_utils, conversion_engine, static_analyzer, validators, etc.
│
├── routes/
│   ├── stream.py               # GET /stream/{pipeline} — SSE
│   ├── graph.py                # GET /graph, /migration-plan — Neo4j
│   ├── skills.py               # GET/POST/DELETE /skills — markdown CRUD
│   └── internal.py             # POST /internal/* — HTTP bridge for Deno tools
│
├── graph/client.py             # Neo4j driver: blast_radius, wave, summary queries
├── skills/*.md              # Domain knowledge (orchestrator.md drives phase order)
├── pipelines/*/  *.hql         # Source HiveQL files (6 example pipelines)
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
# Fill in ANTHROPIC_API_KEY (same value goes in RLM_MODEL_API_KEY)
```

Required variables:

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key — used by LiteLLM proxy |
| `RLM_MODEL_API_KEY` | Same key — used by fast-rlm Deno engine to authenticate with LiteLLM |
| `RLM_MODEL_BASE_URL` | `http://localhost:4000` — LiteLLM proxy URL |
| `RLM_PRIMARY_MODEL` | `claude-sonnet-4-6` (default) |
| `NEO4J_URI` | `bolt://localhost:7687` |
| `NEO4J_USER` | `neo4j` |
| `NEO4J_PASSWORD` | `dtcm_local` |

### 4. Frontend

```bash
cd frontend && npm install
```

### 5. Run everything

```bash
python starter.py
```

Starts: **LiteLLM** → `:4000` · **Backend** → `:8001` · **Frontend** → `:8080`

---

## Frontend Pages

| Route | Purpose |
|---|---|
| `/` | Dashboard — trigger migrations per pipeline or Run All in wave order |
| `/orchestration` | Live SSE stream — watch agent reasoning and tool calls in real time |
| `/validation` | Reconciliation report — semantic similarity scores per file |
| `/deployments` | Governance approval + smoke test results |
| `/context-graph` | Interactive pipeline dependency graph + migration plan waves |
| `/skills` | View, create, and delete agent skill files |
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
| `/skills` | GET | List skill names |
| `/output/{pipeline}` | GET | List generated output files |
| `/reset` | POST | Clear in-memory results |

---

## How the Agent Works

The fast-rlm engine runs a single Claude Sonnet agent with 20 tools exposed via HTTP. The agent:

1. Reads `orchestrator.md` skill to understand the phase sequence
2. Reads phase-specific skills before each phase (`repo_scan`, `hiveql_to_pyspark`, etc.)
3. Calls tools sequentially — each tool POSTs to `/internal/*` on the backend
4. The backend executes real Python logic and returns JSON
5. Results accumulate in `orchestrator.py` dicts, served via REST to the frontend

The tool bridge: **Deno (fast-rlm) → HTTP → `/internal/*` (FastAPI) → Python modules**

---

## Notes

- **Runtime validation** (row count, checksum, SLA) is **simulated** — no live Hive/Iceberg cluster connected. Documented in the `data_provenance` field of every reconciliation report.
- **S3 upload** and **MWAA deployment** are stubbed — generated artifacts stay on local disk under `output/`.

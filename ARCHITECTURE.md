# Architecture

## System Components

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser  :8080                                                  │
│  React + TanStack Router (Vite)                                  │
│  Dashboard · Orchestration · Validation · Deployments           │
│  Context Graph · Skills · Observability                          │
└───────────────────────┬─────────────────────────────────────────┘
                        │ REST + SSE
┌───────────────────────▼─────────────────────────────────────────┐
│  FastAPI Backend  :8001          main.py                         │
│                                                                  │
│  Middleware:                                                      │
│    ToolCallLogger  — intercepts /internal/* calls,               │
│                      pushes tool events to SSE queue             │
│    CORS            — allows :8080 / :5173 / :3000                │
│                                                                  │
│  Routes:                                                         │
│    /run             POST  → orchestrator → rlm/migrate.py        │
│    /stream/{p}      GET   → SSE (event_queue)                    │
│    /graph           GET   → Neo4j full graph                     │
│    /migration-plan  GET   → wave-ordered plan                    │
│    /skills          GET/POST/DELETE → skills/ markdown           │
│    /internal/*      POST  → tool HTTP bridge                     │
│    /result /conversion /reconcile /deployment                    │
│    /pipelines /output /reset /pending-input /user-input          │
└──────────┬────────────────────────┬────────────────────────────┘
           │                        │
           ▼                        ▼
┌──────────────────┐    ┌──────────────────────────────────────────┐
│  Neo4j  :7687    │    │  fast-rlm Agent  (rlm/migrate.py)         │
│  graph/client.py │    │                                           │
│                  │    │  RLMConfig:                               │
│  Node types:     │    │    primary_agent: claude-sonnet-4-6       │
│    Pipeline      │    │    max_depth: 3                           │
│    Table         │    │    max_calls_per_subagent: 25             │
│    UDF           │    │    max_prompt_tokens: 180000              │
│                  │    │    max_money_spent: $5.00                 │
│  Relationships:  │    │                                           │
│    READS         │    │  20 tools exposed to agent                │
│    WRITES        │    │  ENV: DTCM_BACKEND_URL                    │
│    DEPENDS_ON    │    │       RLM_MODEL_BASE_URL → :4000          │
│    USES_UDF      │    │       RLM_MODEL_API_KEY                   │
└──────────────────┘    └────────────────┬─────────────────────────┘
                                         │ OpenAI-compatible API
                        ┌────────────────▼─────────────────────────┐
                        │  LiteLLM Proxy  :4000                     │
                        │  rlm/litellm_config.yaml                  │
                        │                                           │
                        │  model_name: claude-sonnet-4-6            │
                        │  → anthropic/claude-sonnet-4-6            │
                        │  → api.anthropic.com                      │
                        └───────────────────────────────────────────┘
```

---

## Tool Bridge

The fast-rlm agent runs inside **Deno** (JavaScript runtime). It cannot import Python directly. Every tool call flows through HTTP:

```
fast-rlm (Deno) → rlm/tools.py (Pyodide HTTP client)
               → POST /internal/<tool-name> (FastAPI)
               → tools/<tool>_tool.py (Python)
               → tools/utils/ (pure logic helpers)
```

`rlm/tools.py` contains Pyodide implementations that `fetch()` the backend. `routes/internal.py` receives the POST, calls the real tool, and returns JSON.

---

## Migration Phase Detail

### ASSESS
| Tool | Input | Output |
|---|---|---|
| `scan_repo` | pipeline name | hql_files, config_files |
| `parse_hql` | pipeline, filename | tables, columns, UDFs, complexity signals |
| `lineage_extract` | all reads/creates/writes | upstream tables, output tables, downstream pipelines |
| `classify_complexity` | tables, UDFs, has_window, etc. | score, complexity tier, effort estimate |
| `neo4j_write` | lineage data | nodes + edges written to Neo4j |
| `query_graph` | pipeline, query type | blast_radius / wave / summary |

### CONVERT
| Tool | Input | Output |
|---|---|---|
| `transform_hql` | pipeline, filename, metadata | PySpark `.py` file written to disk |
| `validate_pyspark` | filename, spark_python | valid bool, errors, warnings |
| `generate_dag` | pipeline, files, complexity | MWAA Airflow DAG `.py` written to disk |

`transform_hql` makes a direct Claude Sonnet API call (not via LiteLLM — uses `ANTHROPIC_API_KEY` from `modules/convert_module/utils/conversion_engine.py`).

### RECONCILE
| Tool | Input | Output |
|---|---|---|
| `analyze_file` | hql_src, pyspark_src | 8-dimension similarity scores |
| `workflow_parity` | conversion result | DAG vs files parity check |
| `runtime_validation` | pipeline, complexity, similarity | row_count, checksum, SLA, consumer_replay |
| `compile_report` | all analysis results | confidence_score, migration_risk, recommendation |

> Runtime validation is **simulated** — no live cluster connection.

### DEPLOY
| Tool | Input | Output |
|---|---|---|
| `validate_artifacts` | conversion, reconcile | all_artifacts_valid, deployment_ready |
| `run_smoke_tests` | pipeline, conversion, reconcile | passed/failed/total, score |
| `compute_governance` | artifact_checks, smoke, reconcile | readiness_score, APPROVED/BLOCKED state |
| `generate_cicd` | pipeline, files, assessment, reconcile | GitHub Actions YAML |
| `write_manifests` | all phase results | JSON files written to output/{pipeline}/ |

---

## Event Flow (SSE)

```
Agent tool call
    → ToolCallLogger middleware intercepts POST /internal/*
    → pushes "tool_call" event to event_queue
    → tool executes
    → pushes "tool_result" event with one-line summary
    → frontend /stream/{pipeline} SSE connection receives events
    → Orchestration page renders live
```

---

## Data Flow Summary

```
pipelines/{name}/*.hql
    │ scan_repo + parse_hql
    ▼
Assessment dict (complexity, lineage, UDFs)
    │ neo4j_write
    ▼
Neo4j graph (Pipeline/Table/UDF nodes + edges)
    │ transform_hql (Claude Sonnet)
    ▼
output/{name}/*.py  (PySpark)
output/{name}/*_dag.py  (Airflow DAG)
    │ analyze_file + compile_report
    ▼
Reconciliation report (confidence score, migration risk)
    │ compute_governance + write_manifests
    ▼
output/{name}/*.json  (assessment, conversion, reconcile, governance, cicd manifests)
```

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
│  FastAPI Backend  :8000          main.py                         │
│                                                                  │
│  Middleware:                                                      │
│    ToolCallLogger  — intercepts /internal/* calls,               │
│                      pushes tool events to SSE queue             │
│    CORS            — allows :8080 / :5173 / :3000                │
│                                                                  │
│  Routes:                                                         │
│    /run             POST  → orchestrator.py → orchestrator agent │
│    /stream/{p}      GET   → SSE (event_queue)                    │
│    /graph           GET   → Neo4j full graph                     │
│    /migration-plan  GET   → wave-ordered plan                    │
│    /skills-api      GET/PUT/DELETE → per-agent skill markdown    │
│    /internal/*      POST  → tool HTTP bridge                     │
│    /result /conversion /reconcile /deployment                    │
│    /pipelines /output /reset /pending-input /user-input          │
└──────────┬────────────────────────┬────────────────────────────┘
           │                        │
           ▼                        ▼
┌──────────────────┐    ┌──────────────────────────────────────────┐
│  Neo4j  :7687    │    │  Orchestrator Agent  (Deno/Pyodide)      │
│  graph/client.py │    │  agents/orchestrator/migrate.py          │
│                  │    │                                           │
│  Node types:     │    │  Sequences 4 phase agents via HTTP:       │
│    Pipeline      │    │    run_assess_phase   → POST /internal/run-assess-phase   │
│    Table         │    │    run_convert_phase  → POST /internal/run-convert-phase  │
│    UDF           │    │    run_reconcile_phase→ POST /internal/run-reconcile-phase│
│                  │    │    run_deploy_phase   → POST /internal/run-deploy-phase   │
│  Relationships:  │    │  + query_graph, read_skill, request_human_approval        │
│    READS         │    │                                           │
│    WRITES        │    │  Config: max_depth=2, max_calls=16, $1.50 │
│    DEPENDS_ON    │    └────────────┬──────────────────────────────┘
│    USES_UDF      │                 │ /internal/run-*-phase
└──────────────────┘    ┌────────────▼──────────────────────────────┐
                        │  Phase Agents  (each independent RLM agent)│
                        │                                            │
                        │  assess_agent    max_calls=20  $2.00       │
                        │  convert_agent   max_calls=20  $2.00       │
                        │  reconcile_agent max_calls=20  $2.00       │
                        │  deploy_agent    max_calls=20  $2.00       │
                        │                                            │
                        │  Each backed by LiteLLM → Anthropic        │
                        └────────────┬───────────────────────────────┘
                                     │ OpenAI-compatible API
                        ┌────────────▼───────────────────────────────┐
                        │  LiteLLM Proxy  :4000                      │
                        │  litellm_config.yaml                       │
                        │                                            │
                        │  model_name: claude-sonnet-4-6             │
                        │  → anthropic/claude-sonnet-4-6             │
                        │  → api.anthropic.com                       │
                        └────────────────────────────────────────────┘
```

---

## Agent Structure

There are **5 independent RLM agents**. Each is fully self-contained with its own tools, tool implementations, and skills.

```
agents/
├── assess_agent/
│   ├── migrate.py          # RLM runner: run_assess(pipeline) → dict
│   ├── tools.py            # Pyodide HTTP bridge (fetch /internal/*)
│   ├── tools_impl/         # Python logic called by routes/internal.py
│   │   ├── scan_repo.py, parse_hql.py, lineage_extract.py
│   │   ├── classify_complexity.py, neo4j_write.py, query_graph.py
│   │   └── utils/  hql_utils.py
│   └── skills/
│       ├── repo_scan.md, complexity_classification.md
│       ├── graph_context.md, hiveql_repair.md
│
├── convert_agent/
│   ├── migrate.py          # run_convert(pipeline, assessment) → dict
│   ├── tools.py
│   ├── tools_impl/
│   │   ├── transform_hql.py, validate_pyspark.py, generate_dag.py
│   │   └── utils/  conversion_engine.py, pyspark_validator.py
│   └── skills/
│       ├── hiveql_to_pyspark.md, dag_generation.md
│       ├── hiveql_repair.md, pyspark_repair.md
│
├── reconcile_agent/
│   ├── migrate.py          # run_reconcile(pipeline, assessment, conversion) → dict
│   ├── tools.py
│   ├── tools_impl/
│   │   ├── analyze_file.py, workflow_parity.py
│   │   ├── runtime_validation.py, compile_report.py, query_graph.py
│   │   └── utils/  static_analyzer.py, validators.py
│   └── skills/
│       ├── semantic_comparison.md, runtime_validation.md, risk_assessment.md
│
├── deploy_agent/
│   ├── migrate.py          # run_deploy(pipeline, assessment, conversion, reconciliation) → dict
│   ├── tools.py
│   ├── tools_impl/
│   │   ├── validate_artifacts.py, run_smoke_tests.py, compute_governance.py
│   │   ├── generate_cicd.py, write_manifests.py, query_graph.py
│   │   └── utils/  artifact_validator.py, smoke_tests.py, governance.py, ...
│   └── skills/
│       ├── artifact_validation.md, deployment_governance.md
│
└── orchestrator/
    ├── migrate.py          # run_orchestrator(pipeline) → dict
    ├── tools.py            # run_*_phase + query_graph + read_skill + request_human_approval
    └── skills/
        ├── orchestrator.md         # phase order + human approval gate rules
        └── graph_interrelations.md # how to read graph data across all agents
```

---

## Tool Bridge

The fast-rlm agent runs inside **Deno** (JavaScript runtime). Every tool call flows through HTTP:

```
fast-rlm (Deno/Pyodide)
    → agents/<phase>/tools.py     fetch() calls to /internal/*
    → POST /internal/<tool-name>  (FastAPI — routes/internal.py)
    → agents/<phase>/tools_impl/  Python logic
    → returns JSON to agent
```

`routes/internal.py` also hosts the 4 phase-runner endpoints that the orchestrator uses:
```
POST /internal/run-assess-phase    → agents/assess_agent/migrate.py   run_assess()
POST /internal/run-convert-phase   → agents/convert_agent/migrate.py  run_convert()
POST /internal/run-reconcile-phase → agents/reconcile_agent/migrate.py run_reconcile()
POST /internal/run-deploy-phase    → agents/deploy_agent/migrate.py   run_deploy()
```

---

## Skills System

Skill files are markdown documents that agents read at runtime via `read_skill('name')`.

All 5 agent skill directories are searched:
```
agents/assess_agent/skills/
agents/convert_agent/skills/
agents/reconcile_agent/skills/
agents/deploy_agent/skills/
agents/orchestrator/skills/
```

`graph_interrelations.md` lives in `orchestrator/skills/` and is accessible to all agents — it covers how to interpret `query_graph` results and calibrate thresholds from graph data.

---

## Migration Phase Detail

### ASSESS
| Tool | Input | Output |
|---|---|---|
| `scan_repo` | pipeline name | hql_files, config_files |
| `parse_hql` | pipeline, filename | tables, columns, UDFs, complexity signals |
| `lineage_extract` | reads/creates/writes | upstream tables, output tables, downstream pipelines |
| `classify_complexity` | tables, UDFs, has_window, etc. | score, complexity tier, effort estimate |
| `neo4j_write` | lineage data | nodes + edges written to Neo4j |
| `query_graph` | pipeline, query type | blast_radius / wave / summary |

### CONVERT
| Tool | Input | Output |
|---|---|---|
| `transform_hql` | pipeline, filename, metadata | PySpark `.py` file written to disk |
| `validate_pyspark` | filename, spark_python | valid bool, errors, warnings |
| `generate_dag` | pipeline, files, complexity | Airflow DAG `.py` written to disk |

`transform_hql` calls Anthropic API directly via `ANTHROPIC_API_KEY` (not via LiteLLM).

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

# DTCM Migration Pipeline

Migrates Hadoop/Hive pipelines to AWS MWAA (Apache Airflow) + Apache Iceberg on Spark using a multi-agent LLM system driven by Claude Sonnet.

---

## Architecture

A Supervisor agent orchestrates four specialized subagents. Claude Sonnet (Anthropic API) drives every agent loop — deciding which subagent to invoke next, evaluating outputs, and routing retries.

```
supervisor/              ← orchestrator; Claude decides routing at each step
subagents/
  assess_subagent/       ← scans HQL, classifies complexity, builds lineage graph
  convert_subagent/      ← converts HQL → PySpark + MWAA DAG via Claude Sonnet
  reconcile_subagent/    ← validates conversion correctness (semantic + static)
  deploy_subagent/       ← validates artifacts, smoke tests, governance approval
graph/
  client.py              ← Neo4j query layer (shared by all subagents)
pipelines/               ← HiveQL source files (6 example pipelines)
```

Each subagent follows the same internal structure:
- Agentic while loop (tool-use + LLM reasoning)
- `skills/` — domain knowledge `.md` files loaded on demand
- `tools/` — Python callable functions exposed to the agent
- `utils/` — pure logic helpers

**Lineage graph:** Neo4j (local via Docker) — stores pipeline dependency relationships, table-level lineage, and complexity classifications.

**Stack:** FastAPI (port 8001) · React + TanStack Router (port 8080) · Python 3.12

---

## Pipeline Flow

```
HiveQL (.hql)
    │
    ▼
[Assess]  — parse HQL, classify complexity (simple/moderate/complex),
            write nodes + edges to Neo4j lineage graph
    │
    ▼
[Convert] — LLM-driven HQL → PySpark transformation + MWAA DAG generation
    │
    ▼
[Reconcile] — static analysis + semantic diff; produces confidence score
    │
    ▼
[Deploy]  — artifact validation, smoke test, governance approval gate
```

---

## Setup

### Prerequisites
- Docker (for Neo4j)
- Python 3.12
- Node.js + [Bun](https://bun.sh)

### 1. Neo4j

```bash
docker run --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/dtcm_local \
  --detach neo4j:5
```

Neo4j Browser: http://localhost:7474

### 2. Python environment

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment variables

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

Required variables:

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required. Anthropic API key. |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Model used by all agent loops. |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j bolt URI. |
| `NEO4J_USER` | `neo4j` | Neo4j username. |
| `NEO4J_PASSWORD` | `dtcm_local` | Neo4j password. |

### 4. Backend

```bash
uvicorn main:app --reload --port 8001
```

API docs: http://localhost:8001/docs

### 5. Frontend

```bash
cd frontend && bun install && bun dev
# → http://localhost:8080
```

---

## Frontend Pages

| Route | Purpose |
|---|---|
| `/` | Dashboard — run individual pipelines or "Run All" in wave order |
| `/orchestration` | Live SSE event stream from all agents |
| `/workbench` | Side-by-side HQL vs PySpark diff |
| `/validation` | Reconciliation report with confidence scores |
| `/deployments` | Governance approval + smoke test results |
| `/context-graph` | Neo4j pipeline dependency DAG (visual) |

---

## Source Pipelines

HiveQL source files live in `pipelines/`. Six example pipelines are included, spanning simple transformations through multi-join aggregations, to exercise all complexity tiers.

---

## Status

**PoC / research.** Core migration logic (assessment, conversion, reconciliation) is real and exercises live Claude API calls. Deployment integration (S3 upload, MWAA DAG registration, EMR job submission) is stubbed. See `features.md` for a real vs. simulated breakdown.

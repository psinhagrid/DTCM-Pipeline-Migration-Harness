# DTCM Migration Pipeline — Feature Reference

For DS architect review. Accurate as of 2026-05-23.

---

## 1. Feature Overview

| Feature | Description | Status |
|---|---|---|
| HiveQL repository assessment | Scans `.hql`/`.sql` files, parses DDL with sqlfluff + regex, scores complexity via weighted formula | ✓ Real |
| HiveQL → PySpark conversion | Per-file Claude Sonnet API call; produces `.py` Spark scripts | ✓ Real |
| MWAA Airflow DAG generation | Claude Sonnet generates a DAG file per pipeline during conversion | ✓ Real |
| PySpark static validation | `ast.parse()` syntax check, import scan, write-op presence, hiveconf variable parity | ✓ Real |
| Semantic comparison | 8-dimension regex-based static analysis: table, column, aggregation, join, filter, partition, runtime var parity, UDF coverage | ✓ Real |
| Runtime validation | Row count, checksum, SLA, consumer replay checks | ✗ Simulated |
| Artifact validation | Python AST checks on converted scripts; DAG structure checks (task count vs DML file count) | ✓ Real |
| Smoke test suite (7 tests) | 4 real + 3 predetermined (see §2) | ⚠ Partial |
| Governance approval scoring | Weighted readiness formula over semantic score, smoke tests, blast radius, upstream status | ✓ Real |
| Deployment manifest generation | JSON manifests written to disk per pipeline | ✓ Real |
| Neo4j pipeline lineage graph | Nodes (Pipeline, Table, UDF) + relationships (READS, WRITES, DEPENDS_ON, USES_UDF) | ✓ Real |
| Context graph visualization | Interactive 4-tier DAG in frontend with blast radius counts on nodes | ✓ Real |
| Wave-ordered migration execution | Pipelines grouped by wave tier from Neo4j query; each wave runs in parallel | ✓ Real |
| Live event streaming (SSE) | `/stream/<pipeline_id>` endpoint pushes agent events to frontend in real time | ✓ Real |
| Skill-based agent knowledge | Domain rules (repo_scan, dag_generation, semantic_comparison, etc.) loaded on demand per subagent | ✓ Real |
| Retry logic on Claude API calls | Exponential backoff with jitter on Anthropic API calls | ✓ Real |
| S3 artifact upload | Stub — no upload occurs | ✗ Simulated |
| Control-M job chain export | Stub — no export occurs | ✗ Simulated |
| MWAA/EMR deployment staging | Stub — no staging occurs | ✗ Simulated |
| CI/CD YAML generation | Syntactically valid template; not executable or wired to any pipeline | ✗ Simulated |
| Governance hooks (PreToolUse/PostToolUse) | SSE log strings only; no real tool interception | ✗ Simulated |

---

## 2. Real vs Simulated

### Real (executes against actual data or code)

- **HQL file scanning and parsing** — `os.walk` over repo path, sqlfluff + regex DDL extraction
- **Complexity scoring** — weighted formula over table count, join count, UDF references, subquery depth, line count
- **HiveQL → PySpark conversion** — actual Claude Sonnet API call per file; output is model-generated code
- **MWAA DAG generation** — actual Claude Sonnet API call per pipeline during the conversion phase
- **PySpark syntax validation** — `ast.parse()` on every converted file; import list inspection; write-op presence check
- **hiveconf variable parity** — regex scan comparing `${hiveconf:...}` references in source HQL vs generated PySpark
- **Semantic comparison (8 dimensions)** — regex-based static analysis comparing source HQL and output PySpark for: table references, column references, aggregation functions, join types, filter conditions, partition expressions, runtime variables, UDF coverage
- **DAG structure parity** — task count in generated DAG compared against DML file count from assessment
- **Python AST artifact validation** — full AST walk on converted scripts to check for prohibited patterns and required structure
- **Smoke tests (4 of 7)** — syntax validation, DAG import check, artifact completeness, reconciliation threshold gate
- **Governance readiness score formula** — deterministic weighted calculation over real sub-scores
- **Manifest JSON files** — written to `output/<pipeline_id>/` on disk
- **Neo4j lineage graph** — writes Pipeline/Table/UDF nodes and READS/WRITES/DEPENDS_ON/USES_UDF edges after every assessment
- **Blast radius and wave ordering** — Cypher queries on the live graph; results feed both agent logic and frontend

### Simulated / Stubbed (no real execution)

- **Row count validation** — seeded fake numbers correlated to semantic similarity score; no Hive or Iceberg query is run
- **Checksum validation** — deterministic fake SHA-256 per partition; not derived from real partition data
- **SLA compliance** — always passes; no real elapsed-time measurement
- **Consumer replay** — seeded numbers; no downstream query is re-executed
- **Confidence score** — 80% real semantic analysis + 20% simulated runtime checks; the `data_provenance` field in every report flags which components are simulated
- **Smoke tests (3 of 7)** — Spark dry-run, data sampling, SLA timing are all predetermined pass/fail
- **S3 artifact upload** — `pass` stub in `deploy_subagent`; files remain on local disk only
- **Control-M job chain export** — `pass` stub; no file produced
- **MWAA/EMR deployment staging** — `pass` stub; no environment interaction
- **CI/CD YAML** — syntactically valid template generated as a string; not connected to any CI system
- **Governance hooks** — `PreToolUse`/`PostToolUse` labels appear in SSE event stream as log strings; there is no actual tool interception or approval gate enforced at runtime

---

## 3. Context Graph Usage

The Neo4j lineage graph is not only for visualization. It is read at multiple points in the pipeline to influence agent behavior.

### Built by

`assess_subagent` writes Pipeline, Table, and UDF nodes plus READS, WRITES, DEPENDS_ON, and USES_UDF relationships to Neo4j after every assessment run.

### Read by

| Where | Query | Effect |
|---|---|---|
| assess_subagent | blast_radius, wave | Included in assessment result; high blast_radius flagged in summary |
| convert_subagent | blast_radius | If ≥ 3, flags that UDF verification is needed in conversion result |
| reconcile_subagent (Python) | blast_radius | Mechanically raises confidence threshold: ≥3 → 0.80, ≥5 → 0.85 |
| deploy_subagent | upstream migration status | Checks that upstream pipelines are migrated as a governance condition |
| supervisor | blast_radius (from assessment summary) | If ≥ 3, applies stricter reconciliation threshold (0.80 instead of 0.75) |
| Frontend /context-graph | all pipelines | Renders interactive 4-tier DAG; blast radius counts shown on nodes |
| Frontend Run All | wave ordering | Groups pipelines by wave tier; each wave batch runs in parallel |

### Graph Schema

- **Nodes:** `Pipeline`, `Table`, `UDF`
- **Relationships:** `READS`, `WRITES`, `DEPENDS_ON`, `USES_UDF`

---

## 4. Agent Architecture

| Agent | Role | Tools | Skills |
|---|---|---|---|
| supervisor | Orchestrator — routes to subagents, makes go/no-go decisions based on assessment and reconciliation scores | run_assessment, run_conversion, run_reconciliation, run_deployment, query_graph, finish_migration | none |
| assess_subagent | Scans HQL repo, computes complexity, builds Neo4j lineage graph | 8 tools | repo_scan, lineage_extraction, complexity_classification |
| convert_subagent | HQL → PySpark + Airflow DAG generation, packages artifacts | 7 tools | hiveql_to_pyspark, dag_generation, artifact_packaging, graph_context |
| reconcile_subagent | Validates conversion correctness via semantic + runtime checks | 7 tools | semantic_comparison, runtime_validation, risk_assessment, graph_context |
| deploy_subagent | Artifact validation, smoke tests, governance scoring, manifest generation | 8 tools | artifact_validation, deployment_governance, cicd_packaging, graph_context |

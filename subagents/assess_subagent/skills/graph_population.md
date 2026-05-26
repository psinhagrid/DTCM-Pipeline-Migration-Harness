---
name: graph_population
description: >
  How to populate the full 5-tier Neo4j graph hierarchy from assess_subagent.
  Covers node types, relationships, ID conventions, intra-pipeline job dependency
  detection, and cross-pipeline linkage rules.
---

# Graph Population Skill

## Graph Schema

The context graph uses a 5-tier hierarchy:

```
Pipeline  (one per pipeline directory)
  └─[:CONTAINS]─▶ Workflow  (one per pipeline, named "{pipeline}_workflow")
                    └─[:HAS_JOB]─▶ Job  (one per .hql file)
                                    └─[:HAS_QUERY]─▶ Query  (one per DML statement)
                                                      ├─[:READS]─▶  Table
                                                      └─[:WRITES]─▶ Table
```

Additional cross-links:

| Relationship | From → To | When |
|---|---|---|
| `DEPENDS_ON` | Job → Job | JobB reads a table that JobA writes, within same pipeline |
| `DEPENDS_ON` | Pipeline → Pipeline | Cross-pipeline consumer chains (from lineage_extract_tool) |
| `READS` | Pipeline → Table | Aggregate — all tables this pipeline reads (backward-compat) |
| `WRITES` | Pipeline → Table | Aggregate — all tables this pipeline writes (backward-compat) |
| `USES_UDF` | Pipeline → UDF | Custom UDFs found in any HQL file |

---

## Node IDs and Properties

### Pipeline
- `name`: pipeline directory name (e.g. `bronze_ingestion`)
- `complexity`: SMALL | MEDIUM | LARGE | COMPLEX
- `estimated_effort`: "1 day" | "3 days" | "1 week" | "2+ weeks"
- `last_assessed`: datetime()

### Workflow
- `name`: `{pipeline}_workflow` (e.g. `bronze_ingestion_workflow`)
- `pipeline`: parent pipeline name
- `scheduler_type`: `oozie` (default for Hadoop pipelines)

### Job
- `job_id`: `{pipeline}.{hql_stem}` (e.g. `bronze_ingestion.ingest_currency_rates`)
- `job_name`: HQL filename without `.hql`
- `filename`: full HQL filename
- `pipeline`: parent pipeline name
- `job_type`: `HIVE`
- `execution_engine`: `MAPREDUCE`
- `migration_status`: `NOT_STARTED`

### Query
- `query_id`: `{job_id}.q{query_index}` (e.g. `bronze_ingestion.ingest_currency_rates.q0`)
- `query_type`: `INSERT_OVERWRITE` | `INSERT_INTO` | `CREATE_TABLE_AS` | `MERGE` | `SELECT`
- `query_text`: statement text (capped at 2 000 chars)
- `pipeline`, `job_id`: parent references
- `join_count`, `subquery_count`, `uses_window`, `uses_udf`: complexity signals

### Table
- `name`: fully-qualified table name as it appears in HQL (e.g. `bronze.currency_rates`)
- `type`: `source` (only read) or `sink` (written/created)

### UDF
- `name`: function name as detected in HQL

---

## How to Call neo4j_write_graph_tool

### Step 1 — Collect jobs from parse_hql_tool

After calling `parse_hql_tool` for each HQL file, build a `jobs` list:

```
jobs = []
for each HQL file:
    result = parse_hql_tool(filename)
    jobs.append({
        "filename":       result["file"],
        "read_tables":    result["read_tables"],    # list
        "written_tables": result["written_tables"], # list
        "created_tables": result["created_tables"], # list
        "queries":        result["queries"]         # list of per-statement dicts
    })
```

The `queries` field is produced automatically by `parse_hql_tool`. Each query dict contains:
- `query_index` — position in file (0-based)
- `query_type` — INSERT_OVERWRITE | INSERT_INTO | CREATE_TABLE_AS | MERGE | SELECT
- `query_text` — statement text (first 2 000 chars)
- `read_tables` — list of tables read in this statement
- `written_tables` — list of tables written in this statement
- `join_count`, `subquery_count`, `uses_window`, `uses_udf` — complexity signals

### Step 2 — Call the tool

```
neo4j_write_graph_tool(
    jobs=<jobs list from above>,
    upstream_tables=<lineage_extract_tool result["upstream"]>,
    output_tables=<lineage_extract_tool result["output_tables"]>,
    downstream=<lineage_extract_tool result["downstream"]>,
    udfs=<sorted list of all UDFs across all files>,
    complexity=<classify_complexity_tool result>,
    estimated_effort=<EFFORT map value>
)
```

---

## Intra-Pipeline Job Dependency Detection

The tool automatically detects when one job within the same pipeline must run before another.
Detection rule: **if JobB reads table T, and JobA writes table T (within the same pipeline), then (JobB)-[:DEPENDS_ON]->(JobA)**.

This is computed inside `neo4j_write_graph_tool` from the `written_tables` + `created_tables` fields of each job. You do not need to compute this manually — just pass accurate per-job table lists.

Example:
```
Pipeline: silver_orders

Job: enrich_orders_currency.hql
    written_tables: [silver.orders_enriched]

Job: compute_order_metrics.hql
    read_tables: [silver.orders_enriched]

Result: (compute_order_metrics)-[:DEPENDS_ON]->(enrich_orders_currency)
```

---

## Cross-Pipeline Dependency Detection

Cross-pipeline dependencies are detected by `lineage_extract_tool`, which scans sibling pipeline directories for any `.hql` file that reads this pipeline's output tables.

The result is the `downstream` list — pipeline names that consume this pipeline's output. Pass this list to `neo4j_write_graph_tool` and it will create:
```
(consumer_pipeline)-[:DEPENDS_ON]->(this_pipeline)
```

---

## What to Do if neo4j_write_graph_tool Returns an Error

If `status == "error"`, the error message will be in the `error` field:
- `"ServiceUnavailable"` — Neo4j is not running. Include `"graph_nodes": 0` in the result and note the failure. Do not halt — proceed to `finish_assessment_tool`.
- Other errors — include the error text in the assessment result. Flag it for human review.

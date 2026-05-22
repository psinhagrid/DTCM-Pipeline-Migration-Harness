# convert_agent — Design Decisions

Converts assessed HiveQL pipelines to PySpark artifacts and streams events to the supervisor.

---

## Structure

| File | Role |
|---|---|
| `convert_agent.py` | Async orchestration — phases, event streaming |
| `conversion_engine.py` | Selects active transformer via `USE_LLM` flag |
| `mock_transformer.py` | Regex + template HiveQL → PySpark (current) |
| `future_llm_transformer.py` | Placeholder for Claude SDK transformer |

## Transformer swap pattern

`conversion_engine.py` exposes a single `transform_file()` function.
Switching to LLM-based conversion requires only:
1. Setting `USE_LLM = True`
2. Implementing `LLMTransformer.transform()` in `future_llm_transformer.py`

Zero changes to `convert_agent.py` or the orchestrator.

## Mock transformer approach

Uses regex extraction + code templates. Handles:
- DDL-only files → Iceberg `CREATE TABLE` equivalent
- DML files → PySpark DataFrame chain (filter → join → groupBy → agg → writeTo)
- Aggregate function mapping (SUM → F.sum, COUNT → F.count, etc.)
- `${hiveconf:var}` → `spark.conf.get("var")`
- JOIN type preservation (INNER, LEFT)
- Partition preservation → `.partitionedBy()`

**Simplification:** output is structurally correct but not guaranteed to run without adjustment. Real conversion requires Claude SDK or validated transformation rules.

## DAG generation

Produces an Apache Airflow DAG with `SparkSubmitOperator` tasks.
**Simplification:** Control-M export is mocked (`controlm_mcp.export_job_chain`).
Production would parse real Control-M XML job definitions.

## Artifact storage

S3 writes are simulated. Events say `S3.put_object → s3://dtcm-artifacts/...`
**Simplification:** no real boto3 calls. See TODO.md.

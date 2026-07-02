---
name: artifact_validation
description: >
  Knows what constitutes a valid migration artifact, DAG structural requirements,
  and reconciliation gate thresholds. Select before validating any artifacts.
---

# Artifact Validation Skill

## File checks
- Each PySpark file must: exist, be non-empty, contain SparkSession setup, contain at least one writeTo() or append() call
- Files with only comments or imports are flagged as incomplete

## DAG check
- DAG file must: exist, be non-empty, contain at least one SparkSubmitOperator, have a valid dag_id
- Task IDs must match PySpark filenames (without .py)

## Reconciliation gate
- validation_status must be PASSED or PARTIAL
- If FAILED: deployment_ready = False — flag for halt
- confidence_score < 0.75: flag as condition

## deployment_ready flag
- True only if: all file checks PASSED + DAG check PASSED + reconciliation gate PASSED
- Any single failure sets deployment_ready = False

---

### Worked example — PASSING artifact

A valid `revenue_daily.py` must contain:
```python
from pyspark.sql import SparkSession  # ← spark_import ✓
from pyspark.sql import functions as F
spark = SparkSession.builder...getOrCreate()  # ← sparksession_setup ✓
...
result.writeTo(...).overwritePartitions()  # ← write_operation ✓
```
And must be ≥ 5 non-comment lines.

### Worked example — FAILING artifact

```python
# Generated file
from pyspark.sql import SparkSession
# TODO: implement conversion
```
Failures:
- `non_empty`: only 2 code lines — LLM likely failed silently
- `write_operation`: no `.writeTo()` or `.append()` → data never written
- `deployment_ready = False`

### DAG validation — what passes vs fails

PASSES:
```python
with DAG(dag_id="daily_revenue_agg_migration", ...) as dag:
    task1 = SparkSubmitOperator(task_id="load_transactions", ...)
    task2 = SparkSubmitOperator(task_id="revenue_daily", ...)
    task1 >> task2
```

FAILS (missing SparkSubmitOperator):
```python
with DAG(dag_id="daily_revenue_agg_migration") as dag:
    pass  # ← no operators
```

### Reconciliation gate examples

| confidence_score | validation_status | deployment_ready |
|---|---|---|
| 0.92 | PASSED | True |
| 0.80 | PARTIAL | True (≥ 0.75) |
| 0.72 | PARTIAL | False (< 0.75 — flag as condition) |
| 0.45 | FAILED | False (halt) |

### When deployment_ready = False

Do NOT halt automatically. Record it and:
- If reconciliation was FAILED: HALT
- If confidence just below threshold: add as a governance CONDITION, proceed to smoke tests
- Let governance scoring determine the final state

---

## CI/CD Stages & Smoke Tests

### CI/CD pipeline stages

1. **validate** — artifact syntax checks + reconciliation gate
2. **package** — bundle PySpark files + DAG into zip, SHA-256 sign
3. **deploy-nonprod** — register DAG in target scheduler non-prod environment
4. **smoke** — run smoke test suite (7 tests)
5. **governance** — compute readiness score + approval state

### Smoke test types

| Test | What it checks | Real or Simulated |
|---|---|---|
| `syntax_validation` | `ast.parse()` on each .py file | Real |
| `dag_import` | SparkSubmitOperator present + valid dag_id | Real |
| `artifact_completeness` | file count vs expected | Real |
| `reconciliation_threshold` | confidence_score ≥ 0.72 | Real |
| `spark_dry_run` | Spark config validation | **Simulated** |
| `data_sampling` | Sample partition row check | **Simulated** |
| `sla_timing` | Runtime vs SLA window | **Simulated** (always PASSES) |

### Manifest files written to disk

All written to `output/{pipeline}/`:
```
assessment.json       ← assess_agent result
conversion.json       ← convert_agent result
reconciliation.json   ← reconcile_agent result
deployment.json       ← this agent's result
cicd_pipeline.yaml    ← generated CI/CD definition
```
Write manifests even for CONDITIONAL or BLOCKED deployments.

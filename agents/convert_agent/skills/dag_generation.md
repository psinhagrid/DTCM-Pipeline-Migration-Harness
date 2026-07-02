---
name: dag_generation
description: >
  Knows Airflow DAG structure, SparkSubmitOperator configuration, and retry logic
  by complexity. Select this skill before generating the Airflow DAG.
---

# DAG Generation Skill

## DAG structure

Use the following defaults for every generated DAG:

- `dag_id`: `{pipeline}_migration`
- `schedule_interval`: `"0 2 * * *"`
- `start_date`: `datetime(2026, 1, 1)`
- `catchup`: `False`
- `tags`: `["migration"]`
- `owner`: `"data-engineering"`
- `email_on_failure`: `True`

## Operators

- Create one `SparkSubmitOperator` per converted PySpark file
- `task_id`: filename without the `.hql` extension, with hyphens and spaces replaced by underscores, lowercase
- `application`: path to the generated `.py` file — use the artifact output path from the conversion result
- `conn_id`: `"spark_default"`

## Retry logic by complexity

Set retries based on the complexity value from the assessment:

- `SMALL`: `retries=1`
- `MEDIUM`: `retries=2`
- `LARGE` or `COMPLEX`: `retries=3`
- `retry_delay`: `timedelta(minutes=5)` for all tasks

## Task dependencies

Chain tasks in the same order the HQL files appear in the assessment metadata:

```
task1 >> task2 >> task3 ...
```

### Full worked example

For pipeline `daily_revenue_agg` with 2 HQL files and complexity=MEDIUM:

```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator

default_args = {
    "owner":            "data-engineering",
    "depends_on_past":  False,
    "email_on_failure": True,
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
}

with DAG(
    dag_id="daily_revenue_agg_migration",
    default_args=default_args,
    schedule_interval="0 2 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["migration"],
) as dag:

    load_transactions = SparkSubmitOperator(
        task_id="load_transactions",
        application="output/daily_revenue_agg/load_transactions.py",
        conn_id="spark_default",
        retries=2,
        dag=dag,
    )

    revenue_daily = SparkSubmitOperator(
        task_id="revenue_daily",
        application="output/daily_revenue_agg/revenue_daily.py",
        conn_id="spark_default",
        retries=2,
        dag=dag,
    )

    load_transactions >> revenue_daily
```

### Filename → task_id rules

| HQL filename | task_id |
|---|---|
| `load_revenue.hql` | `load_revenue` |
| `compute-metrics.hql` | `compute_metrics` |
| `Update Daily.hql` | `update_daily` |

### What to watch for

- **Single file pipeline**: no `>>` dependency needed — just one operator.
- **Files with no clear order**: use alphabetical order as fallback; note it in a DAG comment.
- **Invalid Python identifiers as task_ids**: strip special characters, replace with underscore.

---

## Artifact Packaging

### File naming conventions

| Source | Output |
|---|---|
| `{name}.hql` | `{name}.py` |
| `{pipeline}` | `{pipeline}_dag.py` |

All filenames: lowercase, hyphens and spaces replaced with underscores.

### Required result fields

```json
{
  "pipeline":                "daily_revenue_agg",
  "dag_filename":            "daily_revenue_agg_dag.py",
  "dag_content":             "...",
  "transformations_applied": 12
}
```

### Order of operations

1. Convert each HQL file to PySpark
2. Generate the Airflow DAG for the pipeline

### Naming edge cases

| Original | Output |
|---|---|
| `Load Revenue.hql` | `load_revenue.py` |
| `compute-metrics.hql` | `compute_metrics.py` |
| `UPDATE_DAILY.hql` | `update_daily.py` |

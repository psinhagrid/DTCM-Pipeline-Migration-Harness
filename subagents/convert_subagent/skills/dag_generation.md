---
name: dag_generation
description: >
  Knows MWAA DAG structure, SparkSubmitOperator configuration, and retry logic
  by complexity. Select this skill before generating the Airflow DAG.
examples:
  - examples/dag_example.md
---

# DAG Generation Skill

## DAG structure

Use the following defaults for every generated DAG:

- `dag_id`: `{pipeline}_migration`
- `schedule_interval`: `"0 2 * * *"`
- `start_date`: `datetime(2026, 1, 1)`
- `catchup`: `False`
- `tags`: `["dtcm", "migration", "wave1"]`
- `owner`: `"dtcm-migration"`
- `email_on_failure`: `True`

## Operators

- Create one `SparkSubmitOperator` per converted PySpark file
- `task_id`: filename without the `.hql` extension, with hyphens replaced by underscores
- `application`: `s3://dtcm-artifacts/wave1/{pipeline}/{task_id}.py`
- `conn_id`: `"spark_default"`

## Retry logic by complexity

Set retries based on the complexity value from the assessment metadata:

- `SMALL`: `retries=1`
- `MEDIUM`: `retries=2`
- `LARGE` or `COMPLEX`: `retries=3`
- `retry_delay`: `timedelta(minutes=5)` for all tasks

## Task dependencies

Chain tasks in the same order the HQL files appear in the assessment metadata:

```
task1 >> task2 >> task3 ...
```

## Source

This DAG replaces the Control-M job chain that was exported via
`controlm_export_tool`. The linear dependency order is derived from that export.

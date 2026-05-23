# Example: DAG for Pipeline with 2 HQL Files

## Input

Pipeline: `daily_revenue_agg`
Complexity: `MEDIUM`
HQL files (in order): `load_raw.hql`, `transform.hql`

## Generated DAG (key lines)

```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator

with DAG(
    dag_id="daily_revenue_agg_migration",
    schedule_interval="0 2 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["dtcm", "migration", "wave1"],
    default_args={
        "owner": "dtcm-migration",
        "email_on_failure": True,
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
) as dag:

    load_raw = SparkSubmitOperator(
        task_id="load_raw",
        application="s3://dtcm-artifacts/wave1/daily_revenue_agg/load_raw.py",
        conn_id="spark_default",
    )

    transform = SparkSubmitOperator(
        task_id="transform",
        application="s3://dtcm-artifacts/wave1/daily_revenue_agg/transform.py",
        conn_id="spark_default",
    )

    load_raw >> transform
```

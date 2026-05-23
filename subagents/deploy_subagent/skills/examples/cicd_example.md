# Example: CI/CD Config — 2-File Pipeline

## Pipeline: `sales_summary`
Files: `load_sales.py`, `agg_summary.py`

## Generated cicd_pipeline.yaml

```yaml
pipeline: sales_summary
stages:
  - name: validate
    steps:
      - artifact_validation: [load_sales.py, agg_summary.py]
      - reconciliation_gate: check

  - name: package
    steps:
      - bundle: [load_sales.py, agg_summary.py, sales_summary_dag.py]
      - sign: sha256

  - name: deploy-nonprod
    steps:
      - mwaa_register: sales_summary_dag
      - emr_config_check: validate

  - name: smoke
    steps:
      - schema_validation: iceberg_sales_summary
      - row_count_spot: sample_partitions
      - dag_integrity: sales_summary_dag
      - spark_job_dry_run: [load_sales, agg_summary]
      - consumer_query: replay

  - name: governance
    steps:
      - readiness_score: compute
      - approval_state: evaluate
```

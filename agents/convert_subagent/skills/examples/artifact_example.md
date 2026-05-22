# Example: S3 Artifact Structure for Pipeline "daily_revenue_agg"

## After conversion the following artifacts are uploaded:

```
s3://dtcm-artifacts/wave1/daily_revenue_agg/
├── load_raw.py
├── transform.py
└── daily_revenue_agg_dag.py
```

## Corresponding result fields

```json
{
  "artifact_path": "s3://dtcm-artifacts/wave1/daily_revenue_agg/",
  "generated_files": [
    "load_raw.py",
    "transform.py",
    "daily_revenue_agg_dag.py"
  ]
}
```

## Notes

- `load_raw.py` and `transform.py` are the converted PySpark files
  (named after their `.hql` sources with the extension replaced)
- `daily_revenue_agg_dag.py` is the generated MWAA DAG
- `artifact_path` and `generated_files` are consumed by `reconcile_subagent`
  and `deploy_subagent` in later pipeline stages

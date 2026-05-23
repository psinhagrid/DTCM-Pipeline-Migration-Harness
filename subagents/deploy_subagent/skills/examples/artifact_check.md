# Example: Artifact Validation — 2-File Pipeline

## Input
Pipeline `sales_summary` has two PySpark files and one DAG file.

## File checks
| File | Exists | Non-empty | SparkSession | writeTo/append | Status |
|---|---|---|---|---|---|
| load_sales.py | yes | yes | yes | yes (writeTo) | PASSED |
| agg_summary.py | yes | yes | yes | yes (append) | PASSED |

## DAG check
- dag_id: `sales_summary_dag` — valid
- SparkSubmitOperator present: yes
- Task IDs: `load_sales`, `agg_summary` — match filenames
- Status: PASSED

## Reconciliation gate
- validation_status: PASSED
- confidence_score: 0.91 (>= 0.75)
- Status: PASSED

## Result
- deployment_ready = True

---
name: cicd_packaging
description: >
  Knows CI/CD pipeline stages, smoke test types, and manifest file format.
  Select before generating CI/CD config or writing manifests.
examples:
  - examples/cicd_example.md
---

# CI/CD Packaging Skill

## CI/CD stages
1. validate — artifact validation + reconciliation gate check
2. package — bundle PySpark files + DAG into zip, SHA-256 sign
3. deploy-nonprod — register DAG in MWAA non-prod, validate EMR config
4. smoke — run smoke test suite
5. governance — compute readiness score + approval state

## Smoke test types
- schema_validation: Iceberg table schema matches expected columns
- row_count_spot: spot-check row counts on sample partitions
- dag_integrity: DAG loads without import errors, no cycles
- spark_job_dry_run: dry-run SparkSubmitOperator (validate config only)
- consumer_query: replay 1–2 downstream consumer queries

## Manifest files written to disk
- assessment.json — assess_subagent result
- conversion.json — convert_subagent result
- reconciliation.json — reconcile_subagent result
- deployment.json — this agent's result
- cicd_pipeline.yaml — CI/CD definition
All written to output/{pipeline}/

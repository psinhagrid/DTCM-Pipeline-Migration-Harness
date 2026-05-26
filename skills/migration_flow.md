---
name: migration_flow
description: >
  Phase order and tool map for the Hive → MWAA + Iceberg migration.
  Defines structure only — read the phase-specific skills for domain knowledge.
---

# Migration Flow

## Phase order

```
ASSESS → CONVERT → RECONCILE → DEPLOY
```

## Tools per phase

**ASSESS**
`scan_repo`, `parse_hql`, `lineage_extract`, `classify_complexity`, `neo4j_write`, `query_graph`
Skills: `repo_scan`, `complexity_classification`, `graph_context`

**CONVERT**
`transform_hql`, `generate_dag`
Skills: `hiveql_to_pyspark`, `dag_generation`

**RECONCILE**
`validate_pyspark`, `analyze_file`, `workflow_parity`, `runtime_validation`, `compile_report`
Skills: `semantic_comparison`, `runtime_validation`, `risk_assessment`

**DEPLOY**
`validate_artifacts`, `generate_cicd`, `run_smoke_tests`, `compute_governance`, `write_manifests`
Skills: `artifact_validation`, `deployment_governance`

## Output

```python
FINAL = {
    "pipeline":       pipeline,
    "outcome":        "SUCCESS" | "PARTIAL" | "HALTED" | "FAILED",
    "summary":        "your reasoning — what you found and why you decided what you did",
    "assessment":     { ... },
    "conversion":     { ... },
    "reconciliation": { ... },
    "deployment":     { ... },
}
```

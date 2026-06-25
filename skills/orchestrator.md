---
name: orchestrator
description: >
  Phase order and tool map for the Hive → MWAA + Iceberg migration.
  Defines structure only — read the phase-specific skills for domain knowledge.
---

# Migration Flow

## Phase order

```
ASSESS → CONVERT → RECONCILE → DEPLOY
```

## What each phase does

**ASSESS** — understand the pipeline before touching it
Before using any tools, call read_skill('repo_scan'), read_skill('complexity_classification'), read_skill('graph_context').
Goal: discover HQL files, parse structure, extract lineage, score complexity, persist to graph, query blast radius and wave.
If parse_hql returns any syntax_errors on a file: call read_skill('hiveql_repair') to understand how to handle them — document each error clearly in your assessment output and note whether the file is safe to convert or should be flagged.

**CONVERT** — generate the target artifacts
Before using any tools, call read_skill('hiveql_to_pyspark'), read_skill('dag_generation').
Goal: convert each HQL file to PySpark, generate the Airflow DAG.
After each transform_hql call, run validate_pyspark on the result. If validate_pyspark returns errors: call read_skill('pyspark_repair') then retry transform_hql once with the error details added to the metadata so Claude can self-correct. If the retry still has errors, record the file as PARTIAL and continue — do not halt the whole pipeline for one file.

**RECONCILE** — validate the conversion is correct
Before using any tools, call read_skill('semantic_comparison'), read_skill('runtime_validation'), read_skill('risk_assessment').
Goal: validate PySpark syntax, compare semantic structure against HQL, check runtime parity, compile confidence report.

**DEPLOY** — govern and package for release
Before using any tools, call read_skill('artifact_validation'), read_skill('deployment_governance').
Goal: validate all artifacts, run smoke tests, compute governance decision, generate CI/CD, write manifests.

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

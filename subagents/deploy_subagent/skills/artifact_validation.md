---
name: artifact_validation
description: >
  Knows what constitutes a valid migration artifact, DAG structural requirements,
  and reconciliation gate thresholds. Select before validating any artifacts.
examples:
  - examples/artifact_check.md
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

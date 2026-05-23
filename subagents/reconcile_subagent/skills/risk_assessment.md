---
name: risk_assessment
description: >
  Knows how to calculate migration risk levels and generate recommendations
  from reconciliation check results. Select this skill before compiling the report.
examples:
  - examples/risk_report.md
---

# Risk Assessment Skill

## Severity mapping

Each check maps to a severity: CRITICAL / HIGH / MEDIUM / LOW

- **CRITICAL**: table_parity FAILED, aggregation_parity FAILED
- **HIGH**: column_parity FAILED, join_parity FAILED, row_count FAILED
- **MEDIUM**: filter_parity FAILED, partition_parity FAILED, checksum WARNING
- **LOW**: runtime_var_parity WARNING, sla_compliance WARNING

## Migration risk levels

- **CRITICAL**: any CRITICAL severity check failed
- **HIGH**: any HIGH severity check failed
- **MODERATE**: MEDIUM severity failures only
- **LOW**: only LOW severity issues or all passed

## Confidence thresholds (for supervisor)

- >= 0.85: proceed to deployment
- 0.75–0.84: proceed with conditions
- 0.60–0.74: retry conversion recommended
- < 0.60: halt — do not deploy

## Recommendation values

`PROCEED` / `PROCEED_WITH_CONDITIONS` / `RETRY_CONVERSION` / `HALT`

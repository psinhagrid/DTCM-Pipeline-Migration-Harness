---
name: risk_assessment
description: >
  Knows how to calculate migration risk levels and generate recommendations
  from reconciliation check results. Select this skill before compiling the report.
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

### Worked example — full risk derivation

Checks from reconciliation:
```
table_parity:       PASSED
column_parity:      FAILED   ← HIGH severity
aggregation_parity: PASSED
join_parity:        WARNING
filter_parity:      FAILED   ← MEDIUM severity
partition_parity:   PASSED
runtime_var_parity: WARNING  ← LOW severity
row_count:          PASSED
checksum:           WARNING  ← MEDIUM severity
```

Severity map:
```
CRITICAL: []
HIGH:     [column_parity]
MEDIUM:   [filter_parity, checksum]
LOW:      [runtime_var_parity]
```

Migration risk: **HIGH** (any HIGH severity failure)
Confidence score: 0.71 (column_parity FAILED pulls it down)

Decision at blast_radius=1 (standard threshold 0.75):
→ confidence 0.71 < 0.75 threshold → retry conversion

Decision at blast_radius=0 (terminal sink, standard threshold):
→ confidence 0.71 < 0.75 threshold → retry conversion

Recommendation: **RETRY_CONVERSION**
Reasoning: "column_parity FAILED — converted code is missing columns present in source. Confidence 0.71 below threshold. Retrying conversion before considering deployment."

### Decision tree: recommendation

```
Any CRITICAL check FAILED?
  YES → HALT
  NO ↓

confidence < 0.50?
  YES → HALT
  NO ↓

migration_risk = CRITICAL?
  YES → HALT
  NO ↓

confidence < blast_radius_threshold?
  YES + first attempt → RETRY_CONVERSION
  YES + already retried → HALT
  NO ↓

validation_status = PARTIAL AND confidence ≥ threshold AND risk ≠ CRITICAL?
  YES → PROCEED_WITH_CONDITIONS
  NO ↓

validation_status = PASSED?
  YES → PROCEED
```

### What to write in the reasoning field

Always include:
1. What the worst check was and its score
2. The confidence score and the threshold that applies (with blast_radius context)
3. The recommendation and why

Example:
> "Highest severity issue: column_parity FAILED (score=0.42) — 3 source columns not found in converted output. Confidence=0.71, blast_radius=3 raises threshold to 0.80. 0.71 < 0.80. Recommending RETRY_CONVERSION."

---
name: runtime_validation
description: >
  Knows how to interpret runtime validation results: row count, checksum, SLA
  compliance, and consumer replay checks. Select this skill before running runtime validation.
examples:
  - examples/runtime_checks.md
---

# Runtime Validation Skill

## Row count check

- Compares COUNT(*) between source Hive and target Iceberg
- `variance_pct = abs(source - target) / source * 100`
- PASSED: variance_pct <= 0.1%
- WARNING: variance_pct 0.1–1.0%
- FAILED: variance_pct > 1.0%

## Checksum check

- SHA-256 checksums of partition data
- PASSED: checksums match exactly
- WARNING: minor mismatch (likely sort order)
- FAILED: checksums differ significantly

## SLA check

- Compares expected vs actual runtime
- PASSED: runtime within SLA window
- WARNING: 10–20% over SLA
- FAILED: >20% over SLA

## Consumer replay check

- Replays downstream consumer queries against Iceberg target
- Measures speedup factor (Iceberg vs Hive)
- PASSED: results match + speedup > 1.0x
- WARNING: results match but speedup < 1.0x
- FAILED: query results differ

## Confidence score

- Weighted combination: `semantic_similarity * 0.6 + runtime_pass_rate * 0.4`
- Used by supervisor for go/no-go decision

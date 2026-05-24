---
name: runtime_validation
description: >
  Knows how to interpret runtime validation results: row count, checksum, SLA
  compliance, and consumer replay checks. Select this skill before running runtime validation.
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

### Important context

**These checks are currently SIMULATED.** Row counts, checksums, SLA timings, and consumer replay results are generated deterministically from pipeline name and semantic similarity — not from real Hive/Iceberg execution. The `data_provenance` field in every reconciliation report documents this explicitly.

Confidence score formula: `semantic_score * 0.80 + runtime_score * 0.20`

Runtime checks contribute only 20% of confidence. The semantic analysis (8 dimensions) drives 80%.

### Worked example — row count

Source cluster: 2,000,000 rows
Target cluster: 1,999,800 rows
Variance: (2,000,000 - 1,999,800) / 2,000,000 * 100 = **0.01%**
Result: **PASSED** (≤ 0.1% threshold)

---

Source: 2,000,000 rows
Target: 1,980,000 rows
Variance: 1.0%
Result: **WARNING** (between 0.1% and 1.0%)

---

Source: 2,000,000 rows
Target: 1,900,000 rows
Variance: 5.0%
Result: **FAILED** (> 1.0%)

### Worked example — confidence calculation

Semantic similarity (8 dimensions avg): 0.88
Runtime pass rate (4 checks): 3 PASSED, 1 WARNING → score = 0.875

Confidence = 0.88 × 0.80 + 0.875 × 0.20 = **0.704 + 0.175 = 0.879**

At blast_radius=2: threshold is 0.75 → **PROCEED** (0.879 ≥ 0.75)
At blast_radius=4: threshold is 0.80 → **PROCEED** (0.879 ≥ 0.80)

### What to do when a check is unavailable

If a runtime check cannot run (connection error, cluster unavailable):
- Record status as `SKIPPED` with reason
- Do NOT fail the reconciliation
- Note in reasoning: "row_count_check skipped — cluster unavailable"
- The confidence score treats SKIPPED as neutral (1.0 contribution)

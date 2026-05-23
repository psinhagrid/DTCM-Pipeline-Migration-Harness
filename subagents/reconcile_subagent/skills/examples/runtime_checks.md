# Example: Runtime Checks

## Pipeline: `customer_orders_daily`

### Row count check

| Metric | Value |
|---|---|
| source_rows (Hive) | 2,000,000 |
| target_rows (Iceberg) | 2,001,000 |
| variance_pct | 0.05% |
| status | **PASSED** (threshold <= 0.1%) |

### Checksum check

| Metric | Value |
|---|---|
| source_checksum | `a3f9c12d...` |
| target_checksum | `a3f9c12d...` |
| match | exact |
| status | **PASSED** |

### SLA check

| Metric | Value |
|---|---|
| expected_runtime | 45 min |
| actual_runtime | 41 min |
| within_sla | yes |
| status | **PASSED** |

### Consumer replay check

| Metric | Value |
|---|---|
| consumers_replayed | 3 |
| results_match | yes |
| speedup_factor | 2.3x |
| status | **PASSED** (results match + speedup > 1.0x) |

### Summary

- runtime_pass_rate: 1.0 (4/4 checks passed)
- semantic_similarity: 0.97 (from file comparison)
- **confidence_score: 0.97 * 0.6 + 1.0 * 0.4 = 0.982**

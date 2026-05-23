# Example: Risk Report

## Pipeline: `product_inventory_snapshot`

### Check results

| Check | Score | Status | Severity |
|---|---|---|---|
| table_parity | 1.0 | PASSED | — |
| column_parity | 0.78 | WARNING | MEDIUM |
| aggregation_parity | 0.91 | PASSED | — |
| join_parity | 0.88 | PASSED | — |
| group_by_parity | 1.0 | PASSED | — |
| filter_parity | 1.0 | PASSED | — |
| partition_parity | 1.0 | PASSED | — |
| runtime_var_parity | 1.0 | PASSED | — |
| row_count | 1.0 | PASSED | — |
| checksum | 1.0 | PASSED | — |
| sla_compliance | 1.0 | PASSED | — |
| consumer_replay | 1.0 | PASSED | — |

### Issue

- `[product_inventory_snapshot.py] column_parity: 2 aliased columns missing in DataFrame output (inventory_delta, reorder_flag)`

### Risk assessment

- Highest severity: MEDIUM (column_parity WARNING only)
- **migration_risk: MODERATE**
- semantic_similarity: (1.0+0.78+0.91+0.88+1.0+1.0+1.0+1.0) / 8 = 0.946
- runtime_pass_rate: 1.0
- **confidence_score: 0.946 * 0.6 + 1.0 * 0.4 = 0.968**

### Recommendation

- confidence_score 0.968 >= 0.85 → threshold says PROCEED
- However, migration_risk is MODERATE due to column_parity WARNING
- **recommendation: PROCEED_WITH_CONDITIONS**
- **reasoning**: All runtime checks passed and confidence is high, but two output columns (inventory_delta, reorder_flag) should be verified manually before deployment to production consumers.

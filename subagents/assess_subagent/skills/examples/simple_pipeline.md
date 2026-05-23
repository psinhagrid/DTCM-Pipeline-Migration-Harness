# Example: Simple Pipeline

**Task context:** Assess a single-file pipeline with one source table and one output table.

**Skill used:** repo_scan

**Input:**
```
pipelines/daily_revenue_agg/
  load_revenue.hql
```

**Expected output:**
- 1 HQL file, ~10 total files
- 2 tables (1 upstream read, 1 output write)
- 0 UDFs, no window functions, no cross-db joins
- Complexity: SMALL

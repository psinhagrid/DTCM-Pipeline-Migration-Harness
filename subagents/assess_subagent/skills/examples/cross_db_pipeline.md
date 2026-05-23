# Example: Cross-Database Pipeline

**Task context:** Pipeline that joins tables across multiple Hive databases.

**Skill used:** lineage_extraction

**Input:** HQL containing `FROM analytics.events JOIN warehouse.dim_user`

**Expected output:**
- Cross-db references: [analytics, warehouse]
- Upstream: analytics.events, warehouse.dim_user
- Complexity score boosted by +5 per cross-db join

# Example: File Comparison

## Source: `daily_sales_agg.hql`

```sql
INSERT OVERWRITE TABLE warehouse.daily_sales_agg
PARTITION (dt)
SELECT
    region,
    product_id,
    SUM(revenue)   AS total_revenue,
    COUNT(*)       AS order_count,
    dt
FROM raw.sales_events
WHERE status = 'COMPLETED'
GROUP BY region, product_id, dt;
```

## Converted: `daily_sales_agg.py`

```python
from pyspark.sql import functions as F

df = spark.table("raw.sales_events") \
    .filter(F.col("status") == "COMPLETED") \
    .groupBy("region", "product_id", "dt") \
    .agg(
        F.sum("revenue").alias("total_revenue"),
        F.count("*").alias("order_count"),
    )

df.write.format("iceberg") \
    .mode("overwrite") \
    .partitionBy("dt") \
    .saveAsTable("warehouse.daily_sales_agg")
```

## Dimension results

| Dimension | Score | Status | Notes |
|---|---|---|---|
| table_parity | 1.0 | PASSED | `raw.sales_events` matches `spark.table("raw.sales_events")` |
| column_parity | 1.0 | PASSED | region, product_id, dt, total_revenue, order_count all present |
| aggregation_parity | 1.0 | PASSED | SUM→F.sum, COUNT→F.count |
| join_parity | — | SKIPPED | No joins in source |
| group_by_parity | 1.0 | PASSED | region, product_id, dt match .groupBy() |
| filter_parity | 1.0 | PASSED | WHERE status='COMPLETED' matches .filter() |
| partition_parity | 1.0 | PASSED | PARTITION (dt) matches .partitionBy("dt") |
| runtime_var_parity | — | SKIPPED | No hiveconf variables used |

**Overall similarity: 1.0 — all applicable dimensions PASSED**

**Issues: none**

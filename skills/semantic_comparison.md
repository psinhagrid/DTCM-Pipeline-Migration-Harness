---
name: semantic_comparison
description: >
  Knows how to validate and compare HiveQL source against PySpark converted code.
  Covers static PySpark validation (syntax, imports, write ops) and 8-dimension
  semantic comparison. Select this skill before analyzing any file pair.
---

# Semantic Comparison Skill

## Step 1 — PySpark static validation (before semantic comparison)

Validate each generated PySpark file before semantic comparison. Check 8 things:

1. **syntax** — `ast.parse()` passes — if FAILED, halt this file immediately
2. **spark_import** — `from pyspark.sql import SparkSession` present
3. **functions_import** — `from pyspark.sql import functions as F` present (WARNING if missing)
4. **sparksession_setup** — `SparkSession.builder` initialised
5. **write_operation** — `.writeTo()` or `.append()` present (skip for DDL-only files)
6. **hiveconf_parity** — every `${hiveconf:var}` in source has `spark.conf.get("var")` in output
7. **udf_presence** — UDFs detected in source appear in the PySpark output (WARNING if missing)
8. **non_empty** — at least 5 code lines generated (catches silent LLM failures)

If `valid=False` (any error): do not run semantic comparison on this file — report errors and move on.

## Step 2 — The 8 semantic dimensions

For each file pair (source `.hql` + converted `.py`), comparison covers:

1. **table_parity** — source tables in FROM/JOIN match `spark.table()` calls
2. **column_parity** — SELECT columns match DataFrame column references
3. **aggregation_parity** — SUM/COUNT/AVG etc match `F.sum()`/`F.count()`/`F.avg()`
4. **join_parity** — JOIN type and condition match `.join(other, condition, type)`
5. **group_by_parity** — GROUP BY columns match `.groupBy()` columns
6. **filter_parity** — WHERE conditions match `.filter()` conditions
7. **partition_parity** — PARTITIONED BY matches `.partitionedBy()` or `.partitionBy()`
8. **runtime_var_parity** — `${hiveconf:var}` matches `spark.conf.get("var")`

## Similarity scoring

- Each dimension gets a score 0.0–1.0 and a status: PASSED / WARNING / FAILED / SKIPPED
- Overall similarity = average across all non-skipped dimensions
- PASSED: score >= 0.85
- WARNING: score 0.70–0.84
- FAILED: score < 0.70

## Skip conditions

- DDL-only files (CREATE TABLE, no SELECT/INSERT) — skip all dimensions
- Empty source or target — skip with warning

## Issues

- Any dimension scoring FAILED generates an issue string: `"[filename] dimension: detail"`
- Issues are critical if they are `table_parity` or `aggregation_parity` failures

### Worked example — PASSED comparison

HiveQL source:
```sql
INSERT OVERWRITE TABLE revenue_daily PARTITION (dt='${hiveconf:run_date}')
SELECT t.merchant_id, SUM(t.amount) AS total
FROM raw.transactions t
JOIN dim.merchants m ON t.merchant_id = m.id
WHERE t.status = 'SETTLED'
GROUP BY t.merchant_id;
```

PySpark output:
```python
run_date = spark.conf.get("run_date")
transactions = spark.table("raw.transactions").alias("t")
merchants    = spark.table("dim.merchants").alias("m")
result = (transactions.join(merchants, transactions.merchant_id == merchants.id, "inner")
    .filter(transactions.status == "SETTLED")
    .groupBy("t.merchant_id")
    .agg(F.sum("t.amount").alias("total"))
)
result.writeTo("glue_catalog.dtcm.revenue_daily").partitionedBy("dt").overwritePartitions()
```

Dimension results:
```
table_parity:       PASSED  (raw.transactions, dim.merchants both present)
column_parity:      PASSED  (merchant_id, total both present)
aggregation_parity: PASSED  (SUM → F.sum with alias)
join_parity:        PASSED  (INNER JOIN preserved)
group_by_parity:    PASSED  (merchant_id in groupBy)
filter_parity:      PASSED  (status='SETTLED' → status=="SETTLED")
partition_parity:   PASSED  (dt in partitionedBy)
runtime_var_parity: PASSED  (run_date = spark.conf.get("run_date"))
overall_similarity: 1.00
```

### Worked example — FAILED comparison

HiveQL has: `WHERE t.status = 'SETTLED' AND t.region = 'EU'`
PySpark has: `.filter(transactions.status == "SETTLED")`  ← missing region filter

Result:
```
filter_parity: FAILED (score=0.50)
issue: "[revenue_daily.hql] filter_parity: WHERE has 2 conditions, only 1 mapped — missing: region='EU'"
```

This is a MEDIUM severity issue. Does NOT trigger halt but must be reported.

### Issue string format

Always format issues as:
```
"[{filename}] {dimension}: {description}"
```

Examples:
- `"[load_revenue.hql] filter_parity: WHERE clause has 3 conditions, only 2 found in .filter()"`
- `"[compute_metrics.hql] table_parity: source references dim.products but spark.table('dim.products') not found"`
- `"[settlement.hql] runtime_var_parity: ${hiveconf:risk_threshold} not mapped to spark.conf.get()"`

### Static validation — what each check catches

| Check | Common failure cause |
|---|---|
| syntax | LLM generated invalid Python (missing colon, mismatched brackets) |
| spark_import | LLM forgot SparkSession import |
| write_operation | LLM used `df.save()` or similar non-standard API |
| hiveconf_parity | LLM hardcoded value instead of `spark.conf.get()` |
| udf_presence | LLM forgot to call a UDF that the source uses |
| non_empty | LLM returned empty or comment-only file |

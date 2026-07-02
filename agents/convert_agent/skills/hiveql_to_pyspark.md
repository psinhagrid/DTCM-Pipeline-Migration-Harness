---
name: hiveql_to_pyspark
description: >
  Knows HiveQL→PySpark syntax translation rules. Select this skill before
  converting any HiveQL file to understand the mapping rules.
---

# HiveQL to PySpark Skill

## SparkSession setup

Always include at the top of every generated file:

```python
from pyspark.sql import SparkSession, functions as F

spark = SparkSession.builder.enableHiveSupport().getOrCreate()
```

If a specific catalog is configured in the environment (e.g. Glue, Iceberg, Unity Catalog), add the appropriate config:
```python
spark = SparkSession.builder.config("spark.sql.catalog.spark_catalog", "<catalog_impl>").enableHiveSupport().getOrCreate()
```

## File header comment

Always include the following comment block at the very top (before the imports):

```python
# Source: {filename} → {filename}.py
# Pipeline: {pipeline}
```

## Syntax mappings

- `INSERT OVERWRITE TABLE target PARTITION(dt) SELECT ... FROM source`
  → `spark.table("source")`, apply transforms, then
  `.writeTo("target").partitionedBy("dt").overwritePartitions()`

- `INSERT INTO TABLE target`
  → same pattern but use `.append()` instead of `.overwritePartitions()`

- `FROM` / `JOIN`
  → `spark.table()` for each relation; joins via `.join(other, condition, "inner"/"left")`

- `WHERE`
  → `.filter()`

- `GROUP BY`
  → `.groupBy().agg()` using `F.sum()`, `F.count()`, `F.avg()`, `F.min()`, `F.max()`
  with `.alias()` for named output columns

- `OVER` clause (window functions)
  → `pyspark.sql.window.Window`; import `Window` from `pyspark.sql.window`

- `${hiveconf:varname}`
  → `varname = spark.conf.get("varname")`; place the assignment before the transform code

- UDFs
  → assume imported from a `udfs` module; keep as direct function calls

- `CREATE TABLE`
  → `spark.sql("CREATE TABLE IF NOT EXISTS target_table USING iceberg PARTITIONED BY (dt) TBLPROPERTIES ('write.format.default'='parquet')")`

## Output rules

- Return ONLY valid Python code. No markdown. No backticks. No explanation.

### Worked examples

**Example 1 — INSERT OVERWRITE with partition and GROUP BY**

HiveQL source:
```sql
INSERT OVERWRITE TABLE revenue_daily
PARTITION (dt = '${hiveconf:run_date}', channel = '${hiveconf:channel}')
SELECT t.merchant_id, SUM(t.amount) AS total_revenue, COUNT(*) AS txn_count
FROM raw.transactions t
JOIN dim.merchants m ON t.merchant_id = m.id
WHERE t.dt = '${hiveconf:run_date}' AND t.status = 'SETTLED'
GROUP BY t.merchant_id;
```

PySpark output:
```python
# Source: revenue_daily.hql → revenue_daily.py
# Pipeline: daily_revenue_agg

from pyspark.sql import SparkSession, functions as F

spark = SparkSession.builder.enableHiveSupport().getOrCreate()

run_date = spark.conf.get("run_date")
channel  = spark.conf.get("channel")

transactions = spark.table("raw.transactions")
merchants    = spark.table("dim.merchants")

result = (
    transactions.alias("t")
    .join(merchants.alias("m"), transactions.merchant_id == merchants.id, "inner")
    .filter((transactions.dt == run_date) & (transactions.status == "SETTLED"))
    .groupBy("t.merchant_id")
    .agg(
        F.sum("t.amount").alias("total_revenue"),
        F.count("*").alias("txn_count"),
    )
)

result.writeTo("revenue_daily") \
    .partitionedBy("dt", "channel") \
    .overwritePartitions()
```

---

**Example 2 — Window function (OVER clause)**

HiveQL source:
```sql
SELECT merchant_id, txn_amount,
    RANK() OVER (PARTITION BY merchant_id ORDER BY txn_amount DESC) AS txn_rank
FROM raw.transactions WHERE dt = '${hiveconf:run_date}';
```

PySpark output:
```python
from pyspark.sql import SparkSession, functions as F
from pyspark.sql.window import Window

spark = SparkSession.builder.enableHiveSupport().getOrCreate()

run_date = spark.conf.get("run_date")

window_spec = Window.partitionBy("merchant_id").orderBy(F.col("txn_amount").desc())

result = (
    spark.table("raw.transactions")
    .filter(F.col("dt") == run_date)
    .withColumn("txn_rank", F.rank().over(window_spec))
    .select("merchant_id", "txn_amount", "txn_rank")
)
```

---

**Example 3 — CREATE TABLE**

HiveQL source:
```sql
CREATE EXTERNAL TABLE IF NOT EXISTS raw.events (
    event_id STRING, user_id STRING, event_type STRING, dt STRING
)
PARTITIONED BY (dt STRING)
STORED AS ORC;
```

PySpark output:
```python
spark.sql("""
    CREATE TABLE IF NOT EXISTS raw.events (
        event_id STRING,
        user_id  STRING,
        event_type STRING
    )
    USING iceberg
    PARTITIONED BY (dt)
    TBLPROPERTIES ('write.format.default' = 'parquet')
""")
```

---

**Example 4 — UDF call**

HiveQL source:
```sql
SELECT udf_currency_normalize(txn_currency, 'USD') AS amount_usd FROM raw.transactions;
```

PySpark output:
```python
# Assumes udf_currency_normalize is registered in the udfs module
from udfs import udf_currency_normalize

result = spark.table("raw.transactions").withColumn(
    "amount_usd", udf_currency_normalize(F.col("txn_currency"), F.lit("USD"))
)
```

### Edge cases and what to avoid

- **Multiple hiveconf vars**: declare ALL of them at the top before any transform code — never inline them.
- **Self-join**: use `.alias()` on both sides — `df.alias("a").join(df.alias("b"), ...)`
- **UNION ALL**: use `df1.union(df2)` — column order must match exactly.
- **Subqueries (SELECT inside FROM)**: convert to a named DataFrame before joining. Avoid nesting.
- **If unsure about a mapping**: generate a code comment `# TODO: verify this mapping` rather than guessing. Never hallucinate Spark APIs.

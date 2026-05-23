---
name: semantic_comparison
description: >
  Knows how to validate and compare HiveQL source against PySpark converted code.
  Covers static PySpark validation (syntax, imports, write ops) and 8-dimension
  semantic comparison. Select this skill before analyzing any file pair.
examples:
  - examples/file_comparison.md
---

# Semantic Comparison Skill

## Step 1 — PySpark static validation (before semantic comparison)

Run `validate_pyspark_tool` on each `.py` file first. Check 8 things:

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

---
name: repo_scan
description: >
  Discovers and parses all source files in a HiveQL pipeline directory.
  Select this skill when the task requires reading and understanding the raw
  contents of a pipeline repo — file inventory, DDL structure, UDFs, syntax errors.
examples:
  - examples/simple_pipeline.md
---

# Repo Scan Skill

## File discovery

1. Enumerate all `.hql` files in the pipeline directory — these are the primary source files.
2. Enumerate `.xml` and `.properties` files — these are pipeline configs.
3. Count total files via recursive glob for full footprint visibility.

## HQL parsing rules

- Use sqlfluff (`dialect=hive`) for syntax validation. Collect all violations as syntax errors.
- Extract table references with targeted regex — faster and more predictable than full AST for the patterns we care about:
  - `FROM` / `JOIN` clauses → read tables
  - `INSERT INTO` / `INSERT OVERWRITE` → written tables
  - `CREATE [EXTERNAL] TABLE` → created tables
- Extract column names from `SELECT ... FROM` blocks; strip `*` and aliases.
- Extract partition keys from `PARTITIONED BY (...)` clauses.
- Flag any function call not in the Hive built-in list and not a SQL keyword as a custom UDF.
- Flag `OVER (` as a window function signal.
- Count `(SELECT` occurrences as subquery depth.
- Flag `PARTITION (...${hiveconf:...})` as dynamic partition usage.

---
name: repo_scan
description: >
  Discovers and parses all source files in a HiveQL pipeline directory.
  Select this skill when the task requires reading and understanding the raw
  contents of a pipeline repo — file inventory, DDL structure, UDFs, syntax errors.
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

### Worked example — what parse_hql_tool returns

For a file containing this HQL:
```sql
INSERT OVERWRITE TABLE raw.revenue PARTITION (dt = '${hiveconf:run_date}')
SELECT t.merchant_id, SUM(t.amount) AS total
FROM raw.transactions t
JOIN dim.merchants m ON t.merchant_id = m.id
WHERE t.status = 'SETTLED'
GROUP BY t.merchant_id;
```

parse_hql_tool returns:
```
read_tables:    {raw.transactions, dim.merchants}
written_tables: {raw.revenue}
created_tables: {}
columns:        [merchant_id, total]
partition_keys: [dt]
udfs:           []
has_window:     false
subqueries:     0
has_dyn_part:   false  (hiveconf used but inside PARTITION clause = dynamic)
cross_db_joins: []
syntax_errors:  []
```

### Edge cases

- **DDL-only files** (`CREATE TABLE`, no `SELECT`/`INSERT`): read_tables and written_tables will be empty. This is expected — note the file is DDL-only and skip semantic comparison later.
- **Empty .hql file**: parse returns empty sets with no errors. Flag as suspicious — a 0-line pipeline file is usually wrong.
- **Syntax errors**: sqlfluff violations are collected but do not stop parsing. The regex extraction still runs. Report `syntax_errors` count and halt the assessment.
- **Multiple statements in one file**: regex scans the entire file, so all FROM/JOIN/INSERT targets across all statements are collected into the same sets.
- **Backtick-quoted tables**: `` `db`.`table` `` — the regex handles backticks. The extracted name will be `db.table` (backticks stripped).

### UDF detection example

Given this function call in SQL:
```sql
SELECT udf_currency_normalize(t.txn_currency, 'USD') AS norm_currency
```

- `udf_currency_normalize` is extracted as a function call
- It is NOT in the `HIVE_BUILTINS` set
- It is NOT a SQL keyword
- It is NOT a table name
- → Flagged as a UDF

But `SUM(amount)` → `sum` is in `HIVE_BUILTINS` → not flagged.

### What to do after scanning

- 0 HQL files found → HALT: nothing to assess
- syntax_errors > 0 → HALT: source is broken
- All files are DDL-only (no INSERT/SELECT) → proceed but note reconciliation will have nothing to compare
- UDFs detected → flag count, will affect complexity score

---

## Lineage Extraction

### Upstream / downstream rules

- **Upstream tables**: tables that appear in `FROM` or `JOIN` clauses but are never `CREATE`d or written to by this pipeline — external feeds this pipeline cannot modify.
- **Output tables**: `written_tables ∪ created_tables` — what downstream consumers depend on.
- **Downstream consumers**: sibling pipeline directories that reference any output table in their own `.hql` files via `FROM` or `JOIN`.

### Worked example

Pipeline `daily_revenue_agg` parses these tables:
```
all_reads:   {raw.transactions, dim.merchants, dim.products}
all_creates: {revenue_daily}
all_writes:  {revenue_daily, settlement_staging}
```
Derived lineage:
```
upstream      = reads - creates - writes
             = {raw.transactions, dim.merchants, dim.products}

output_tables = creates ∪ writes
             = {revenue_daily, settlement_staging}

downstream    = [executive_reporting, merchant_settlement]
```

### Cross-database detection

SQL: `JOIN compliance.blacklist_merchants bl ON t.merchant_id = bl.id`
- `compliance.blacklist_merchants` → `compliance` is a different schema/cluster
- Added to `cross_db_joins` and carries +5 complexity weight
- Signals inter-cluster dependency that may not exist in the Spark target environment

### What to watch for

- **Table in both reads and writes**: self-join or update pattern — unusual for Hive, flag it
- **Empty upstream**: root pipeline, wave 0, safe to migrate independently
- **Empty downstream**: terminal sink, nothing breaks downstream if this fails
- **`downstream` count ≥ 3**: high blast radius — note prominently in the result

### After lineage is extracted

Pass to `neo4j_write_graph_tool`:
- `upstream_tables` ← lineage.upstream
- `output_tables` ← lineage.output_tables
- `downstream` ← lineage.downstream
- `udfs` ← aggregated from all parse_hql_tool results
- `complexity` + `estimated_effort` ← from classify_complexity_tool

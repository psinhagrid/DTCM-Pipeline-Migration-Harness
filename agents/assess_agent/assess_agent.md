# assess_agent — Design Decisions

Scans a local HiveQL pipeline directory, parses SQL, scores complexity,
and returns structured metadata to the supervisor.

---

## File source
Files are read from `pipelines/<pipeline_name>/` on local disk.
**Simplification:** production would read from S3 (`s3://dtcm-source/hive/pipelines/`).

## SQL parsing
Uses **sqlfluff** (`dialect=hive`) for syntax validation.
Extraction of tables, columns, UDFs, and complexity signals is done with
targeted regex — faster and more predictable than full AST traversal for
the patterns we care about.

## Complexity scoring

| Signal | Points |
|---|---|
| Per table referenced | +1 |
| Per UDF | +2 |
| Window function (`OVER`) | +3 |
| Cross-database join (`db.table`) | +5 |
| Dynamic partition | +2 |
| Per subquery | +2 |
| Per downstream consumer | +1 |

| Score | Classification |
|---|---|
| 0 – 5 | SMALL |
| 6 – 12 | MEDIUM |
| 13 – 20 | LARGE |
| 21+ | COMPLEX |

**Simplification:** thresholds are assumed — not yet verified with the migration team.

## UDF detection
Any function call not in the built-in Hive function list is flagged as a UDF.
**Simplification:** the built-in list is a hand-curated set in code.
Production would query the Hive metastore or a central UDF registry.

## Downstream consumer discovery
Greps sibling directories inside `pipelines/` for references to output table names.
**Simplification:** production would query Neo4j lineage graph or a data catalog API.

## Effort estimate
Derived mechanically from complexity classification. Not ML-based.

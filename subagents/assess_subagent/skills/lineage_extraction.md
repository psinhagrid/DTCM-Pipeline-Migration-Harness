---
name: lineage_extraction
description: >
  Maps upstream dependencies and downstream consumers for a pipeline from its
  parsed table sets. Select this skill when the task requires understanding
  what a pipeline depends on and what depends on it.
examples:
  - examples/cross_db_pipeline.md
---

# Lineage Extraction Skill

## Upstream / downstream rules

- **Upstream tables**: tables that appear in `FROM` or `JOIN` clauses but are never `CREATE`d or written to by this pipeline. These are external feeds — dependencies this pipeline cannot modify.
- **Output tables**: written tables ∪ created tables. These are what downstream consumers depend on.
- **Downstream consumers**: sibling pipeline directories that reference any of this pipeline's output table names in their own `.hql` files.

## Cross-database detection

- Any `FROM db.table` or `JOIN db.table` reference (dot-notation) is flagged as a cross-database join.
- These indicate inter-cluster dependencies that may not exist in the target environment and carry the highest complexity weight (+5 per join).
- Collect the `db` prefix as the cross-cluster reference to report.

## Lineage graph

- Nodes: all unique tables + downstream consumer pipeline names.
- Edges: upstream→pipeline dependencies + pipeline→downstream consumer links + intra-pipeline table-to-table flow.
- Graph is persisted to Neo4j via `neo4j_write_graph_tool` (currently stubbed — TODO: implement MCP call).

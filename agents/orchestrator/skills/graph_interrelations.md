---
name: graph_interrelations
description: >
  Explains how to query the pipeline lineage graph and interpret interdependencies.
  Covers blast radius, wave ordering, upstream prerequisites, and how graph data
  should influence decisions at each phase. Select this skill before calling query_graph.
---

# Graph Interrelations Skill

## What the graph stores

The lineage graph holds one node per pipeline and one node per table, connected by directed edges:

```
[upstream tables] → [this pipeline] → [output tables] → [downstream pipelines]
```

Every pipeline that has been assessed is in the graph. Pipelines not yet assessed may appear as partial nodes (referenced by others but not yet fully written).

---

## query_graph — three query types

Call `query_graph(pipeline, query)` where `query` is one of:

### `"blast_radius"`
Returns all pipelines that would break if this one fails — transitively, not just direct consumers.

```
query_graph("orders_enrichment", "blast_radius")
→ {
    "blast_radius": ["daily_revenue_summary", "finance_report", "exec_dashboard"],
    "count": 3
  }
```

**Meaning:** 3 downstream pipelines depend on the output of `orders_enrichment`. If it fails or produces wrong data, all 3 are affected. Use this to calibrate how careful to be.

---

### `"wave"`
Returns the migration wave number for this pipeline.

```
query_graph("orders_enrichment", "wave")
→ { "migration_wave": 2 }
```

**Meaning:**
- Wave 1 — no upstream dependencies, safe to migrate first
- Wave 2 — depends on wave-1 pipelines being migrated first
- Wave N — must wait for all wave N-1 pipelines to complete

Use this to understand ordering. Do not deploy a wave-2 pipeline before its wave-1 dependencies are migrated.

---

### `"summary"`
Returns the full stored profile for a pipeline.

```
query_graph("orders_enrichment", "summary")
→ {
    "complexity":        "MEDIUM",
    "estimated_effort":  "3 days",
    "last_assessed":     "2026-06-15T10:22:00",
    "reads":             ["bronze.orders", "bronze.customers"],
    "writes":            ["silver.orders_enriched"],
    "udfs":              ["mask_pii"],
    "depends_on":        ["bronze_ingest"],
    "consumed_by":       ["daily_revenue_summary", "finance_report"]
  }
```

**Use this when you need to check:**
- Whether an upstream pipeline has already been assessed
- What tables a pipeline reads/writes (cross-check with your current assessment)
- Whether UDFs have been flagged in a related pipeline

---

## When each agent should query the graph

| Agent | When to query | Query type | Purpose |
|---|---|---|---|
| ASSESS | After complexity classification | `blast_radius`, `wave` | Include in result; calibrate severity |
| CONVERT | Before transforming UDF-heavy files | `blast_radius` | Flag high-risk UDFs more prominently if blast_radius ≥ 3 |
| RECONCILE | Before compiling report | `blast_radius` | Select the right confidence threshold |
| DEPLOY | Before governance decision | `summary` for each upstream | Check upstream migration status |
| ORCHESTRATOR | Before sequencing phases | `wave`, `blast_radius` | Decide pipeline order and risk level |

The graph is read-only for all agents except ASSESS (which writes to it via `neo4j_write`).

---

## How blast radius changes your decisions

| blast_radius count | What it means | How to adjust |
|---|---|---|
| 0 | Terminal sink — nothing depends on this | Standard thresholds throughout |
| 1–2 | Low impact | Standard thresholds; note count in result |
| 3–4 | Moderate impact | Raise reconciliation threshold to 0.80; flag UDFs |
| 5+ | High impact | Raise threshold to 0.85; require all smoke tests PASSED; add governance condition |

**Example reasoning to write:**
> "blast_radius=4 — 4 downstream pipelines depend on this output. Raising reconciliation threshold to 0.80. Confidence 0.77 is below this threshold. Retrying conversion before proceeding."

---

## Reading upstream interdependency

Query `"summary"` for each pipeline that is listed as an upstream dependency to check if it has already been migrated.

```python
upstream_summary = query_graph("finance_report", "summary")
depends_on = upstream_summary.get("depends_on", [])

for dep_pipeline in depends_on:
    dep_info = query_graph(dep_pipeline, "summary")
    # check dep_info for last_assessed, complexity, etc.
    # if no record → not yet assessed → flag as condition, not a halt
```

**Decision rule:**
- Upstream not yet assessed → add governance condition: *"Upstream pipeline X not yet assessed — verify source table availability before production promotion"*
- Upstream assessed but not deployed → same condition
- This is always a CONDITION, never a HALT — non-production deployment may still proceed

---

## Wave ordering — worked example

Three pipelines:
```
bronze_ingest    → wave 1 (no dependencies)
orders_enriched  → wave 2 (depends on bronze_ingest)
finance_report   → wave 3 (depends on orders_enriched)
```

If you are migrating `finance_report`:
1. `query_graph("finance_report", "wave")` → wave 3
2. `query_graph("finance_report", "summary")` → `depends_on: ["orders_enriched"]`
3. `query_graph("orders_enriched", "summary")` → check `last_assessed`
4. If `orders_enriched` has not been migrated → add condition

Never block migration entirely based on wave — the human decides. Surface the information clearly.

---

## What to do when the graph is unavailable

| Situation | graph returns | Action |
|---|---|---|
| Graph built, data present | Full result | Use for all decisions |
| Graph empty (not yet built) | `[]` or `{}` | Proceed with standard thresholds; note "graph not yet built" |
| Pipeline not in graph | Empty / null | Treat as blast_radius=0; wave=1 |
| Connection error | `{"error": "..."}` | Proceed with standard thresholds; log warning |

**Never halt because the graph is unavailable.** Always fall back gracefully. Log a warning and use defaults.

---

## What to include in your result

When you use graph data in a decision, record it explicitly:

```json
{
  "blast_radius_count": 3,
  "migration_wave":     2,
  "threshold_applied":  0.80,
  "upstream_status":    "orders_enriched: assessed, bronze_ingest: assessed"
}
```

This makes the reasoning auditable — the human reviewing the result can see exactly what graph data influenced the decision.

---
name: graph_context
description: >
  Knows when and how every subagent should use Neo4j lineage graph data.
  Covers blast radius threshold calibration, wave ordering, UDF risk,
  and upstream migration prerequisite checking.
examples: []
---

# Graph Context Skill

## What the graph tells you

| Query | Returns | Use when |
|---|---|---|
| `blast_radius` | Pipelines that break if this one fails (transitive) | Deciding how strict to be |
| `wave` | Migration wave (0 = no deps, migrate first) | Ordering and result metadata |
| `upstream` | Pipelines this one directly depends on | Checking prerequisites before deployment |
| `downstream` | Pipelines that directly consume this one's output | UDF risk, consumer count |

Empty result means the graph has not been built yet — proceed with file-based data and do not halt.

---

## Blast radius → threshold calibration

Used by: **reconcile_subagent**, **supervisor**

| blast_radius count | Reconciliation threshold | Governance readiness |
|---|---|---|
| 0 — terminal sink | Standard (proceed ≥ 0.75) | Standard (70%) |
| 1–2 consumers | Standard (proceed ≥ 0.75) | Slight raise (75%) |
| 3–4 consumers | Raised (proceed ≥ 0.80) | High (80%) |
| 5+ consumers | High (proceed ≥ 0.85, halt < 0.60) | High (80%) + all smoke tests PASSED |

**Example reasoning:**
> confidence=0.72, blast_radius=4 → threshold is 0.80 → 0.72 < 0.80 → retry conversion.
> "Blast radius of 4 raises threshold to 0.80. Retrying conversion before proceeding."

---

## Wave context

Used by: **assess_subagent**, **convert_subagent**

- `wave = 0` — root pipeline, no upstream dependencies, safe to migrate first
- `wave = N` — must wait for wave N-1 pipelines to complete migration
- Include `migration_wave` in the result for supervisor wave ordering

---

## UDF handling with high blast radius

Used by: **convert_subagent**

- `blast_radius ≥ 3` AND UDFs detected → flag in result that UDF mappings need human verification before production promotion
- `downstream` query returns many consumers → auto-conversion of UDFs is high-risk; note explicitly

---

## Upstream prerequisite check

Used by: **deploy_subagent**

1. Call `query_graph_tool(pipeline, "upstream")` before governance approval
2. For each upstream pipeline returned: check if it has been migrated
3. If any upstream NOT yet migrated → add governance condition:
   *"Upstream pipeline X not yet migrated — verify table availability before prod promotion"*
4. This is a CONDITION, not a HALT — non-prod deployment may still proceed

---

## Result fields to include when graph data is available

| Subagent | Fields to add |
|---|---|
| assess | `migration_wave`, `blast_radius` |
| convert | `migration_wave`, `blast_radius_count` |
| reconcile | `blast_radius_count`, `threshold_applied` |
| deploy | `upstream_migration_status`, `blast_radius_count` |

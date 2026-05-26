---
name: graph_context
description: >
  Knows when and how every subagent should use Neo4j lineage graph data.
  Covers blast radius threshold calibration, wave ordering, UDF risk,
  and upstream migration prerequisite checking.
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

1. Query the graph for upstream dependencies before governance approval
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

---

## Worked examples

### reconcile_subagent — borderline confidence decision

Scenario: `fraud_risk_scoring` pipeline, reconciliation report returns `confidence=0.72`.

**Step 1 — Is confidence borderline?** Yes — 0.72 is between 0.50 and 0.85.

**Step 2 — Query graph:**
```
blast_radius query for "fraud_risk_scoring"
→ {"blast_radius": ["executive_reporting", "merchant_settlement", "ops_dashboard"]}
  count = 3
```

**Step 3 — Look up threshold:** blast_radius=3 → raised threshold is **0.80**

**Step 4 — Compare:** 0.72 < 0.80 → **retry conversion**

Reasoning to write:
> "blast_radius=3 raises reconciliation threshold to 0.80. Confidence 0.72 is below this raised threshold. Retrying conversion to improve accuracy before proceeding."

---

### deploy_subagent — upstream prerequisite check

Scenario: deploying `executive_reporting`.

**Step 1 — Query upstream:**
```
upstream query for "executive_reporting"
→ {"upstream": ["daily_revenue_agg", "merchant_settlement", "fraud_risk_scoring", "user_activity_enrichment"]}
```

**Step 2 — Check which are migrated** (compare against pipelines in the context that have completed deployment):
- `daily_revenue_agg` → deployed ✓
- `merchant_settlement` → deployed ✓
- `user_activity_enrichment` → deployed ✓
- `fraud_risk_scoring` → **not yet deployed** ✗

**Step 3 — Add governance condition** (NOT a halt):
```
"Upstream pipeline fraud_risk_scoring not yet migrated —
 verify risk.fraud_flags table availability in Iceberg before prod promotion"
```

Set in governance result:
```json
"conditions": [
  "Upstream pipeline fraud_risk_scoring not yet migrated — verify table availability before prod promotion"
]
```

---

## Neo4j availability — what to do in each case

| Situation | Graph query returns | Action |
|---|---|---|
| Neo4j running, graph built | Full data | Use for threshold decisions and upstream checks |
| Neo4j running, graph empty (not built) | `[]` or `{}` | Proceed with standard thresholds. Note: "graph not yet built" |
| Neo4j not running / unreachable | `{"error": "..."}` | Proceed with standard thresholds. Log warning. |
| Pipeline not in graph | Empty list | Treat as blast_radius=0. No known consumers. |

**Never halt because the graph is unavailable.** Always fall back to standard thresholds gracefully.

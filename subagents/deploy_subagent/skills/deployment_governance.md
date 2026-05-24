---
name: deployment_governance
description: >
  Knows readiness score thresholds, governance states, and what conditions
  trigger each state. Select before computing governance approval.
---

# Deployment Governance Skill

## Readiness score
Weighted combination of:
- Artifact validation: 30% weight
- Smoke test score: 40% weight
- Reconciliation confidence: 30% weight
Score range: 0–100

## Governance states
| State | When | Meaning |
|---|---|---|
| APPROVED | readiness >= 85, all smoke passed, reconciliation PASSED | Full production promotion |
| APPROVED_NON_PROD | readiness 70–84, smoke mostly passed | Non-prod only |
| CONDITIONAL | readiness 55–69, OR open conditions | Deploy with listed conditions |
| BLOCKED | readiness < 55, OR critical failures | Do not deploy |

## Conditions (examples)
- "Reconciliation confidence below 85% — monitor row counts post-deploy"
- "Smoke test {name} WARNING — verify manually before prod promotion"
- "UDFs present — validate custom function output in non-prod"

---

### Worked example — score calculation

Pipeline `daily_revenue_agg`, complexity=MEDIUM:

```
Artifact validation:
  - revenue_daily.py: PASSED         (syntax + SparkSession + writeTo all present)
  - daily_revenue_agg_dag.py: PASSED
  - Reconciliation confidence: 0.82  (≥ 0.75 threshold)
  → artifact_score = 100%  → 30 pts

Smoke tests (5 tests):
  - syntax_validation:    PASSED
  - dag_import:           PASSED
  - artifact_completeness: PASSED
  - spark_dry_run:        PASSED  (simulated)
  - sla_timing:           PASSED  (simulated)
  → smoke_score = 100% → 40 pts

Reconciliation confidence: 0.82
  → 0.82 / 0.90 * 25 = 22.8 pts (capped at 25)

No failed reconciliation checks: +10 pts

Total: 30 + 40 + 22.8 + 10 = 102.8 → capped at 100
Readiness score: 88
Governance state: APPROVED
```

### Worked example — CONDITIONAL state

Readiness score: 72
Smoke tests: 4/5 passed (consumer_query WARNING)
Reconciliation: PARTIAL, confidence=0.79

Governance state: **APPROVED_NON_PROD**
Conditions:
- "consumer_query smoke test returned WARNING — verify downstream query results in non-prod before prod promotion"
- "Reconciliation PARTIAL — reconciliation confidence 79% below recommended 85% for full production approval"

### Building the conditions list

Add a condition for each of the following when present:
- Any smoke test with status WARNING or FAILED
- Reconciliation confidence < 0.85
- UDFs present in the pipeline (always add: "Validate UDF output in non-prod")
- Upstream pipelines not yet migrated (from graph query)
- blast_radius ≥ 3 (add: "High blast radius — monitor downstream pipelines post-deploy")

### What to write in governance result

```json
{
  "state":      "APPROVED_NON_PROD",
  "label":      "Approved for non-production — 2 open conditions",
  "readiness_score": 72,
  "conditions": [
    "consumer_query smoke test WARNING — verify before prod",
    "Reconciliation confidence 79% — below 85% recommended for full approval"
  ]
}
```

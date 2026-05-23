---
name: deployment_governance
description: >
  Knows readiness score thresholds, governance states, and what conditions
  trigger each state. Select before computing governance approval.
examples:
  - examples/governance_decision.md
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

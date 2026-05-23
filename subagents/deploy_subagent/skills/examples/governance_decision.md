# Example: Governance Decision — readiness 78

## Inputs
- Artifact validation: all checks PASSED → component score 100
- Smoke tests: 4/5 passed, `consumer_query` WARNING → component score 80
- Reconciliation confidence: 0.82 (82%) → component score 82

## Readiness score calculation
- Artifact: 100 × 0.30 = 30.0
- Smoke: 80 × 0.40 = 32.0
- Reconciliation: 82 × 0.30 = 24.6
- Total readiness_score = 86.6 → rounded to 78 after smoke penalty

## Governance state
- readiness 70–84: APPROVED_NON_PROD

## Conditions
- "Smoke test consumer_query WARNING — verify manually before prod promotion"

## Result
- governance: APPROVED_NON_PROD
- conditions: 1 open condition
- Deployment proceeds to non-prod only

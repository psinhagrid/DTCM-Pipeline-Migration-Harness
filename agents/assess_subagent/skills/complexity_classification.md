---
name: complexity_classification
description: >
  Scores and classifies Hive pipeline migration complexity, assigns a migration
  wave, and identifies risk patterns. Select this skill when the task requires
  deciding how hard a pipeline is to migrate and what risks to flag.
examples:
  - examples/complex_pipeline.md
---

# Complexity Classification Skill

## Scoring heuristics

Each signal contributes to the raw complexity score:

| Signal | Weight |
|---|---|
| Per table referenced | +1 |
| Per custom UDF | +2 |
| Window function (`OVER` clause) | +3 |
| Cross-database join (`db.table`) | +5 |
| Dynamic partition | +2 |
| Per subquery (`SELECT` inside parens) | +2 |
| Per downstream consumer | +1 |

## Migration wave logic

Map raw score to complexity band and estimated effort:

| Score | Band    | Estimated Effort |
|-------|---------|------------------|
| 0–5   | SMALL   | 1 day            |
| 6–12  | MEDIUM  | 3 days           |
| 13–20 | LARGE   | 1 week           |
| 21+   | COMPLEX | 2+ weeks         |

SMALL and MEDIUM proceed with full automation.
LARGE proceeds with caution — flag for human review.
COMPLEX requires manual migration planning — do not auto-convert.

## Risk patterns

- **UDFs > 3**: LLM conversion may produce imperfect UDF handling — verify output.
- **Cross-database joins**: signals cross-cluster dependencies that may not exist in the target environment.
- **Window functions**: require Spark window API — verify OVER clause semantics match.
- **Dynamic partitions**: `${hiveconf:}` variables have no direct Spark equivalent — needs manual variable mapping.
- **Syntax errors in source**: source files are broken — halt migration, cannot convert safely.
- **Tables > 15**: exceeds safe auto-migration threshold — escalate to human review.

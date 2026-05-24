---
name: complexity_classification
description: >
  Scores and classifies Hive pipeline migration complexity, assigns a migration
  wave, and identifies risk patterns. Select this skill when the task requires
  deciding how hard a pipeline is to migrate and what risks to flag.
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

### Worked example — score calculation

Pipeline with:
- 6 tables referenced → 6 × 1 = **6**
- 3 UDFs → 3 × 2 = **6**
- 1 window function → 1 × 3 = **3**
- 0 cross-database joins → 0
- 1 dynamic partition → 1 × 2 = **2**
- 2 subqueries → 2 × 2 = **4**
- 2 downstream consumers → 2 × 1 = **2**
- **Total: 23 → COMPLEX**

Estimated effort: 2+ weeks. Do not auto-convert — escalate to manual planning.

### Band examples (what each level looks like in practice)

**SMALL (0–5)**: Single INSERT OVERWRITE, 2–3 tables, no UDFs, no joins beyond a simple lookup.
Example: daily file ingestion from external source to a raw table.

**MEDIUM (6–12)**: 4–6 tables, 1–2 UDFs, standard GROUP BY aggregations, maybe one window function.
Example: daily revenue aggregation joining transactions with merchant profiles.

**LARGE (13–20)**: 7–10 tables, 3+ UDFs, multiple window functions, cross-database joins, dynamic partitions.
Example: settlement pipeline with chargebacks, multiple schemas, complex window ranking.

**COMPLEX (21+)**: High table count, many UDFs, cross-cluster joins, deep subqueries, many downstream consumers.
Example: executive reporting that reads from 5+ upstream pipeline outputs across multiple schemas.

### What to do at each band

- **SMALL / MEDIUM**: proceed confidently with automation. Flag any UDFs for review but don't block.
- **LARGE**: flag in result (`complexity_flag: true`), note specific risk patterns. Supervisor decides — usually proceeds.
- **COMPLEX**: include explicit note in result. Supervisor will HALT and escalate.
- **Any band with syntax_errors > 0**: HALT regardless of complexity score.
- **Tables > 15**: HALT regardless of complexity band.

Write both the computed score AND the band in the result — the supervisor reads both.

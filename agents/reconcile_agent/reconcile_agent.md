# reconcile_agent — Design Decisions

Validates that converted PySpark faithfully represents the source HiveQL.
Runs after convert_agent, receives both assessment and conversion metadata.

---

## Module structure

| File | What | Real or Simulated |
|---|---|---|
| `static_analyzer.py` | Parse HiveQL + PySpark, compare structure | **REAL** |
| `validators.py` | Row count, checksum, SLA, consumer replay | **SIMULATED** (deterministic) |
| `schemas.py` | TypedDict event + report schemas | — |
| `reconcile_agent.py` | Async orchestration + SSE streaming | — |

---

## Static analysis (real)

Uses regex to extract structural elements from both source and target:
- Table references (FROM/JOIN vs spark.table)
- Aggregation functions (SUM/COUNT/AVG vs F.sum/count/avg)
- JOIN count and types
- GROUP BY columns
- WHERE/filter presence

Compares element by element, scores each dimension 0.0 → 1.0.
Overall similarity = mean of per-dimension scores.

**Limitation:** Column-level comparison is not implemented — column names
in PySpark aliases often differ from HiveQL aliases after LLM conversion.
See TODO.md.

---

## Simulated validators (deterministic)

All runtime checks use `hashlib.md5(pipeline + salt)` as seed, so the
same pipeline always produces the same metrics across runs.

| Check | Simulated metric |
|---|---|
| Row count | Scaled by complexity (SMALL=500K–5M, MEDIUM=5M–20M, LARGE=20M–80M) |
| Checksum | SHA-256 of pipeline name, source == target |
| SLA | Runtime = 55–90% of SLA window, always within limit |
| Consumer replay | N queries (3–20 by complexity), target always faster |

**Why deterministic?** Demo stability — rerunning the same pipeline
produces identical reports, which is expected in a POC.

---

## Confidence score

Weighted blend of static (real) and runtime (simulated):
- Static analysis: 50%
- Row count: 20%
- Checksum: 15%
- SLA: 8%
- Consumer replay: 7%

---

## TODO

- Column-level alias comparison (static_analyzer)
- Real row count via Spark `COUNT(*)` or Hive metastore stats
- Real checksum via partition-level hash computation
- Real consumer query replay framework
- FAILED status handling in orchestrator (currently always PASSED)

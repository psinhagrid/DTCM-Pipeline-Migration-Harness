# deploy_agent — Design Decisions

Runs after reconcile_agent. Validates artifacts, generates CI/CD config,
simulates deployment, runs smoke tests, and produces governance approval.

## Module structure

| File | What | Real/Simulated |
|---|---|---|
| `artifact_validator.py` | Python AST syntax check, DAG structure, reconciliation gate | **REAL** |
| `smoke_tests.py` | Syntax, DAG import, artifact completeness, reconciliation threshold | **REAL** |
| `smoke_tests.py` | Spark dry-run, data sampling, SLA timing | **SIMULATED** |
| `cicd_generator.py` | Deployment YAML + pipeline config generation | **REAL** (content) |
| `governance.py` | Approval state from real scores | **REAL** |
| `manifest_builder.py` | Writes JSON files to `output/{pipeline}/` | **REAL** |
| `deploy_agent.py` | Async orchestration + SSE streaming | — |

## Real checks

- `ast.parse()` on every PySpark file — catches Llama conversion syntax errors
- Airflow DAG structural validation (imports, DAG block, task definitions)
- Reconciliation confidence threshold gate (≥ 0.72)
- Artifact completeness check
- Readiness score formula (weighted: artifacts 45% + smoke 20% + reconciliation 25% + checks 10%)

## Simulated (deterministic)

- MWAA DAG registration event
- EMR Serverless job config validation
- S3 artifact upload events
- Spark dry-run, data sampling, SLA timing — seeded from pipeline name

## Output files (written to disk)

`output/{pipeline}/`:
- `deployment_manifest.json` — artifact inventory + CI/CD config
- `deployment_report.json` — governance result + readiness score
- `smoke_test_report.json` — all smoke test results
- `rollout_summary.json` — next steps + planned capabilities

## Governance states

| State | Condition |
|---|---|
| `APPROVED` | readiness ≥ 88%, risk LOW/MINIMAL, 0 smoke failures |
| `APPROVED_NON_PROD` | readiness ≥ 72%, risk not CRITICAL, artifacts valid |
| `CONDITIONAL` | readiness ≥ 55%, issues present |
| `BLOCKED` | confidence < threshold or critical failures |

## TODO

- Real MWAA DAG registration via boto3
- Real EMR Serverless job submission
- OpenLineage deployment hooks
- GitOps integration (Argo CD)
- Canary deployment support
- Automated rollback on smoke test failure

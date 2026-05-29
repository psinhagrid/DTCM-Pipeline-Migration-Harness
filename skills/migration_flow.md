---
name: migration_flow
description: >
  10-step end-to-end migration flow for Hive → MWAA + Iceberg.
  Defines phase order, agent actions, human gates, and exit criteria.
---

# Migration Flow

## Pipeline Steps

**1. Intake → 2. Discovery → 3. Architecture → 4. Build & PR → 5. Deploy (Non-Prod) → 6. Validation & Parallel Run → 7. Security Gate → 8. Cutover & Rollback → 9. Handover → 10. Pipeline Accepted**

---

**1. Intake**
Auto-populate pipeline metadata from context graph. Confirm scope and assign to wave/POD.
*Exit: Scope Lock*

**2. Discovery**
Auto-ingest repos, schemas, DAGs, policies, and logs; generate discovery report. SME reviews findings and confirms business logic.
*Exit: Discovery Accepted*

**3. Architecture**
Agent recommends target architecture based on pipeline profile and skill library. Architect reviews and approves target pattern; handles exceptions.
*Exit: Architecture Approved*

**4. Build & PR**
Agent generates code conversion artifacts using CodeAct and creates PR. Engineers review PR and handle edge cases (UDFs, complex joins).
*Exit: PR Approved*

**5. Deploy (Non-Prod)**
Agent generates Terraform and triggers CI/CD via Oneflow. DevOps validates infrastructure; release engineering review.
*Exit: Non-Prod Deployed*

**6. Validation & Parallel Run**
Agent generates and executes reconciliation plan; monitors parallel run (2–4 weeks minimum). SME reviews evidence bundle and resolves discrepancies.
*Exit: Validation Passed*

**7. Security Gate**
Agent generates security assessment package and maps Ranger to Lake Formation. Visa Cybersecurity reviews and approves.
*Exit: Security Cleared*

**8. Cutover & Rollback**
Agent generates rollback/canary plan with checklist. Release engineering and SME approve cutover.
*Exit: Production Live*

**9. Handover**
Agent generates handover package (docs, runbook, architecture summary). Structured KT sessions with Visa pipeline owners.
*Exit: Handover Accepted*

**10. Pipeline Accepted**
Final evidence bundle committed to context graph. ATC (Application Technology Contact) formal sign-off.
*Exit: Milestone Complete*

## Output

```python
FINAL = {
    "pipeline":       pipeline,
    "outcome":        "SUCCESS" | "PARTIAL" | "HALTED" | "FAILED",
    "summary":        "reasoning — what you found and why",
    "assessment":     { ... },
    "conversion":     { ... },
    "reconciliation": { ... },
    "deployment":     { ... },
}
```

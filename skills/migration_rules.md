# Migration Rules

Read this skill FIRST — before writing any plan, before calling any tool, and
before replanning after a repair or retry. All rules here are authoritative.

---

## Part 1 — Migration Flow

### Step order (mandatory, sequential)

```
assess_pipeline → convert_pipeline → reconcile_pipeline → deploy_pipeline (if allowed)
```

- Never skip a step or call a later step without the previous one completing.
- Always pass the full returned dict from each step as input to the next.
- Never call steps in parallel.

### Step 1 — assess_pipeline

- Always call this first, no exceptions.
- If `syntax_errors > 0` in the result:
  1. Call `repair_pipeline(target='hql')`
  2. Call `assess_pipeline` again (re-assess after repair)
  3. Proceed to convert only after re-assessment returns `syntax_errors == 0`

### Step 2 — convert_pipeline

- Requires the full `assessment` dict from Step 1.
- If `status == 'ERROR'` in the result, set `final_status = 'ERROR'` and call FINAL.

### Step 3 — reconcile_pipeline

- Requires both `assessment` and `conversion` dicts.
- After it returns, apply Part 2 rules before doing anything else.

### Step 4 — deploy_pipeline

- Only call if Part 2 rules permit it.
- If the result contains key `'error'`, include it in FINAL as `deployment` and do not retry.

---

## Part 2 — Deployment Decision Rules

Apply these rules **in priority order** after reconcile_pipeline returns.
Stop at the first rule that matches. Do not invent additional cases.

### RULE 1 — Hard Gate: FAILED status (highest priority)

**Condition:** `validation_status == 'FAILED'`

**Action:**
- Do NOT call `deploy_pipeline`. No exceptions, regardless of `confidence_score`.
- Set `final_status = 'FAILED'`.
- Call `FINAL` immediately.

### RULE 2 — Hard Gate: Low confidence

**Condition:** `confidence_score < 0.60`

**Action:**
- Do NOT call `deploy_pipeline`.
- Set `final_status = 'FAILED'`.
- Call `FINAL` immediately.

### RULE 3 — Full approval

**Condition:** `confidence_score >= 0.80` AND `validation_status == 'PASSED'`

**Action:**
- Call `deploy_pipeline`.
- Set `final_status = 'PASSED'`.

### RULE 4 — Conditional approval

**Condition:** `confidence_score` in `[0.60, 0.80)` OR `validation_status == 'WARNING'`

**Action:**
- Call `deploy_pipeline` with caution.
- Set `final_status = 'WARNING'`.

### Decision table

| validation_status | confidence_score | Deploy? | final_status |
|-------------------|-----------------|---------|--------------|
| FAILED            | any             | NO      | FAILED       |
| any               | < 0.60          | NO      | FAILED       |
| PASSED            | >= 0.80         | YES     | PASSED       |
| WARNING           | >= 0.60         | YES     | WARNING      |
| PASSED            | [0.60, 0.80)    | YES     | WARNING      |

---

## Part 3 — Replanning Rules

### After repair_pipeline(target='hql')

1. Call `assess_pipeline` again — never skip the re-assessment.
2. If re-assessment still shows `syntax_errors > 0`, set `final_status = 'ERROR'` and call FINAL.
3. If clean, proceed to `convert_pipeline` with the new assessment.

### After repair_pipeline(target='pyspark')

- Only valid when RULE 2 triggered (confidence_score < 0.60).
- After repair, do a FULL RESTART: call assess_pipeline → convert_pipeline → reconcile_pipeline
  in sequence with fresh results. Do NOT re-use the old assessment or conversion dicts.
- Do NOT call reconcile_pipeline directly with the old conversion — the PySpark files on disk
  have been modified by repair, so the conversion result in memory is stale.
- Only one repair+restart cycle is allowed. If confidence is still < 0.60 after
  the second reconciliation, set `final_status = 'FAILED'` and call FINAL.

### After any tool raises an exception

- Do not retry more than once.
- Record the error in `summary` and call FINAL with `final_status = 'ERROR'`.

---

## Part 4 — FINAL output contract

| Key            | Type | Required | Description                              |
|----------------|------|----------|------------------------------------------|
| pipeline       | str  | YES      | Pipeline name                            |
| assessment     | dict | YES      | Full dict from assess_pipeline           |
| conversion     | dict | YES      | Full dict from convert_pipeline          |
| reconciliation | dict | YES      | Full dict from reconcile_pipeline        |
| deployment     | dict | NO       | Full dict from deploy_pipeline if called |
| final_status   | str  | YES      | PASSED \| WARNING \| FAILED \| ERROR     |
| summary        | str  | YES      | One-paragraph human-readable summary     |

`final_status` must match the value from Part 2 — do not override it.

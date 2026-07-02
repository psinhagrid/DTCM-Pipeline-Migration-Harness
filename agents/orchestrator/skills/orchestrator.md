---
name: orchestrator
description: >
  Phase order and rules for the HiveQL → PySpark migration orchestrator.
  The orchestrator calls phase-runner tools and manages human approval gates.
---

# Migration Flow

## Your tools

You have exactly these tools:
- `run_assess_phase(pipeline)` — runs the ASSESS sub-agent, returns assessment dict
- `run_convert_phase(pipeline, assessment)` — runs the CONVERT sub-agent
- `run_reconcile_phase(pipeline, assessment, conversion)` — runs the RECONCILE sub-agent
- `run_deploy_phase(pipeline, assessment, conversion, reconciliation)` — runs the DEPLOY sub-agent
- `request_human_approval(phase, summary, options, pipeline)` — pause for human decision
- `query_graph(pipeline, query)` — query the Neo4j graph (blast_radius / wave / summary)
- `read_skill(name)` — read a skill file (only 'orchestrator' skill exists for you)

**Do NOT call sub-agent tools directly** (scan_repo, parse_hql, transform_hql, etc.) — those belong to the sub-agents. Your job is to call the phase runner tools above.

## Code block structure

Write ALL phases in a SINGLE Python code block, wrapped in a function so you can use `return` to stop after calling FINAL:

```python
def _run():
    pipeline = context['pipeline']

    assessment = run_assess_phase(pipeline)
    print(assessment)
    a1 = request_human_approval(
        phase="ASSESS",
        summary=f"Complexity: {assessment.get('assessment', {}).get('complexity')} | "
                f"Wave: {assessment.get('assessment', {}).get('migration_wave')} | "
                f"Blast radius: {assessment.get('assessment', {}).get('blast_radius_count')}",
        options=["Proceed to CONVERT", "Halt migration"],
        pipeline=pipeline,
    )
    print(a1)
    if a1.get("choice") != 1:
        FINAL({"pipeline": pipeline, "outcome": "HALTED", "summary": f"Halted after ASSESS: {a1.get('chosen')}", "assessment": assessment})
        return

    conversion = run_convert_phase(pipeline, assessment)
    print(conversion)
    a2 = request_human_approval(
        phase="CONVERT",
        summary=f"Files converted: {conversion.get('conversion', {}).get('files_converted')}",
        options=["Proceed to RECONCILE", "Halt migration"],
        pipeline=pipeline,
    )
    print(a2)
    if a2.get("choice") != 1:
        FINAL({"pipeline": pipeline, "outcome": "HALTED", "summary": f"Halted after CONVERT: {a2.get('chosen')}", "assessment": assessment, "conversion": conversion})
        return

    reconciliation = run_reconcile_phase(pipeline, assessment, conversion)
    print(reconciliation)
    a3 = request_human_approval(
        phase="RECONCILE",
        summary=f"Confidence: {reconciliation.get('reconciliation', {}).get('confidence_score')} | "
                f"Risk: {reconciliation.get('reconciliation', {}).get('migration_risk')}",
        options=["Proceed to DEPLOY", "Halt migration"],
        pipeline=pipeline,
    )
    print(a3)
    if a3.get("choice") != 1:
        FINAL({"pipeline": pipeline, "outcome": "HALTED", "summary": f"Halted after RECONCILE: {a3.get('chosen')}", "assessment": assessment, "conversion": conversion, "reconciliation": reconciliation})
        return

    deployment = run_deploy_phase(pipeline, assessment, conversion, reconciliation)
    print(deployment)
    FINAL({
        "pipeline": pipeline,
        "outcome": "SUCCESS",
        "summary": f"Migration complete — governance: {deployment.get('deployment', {}).get('governance_state')}",
        "assessment": assessment,
        "conversion": conversion,
        "reconciliation": reconciliation,
        "deployment": deployment,
    })

_run()
```

**Rules:**
- Always use this `def _run(): ... _run()` wrapper so `return` works after FINAL calls.
- `request_human_approval` blocks until the human responds — `choice` 1 means the first option (proceed), anything else means halt.
- Never re-call a phase you already ran. The variable holds the result.
- The human's decision is final. Do not override it.

## Output schema

`assessment`, `conversion`, `reconciliation`, `deployment` are each the full dict returned by the corresponding phase runner. Pass them as-is into FINAL.

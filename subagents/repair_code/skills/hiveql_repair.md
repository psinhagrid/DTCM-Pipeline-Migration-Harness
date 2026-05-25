---
name: hiveql_repair
description: >
  Teaches how to repair HiveQL files — the thought process for finding
  the minimal correct fix and presenting it clearly to the user.
---

# HiveQL Repair Skill

## The repair mindset

When you find something wrong in a `.hql` file, the goal is the smallest change
that makes the statement valid Hive SQL while preserving exactly what it was trying to do.

Ask before proposing: "If I apply this fix, does the query still compute the same result?
Does it parse correctly? Would Hive execute it without error?"

If you can not answer yes to all three — don't propose that fix. Skip the issue and report it.

## How to arrive at a fix

1. **Understand what the statement intends** — before touching anything, be clear on what data transformation it's doing. A fix that changes semantics is worse than no fix.

2. **Identify the smallest broken part** — often one clause, one keyword, one column reference is wrong. Fix only that. Don't restructure the whole query to fix one line.

3. **Translate the intent into valid Hive SQL** — use your knowledge of Hive dialect to write the equivalent that works. If a construct from another database crept in (Snowflake, BigQuery, Spark SQL), replace it with the Hive equivalent that achieves the same result.

4. **Check the fix in your head** — mentally trace through: does the fixed version parse? Does it produce the same rows as intended?

## How to present a fix

Show exactly what changes:

```
filename.hql — Line 42

BEFORE:
  [exact original lines]

AFTER:
  [exact replacement lines]

Why: one sentence explaining what was wrong and why this fixes it.
```

Be precise about line numbers. Show only the lines that change, not the whole file.
If the fix requires adding a wrapping subquery, show enough context (surrounding lines)
for the user to understand where the change fits.

## What not to do

- Do not reformat or rename anything that was not broken
- Do not change business logic — if unsure whether a change affects output, skip it
- Do not propose multiple alternative fixes — pick the best one and propose it

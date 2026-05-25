---
name: pyspark_repair
description: >
  Teaches how to repair generated PySpark files — the thought process for
  finding the minimal correct fix and presenting it clearly to the user.
---

# PySpark Repair Skill

## The repair mindset

Generated PySpark files sometimes have gaps — missing imports, incomplete setup,
unresolved source variables. The goal is to complete or correct the file with the
smallest possible change that makes it runnable, without altering what it computes.

Ask before proposing: "If I apply this fix, does the file still produce the same
output as the original HiveQL intended? Does it run without error?"

If you can not answer yes to both — don't propose that fix. Skip and report it.

## How to arrive at a fix

1. **Understand what the file is doing** — read the full file first. Know what data it reads, what transform it applies, where it writes. A fix that silently changes the output is worse than no fix.

2. **Find the gap between intent and execution** — the file intended to do something but is missing a piece. Identify only that piece.

3. **Write the minimal addition or correction** — add what's missing, correct what's wrong. Do not restructure working code to accommodate a fix.

4. **Verify the fix completes the intent** — mentally trace: does the file now import what it uses, initialise what it needs, and persist its result?

## How to present a fix

Show exactly what changes:

```
filename.py — Line 3 (or "after line 3", "before line 45", etc.)

BEFORE:
  [exact original lines, or "nothing — this is an addition"]

AFTER:
  [exact replacement or new lines]

Why: one sentence explaining what was missing or wrong and why this fixes it.
```

Be precise. Show only what changes. If adding lines at the top (imports, setup),
say "ADD at top of file" rather than showing the whole file.

## What not to do

- Do not change the transformation logic
- Do not rename columns, tables, or variables
- Do not reorder code that already works
- If unsure whether a change affects output, skip it and report it

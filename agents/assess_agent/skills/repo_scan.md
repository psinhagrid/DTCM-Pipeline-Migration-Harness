---
name: repo_scan
description: >
  Discovers and parses all source files in a HiveQL pipeline directory.
  Select this skill when the task requires reading and understanding the raw
  contents of a pipeline repo — file inventory, DDL structure, UDFs, syntax errors.
---

# Repo Scan Skill

## CRITICAL: Tool Usage — No Direct File System Access

You do NOT have access to the pipeline files directly. Pyodide does NOT mount the pipeline
directories. ALL file discovery and parsing MUST go through the provided tool functions.

**Never use**: `os.listdir`, `os.walk`, `glob.glob`, `open(...)`, `pathlib.Path`, or any
direct filesystem calls. They will fail with FileNotFoundError.

## Step 1: Discover files

Call `scan_repo(pipeline)` with the pipeline name string:
```python
scan = scan_repo(context['pipeline'])
# returns: {'hql_files': [...], 'config_files': [...], 'total_files': int}
```

- 0 HQL files → HALT: nothing to assess

## Step 2: Parse each HQL file

For each filename in `scan['hql_files']`:
```python
parsed = parse_hql(context['pipeline'], filename)
# returns: {file, read_tables, created_tables, written_tables, all_tables,
#           columns, partition_keys, udfs, has_window, subqueries,
#           has_dyn_part, cross_db_joins, syntax_errors}
```

- syntax_errors > 0 → also call `read_skill('hiveql_repair')`

## Step 3: Extract lineage

Aggregate across all parsed files, then call:
```python
lineage = lineage_extract(
    context['pipeline'],
    all_reads,    # union of all read_tables
    all_creates,  # union of all created_tables
    all_writes,   # union of all written_tables
)
# returns: {upstream, output_tables, downstream}
```

## Step 4: Classify complexity

```python
complexity = classify_complexity(
    tables=all_tables,
    udfs=all_udfs,
    has_window=any_has_window,
    cross_db=all_cross_db,
    has_dyn_part=any_has_dyn_part,
    subqueries=total_subqueries,
    downstream=lineage['downstream'],
)
# returns: {score, complexity, estimated_effort}
```

## Step 5: Persist to graph

```python
neo4j = neo4j_write(
    pipeline=context['pipeline'],
    upstream_tables=lineage['upstream'],
    output_tables=lineage['output_tables'],
    downstream=lineage['downstream'],
    udfs=all_udfs,
    complexity=complexity['complexity'],
    estimated_effort=complexity['estimated_effort'],
)
blast = query_graph(context['pipeline'], 'blast_radius')
wave  = query_graph(context['pipeline'], 'wave')
```

## Step 6: Build result and call FINAL

```python
result = {
    'pipeline': context['pipeline'],
    'outcome':  'SUCCESS',
    'summary':  f"{len(scan['hql_files'])} HQL files · {complexity['complexity']} complexity · wave {wave.get('migration_wave')}",
    'assessment': {
        'hql_files':       scan['hql_files'],
        'config_files':    scan['config_files'],
        'complexity':      complexity['complexity'],
        'estimated_effort': complexity['estimated_effort'],
        'tables':          len(set(all_tables)),
        'udfs':            all_udfs,
        'upstream':        lineage['upstream'],
        'output_tables':   lineage['output_tables'],
        'downstream':      lineage['downstream'],
        'blast_radius':    blast.get('blast_radius', []),
        'migration_wave':  wave.get('migration_wave', 0),
    }
}
FINAL(result)
```

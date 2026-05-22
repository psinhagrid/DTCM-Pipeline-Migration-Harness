---
name: artifact_packaging
description: >
  Knows output naming conventions, S3 path structure, and artifact registry
  format. Select this skill before uploading or registering conversion output.
examples:
  - examples/artifact_example.md
---

# Artifact Packaging Skill

## File naming

- HQL source: `{name}.hql` → PySpark output: `{name}.py`
- DAG file: `{pipeline}_dag.py`
- All filenames are lowercase, with hyphens and spaces replaced by underscores

## S3 path structure

- Base path: `s3://dtcm-artifacts/wave1/{pipeline}/`
- PySpark files: `s3://dtcm-artifacts/wave1/{pipeline}/{name}.py`
- DAG file: `s3://dtcm-artifacts/wave1/{pipeline}/{pipeline}_dag.py`

## Upload

- `s3_upload_tool` is currently stubbed (TODO: implement via boto3 `put_object`)
- Upload every entry in the `generated_files` list, plus the DAG file
- Log each upload as a `tool_call` event in the agent trace

## Result fields

- `artifact_path`: the S3 base path for the pipeline
- `generated_files`: list of all filenames uploaded (PySpark files + DAG file)
- These fields are read by `reconcile_subagent` and `deploy_subagent` in
  subsequent pipeline stages

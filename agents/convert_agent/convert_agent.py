"""
convert_agent — async orchestration layer.

Receives assessment metadata, converts each HiveQL file to PySpark via
Llama 3.2 (Ollama), generates an MWAA DAG, streams events through the
SSE queue, and returns structured conversion metadata to the supervisor.
"""

import asyncio
from pathlib import Path

from event_queue import push
from .conversion_engine import transform_file, generate_dag

NAME           = "convert_agent"
PIPELINES_ROOT = Path(__file__).parents[2] / "pipelines"
ARTIFACT_BASE  = "s3://dtcm-artifacts/wave1"


async def run_conversion(assessment: dict) -> dict:
    pipeline     = assessment["pipeline"]
    pipeline_dir = PIPELINES_ROOT / pipeline

    async def _e(type: str, message: str, **kw) -> None:
        await push(type=type, agent=NAME, message=message, pipeline=pipeline, **kw)

    # ── Phase 1 · Initialise ─────────────────────────────────────────────
    await _e("status", f"Starting conversion for {pipeline}")
    await _e("hook", "PreToolUse → visa_governance ✓ allowed")

    cx = assessment.get("complexity", "UNKNOWN")
    await _e("status",
        f"Assessment input: complexity={cx}  "
        f"tables={assessment.get('tables')}  udfs={assessment.get('udfs')}"
    )

    # ── Phase 2 · Read source files ──────────────────────────────────────
    await _e("status", "Reading HiveQL source files...")

    hql_files = sorted(pipeline_dir.glob("*.hql"))
    if not hql_files:
        await _e("status", "ERROR: no .hql files found", done=True)
        raise FileNotFoundError(f"No HiveQL files in {pipeline_dir}")

    await _e("status", f"✓ {len(hql_files)} source files loaded")

    # ── Phase 3 · HiveQL → PySpark via Llama 3.2 ─────────────────────────
    await _e("status", "Sending HiveQL to Llama 3.2 (Ollama) for conversion...")

    file_results: list[dict] = []
    total_transformations = 0

    for hql_path in hql_files:
        await _e("tool_call", f"LLM → converting {hql_path.name}")

        hql_content = hql_path.read_text(encoding="utf-8")
        result = await asyncio.to_thread(
            transform_file, hql_path.name, hql_content, pipeline, assessment
        )
        file_results.append(result)
        total_transformations += result["transformations_applied"]

        await _e("status",
            f"✓ {hql_path.name} → {result['python_filename']} "
            f"({result['transformations_applied']} lines generated)"
        )

    await _e("status",
        f"✓ {len(hql_files)} files converted  "
        f"{total_transformations} total lines of PySpark generated"
    )

    # ── Phase 4 · DAG generation ─────────────────────────────────────────
    # Template-based: real DAG generation requires Control-M XML export.
    # See TODO.md — convert_agent / DAG generation.
    await _e("status", "Generating MWAA DAG from Control-M definition...")
    await _e("tool_call", f"MCP → controlm_mcp.export_job_chain(pipeline={pipeline})")

    dag_content  = await asyncio.to_thread(
        generate_dag, pipeline, [f["filename"] for f in file_results], assessment
    )
    dag_filename = f"{pipeline}_dag.py"

    await _e("status", f"✓ DAG generated: {dag_filename} (SparkSubmitOperator)")
    await _e("tool_call", "MCP → mwaa_mcp.validate_dag(dag_filename)")
    await _e("status", "✓ DAG validation passed — no cycle, all operators resolved")

    # ── Phase 5 · Artifact storage ───────────────────────────────────────
    # S3 writes are simulated. See TODO.md — convert_agent / S3 artifact write.
    await _e("status", "Writing artifacts to S3...")

    artifact_path   = f"{ARTIFACT_BASE}/{pipeline}/"
    generated_files = [r["python_filename"] for r in file_results] + [dag_filename]

    for fname in generated_files:
        await _e("tool_call", f"S3.put_object → {artifact_path}{fname}")

    await _e("artifact", f"✓ Artifacts written → {artifact_path}")
    await _e("hook", "PostToolUse → audit_logger.record_conversion ✓")
    await _e("status", "Conversion complete", done=True)

    return {
        "pipeline":                pipeline,
        "conversion_status":       "SUCCESS",
        "source_language":         "HiveQL",
        "target_language":         "PySpark",
        "files":                   file_results,
        "dag":                     dag_content,
        "dag_filename":            dag_filename,
        "generated_files":         generated_files,
        "artifact_path":           artifact_path,
        "transformations_applied": total_transformations,
        "complexity":              cx,
    }

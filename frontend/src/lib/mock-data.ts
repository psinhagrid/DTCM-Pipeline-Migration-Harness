// Mock data for the DTCM Migration Harness POC frontend.
// Designed to feel realistic at enterprise scale even though only one
// real pipeline currently exists in the backend.

export type PipelineStatus = "running" | "queued" | "validating" | "succeeded" | "failed" | "paused";

export interface Pipeline {
  id: string;
  name: string;
  source: string;
  target: string;
  wave: string;
  phase: string;
  status: PipelineStatus;
  progress: number;
  eta: string;
  confidence: number;
  owner: string;
  activeAgent?: string;
}

export const pipelines: Pipeline[] = [
  {
    id: "PL-00471",
    name: "fct_consumer_replay_daily",
    source: "Hive / EMR 5.36",
    target: "MWAA 2.8 / Spark 3.4",
    wave: "Wave 03 — Consumer Domain",
    phase: "Convert › PySpark",
    status: "running",
    progress: 64,
    eta: "00:04:12",
    confidence: 0.92,
    owner: "platform-data",
    activeAgent: "convert_agent",
  },
  {
    id: "PL-00468",
    name: "dim_account_scd2",
    source: "Hive / EMR 5.36",
    target: "MWAA 2.8 / Spark 3.4",
    wave: "Wave 03 — Consumer Domain",
    phase: "Validate › Schema parity",
    status: "validating",
    progress: 88,
    eta: "00:01:48",
    confidence: 0.97,
    owner: "platform-data",
    activeAgent: "validate_agent",
  },
  {
    id: "PL-00463",
    name: "agg_merchant_settlement_hourly",
    source: "Hive / EMR 5.36",
    target: "MWAA 2.8 / Spark 3.4",
    wave: "Wave 02 — Settlement",
    phase: "Reconcile › Aggregations",
    status: "running",
    progress: 41,
    eta: "00:09:30",
    confidence: 0.81,
    owner: "settlement-eng",
    activeAgent: "reconcile_agent",
  },
  {
    id: "PL-00459",
    name: "fct_card_auth_events",
    source: "Hive / EMR 5.36",
    target: "MWAA 2.8 / Spark 3.4",
    wave: "Wave 02 — Settlement",
    phase: "Deploy › MWAA DAG",
    status: "succeeded",
    progress: 100,
    eta: "—",
    confidence: 0.99,
    owner: "issuing-eng",
  },
  {
    id: "PL-00455",
    name: "dim_merchant_hierarchy",
    source: "Hive / EMR 5.36",
    target: "MWAA 2.8 / Spark 3.4",
    wave: "Wave 02 — Settlement",
    phase: "Validate › Row variance",
    status: "failed",
    progress: 72,
    eta: "—",
    confidence: 0.46,
    owner: "settlement-eng",
  },
  {
    id: "PL-00452",
    name: "fct_dispute_lifecycle",
    source: "Hive / EMR 5.36",
    target: "MWAA 2.8 / Spark 3.4",
    wave: "Wave 04 — Disputes",
    phase: "Queued",
    status: "queued",
    progress: 0,
    eta: "—",
    confidence: 0.0,
    owner: "risk-eng",
  },
  {
    id: "PL-00449",
    name: "agg_chargeback_window",
    source: "Hive / EMR 5.36",
    target: "MWAA 2.8 / Spark 3.4",
    wave: "Wave 04 — Disputes",
    phase: "Convert › PySpark",
    status: "paused",
    progress: 23,
    eta: "—",
    confidence: 0.74,
    owner: "risk-eng",
  },
];

export const stats = {
  total: 312,
  migrated: 184,
  inProgress: 27,
  validating: 11,
  failed: 4,
  modernizationPct: 0.59,
  artifactsGenerated: 4218,
  linesConverted: 1_284_902,
  mcpCalls: 38_104,
  govDecisions: 1_672,
};

export const waves = [
  { name: "Wave 01 — Reference", total: 42, done: 42, status: "succeeded" as PipelineStatus },
  { name: "Wave 02 — Settlement", total: 88, done: 71, status: "running" as PipelineStatus },
  { name: "Wave 03 — Consumer Domain", total: 96, done: 41, status: "running" as PipelineStatus },
  { name: "Wave 04 — Disputes", total: 54, done: 18, status: "queued" as PipelineStatus },
  { name: "Wave 05 — Reporting", total: 32, done: 0, status: "queued" as PipelineStatus },
];

export type EventLevel = "supervisor" | "hook" | "mcp" | "convert" | "validate" | "reconcile" | "deploy" | "system" | "error";

export interface OrchestrationEvent {
  ts: string;
  level: EventLevel;
  msg: string;
  meta?: string;
}

export const seedEvents: OrchestrationEvent[] = [
  { ts: "12:04:11.221", level: "supervisor", msg: "Delegating to convert_agent", meta: "task=convert pipeline=PL-00471" },
  { ts: "12:04:11.244", level: "hook", msg: "visa_governance approved action", meta: "policy=migration.write.v3" },
  { ts: "12:04:11.301", level: "mcp", msg: "neo4j_mcp.read_graph(node=fct_consumer_replay_daily)", meta: "latency=42ms" },
  { ts: "12:04:11.612", level: "convert", msg: "Parsing HiveQL AST · 1,284 tokens", meta: "parser=v2.4.1" },
  { ts: "12:04:12.108", level: "mcp", msg: "s3_mcp.list(prefix=raw/consumer/2026/05/)", meta: "objects=2,341" },
  { ts: "12:04:12.844", level: "convert", msg: "Generating MWAA DAG · airflow_2_8 template", meta: "tasks=14 deps=21" },
  { ts: "12:04:13.011", level: "hook", msg: "naming_convention hook normalized 3 identifiers", meta: "" },
  { ts: "12:04:13.488", level: "validate", msg: "Schema parity OK · 84/84 columns", meta: "drift=0" },
  { ts: "12:04:14.020", level: "supervisor", msg: "Phase complete · routing to reconcile_agent", meta: "confidence=0.92" },
  { ts: "12:04:14.220", level: "reconcile", msg: "Row variance Δ = 0.0007 (within tolerance)", meta: "tol=0.005" },
  { ts: "12:04:14.401", level: "mcp", msg: "neo4j_mcp.write_graph(edge=converted_to)", meta: "" },
];

export const validationChecks = [
  { name: "Schema parity",        state: "pass" as const,    score: 1.00, runtime: "412ms", note: "84/84 columns aligned, 0 drift." },
  { name: "Aggregation parity",   state: "pass" as const,    score: 0.999, runtime: "1.8s",  note: "All GROUP BY surfaces match within 1e-6." },
  { name: "Join validation",      state: "pass" as const,    score: 0.998, runtime: "2.1s",  note: "Cardinality stable across 6 joins." },
  { name: "Row variance",         state: "warning" as const, score: 0.976, runtime: "3.4s",  note: "Δ 0.024 in dim_merchant_hierarchy partition 2026-05-21." },
  { name: "Checksum validation",  state: "pass" as const,    score: 1.00, runtime: "5.0s",  note: "SHA-256 column hashes identical." },
  { name: "SLA validation",       state: "pass" as const,    score: 0.992, runtime: "11ms",  note: "Target window 04:00 UTC, ETA 03:42." },
  { name: "Consumer replay",      state: "pass" as const,    score: 0.989, runtime: "8.7s",  note: "12 downstream consumers replayed clean." },
  { name: "Partition parity",     state: "failed" as const,  score: 0.612, runtime: "6.2s",  note: "Partition 2026-05-19 missing in target — backfill required." },
];

export const diffSamples = {
  hive: `-- source: hql/fct_consumer_replay_daily.hql
SET hive.exec.dynamic.partition.mode=nonstrict;

INSERT OVERWRITE TABLE consumer.fct_consumer_replay_daily
PARTITION (event_date)
SELECT
  c.consumer_id,
  c.account_id,
  COUNT(DISTINCT e.event_id)              AS event_cnt,
  SUM(CASE WHEN e.kind='REPLAY' THEN 1 END) AS replay_cnt,
  MAX(e.event_ts)                         AS last_event_ts,
  e.event_date
FROM consumer.evt_consumer_stream e
JOIN consumer.dim_consumer c
  ON c.consumer_id = e.consumer_id
WHERE e.event_date BETWEEN '\${hiveconf:start_dt}' AND '\${hiveconf:end_dt}'
GROUP BY c.consumer_id, c.account_id, e.event_date;`,
  spark: `# generated: dags/consumer/fct_consumer_replay_daily.py
from pyspark.sql import functions as F

def build(spark, start_dt: str, end_dt: str):
    evt = (spark.table("consumer.evt_consumer_stream")
                .where(F.col("event_date").between(start_dt, end_dt)))
    dim = spark.table("consumer.dim_consumer")

    out = (evt.alias("e")
              .join(dim.alias("c"), "consumer_id", "inner")
              .groupBy("c.consumer_id", "c.account_id", "e.event_date")
              .agg(
                  F.countDistinct("e.event_id").alias("event_cnt"),
                  F.sum(F.when(F.col("e.kind") == "REPLAY", 1)).alias("replay_cnt"),
                  F.max("e.event_ts").alias("last_event_ts"),
              ))

    (out.write.mode("overwrite")
        .partitionBy("event_date")
        .saveAsTable("consumer.fct_consumer_replay_daily"))`,
  dag: `# generated: dags/consumer/fct_consumer_replay_daily_dag.py
from airflow import DAG
from airflow.providers.amazon.aws.operators.emr import EmrServerlessStartJobOperator
from datetime import datetime, timedelta

default_args = {"owner": "platform-data", "retries": 2, "retry_delay": timedelta(minutes=5)}

with DAG(
    dag_id="fct_consumer_replay_daily",
    start_date=datetime(2026, 5, 1),
    schedule="0 4 * * *",
    catchup=False,
    tags=["wave-03", "consumer", "migrated"],
    default_args=default_args,
) as dag:
    run = EmrServerlessStartJobOperator(
        task_id="run_pyspark",
        application_id="{{ var.value.emrs_app_id }}",
        execution_role_arn="{{ var.value.emrs_role }}",
        job_driver={
            "sparkSubmit": {
                "entryPoint": "s3://dtcm-artifacts/dags/consumer/fct_consumer_replay_daily.py",
                "sparkSubmitParameters": "--conf spark.sql.shuffle.partitions=400",
            }
        },
    )`,
  summary: `Validation Summary — PL-00471 / fct_consumer_replay_daily
================================================================
Semantic similarity   : 0.974   (HiveQL ↔ PySpark)
Transformation conf.  : 0.92
Files generated       : 4   (pyspark.py, dag.py, tests.py, manifest.json)
Static analysis       : 0 errors · 2 info
Sample run rowcount Δ : 0.0007   (within 0.005 tolerance)
Recommendation        : APPROVE for staging deploy.`,
};

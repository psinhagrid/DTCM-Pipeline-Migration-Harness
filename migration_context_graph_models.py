from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# ENUMS
# ============================================================


class MigrationStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class Criticality(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class JobType(str, Enum):
    HIVE = "HIVE"
    SPARK = "SPARK"
    SHELL = "SHELL"
    PYTHON = "PYTHON"
    SQL = "SQL"


class ExecutionEngine(str, Enum):
    MAPREDUCE = "MAPREDUCE"
    TEZ = "TEZ"
    SPARK = "SPARK"


class QueryType(str, Enum):
    SELECT = "SELECT"
    INSERT_OVERWRITE = "INSERT_OVERWRITE"
    INSERT_INTO = "INSERT_INTO"
    CREATE_TABLE_AS = "CREATE_TABLE_AS"
    MERGE = "MERGE"


class AwsTargetService(str, Enum):
    AWS_GLUE = "AWS_GLUE"
    EMR = "EMR"
    EMR_SERVERLESS = "EMR_SERVERLESS"
    ATHENA = "ATHENA"
    STEP_FUNCTIONS = "STEP_FUNCTIONS"


# ============================================================
# BASE NODE
# ============================================================


class BaseGraphNode(BaseModel):
    node_id: str
    node_type: str

    name: str
    description: Optional[str] = None

    owner: Optional[str] = None
    environment: str = "prod"

    tags: List[str] = Field(default_factory=list)

    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ============================================================
# WORKFLOW NODE
# ============================================================


class WorkflowNode(BaseGraphNode):
    workflow_id: str
    workflow_name: str

    scheduler_type: str
    schedule_cron: Optional[str] = None

    execution_frequency: str = "DAILY"

    sla_minutes: Optional[int] = None

    workflow_priority: Criticality = Criticality.MEDIUM

    criticality_score: float = 0.5

    retry_count: int = 0
    timeout_minutes: Optional[int] = None

    migration_wave: Optional[int] = None
    migration_status: MigrationStatus = MigrationStatus.NOT_STARTED


# ============================================================
# JOB NODE
# ============================================================


class JobNode(BaseGraphNode):
    job_id: str
    job_name: str

    job_type: JobType
    execution_engine: ExecutionEngine

    hql_path: Optional[str] = None
    script_path: Optional[str] = None

    avg_runtime_minutes: Optional[float] = None
    peak_runtime_minutes: Optional[float] = None

    memory_mb: Optional[int] = None
    vcores: Optional[int] = None

    failure_rate: Optional[float] = None

    migration_complexity: str = "MEDIUM"

    migration_status: MigrationStatus = MigrationStatus.NOT_STARTED

    migration_confidence: Optional[float] = None

    requires_human_review: bool = False

    blocker_reason: Optional[str] = None


# ============================================================
# TABLE NODE
# ============================================================


class TableNode(BaseGraphNode):
    table_id: str

    database_name: str
    table_name: str

    storage_type: str = "ORC"

    partitioned: bool = False
    partition_columns: List[str] = Field(default_factory=list)

    row_count: Optional[int] = None

    avg_daily_growth_gb: Optional[float] = None

    retention_days: Optional[int] = None

    schema_version: Optional[str] = None

    pii_flag: bool = False

    business_criticality: Criticality = Criticality.MEDIUM

    blast_radius_score: Optional[float] = None

    upstream_count: Optional[int] = None
    downstream_count: Optional[int] = None


# ============================================================
# QUERY NODE
# ============================================================


class QueryNode(BaseGraphNode):
    query_id: str

    query_type: QueryType

    hql_text: str

    join_count: int = 0
    subquery_count: int = 0

    uses_window_functions: bool = False
    uses_udf: bool = False

    estimated_complexity: str = "MEDIUM"

    semantic_hash: Optional[str] = None


# ============================================================
# SEMANTIC IR MODELS
# ============================================================


class AggregationDefinition(BaseModel):
    function: str
    column: str
    alias: Optional[str] = None


class FilterDefinition(BaseModel):
    column: str
    operator: str
    value: str


class JoinDefinition(BaseModel):
    join_type: str
    left_table: str
    right_table: str
    join_condition: str


class SemanticIRNode(BaseGraphNode):
    ir_id: str

    operation_types: List[str] = Field(default_factory=list)

    source_tables: List[str] = Field(default_factory=list)
    target_tables: List[str] = Field(default_factory=list)

    group_by_columns: List[str] = Field(default_factory=list)

    aggregations: List[AggregationDefinition] = Field(default_factory=list)

    filters: List[FilterDefinition] = Field(default_factory=list)

    joins: List[JoinDefinition] = Field(default_factory=list)

    window_functions: List[str] = Field(default_factory=list)

    temp_tables: List[str] = Field(default_factory=list)

    lineage_depth: Optional[int] = None


# ============================================================
# VALIDATION NODE
# ============================================================


class ValidationNode(BaseGraphNode):
    validation_id: str

    validation_status: str

    schema_match: bool = False
    row_count_match: bool = False
    null_distribution_match: bool = False

    aggregation_match_score: Optional[float] = None

    execution_time_ratio: Optional[float] = None

    validation_timestamp: Optional[str] = None

    validation_notes: Optional[str] = None


# ============================================================
# AWS TARGET NODE
# ============================================================


class AwsTargetNode(BaseGraphNode):
    target_id: str

    target_service: AwsTargetService

    target_runtime: str

    glue_job_name: Optional[str] = None

    emr_cluster_type: Optional[str] = None

    s3_output_path: Optional[str] = None

    iceberg_enabled: bool = False

    step_function_name: Optional[str] = None

    deployment_status: str = "NOT_DEPLOYED"


# ============================================================
# CONSUMER NODE
# ============================================================


class ConsumerNode(BaseGraphNode):
    consumer_id: str

    consumer_name: str

    consumer_type: str

    sla_minutes: Optional[int] = None

    business_criticality: Criticality = Criticality.MEDIUM


# ============================================================
# MIGRATION METADATA
# ============================================================


class MigrationMetadata(BaseModel):
    migration_status: MigrationStatus

    migration_wave: Optional[int] = None

    migration_confidence: Optional[float] = None

    validation_passed: bool = False

    blocker_reason: Optional[str] = None

    risk_score: Optional[float] = None

    requires_human_review: bool = False


# ============================================================
# RUNTIME EXECUTION STATE
# ============================================================


class MigrationRuntimeState(BaseModel):
    execution_id: str

    workflow_id: str

    current_step: str

    completed_steps: List[str] = Field(default_factory=list)

    failed_steps: List[str] = Field(default_factory=list)

    retry_counts: Dict[str, int] = Field(default_factory=dict)

    current_job_id: Optional[str] = None

    planner_decision: Optional[str] = None

    validation_status: Optional[str] = None

    escalation_required: bool = False

    execution_logs: List[str] = Field(default_factory=list)


# ============================================================
# RELATIONSHIP MODELS
# ============================================================


class GraphRelationship(BaseModel):
    relationship_id: str

    source_node_id: str
    target_node_id: str

    relationship_type: str

    metadata: Dict = Field(default_factory=dict)


# ============================================================
# GRAPH CONTAINER
# ============================================================


class ContextGraph(BaseModel):
    workflows: List[WorkflowNode] = Field(default_factory=list)

    jobs: List[JobNode] = Field(default_factory=list)

    tables: List[TableNode] = Field(default_factory=list)

    queries: List[QueryNode] = Field(default_factory=list)

    semantic_ir_nodes: List[SemanticIRNode] = Field(default_factory=list)

    validations: List[ValidationNode] = Field(default_factory=list)

    aws_targets: List[AwsTargetNode] = Field(default_factory=list)

    consumers: List[ConsumerNode] = Field(default_factory=list)

    relationships: List[GraphRelationship] = Field(default_factory=list)


# ============================================================
# EXAMPLE OBJECTS
# ============================================================


example_workflow = WorkflowNode(
    node_id="workflow_node_1",
    node_type="Workflow",
    name="finance_daily_pipeline",
    workflow_id="wf_001",
    workflow_name="finance_daily_pipeline",
    scheduler_type="oozie",
    schedule_cron="0 2 * * *",
    owner="finance_team",
    criticality_score=0.92,
)


example_job = JobNode(
    node_id="job_node_1",
    node_type="Job",
    name="sales_aggregation_job",
    job_id="job_001",
    job_name="sales_aggregation_job",
    job_type=JobType.HIVE,
    execution_engine=ExecutionEngine.MAPREDUCE,
    hql_path="/warehouse/hql/sales_agg.hql",
    avg_runtime_minutes=24.5,
)


example_table = TableNode(
    node_id="table_node_1",
    node_type="Table",
    name="sales_agg",
    table_id="table_001",
    database_name="finance_db",
    table_name="sales_agg",
    partitioned=True,
    partition_columns=["dt"],
    row_count=125000000,
)


example_relationship = GraphRelationship(
    relationship_id="rel_001",
    source_node_id="job_node_1",
    target_node_id="table_node_1",
    relationship_type="WRITES_TO",
)

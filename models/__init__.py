"""Models module initialization."""
from .schemas import (
    # Enums
    QueryIntent,
    ExecutionStatus,
    # Schema models
    ColumnInfo,
    TableInfo,
    ForeignKeyRelation,
    SchemaContext,
    # Intent models
    IntentClassification,
    # Query planning models
    JoinSpec,
    FilterSpec,
    AggregationSpec,
    QueryPlan,
    # Execution models
    ExecutionResult,
    ValidationResult,
    # Self-correction models
    CorrectionAttempt,
    # Response models
    AgentAction,
    ReasoningTrace,
    FinalResponse
)

# Structured agent outputs for deterministic orchestration
from .agent_outputs import (
    AgentStatus,
    BaseAgentOutput,
    IntentType,
    IntentAnalyzerOutput,
    ClarificationOutput,
    SchemaExplorerOutput,
    TableSchema,
    QueryDecomposerOutput,
    QueryStep,
    DataExplorerOutput,
    ColumnStats,
    QueryPlannerOutput,
    JoinPlan,
    FilterPlan,
    SQLGeneratorOutput,
    SafetyValidatorOutput,
    SQLExecutorOutput,
    SelfCorrectionOutput,
    ResultValidatorOutput,
    ResponseSynthesizerOutput,
    PipelineState
)

__all__ = [
    # From schemas.py
    "QueryIntent",
    "ExecutionStatus",
    "ColumnInfo",
    "TableInfo",
    "ForeignKeyRelation",
    "SchemaContext",
    "IntentClassification",
    "JoinSpec",
    "FilterSpec",
    "AggregationSpec",
    "QueryPlan",
    "ExecutionResult",
    "ValidationResult",
    "CorrectionAttempt",
    "AgentAction",
    "ReasoningTrace",
    "FinalResponse",
    # From agent_outputs.py (structured outputs)
    "AgentStatus",
    "BaseAgentOutput",
    "IntentType",
    "IntentAnalyzerOutput",
    "ClarificationOutput",
    "SchemaExplorerOutput",
    "TableSchema",
    "QueryDecomposerOutput",
    "QueryStep",
    "DataExplorerOutput",
    "ColumnStats",
    "QueryPlannerOutput",
    "JoinPlan",
    "FilterPlan",
    "SQLGeneratorOutput",
    "SafetyValidatorOutput",
    "SQLExecutorOutput",
    "SelfCorrectionOutput",
    "ResultValidatorOutput",
    "ResponseSynthesizerOutput",
    "PipelineState"
]

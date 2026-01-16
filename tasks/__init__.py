"""Tasks module initialization."""
from .task_definitions import (
    # Core tasks (8)
    create_schema_exploration_task,
    create_intent_analysis_task,
    create_query_planning_task,
    create_sql_generation_task,
    create_sql_execution_task,
    create_self_correction_task,
    create_response_synthesis_task,
    create_meta_query_task,
    # New tasks (5)
    create_clarification_task,
    create_safety_validation_task,
    create_query_decomposition_task,
    create_data_exploration_task,
    create_result_validation_task
)

__all__ = [
    # Core tasks
    "create_schema_exploration_task",
    "create_intent_analysis_task",
    "create_query_planning_task",
    "create_sql_generation_task",
    "create_sql_execution_task",
    "create_self_correction_task",
    "create_response_synthesis_task",
    "create_meta_query_task",
    # New tasks
    "create_clarification_task",
    "create_safety_validation_task",
    "create_query_decomposition_task",
    "create_data_exploration_task",
    "create_result_validation_task"
]

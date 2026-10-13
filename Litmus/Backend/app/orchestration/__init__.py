"""
Orchestration package for Swarm Debugger.

Defines the LangGraph workflow state, routing decisions, and graph nodes/transitions.
"""

from app.orchestration.state import WorkflowState, create_initial_workflow_state
from app.orchestration.state import WorkflowState, create_initial_workflow_state
from app.orchestration.routing import (
    RoutingDecision,
    evaluate_round_outcome,
    route_after_judging,
    route_after_intake,
    route_after_prosecutor,
    route_after_defender,
)
from app.orchestration.graph import (
    CourtroomWorkflow,
    WorkflowGraphScaffolding,
    build_courtroom_workflow,
    PLANNED_NODES,
    PLANNED_EDGES,
)

__all__ = [
    "WorkflowState",
    "create_initial_workflow_state",
    "RoutingDecision",
    "evaluate_round_outcome",
    "route_after_judging",
    "route_after_intake",
    "route_after_prosecutor",
    "route_after_defender",
    "CourtroomWorkflow",
    "WorkflowGraphScaffolding",
    "build_courtroom_workflow",
    "PLANNED_NODES",
    "PLANNED_EDGES",
]

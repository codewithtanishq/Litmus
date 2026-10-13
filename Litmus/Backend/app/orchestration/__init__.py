"""
Orchestration package for Swarm Debugger.

Defines the LangGraph workflow state, routing decisions, and graph nodes/transitions.
"""

from app.orchestration.state import WorkflowState, create_initial_workflow_state
from app.orchestration.routing import RoutingDecision, evaluate_round_outcome, route_after_judging
from app.orchestration.graph import (
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
    "WorkflowGraphScaffolding",
    "build_courtroom_workflow",
    "PLANNED_NODES",
    "PLANNED_EDGES",
]

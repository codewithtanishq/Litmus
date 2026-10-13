"""
Routing logic for Swarm Debugger LangGraph orchestration.

Decides conditional transitions after evaluating test evidence and Judge verdict.
"""

from enum import Enum
from typing import Dict, Any
from app.orchestration.state import WorkflowState
from app.schemas.test_result import TestExecutionStatus


class RoutingDecision(str, Enum):
    """Conditional routing outcomes after round evaluation."""
    FINISH_SUCCESS = "finish_success"
    RETRY_ROUND = "retry_round"
    MAX_ROUNDS_EXCEEDED = "max_rounds_exceeded"
    TERMINATE_ERROR = "terminate_error"


def evaluate_round_outcome(state: WorkflowState) -> RoutingDecision:
    """
    Evaluates empirical test evidence stored in the workflow state.

    Rules:
    1. If critical errors occurred in state, return TERMINATE_ERROR.
    2. Check test results for all candidate patches in the current round.
       A missing test result is NEVER treated as successful.
    3. If ANY candidate patch passed deterministically (status == PASSED and passed is True):
       return FINISH_SUCCESS.
    4. If ALL candidate patches failed (or had timeouts/infra errors):
       - If current_round < max_rounds: return RETRY_ROUND (triggering Constraint Ledger update).
       - If current_round >= max_rounds: return MAX_ROUNDS_EXCEEDED.
    """
    if state.get("errors") and len(state.get("errors", [])) > 0:
        return RoutingDecision.TERMINATE_ERROR

    test_results: Dict[str, Any] = state.get("test_results", {})

    # If no candidate patches were evaluated at all, this is an incomplete round, not a pass
    if not test_results:
        current_round = state.get("current_round", 1)
        max_rounds = state.get("max_rounds", 3)
        if current_round < max_rounds:
            return RoutingDecision.RETRY_ROUND
        return RoutingDecision.MAX_ROUNDS_EXCEEDED

    any_passed = False
    all_failed = True

    for patch_id, result in test_results.items():
        # Check explicit status and boolean passed
        if isinstance(result, dict):
            status = result.get("status")
            passed = result.get("passed")
        else:
            status = getattr(result, "status", None)
            passed = getattr(result, "passed", None)

        # Ensure string comparison or enum value
        status_str = status.value if hasattr(status, "value") else str(status)

        # Compatible with both Member 1 schema (explicit passed bool)
        # and Member 2 contracts (ExecutionStatus.PASSED with no passed attribute)
        is_passed = (status_str.upper() == "PASSED") and (passed is True or passed is None)

        if is_passed:
            any_passed = True
            all_failed = False
            break

    if any_passed:
        return RoutingDecision.FINISH_SUCCESS

    if all_failed:
        current_round = state.get("current_round", 1)
        max_rounds = state.get("max_rounds", 3)
        if current_round < max_rounds:
            return RoutingDecision.RETRY_ROUND
        return RoutingDecision.MAX_ROUNDS_EXCEEDED

    return RoutingDecision.TERMINATE_ERROR


def route_after_judging(state: WorkflowState) -> str:
    """
    Conditional edge function compatible with LangGraph.
    Maps RoutingDecision to destination node names.

    Returns:
        Destination node name ('finalize_success', 'record_constraints_and_retry', 'finalize_failure')
    """
    decision = evaluate_round_outcome(state)

    if decision == RoutingDecision.FINISH_SUCCESS:
        return "finalize_success"
    elif decision == RoutingDecision.RETRY_ROUND:
        return "record_constraints_and_retry"
    elif decision in (RoutingDecision.MAX_ROUNDS_EXCEEDED, RoutingDecision.TERMINATE_ERROR):
        return "finalize_failure"

    return "finalize_failure"


def route_after_intake(state: WorkflowState) -> str:
    """
    Conditional edge routing after intake_session.
    If session validation failed or errors exist, route to finalize_failure.
    Otherwise, route to prosecutor.
    """
    if state.get("errors") and len(state.get("errors", [])) > 0:
        return "finalize_failure"
    return "prosecutor"


def route_after_prosecutor(state: WorkflowState) -> str:
    """
    Conditional edge routing after prosecutor node.
    If Prosecutor encountered an error or failed to generate Fix A, route to finalize_failure.
    Never silently continue with a missing candidate patch.
    """
    has_errors = bool(state.get("errors"))
    has_fix_a = bool(state.get("fix_a") or state.get("candidate_patches", {}).get("prosecutor"))
    if has_errors or not has_fix_a:
        return "finalize_failure"
    return "defender"


def route_after_defender(state: WorkflowState) -> str:
    """
    Conditional edge routing after defender node.
    If Defender encountered an error or failed to generate Fix B, route to finalize_failure.
    Never silently continue with a missing candidate patch.
    """
    has_errors = bool(state.get("errors"))
    has_fix_b = bool(state.get("fix_b") or state.get("candidate_patches", {}).get("defender"))
    if has_errors or not has_fix_b:
        return "finalize_failure"
    return "evaluation_boundary"

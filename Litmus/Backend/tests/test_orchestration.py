"""
Unit tests for workflow state, routing logic, and orchestration scaffolding.
"""

from app.schemas.session import DebugSession
from app.schemas.test_result import TestExecutionStatus
from app.orchestration.state import create_initial_workflow_state
from app.orchestration.routing import (
    evaluate_round_outcome,
    route_after_judging,
    RoutingDecision,
)
from app.orchestration.graph import WorkflowGraphScaffolding


class TestWorkflowState:
    def test_state_initialization(self):
        session = DebugSession(
            original_code="def sub(a, b): return a - b",
            bug_description="Calculates difference instead of sum",
            test_suite="assert sub(1, 2) == 3",
        )
        state = create_initial_workflow_state(session, max_rounds=3)

        assert state["session_id"] == session.session_id
        assert state["current_round"] == 1
        assert state["max_rounds"] == 3
        assert state["original_code"] == session.original_code
        assert state["candidate_patches"] == {}
        assert state["test_results"] == {}
        assert state["constraints"] == []
        assert state["verdict"] is None
        assert state["errors"] == []


class TestRoutingLogic:
    def test_routing_finish_when_candidate_passes(self):
        state = {
            "session_id": "session-1",
            "current_round": 1,
            "max_rounds": 3,
            "errors": [],
            "test_results": {
                "patch-A": {"status": "failed", "passed": False},
                "patch-B": {"status": "passed", "passed": True},
            },
        }
        decision = evaluate_round_outcome(state)
        assert decision == RoutingDecision.FINISH_SUCCESS
        assert route_after_judging(state) == "finalize_success"

    def test_routing_retry_when_both_fail_under_max_rounds(self):
        state = {
            "session_id": "session-1",
            "current_round": 1,
            "max_rounds": 3,
            "errors": [],
            "test_results": {
                "patch-A": {"status": "failed", "passed": False},
                "patch-B": {"status": "timeout", "passed": False},
            },
        }
        decision = evaluate_round_outcome(state)
        assert decision == RoutingDecision.RETRY_ROUND
        assert route_after_judging(state) == "record_constraints_and_retry"

    def test_routing_fail_when_max_rounds_reached(self):
        state = {
            "session_id": "session-1",
            "current_round": 3,
            "max_rounds": 3,
            "errors": [],
            "test_results": {
                "patch-A": {"status": "failed", "passed": False},
                "patch-B": {"status": "failed", "passed": False},
            },
        }
        decision = evaluate_round_outcome(state)
        assert decision == RoutingDecision.MAX_ROUNDS_EXCEEDED
        assert route_after_judging(state) == "finalize_failure"

    def test_missing_test_results_never_treated_as_success(self):
        state = {
            "session_id": "session-1",
            "current_round": 1,
            "max_rounds": 3,
            "errors": [],
            "test_results": {},
        }
        # Incomplete round should retry rather than succeed
        decision = evaluate_round_outcome(state)
        assert decision == RoutingDecision.RETRY_ROUND

    def test_routing_error_termination(self):
        state = {
            "session_id": "session-1",
            "current_round": 1,
            "max_rounds": 3,
            "errors": ["Fatal environment error"],
            "test_results": {},
        }
        decision = evaluate_round_outcome(state)
        assert decision == RoutingDecision.TERMINATE_ERROR
        assert route_after_judging(state) == "finalize_failure"


class TestWorkflowGraphScaffolding:
    def test_node_executions_and_state_updates(self):
        session = DebugSession(
            original_code="code",
            bug_description="desc",
        )
        state = create_initial_workflow_state(session, max_rounds=2)
        scaffolding = WorkflowGraphScaffolding()

        # Step 1: Intake
        state = scaffolding.intake_session_node(state)
        assert state["status"] == "investigating"

        # Step 2: Prosecutor
        state = scaffolding.prosecutor_node(state)
        assert "Prosecutor node activated" in state["audit_log"][-1]

        # Step 3: Defender
        state = scaffolding.defender_node(state)
        assert "Defender node activated" in state["audit_log"][-1]

        # Step 4: Execute candidates
        state = scaffolding.execute_candidates_node(state)
        assert state["status"] == "evaluating"

        # Step 5: Judge
        state = scaffolding.judge_node(state)
        assert state["status"] == "judging"

        # Step 6: Retry increment
        assert state["current_round"] == 1
        state = scaffolding.record_constraints_and_retry_node(state)
        assert state["current_round"] == 2

        # Step 7: Finalize failure
        state = scaffolding.finalize_failure_node(state)
        assert state["status"] == "max_rounds_reached"

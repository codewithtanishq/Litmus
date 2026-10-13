"""
LangGraph workflow orchestration scaffolding for Swarm Debugger.

Defines the planned nodes, edges, conditional transitions, and execution graph.

Architecture:
  [Intake Session]
         │
         ▼
  [Prosecutor (Fix A)]
         │
         ▼
  [Defender (Fix B)]
         │
         ▼
  [Execute Candidates (Member 2 Sandbox)]
         │
         ▼
  [Evaluate Tests (Member 2 Evaluator)]
         │
         ▼
  [Judge Verdict]
         │
         ▼
  <Conditional Router>
     ├── (Test Passed) ───────────────► [Finalize Success]
     ├── (All Failed & Round < Max) ──► [Record Constraints] ──► (Loop back to Prosecutor)
     └── (All Failed & Round >= Max) ─► [Finalize Failure]
"""

from typing import Any, Dict, List, Optional
import logging

from app.orchestration.state import WorkflowState
from app.orchestration.routing import route_after_judging, RoutingDecision, evaluate_round_outcome
from app.schemas.events import WorkflowEventType
from app.events.publisher import get_event_publisher

logger = logging.getLogger(__name__)

# Registry of planned nodes and documentation
PLANNED_NODES: List[Dict[str, str]] = [
    {
        "name": "intake_session",
        "owner": "Member 1",
        "description": "Initializes workflow state and publishes SESSION_STARTED event.",
    },
    {
        "name": "prosecutor",
        "owner": "Member 1",
        "description": "Prosecutor analyzes bug description, original code, and prior constraints to propose Fix A.",
    },
    {
        "name": "defender",
        "owner": "Member 1",
        "description": "Defender critiques Prosecutor's diagnosis and independently proposes Fix B.",
    },
    {
        "name": "execute_candidates",
        "owner": "Member 2 Interface",
        "description": "Passes candidate patches to sandbox for isolated execution.",
    },
    {
        "name": "evaluate_tests",
        "owner": "Member 2 Interface",
        "description": "Parses execution evidence into deterministic TestResult records.",
    },
    {
        "name": "judge",
        "owner": "Member 1",
        "description": "Judge compares empirical test results and synthesizes courtroom verdict.",
    },
    {
        "name": "record_constraints_and_retry",
        "owner": "Member 2 Interface + Member 1 Orchestration",
        "description": "Persists rejected fixes into Constraint Ledger, increments round counter, and loops.",
    },
    {
        "name": "finalize_success",
        "owner": "Member 1",
        "description": "Marks session as RESOLVED and emits SESSION_COMPLETED event.",
    },
    {
        "name": "finalize_failure",
        "owner": "Member 1",
        "description": "Marks session as FAILED / MAX_ROUNDS_REACHED and emits SESSION_FAILED event.",
    },
]

PLANNED_EDGES: List[Dict[str, str]] = [
    {"from": "intake_session", "to": "prosecutor", "type": "direct"},
    {"from": "prosecutor", "to": "defender", "type": "direct"},
    {"from": "defender", "to": "execute_candidates", "type": "direct"},
    {"from": "execute_candidates", "to": "evaluate_tests", "type": "direct"},
    {"from": "evaluate_tests", "to": "judge", "type": "direct"},
    {"from": "judge", "to": "conditional_router", "type": "conditional"},
    {"from": "record_constraints_and_retry", "to": "prosecutor", "type": "loop"},
]


class WorkflowGraphScaffolding:
    """
    Scaffolding for the LangGraph courtroom workflow.
    Defines architectural node handlers and validates state transitions.
    """

    def __init__(self) -> None:
        self.publisher = get_event_publisher()

    def intake_session_node(self, state: WorkflowState) -> WorkflowState:
        """Intake node: registers session and publishes session_started event."""
        session_id = state["session_id"]
        round_no = state.get("current_round", 1)
        self.publisher.emit(
            event_type=WorkflowEventType.SESSION_STARTED,
            session_id=session_id,
            round_number=round_no,
            data={"bug_description": state.get("bug_description", "")},
        )
        state["status"] = "investigating"
        state.setdefault("audit_log", []).append(f"Session {session_id} entered intake.")
        return state

    def prosecutor_node(self, state: WorkflowState) -> WorkflowState:
        """
        Prosecutor node scaffolding:
        Prepares state for Prosecutor agent prompt execution.
        """
        session_id = state["session_id"]
        round_no = state.get("current_round", 1)
        self.publisher.emit(
            event_type=WorkflowEventType.AGENT_STARTED,
            session_id=session_id,
            round_number=round_no,
            data={"agent_role": "prosecutor"},
        )
        state.setdefault("audit_log", []).append(f"Round {round_no}: Prosecutor node activated.")
        return state

    def defender_node(self, state: WorkflowState) -> WorkflowState:
        """
        Defender node scaffolding:
        Prepares state for Defender agent prompt execution.
        """
        session_id = state["session_id"]
        round_no = state.get("current_round", 1)
        self.publisher.emit(
            event_type=WorkflowEventType.AGENT_STARTED,
            session_id=session_id,
            round_number=round_no,
            data={"agent_role": "defender"},
        )
        state.setdefault("audit_log", []).append(f"Round {round_no}: Defender node activated.")
        return state

    def execute_candidates_node(self, state: WorkflowState) -> WorkflowState:
        """
        Scaffolding boundary interface for Member 2's sandbox execution.
        """
        session_id = state["session_id"]
        round_no = state.get("current_round", 1)
        self.publisher.emit(
            event_type=WorkflowEventType.EXECUTION_STARTED,
            session_id=session_id,
            round_number=round_no,
            data={"candidates": list(state.get("candidate_patches", {}).keys())},
        )
        state["status"] = "evaluating"
        state.setdefault("audit_log", []).append(f"Round {round_no}: Execution initiated in sandbox.")
        return state

    def evaluate_tests_node(self, state: WorkflowState) -> WorkflowState:
        """
        Scaffolding boundary interface for Member 2's deterministic test evaluation.
        """
        session_id = state["session_id"]
        round_no = state.get("current_round", 1)
        self.publisher.emit(
            event_type=WorkflowEventType.TESTS_COMPLETED,
            session_id=session_id,
            round_number=round_no,
            data={"results_count": len(state.get("test_results", {}))},
        )
        state.setdefault("audit_log", []).append(f"Round {round_no}: Test evaluation completed.")
        return state

    def judge_node(self, state: WorkflowState) -> WorkflowState:
        """
        Judge node scaffolding:
        Prepares state for Judge agent to produce empirical verdict.
        """
        session_id = state["session_id"]
        round_no = state.get("current_round", 1)
        state["status"] = "judging"
        self.publisher.emit(
            event_type=WorkflowEventType.VERDICT_CREATED,
            session_id=session_id,
            round_number=round_no,
            data={"verdict_pending": True},
        )
        state.setdefault("audit_log", []).append(f"Round {round_no}: Judge deliberation activated.")
        return state

    def record_constraints_and_retry_node(self, state: WorkflowState) -> WorkflowState:
        """
        Scaffolding boundary interface for Member 2's Constraint Ledger persistence.
        Increments round and loops back for next debate round.
        """
        session_id = state["session_id"]
        old_round = state.get("current_round", 1)
        new_round = old_round + 1
        state["current_round"] = new_round

        self.publisher.emit(
            event_type=WorkflowEventType.CONSTRAINT_RECORDED,
            session_id=session_id,
            round_number=old_round,
            data={"reason": "Both candidate patches failed in round"},
        )
        self.publisher.emit(
            event_type=WorkflowEventType.RETRY_STARTED,
            session_id=session_id,
            round_number=new_round,
            data={"previous_round": old_round},
        )
        state.setdefault("audit_log", []).append(
            f"Constraint recorded for round {old_round}. Transitioning to round {new_round}."
        )
        return state

    def finalize_success_node(self, state: WorkflowState) -> WorkflowState:
        """Finalizes workflow when a successful patch is verified."""
        session_id = state["session_id"]
        round_no = state.get("current_round", 1)
        state["status"] = "resolved"
        self.publisher.emit(
            event_type=WorkflowEventType.SESSION_COMPLETED,
            session_id=session_id,
            round_number=round_no,
            data={"status": "resolved"},
        )
        state.setdefault("audit_log", []).append(f"Session {session_id} successfully resolved.")
        return state

    def finalize_failure_node(self, state: WorkflowState) -> WorkflowState:
        """Finalizes workflow when all attempts fail or max rounds are exhausted."""
        session_id = state["session_id"]
        round_no = state.get("current_round", 1)
        max_rounds = state.get("max_rounds", 3)
        final_status = "max_rounds_reached" if round_no >= max_rounds else "failed"
        state["status"] = final_status
        self.publisher.emit(
            event_type=WorkflowEventType.SESSION_FAILED,
            session_id=session_id,
            round_number=round_no,
            data={"status": final_status},
        )
        state.setdefault("audit_log", []).append(f"Session {session_id} terminated with status {final_status}.")
        return state


def build_courtroom_workflow():
    """
    Builds the workflow graph definition.
    If 'langgraph' is installed, compiles and returns a LangGraph StateGraph.
    Otherwise, returns the WorkflowGraphScaffolding instance.
    """
    scaffolding = WorkflowGraphScaffolding()

    try:
        from langgraph.graph import StateGraph, END  # type: ignore

        graph_builder = StateGraph(WorkflowState)

        # Register nodes
        graph_builder.add_node("intake_session", scaffolding.intake_session_node)
        graph_builder.add_node("prosecutor", scaffolding.prosecutor_node)
        graph_builder.add_node("defender", scaffolding.defender_node)
        graph_builder.add_node("execute_candidates", scaffolding.execute_candidates_node)
        graph_builder.add_node("evaluate_tests", scaffolding.evaluate_tests_node)
        graph_builder.add_node("judge", scaffolding.judge_node)
        graph_builder.add_node("record_constraints_and_retry", scaffolding.record_constraints_and_retry_node)
        graph_builder.add_node("finalize_success", scaffolding.finalize_success_node)
        graph_builder.add_node("finalize_failure", scaffolding.finalize_failure_node)

        # Set entry point
        graph_builder.set_entry_point("intake_session")

        # Define deterministic sequential transitions
        graph_builder.add_edge("intake_session", "prosecutor")
        graph_builder.add_edge("prosecutor", "defender")
        graph_builder.add_edge("defender", "execute_candidates")
        graph_builder.add_edge("execute_candidates", "evaluate_tests")
        graph_builder.add_edge("evaluate_tests", "judge")

        # Define conditional transition after judging
        graph_builder.add_conditional_edges(
            "judge",
            route_after_judging,
            {
                "finalize_success": "finalize_success",
                "record_constraints_and_retry": "record_constraints_and_retry",
                "finalize_failure": "finalize_failure",
            },
        )

        # Loop back from retry to prosecutor
        graph_builder.add_edge("record_constraints_and_retry", "prosecutor")

        # Terminal edges
        graph_builder.add_edge("finalize_success", END)
        graph_builder.add_edge("finalize_failure", END)

        return graph_builder.compile()

    except ImportError:
        logger.info("LangGraph is not installed in the current environment; using WorkflowGraphScaffolding.")
        return scaffolding

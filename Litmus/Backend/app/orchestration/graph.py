"""
LangGraph workflow orchestration for Swarm Debugger.

Connects the Prosecutor and Defender AI agents into an orchestrated execution graph
leading to the evaluation integration boundary for Member 2's sandbox runner.

Execution Flow for Prompt 3:
  [Intake Session Node]
         │ (route_after_intake)
         ▼
  [Prosecutor Node: Propose Fix A]
         │ (route_after_prosecutor: success -> defender, error -> finalize_failure)
         ▼
  [Defender Node: Critique & Propose Fix B]
         │ (route_after_defender: success -> evaluation_boundary, error -> finalize_failure)
         ▼
  [Evaluation Integration Boundary Node]
         │ (ready for Member 2 sandbox & deterministic evaluator)
         ▼
       [END]
"""

from typing import Any, Dict, List, Optional
import logging

from app.orchestration.state import WorkflowState
from app.orchestration.routing import (
    route_after_intake,
    route_after_prosecutor,
    route_after_defender,
    route_after_judging,
    RoutingDecision,
    evaluate_round_outcome,
)
from app.agents.prosecutor import ProsecutorAgent
from app.agents.defender import DefenderAgent
from app.schemas.session import DebugSession
from app.schemas.patch import CandidatePatch, AgentRole
from app.schemas.interfaces import IConstraintLedger, ConstraintRecord
from app.schemas.events import WorkflowEventType
from app.events.publisher import get_event_publisher, BaseEventPublisher

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
        "name": "evaluation_boundary",
        "owner": "Member 1 (Boundary) / Member 2 (Destination)",
        "description": "Validates both Fix A and Fix B are complete and signals readiness for Member 2 sandbox execution.",
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
    {"from": "intake_session", "to": "prosecutor", "type": "conditional"},
    {"from": "prosecutor", "to": "defender", "type": "conditional"},
    {"from": "defender", "to": "evaluation_boundary", "type": "conditional"},
    {"from": "evaluation_boundary", "to": "execute_candidates", "type": "boundary"},
    {"from": "execute_candidates", "to": "evaluate_tests", "type": "direct"},
    {"from": "evaluate_tests", "to": "judge", "type": "direct"},
    {"from": "judge", "to": "conditional_router", "type": "conditional"},
    {"from": "record_constraints_and_retry", "to": "prosecutor", "type": "loop"},
]


class CourtroomWorkflow:
    """
    Workflow engine managing node execution and state transitions.
    Supports dependency injection for agents, constraint ledger, and event publisher.
    """

    def __init__(
        self,
        prosecutor_agent: Optional[ProsecutorAgent] = None,
        defender_agent: Optional[DefenderAgent] = None,
        constraint_ledger: Optional[IConstraintLedger] = None,
        event_publisher: Optional[BaseEventPublisher] = None,
    ) -> None:
        self.publisher = event_publisher or get_event_publisher()
        self.prosecutor_agent = prosecutor_agent or ProsecutorAgent(event_publisher=self.publisher)
        self.defender_agent = defender_agent or DefenderAgent(event_publisher=self.publisher)
        self.constraint_ledger = constraint_ledger

    def intake_session_node(self, state: WorkflowState) -> WorkflowState:
        """
        Intake node: validates input, registers session, and publishes session_started event.
        """
        session_id = state.get("session_id", "")
        round_no = state.get("current_round", 1)
        original_code = state.get("original_code", "")
        bug_description = state.get("bug_description", "")

        # Input validation
        if not original_code or not bug_description:
            err = "Invalid input: original_code and bug_description must not be empty."
            logger.error(err)
            state.setdefault("errors", []).append(err)
            state["status"] = "failed"
            self.publisher.emit(
                event_type=WorkflowEventType.SESSION_FAILED,
                session_id=session_id,
                round_number=round_no,
                data={"error": err},
            )
            state.setdefault("audit_log", []).append(f"Session {session_id} intake rejected: {err}")
            return state

        self.publisher.emit(
            event_type=WorkflowEventType.SESSION_STARTED,
            session_id=session_id,
            round_number=round_no,
            data={"bug_description": bug_description},
        )
        state["status"] = "investigating"
        state.setdefault("audit_log", []).append(f"Session {session_id} entered intake.")
        return state

    def prosecutor_node(self, state: WorkflowState) -> WorkflowState:
        """
        Prosecutor node:
        Retrieves active constraints from Member 2's Constraint Ledger,
        invokes ProsecutorAgent to diagnose the bug, and stores Fix A.
        """
        if state.get("errors") and len(state["errors"]) > 0:
            return state

        session_id = state.get("session_id", "")
        round_no = state.get("current_round", 1)
        original_code = state.get("original_code", "")
        bug_description = state.get("bug_description", "")
        test_suite = state.get("test_suite", "")

        state.setdefault("audit_log", []).append(f"Round {round_no}: Prosecutor node activated.")

        # Retrieve active constraints from Member 2 ledger
        constraints: List[ConstraintRecord] = []
        if self.constraint_ledger is not None:
            try:
                constraints = self.constraint_ledger.get_active_constraints(session_id) or []
            except Exception as exc:
                logger.warning(f"Failed to query Constraint Ledger for session {session_id}: {exc}")
                constraints = []

        try:
            session = DebugSession(
                session_id=session_id,
                original_code=original_code,
                bug_description=bug_description,
                test_suite=test_suite,
                current_round=round_no,
            )

            patch = self.prosecutor_agent.analyze_and_propose(
                session=session,
                constraints=constraints,
                round_number=round_no,
            )

            # Store validated Fix A
            patch_dict = patch.model_dump()
            state.setdefault("candidate_patches", {})["prosecutor"] = patch_dict
            state["fix_a"] = patch_dict
            state.setdefault("audit_log", []).append(
                f"Round {round_no}: Prosecutor successfully proposed Fix A (patch_id: {patch.patch_id})."
            )

        except Exception as exc:
            err_msg = f"Prosecutor agent failed: {exc}"
            logger.error(err_msg, exc_info=True)
            state.setdefault("errors", []).append(err_msg)
            state.setdefault("agent_errors", {})["prosecutor"] = str(exc)
            state["status"] = "failed"
            self.publisher.emit(
                event_type=WorkflowEventType.SESSION_FAILED,
                session_id=session_id,
                round_number=round_no,
                data={"agent_role": AgentRole.PROSECUTOR.value, "error": str(exc)},
            )
            state.setdefault("audit_log", []).append(f"Round {round_no}: {err_msg}")

        return state

    def defender_node(self, state: WorkflowState) -> WorkflowState:
        """
        Defender node:
        Critically evaluates Fix A from the Prosecutor, formulates an adversarial
        critique, and generates Candidate Patch B.
        """
        if state.get("errors") and len(state["errors"]) > 0:
            return state

        session_id = state.get("session_id", "")
        round_no = state.get("current_round", 1)
        original_code = state.get("original_code", "")
        bug_description = state.get("bug_description", "")
        test_suite = state.get("test_suite", "")

        state.setdefault("audit_log", []).append(f"Round {round_no}: Defender node activated.")

        fix_a_data = state.get("fix_a") or state.get("candidate_patches", {}).get("prosecutor")
        if not fix_a_data:
            err_msg = "Defender failed: Fix A is missing; Defender cannot critique without Fix A from Prosecutor."
            logger.error(err_msg)
            state.setdefault("errors", []).append(err_msg)
            state.setdefault("agent_errors", {})["defender"] = err_msg
            state["status"] = "failed"
            self.publisher.emit(
                event_type=WorkflowEventType.SESSION_FAILED,
                session_id=session_id,
                round_number=round_no,
                data={"agent_role": AgentRole.DEFENDER.value, "error": err_msg},
            )
            state.setdefault("audit_log", []).append(f"Round {round_no}: {err_msg}")
            return state

        # Deserialize Fix A
        if isinstance(fix_a_data, dict):
            prosecutor_patch = CandidatePatch(**fix_a_data)
        else:
            prosecutor_patch = fix_a_data

        # Retrieve active constraints
        constraints: List[ConstraintRecord] = []
        if self.constraint_ledger is not None:
            try:
                constraints = self.constraint_ledger.get_active_constraints(session_id) or []
            except Exception as exc:
                logger.warning(f"Failed to query Constraint Ledger for session {session_id}: {exc}")
                constraints = []

        try:
            session = DebugSession(
                session_id=session_id,
                original_code=original_code,
                bug_description=bug_description,
                test_suite=test_suite,
                current_round=round_no,
            )

            patch = self.defender_agent.critique_and_propose(
                session=session,
                prosecutor_patch=prosecutor_patch,
                constraints=constraints,
                round_number=round_no,
            )

            # Store validated Fix B
            patch_dict = patch.model_dump()
            state.setdefault("candidate_patches", {})["defender"] = patch_dict
            state["fix_b"] = patch_dict
            state.setdefault("audit_log", []).append(
                f"Round {round_no}: Defender successfully proposed Fix B (patch_id: {patch.patch_id})."
            )

        except Exception as exc:
            err_msg = f"Defender agent failed: {exc}"
            logger.error(err_msg, exc_info=True)
            state.setdefault("errors", []).append(err_msg)
            state.setdefault("agent_errors", {})["defender"] = str(exc)
            state["status"] = "failed"
            self.publisher.emit(
                event_type=WorkflowEventType.SESSION_FAILED,
                session_id=session_id,
                round_number=round_no,
                data={"agent_role": AgentRole.DEFENDER.value, "error": str(exc)},
            )
            state.setdefault("audit_log", []).append(f"Round {round_no}: {err_msg}")

        return state

    def evaluation_boundary_node(self, state: WorkflowState) -> WorkflowState:
        """
        Evaluation integration boundary:
        Confirms both candidate patches (Fix A and Fix B) are validated and ready
        for Member 2's sandbox execution and deterministic evaluation.
        Does NOT claim that any test passed or fabricate results.
        """
        session_id = state.get("session_id", "")
        round_no = state.get("current_round", 1)
        fix_a = state.get("fix_a")
        fix_b = state.get("fix_b")

        if not fix_a or not fix_b:
            err_msg = "Evaluation boundary error: Missing Candidate Patch A or B."
            logger.error(err_msg)
            state.setdefault("errors", []).append(err_msg)
            state["status"] = "failed"
            return state

        state["status"] = "evaluating"
        self.publisher.emit(
            event_type=WorkflowEventType.EXECUTION_STARTED,
            session_id=session_id,
            round_number=round_no,
            data={
                "candidates_ready": ["prosecutor", "defender"],
                "ready_for_evaluation": True,
                "fix_a_id": fix_a.get("patch_id"),
                "fix_b_id": fix_b.get("patch_id"),
            },
        )
        state.setdefault("audit_log", []).append(
            f"Round {round_no}: Evaluation boundary reached. Candidate Patch A and Candidate Patch B "
            f"are validated and ready for Member 2 sandbox execution and deterministic evaluation."
        )
        return state

    def finalize_failure_node(self, state: WorkflowState) -> WorkflowState:
        """
        Finalizes workflow when an agent or session fails.
        """
        session_id = state.get("session_id", "")
        round_no = state.get("current_round", 1)
        max_rounds = state.get("max_rounds", 3)
        final_status = "max_rounds_reached" if round_no >= max_rounds and not state.get("errors") else "failed"
        state["status"] = final_status

        self.publisher.emit(
            event_type=WorkflowEventType.SESSION_FAILED,
            session_id=session_id,
            round_number=round_no,
            data={"status": final_status, "errors": state.get("errors", [])},
        )
        state.setdefault("audit_log", []).append(
            f"Session {session_id} terminated with status {final_status}."
        )
        return state

    # --- Backward compatibility scaffolding methods for full courtroom lifecycle ---

    def execute_candidates_node(self, state: WorkflowState) -> WorkflowState:
        return self.evaluation_boundary_node(state)

    def evaluate_tests_node(self, state: WorkflowState) -> WorkflowState:
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


# Alias for backwards compatibility with Prompt 1 imports
WorkflowGraphScaffolding = CourtroomWorkflow


def build_courtroom_workflow(
    prosecutor_agent: Optional[ProsecutorAgent] = None,
    defender_agent: Optional[DefenderAgent] = None,
    constraint_ledger: Optional[IConstraintLedger] = None,
    event_publisher: Optional[BaseEventPublisher] = None,
):
    """
    Builds and compiles the LangGraph workflow graph for Prompt 3.
    Flow: intake_session -> prosecutor -> defender -> evaluation_boundary -> END.
    Handles conditional error routing to finalize_failure.
    """
    workflow = CourtroomWorkflow(
        prosecutor_agent=prosecutor_agent,
        defender_agent=defender_agent,
        constraint_ledger=constraint_ledger,
        event_publisher=event_publisher,
    )

    from langgraph.graph import StateGraph, START, END

    builder = StateGraph(WorkflowState)

    # Register nodes
    builder.add_node("intake_session", workflow.intake_session_node)
    builder.add_node("prosecutor", workflow.prosecutor_node)
    builder.add_node("defender", workflow.defender_node)
    builder.add_node("evaluation_boundary", workflow.evaluation_boundary_node)
    builder.add_node("finalize_failure", workflow.finalize_failure_node)

    # Entry point
    builder.add_edge(START, "intake_session")

    # Conditional edge: intake_session -> prosecutor or finalize_failure
    builder.add_conditional_edges(
        "intake_session",
        route_after_intake,
        {
            "prosecutor": "prosecutor",
            "finalize_failure": "finalize_failure",
        },
    )

    # Conditional edge: prosecutor -> defender or finalize_failure
    builder.add_conditional_edges(
        "prosecutor",
        route_after_prosecutor,
        {
            "defender": "defender",
            "finalize_failure": "finalize_failure",
        },
    )

    # Conditional edge: defender -> evaluation_boundary or finalize_failure
    builder.add_conditional_edges(
        "defender",
        route_after_defender,
        {
            "evaluation_boundary": "evaluation_boundary",
            "finalize_failure": "finalize_failure",
        },
    )

    # Terminal edges
    builder.add_edge("evaluation_boundary", END)
    builder.add_edge("finalize_failure", END)

    return builder.compile()

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
from app.agents.judge import JudgeAgent
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
        judge_agent: Optional[JudgeAgent] = None,
        constraint_ledger: Optional[Any] = None,
        event_publisher: Optional[BaseEventPublisher] = None,
        sandbox_runner: Optional[Any] = None,
        test_evaluator: Optional[Any] = None,
    ) -> None:
        self.publisher = event_publisher or get_event_publisher()
        self.prosecutor_agent = prosecutor_agent or ProsecutorAgent(event_publisher=self.publisher)
        self.defender_agent = defender_agent or DefenderAgent(event_publisher=self.publisher)
        self.judge_agent = judge_agent or JudgeAgent(event_publisher=self.publisher)
        self.constraint_ledger = constraint_ledger
        self.sandbox_runner = sandbox_runner
        self.test_evaluator = test_evaluator

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

    # --- Full courtroom lifecycle nodes ---

    def execute_candidates_node(self, state: WorkflowState) -> WorkflowState:
        """
        Executes Candidate Fix A and Candidate Fix B in separate, isolated workspaces
        against the trusted test suite using the sandbox runner.
        Never runs Fix A in Fix B's workspace or allows environment leakage.
        Handles SandboxUnavailableError as INFRASTRUCTURE_ERROR without crashing.
        """
        session_id = state.get("session_id", "")
        round_no = state.get("current_round", 1)
        trusted_tests = state.get("test_suite", "")
        fix_a = state.get("fix_a") or {}
        fix_b = state.get("fix_b") or {}
        state["status"] = "evaluating"

        code_a = fix_a.get("proposed_code", "") if isinstance(fix_a, dict) else getattr(fix_a, "proposed_code", "")
        code_b = fix_b.get("proposed_code", "") if isinstance(fix_b, dict) else getattr(fix_b, "proposed_code", "")

        cid_a = fix_a.get("patch_id", f"candidate_a_r{round_no}") if isinstance(fix_a, dict) else getattr(fix_a, "patch_id", f"candidate_a_r{round_no}")
        cid_b = fix_b.get("patch_id", f"candidate_b_r{round_no}") if isinstance(fix_b, dict) else getattr(fix_b, "patch_id", f"candidate_b_r{round_no}")

        self.publisher.emit(
            event_type=WorkflowEventType.EXECUTION_STARTED,
            session_id=session_id,
            round_number=round_no,
            data={
                "candidate_ids": [cid_a, cid_b],
                "prosecutor_id": cid_a,
                "defender_id": cid_b,
            },
        )

        state.setdefault("audit_log", []).append(
            f"Round {round_no}: Beginning isolated execution of Fix A ({cid_a}) and Fix B ({cid_b})."
        )

        runner = self.sandbox_runner
        if runner is None:
            from app.sandbox.runner import run_candidate
            runner = run_candidate

        from app.contracts import ExecutionEvidence, ExecutionStatus
        from app.sandbox.runner import SandboxUnavailableError

        # Execute Fix A in isolated workspace
        try:
            ev_a = runner(
                source_code=code_a,
                trusted_tests=trusted_tests,
                candidate_id=cid_a,
            )
        except SandboxUnavailableError as err:
            logger.warning(f"Sandbox unavailable for Fix A ({cid_a}): {err}")
            ev_a = ExecutionEvidence(
                candidate_id=cid_a,
                status=ExecutionStatus.INFRASTRUCTURE_ERROR,
                error_detail=str(err),
            )
        except Exception as err:
            logger.error(f"Execution failed for Fix A ({cid_a}): {err}", exc_info=True)
            ev_a = ExecutionEvidence(
                candidate_id=cid_a,
                status=ExecutionStatus.INFRASTRUCTURE_ERROR,
                error_detail=str(err),
            )

        # Execute Fix B in separate isolated workspace (no leakage)
        try:
            ev_b = runner(
                source_code=code_b,
                trusted_tests=trusted_tests,
                candidate_id=cid_b,
            )
        except SandboxUnavailableError as err:
            logger.warning(f"Sandbox unavailable for Fix B ({cid_b}): {err}")
            ev_b = ExecutionEvidence(
                candidate_id=cid_b,
                status=ExecutionStatus.INFRASTRUCTURE_ERROR,
                error_detail=str(err),
            )
        except Exception as err:
            logger.error(f"Execution failed for Fix B ({cid_b}): {err}", exc_info=True)
            ev_b = ExecutionEvidence(
                candidate_id=cid_b,
                status=ExecutionStatus.INFRASTRUCTURE_ERROR,
                error_detail=str(err),
            )

        evidence_dict = {
            "prosecutor": ev_a,
            "defender": ev_b,
            cid_a: ev_a,
            cid_b: ev_b,
        }
        state["execution_evidence"] = evidence_dict
        state.setdefault("audit_log", []).append(
            f"Round {round_no}: Candidate execution completed. Fix A: {ev_a.status.value}, Fix B: {ev_b.status.value}."
        )
        return state

    def evaluate_tests_node(self, state: WorkflowState) -> WorkflowState:
        """
        Deterministically evaluates raw execution evidence into structured TestResults.
        Strictly relies on deterministic evaluation (JUnit XML / test execution facts).
        Never invents or fabricates results.
        """
        session_id = state.get("session_id", "")
        round_no = state.get("current_round", 1)
        evidence_dict = state.get("execution_evidence", {})

        evaluator = self.test_evaluator
        if evaluator is None:
            from app.evaluation.test_evaluator import evaluate_candidate
            evaluator = evaluate_candidate

        ev_a = evidence_dict.get("prosecutor")
        ev_b = evidence_dict.get("defender")

        results = {}
        if ev_a is not None:
            res_a = evaluator(evidence=ev_a, session_id=session_id)
            results["prosecutor"] = res_a
            results[ev_a.candidate_id] = res_a
        if ev_b is not None:
            res_b = evaluator(evidence=ev_b, session_id=session_id)
            results["defender"] = res_b
            results[ev_b.candidate_id] = res_b

        state["test_results"] = results

        self.publisher.emit(
            event_type=WorkflowEventType.TESTS_COMPLETED,
            session_id=session_id,
            round_number=round_no,
            data={
                "results_count": len(results),
                "prosecutor_status": getattr(results.get("prosecutor"), "status", None),
                "defender_status": getattr(results.get("defender"), "status", None),
            },
        )
        state.setdefault("audit_log", []).append(
            f"Round {round_no}: Deterministic test evaluation completed. "
            f"Fix A: {getattr(results.get('prosecutor'), 'status', 'N/A')}, "
            f"Fix B: {getattr(results.get('defender'), 'status', 'N/A')}."
        )
        return state

    def judge_node(self, state: WorkflowState) -> WorkflowState:
        """
        Synthesizes an empirical, evidence-grounded courtroom verdict.
        Judge receives actual test evidence and explains results without contradicting facts.
        """
        session_id = state.get("session_id", "")
        round_no = state.get("current_round", 1)
        state["status"] = "judging"

        session = DebugSession(
            session_id=session_id,
            original_code=state.get("original_code", ""),
            bug_description=state.get("bug_description", ""),
            test_suite=state.get("test_suite", ""),
            current_round=round_no,
        )

        fix_a = state.get("fix_a")
        fix_b = state.get("fix_b")
        prosecutor_patch = CandidatePatch(**fix_a) if isinstance(fix_a, dict) else fix_a
        defender_patch = CandidatePatch(**fix_b) if isinstance(fix_b, dict) else fix_b

        verdict = self.judge_agent.evaluate_verdict(
            session=session,
            prosecutor_patch=prosecutor_patch,
            defender_patch=defender_patch,
            test_results=state.get("test_results", {}),
            round_number=round_no,
        )

        state["verdict"] = verdict.model_dump() if hasattr(verdict, "model_dump") else verdict
        decision_val = verdict.decision.value if hasattr(verdict.decision, "value") else str(verdict.decision)
        state.setdefault("audit_log", []).append(
            f"Round {round_no}: Judge delivered verdict: {decision_val} "
            f"(Winner: {verdict.winning_patch_id})."
        )
        return state

    def record_constraints_and_retry_node(self, state: WorkflowState) -> WorkflowState:
        """
        Records failure evidence from rejected candidates into the Constraint Ledger,
        increments the round counter, clears round-specific artifacts, and prepares for next retry.
        """
        session_id = state.get("session_id", "")
        old_round = state.get("current_round", 1)
        test_results = state.get("test_results", {})
        fix_a = state.get("fix_a") or {}
        fix_b = state.get("fix_b") or {}

        # Record failure constraints in ledger if available
        if self.constraint_ledger is not None:
            from app.contracts import (
                CandidatePatch as ContractCandidatePatch,
                DebugSession as ContractDebugSession,
                ExecutionStatus,
            )

            repo = getattr(self.constraint_ledger, "_repo", None)
            if repo is not None:
                try:
                    if repo.get_session(session_id) is None:
                        repo.create_session(
                            ContractDebugSession(
                                session_id=session_id,
                                bug_description=state.get("bug_description", "Bug report"),
                                original_source=state.get("original_code", ""),
                                trusted_tests=state.get("test_suite", ""),
                                max_rounds=state.get("max_rounds", 3),
                            )
                        )
                except Exception as exc:
                    logger.debug(f"Session save note: {exc}")

            # Fix A failure check
            res_a = test_results.get("prosecutor") or test_results.get(fix_a.get("patch_id"))
            if res_a is not None and getattr(res_a, "status", None) == ExecutionStatus.FAILED:
                cand_a = ContractCandidatePatch(
                    candidate_id=fix_a.get("patch_id", f"candidate_a_r{old_round}"),
                    session_id=session_id,
                    agent="prosecutor",
                    round_number=old_round,
                    source_code=fix_a.get("proposed_code", ""),
                    explanation=fix_a.get("explanation", ""),
                )
                if repo is not None:
                    try:
                        if repo.get_candidate(cand_a.candidate_id) is None:
                            repo.save_candidate(cand_a)
                        if repo.get_test_result(res_a.result_id) is None:
                            repo.save_test_result(res_a)
                    except Exception as exc:
                        logger.debug(f"Candidate/Result save note: {exc}")

                if hasattr(self.constraint_ledger, "record_failure"):
                    try:
                        self.constraint_ledger.record_failure(cand_a, res_a)
                    except Exception as exc:
                        logger.warning(f"Failed to record Fix A failure in ledger: {exc}")

            # Fix B failure check
            res_b = test_results.get("defender") or test_results.get(fix_b.get("patch_id"))
            if res_b is not None and getattr(res_b, "status", None) == ExecutionStatus.FAILED:
                cand_b = ContractCandidatePatch(
                    candidate_id=fix_b.get("patch_id", f"candidate_b_r{old_round}"),
                    session_id=session_id,
                    agent="defender",
                    round_number=old_round,
                    source_code=fix_b.get("proposed_code", ""),
                    explanation=fix_b.get("explanation", ""),
                )
                if repo is not None:
                    try:
                        if repo.get_candidate(cand_b.candidate_id) is None:
                            repo.save_candidate(cand_b)
                        if repo.get_test_result(res_b.result_id) is None:
                            repo.save_test_result(res_b)
                    except Exception as exc:
                        logger.debug(f"Candidate/Result save note: {exc}")

                if hasattr(self.constraint_ledger, "record_failure"):
                    try:
                        self.constraint_ledger.record_failure(cand_b, res_b)
                    except Exception as exc:
                        logger.warning(f"Failed to record Fix B failure in ledger: {exc}")

        new_round = old_round + 1
        state["current_round"] = new_round

        self.publisher.emit(
            event_type=WorkflowEventType.CONSTRAINT_RECORDED,
            session_id=session_id,
            round_number=old_round,
            data={"reason": "Candidate patches evaluated and constraints recorded", "round": old_round},
        )
        self.publisher.emit(
            event_type=WorkflowEventType.RETRY_STARTED,
            session_id=session_id,
            round_number=new_round,
            data={"previous_round": old_round, "new_round": new_round},
        )

        # Clear round-specific candidate patches and results for clean retry
        state["fix_a"] = None
        state["fix_b"] = None
        state.setdefault("candidate_patches", {}).clear()
        state["test_results"] = {}
        state["execution_evidence"] = {}

        state.setdefault("audit_log", []).append(
            f"Constraint recorded for round {old_round}. Transitioning to retry round {new_round}."
        )
        return state

    def finalize_success_node(self, state: WorkflowState) -> WorkflowState:
        """
        Finalizes workflow when a candidate patch passes all tests deterministically.
        """
        session_id = state.get("session_id", "")
        round_no = state.get("current_round", 1)
        state["status"] = "resolved"
        winning_patch = state.get("verdict", {}).get("winning_patch_id")
        self.publisher.emit(
            event_type=WorkflowEventType.SESSION_COMPLETED,
            session_id=session_id,
            round_number=round_no,
            data={"status": "resolved", "winning_patch_id": winning_patch},
        )
        state.setdefault("audit_log", []).append(
            f"Session {session_id} successfully resolved in round {round_no}."
        )
        return state


# Alias for backwards compatibility with Prompt 1 imports
WorkflowGraphScaffolding = CourtroomWorkflow


def build_courtroom_workflow(
    prosecutor_agent: Optional[ProsecutorAgent] = None,
    defender_agent: Optional[DefenderAgent] = None,
    judge_agent: Optional[JudgeAgent] = None,
    constraint_ledger: Optional[Any] = None,
    event_publisher: Optional[BaseEventPublisher] = None,
    sandbox_runner: Optional[Any] = None,
    test_evaluator: Optional[Any] = None,
    stop_at_evaluation: Optional[bool] = None,
    full_pipeline: Optional[bool] = None,
):
    """
    Builds and compiles the LangGraph courtroom workflow.

    Modes:
    - If stop_at_evaluation is True (or full_pipeline is not True and judge/runner are None):
      compiles the Prompt 3 boundary workflow (intake -> prosecutor -> defender -> evaluation_boundary -> END).
    - If full_pipeline is True (or stop_at_evaluation is False or judge/runner are injected):
      compiles the complete end-to-end courtroom workflow:
      intake -> prosecutor -> defender -> evaluation_boundary -> execute_candidates ->
      evaluate_tests -> judge -> [route_after_judging] -> (finalize_success | record_constraints_and_retry -> prosecutor | finalize_failure).
    """
    if stop_at_evaluation is True:
        is_full = False
    elif full_pipeline is True or stop_at_evaluation is False:
        is_full = True
    elif judge_agent is not None or sandbox_runner is not None or test_evaluator is not None:
        is_full = True
    else:
        is_full = False

    workflow = CourtroomWorkflow(
        prosecutor_agent=prosecutor_agent,
        defender_agent=defender_agent,
        judge_agent=judge_agent,
        constraint_ledger=constraint_ledger,
        event_publisher=event_publisher,
        sandbox_runner=sandbox_runner,
        test_evaluator=test_evaluator,
    )

    from langgraph.graph import StateGraph, START, END

    builder = StateGraph(WorkflowState)

    # Register core nodes
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

    if not is_full:
        builder.add_edge("evaluation_boundary", END)
        builder.add_edge("finalize_failure", END)
    else:
        builder.add_node("execute_candidates", workflow.execute_candidates_node)
        builder.add_node("evaluate_tests", workflow.evaluate_tests_node)
        builder.add_node("judge", workflow.judge_node)
        builder.add_node("record_constraints_and_retry", workflow.record_constraints_and_retry_node)
        builder.add_node("finalize_success", workflow.finalize_success_node)

        builder.add_edge("evaluation_boundary", "execute_candidates")
        builder.add_edge("execute_candidates", "evaluate_tests")
        builder.add_edge("evaluate_tests", "judge")

        builder.add_conditional_edges(
            "judge",
            route_after_judging,
            {
                "finalize_success": "finalize_success",
                "record_constraints_and_retry": "record_constraints_and_retry",
                "finalize_failure": "finalize_failure",
            },
        )

        builder.add_edge("record_constraints_and_retry", "prosecutor")
        builder.add_edge("finalize_success", END)
        builder.add_edge("finalize_failure", END)

    return builder.compile()


def build_full_courtroom_workflow(
    prosecutor_agent: Optional[ProsecutorAgent] = None,
    defender_agent: Optional[DefenderAgent] = None,
    judge_agent: Optional[JudgeAgent] = None,
    constraint_ledger: Optional[Any] = None,
    event_publisher: Optional[BaseEventPublisher] = None,
    sandbox_runner: Optional[Any] = None,
    test_evaluator: Optional[Any] = None,
):
    """Compiles the complete full courtroom workflow graph."""
    return build_courtroom_workflow(
        prosecutor_agent=prosecutor_agent,
        defender_agent=defender_agent,
        judge_agent=judge_agent,
        constraint_ledger=constraint_ledger,
        event_publisher=event_publisher,
        sandbox_runner=sandbox_runner,
        test_evaluator=test_evaluator,
        full_pipeline=True,
    )

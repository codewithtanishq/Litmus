"""
Workflow state definitions for Swarm Debugger LangGraph orchestration.
"""

from typing import Any, Dict, List, Optional, TypedDict
from app.schemas.session import DebugSession, SessionStatus


class WorkflowState(TypedDict, total=False):
    """
    Central state container passed between nodes in the courtroom workflow graph.

    Fields:
        session_id: Active debugging session ID.
        original_code: Buggy input source code.
        bug_description: Human/automated failure description.
        test_suite: Reproduction test code.
        current_round: 1-indexed counter of current courtroom round.
        max_rounds: Upper limit of retry rounds permitted.
        status: Lifecycle status string corresponding to SessionStatus.
        candidate_patches: Dict mapping agent role ('prosecutor', 'defender') to CandidatePatch dict.
        execution_evidence: Dict mapping patch_id to Member 2's SandboxExecutionEvidence dict.
        test_results: Dict mapping patch_id to Member 2's evaluated TestResult dict.
        constraints: Cumulative list of Member 2 ConstraintRecord dicts active for this session.
        verdict: Serialized JudgeVerdict dict produced in the current round.
        errors: List of unrecoverable system or infrastructure errors.
        audit_log: Ordered trail of orchestration events.
    """
    session_id: str
    original_code: str
    bug_description: str
    test_suite: str
    current_round: int
    max_rounds: int
    status: str
    candidate_patches: Dict[str, Any]
    execution_evidence: Dict[str, Any]
    test_results: Dict[str, Any]
    constraints: List[Dict[str, Any]]
    verdict: Optional[Dict[str, Any]]
    errors: List[str]
    audit_log: List[str]


def create_initial_workflow_state(
    session: DebugSession,
    max_rounds: int = 3,
) -> WorkflowState:
    """
    Initializes a new workflow state from a DebugSession.

    Args:
        session: Validated DebugSession input.
        max_rounds: Max debate/retry cycles before giving up.

    Returns:
        WorkflowState ready for the LangGraph pipeline.
    """
    return {
        "session_id": session.session_id,
        "original_code": session.original_code,
        "bug_description": session.bug_description,
        "test_suite": session.test_suite,
        "current_round": session.current_round,
        "max_rounds": max_rounds,
        "status": session.status.value if hasattr(session.status, "value") else str(session.status),
        "candidate_patches": {},
        "execution_evidence": {},
        "test_results": {},
        "constraints": [],
        "verdict": None,
        "errors": [],
        "audit_log": [f"Session {session.session_id} initialized at round {session.current_round}"],
    }

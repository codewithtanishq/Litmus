"""
Unit tests for Swarm Debugger shared data schemas and contracts.
"""

import pytest
from pydantic import ValidationError

from app.schemas.session import DebugSession, SessionStatus
from app.schemas.patch import CandidatePatch, AgentRole
from app.schemas.test_result import TestResult, TestCaseResult, TestExecutionStatus
from app.schemas.events import WorkflowEvent, WorkflowEventType
from app.schemas.interfaces import (
    SandboxExecutionRequest,
    SandboxExecutionEvidence,
    ConstraintRecord,
    JudgeVerdict,
    VerdictDecision,
)


class TestDebugSession:
    def test_debug_session_defaults(self):
        session = DebugSession(
            original_code="def foo(): pass",
            bug_description="Does nothing",
        )
        assert session.session_id is not None
        assert session.current_round == 1
        assert session.status == SessionStatus.PENDING
        assert session.test_suite == ""
        assert session.created_at is not None
        assert session.updated_at is not None

    def test_debug_session_validation(self):
        # Empty code should raise ValidationError
        with pytest.raises(ValidationError):
            DebugSession(original_code="", bug_description="Invalid empty code")

        # Empty bug description should raise ValidationError
        with pytest.raises(ValidationError):
            DebugSession(original_code="valid code", bug_description="")

        # Invalid round (< 1) should raise ValidationError
        with pytest.raises(ValidationError):
            DebugSession(
                original_code="valid",
                bug_description="desc",
                current_round=0,
            )

    def test_mark_status(self):
        session = DebugSession(
            original_code="def foo(): pass",
            bug_description="test",
        )
        initial_updated_at = session.updated_at
        session.mark_status(SessionStatus.INVESTIGATING)
        assert session.status == SessionStatus.INVESTIGATING
        assert session.updated_at >= initial_updated_at


class TestCandidatePatch:
    def test_candidate_patch_creation(self):
        patch = CandidatePatch(
            agent_role=AgentRole.PROSECUTOR,
            proposed_code="def foo(): return 42",
            explanation="Returned fixed value 42",
            round_number=1,
        )
        assert patch.patch_id is not None
        assert patch.agent_role == AgentRole.PROSECUTOR
        assert patch.proposed_code == "def foo(): return 42"
        assert patch.diff is None

    def test_candidate_patch_validation(self):
        with pytest.raises(ValidationError):
            CandidatePatch(
                agent_role=AgentRole.DEFENDER,
                proposed_code="",  # empty code not allowed
                explanation="Fix description",
            )

        with pytest.raises(ValidationError):
            CandidatePatch(
                agent_role=AgentRole.DEFENDER,
                proposed_code="code",
                explanation="",  # empty explanation not allowed
            )


class TestTestResult:
    def test_valid_passed_result(self):
        result = TestResult(
            patch_id="patch-123",
            status=TestExecutionStatus.PASSED,
            passed=True,
            exit_code=0,
            stdout="1 passed in 0.05s",
        )
        assert result.passed is True
        assert result.status == TestExecutionStatus.PASSED
        assert result.exit_code == 0

    def test_valid_failed_result(self):
        result = TestResult(
            patch_id="patch-123",
            status=TestExecutionStatus.FAILED,
            passed=False,
            exit_code=1,
            stderr="AssertionError: 2 != 3",
        )
        assert result.passed is False
        assert result.status == TestExecutionStatus.FAILED

    def test_timeout_auto_sets_status(self):
        result = TestResult(
            patch_id="patch-123",
            is_timeout=True,
            timeout_seconds=30.0,
            passed=False,
        )
        assert result.status == TestExecutionStatus.TIMEOUT

    def test_cannot_pass_when_status_is_not_passed(self):
        # A failed test cannot have passed=True
        with pytest.raises(ValueError, match="cannot have passed=True when status is"):
            TestResult(
                patch_id="patch-123",
                status=TestExecutionStatus.FAILED,
                passed=True,
            )

        # A timeout test cannot have passed=True
        with pytest.raises(ValueError, match="cannot have passed=True when status is"):
            TestResult(
                patch_id="patch-123",
                status=TestExecutionStatus.TIMEOUT,
                passed=True,
            )

        # An unrun/missing test cannot have passed=True
        with pytest.raises(ValueError, match="cannot have passed=True when status is"):
            TestResult(
                patch_id="patch-123",
                status=TestExecutionStatus.NOT_RUN,
                passed=True,
            )

    def test_cannot_pass_with_nonzero_exit_code(self):
        with pytest.raises(ValueError, match="cannot have status='passed' when exit_code is non-zero"):
            TestResult(
                patch_id="patch-123",
                status=TestExecutionStatus.PASSED,
                passed=True,
                exit_code=1,
            )


class TestWorkflowEvent:
    def test_workflow_event_creation(self):
        event = WorkflowEvent(
            session_id="session-456",
            round_number=2,
            event_type=WorkflowEventType.PATCH_PROPOSED,
            data={"agent_role": "prosecutor", "patch_id": "patch-1"},
        )
        assert event.event_id is not None
        assert event.session_id == "session-456"
        assert event.round_number == 2
        assert event.event_type == WorkflowEventType.PATCH_PROPOSED
        assert event.data["agent_role"] == "prosecutor"


class TestSharedMemberInterfaces:
    def test_sandbox_contracts(self):
        patch = CandidatePatch(
            agent_role=AgentRole.PROSECUTOR,
            proposed_code="def fixed(): return True",
            explanation="Fixed return value",
        )
        req = SandboxExecutionRequest(
            session_id="session-1",
            round_number=1,
            patch=patch,
            test_suite="assert fixed() is True",
        )
        assert req.timeout_seconds == 30.0

        evidence = SandboxExecutionEvidence(
            patch_id=patch.patch_id,
            stdout="Ran 1 test. OK",
            stderr="",
            exit_code=0,
        )
        assert evidence.is_timeout is False
        assert evidence.exit_code == 0

    def test_constraint_record_contract(self):
        record = ConstraintRecord(
            session_id="session-1",
            round_number=1,
            agent_role=AgentRole.PROSECUTOR,
            patch_id="patch-abc",
            rejected_code="def broken(): return 0",
            failure_reason="Failed division by zero test",
            test_stderr="ZeroDivisionError",
        )
        assert record.constraint_id is not None
        assert record.agent_role == AgentRole.PROSECUTOR

    def test_judge_verdict_contract(self):
        verdict = JudgeVerdict(
            session_id="session-1",
            round_number=1,
            decision=VerdictDecision.RETRY_ROUND,
            explanation="Both fixes failed deterministic tests. New constraints recorded.",
        )
        assert verdict.decision == VerdictDecision.RETRY_ROUND
        assert verdict.winning_patch_id is None

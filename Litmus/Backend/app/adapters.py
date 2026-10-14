"""
app/adapters.py
===============
Explicit, bidirectional adapters between Member 1 schemas (`app.schemas.*`)
and Member 2 data contracts (`app.contracts.*`).

Unifies two competing data-model representations without silent swallows
or ad-hoc dictionary munging.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import uuid4

import app.contracts as contracts
from app.schemas.session import DebugSession as SchemaDebugSession, SessionStatus as SchemaSessionStatus
from app.schemas.patch import CandidatePatch as SchemaCandidatePatch, AgentRole
from app.schemas.test_result import (
    TestResult as SchemaTestResult,
    TestCaseResult as SchemaTestCaseResult,
    TestExecutionStatus,
)


def contract_to_schema_session(session: contracts.DebugSession) -> SchemaDebugSession:
    """Converts a Member 2 contract DebugSession to Member 1 schema DebugSession."""
    status_map = {
        contracts.SessionStatus.PENDING: SchemaSessionStatus.PENDING,
        contracts.SessionStatus.RUNNING: SchemaSessionStatus.INVESTIGATING,
        contracts.SessionStatus.COMPLETED: SchemaSessionStatus.RESOLVED,
        contracts.SessionStatus.FAILED: SchemaSessionStatus.FAILED,
    }
    return SchemaDebugSession(
        session_id=session.session_id,
        original_code=session.original_source,
        bug_description=session.bug_description,
        test_suite=session.trusted_tests,
        current_round=1,
        status=status_map.get(session.status, SchemaSessionStatus.PENDING),
        created_at=session.created_at,
        updated_at=session.updated_at,
        metadata={"language": session.language, "max_rounds": session.max_rounds},
    )


def schema_to_contract_session(session: SchemaDebugSession) -> contracts.DebugSession:
    """Converts a Member 1 schema DebugSession to Member 2 contract DebugSession."""
    status_map = {
        SchemaSessionStatus.PENDING: contracts.SessionStatus.PENDING,
        SchemaSessionStatus.INVESTIGATING: contracts.SessionStatus.RUNNING,
        SchemaSessionStatus.EVALUATING: contracts.SessionStatus.RUNNING,
        SchemaSessionStatus.JUDGING: contracts.SessionStatus.RUNNING,
        SchemaSessionStatus.RESOLVED: contracts.SessionStatus.COMPLETED,
        SchemaSessionStatus.FAILED: contracts.SessionStatus.FAILED,
        SchemaSessionStatus.MAX_ROUNDS_REACHED: contracts.SessionStatus.FAILED,
    }
    lang = (session.metadata or {}).get("language", "python")
    max_rounds = (session.metadata or {}).get("max_rounds", 3)
    return contracts.DebugSession(
        session_id=session.session_id,
        language=lang,
        bug_description=session.bug_description,
        original_source=session.original_code,
        trusted_tests=session.test_suite,
        max_rounds=max_rounds,
        status=status_map.get(session.status, contracts.SessionStatus.PENDING),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def contract_to_schema_patch(patch: contracts.CandidatePatch) -> SchemaCandidatePatch:
    """Converts a Member 2 contract CandidatePatch to Member 1 schema CandidatePatch."""
    role_val = patch.agent.lower()
    role = AgentRole.DEFENDER if "defender" in role_val else AgentRole.PROSECUTOR
    return SchemaCandidatePatch(
        patch_id=patch.candidate_id,
        agent_role=role,
        proposed_code=patch.source_code,
        explanation=patch.explanation,
        round_number=patch.round_number,
        created_at=patch.created_at,
    )


def schema_to_contract_patch(
    patch: SchemaCandidatePatch, session_id: str = ""
) -> contracts.CandidatePatch:
    """Converts a Member 1 schema CandidatePatch to Member 2 contract CandidatePatch."""
    role_str = (
        patch.agent_role.value if hasattr(patch.agent_role, "value") else str(patch.agent_role)
    )
    return contracts.CandidatePatch(
        candidate_id=patch.patch_id,
        session_id=session_id,
        agent=role_str,
        round_number=patch.round_number,
        source_code=patch.proposed_code,
        explanation=patch.explanation,
        created_at=patch.created_at,
    )


def contract_to_schema_result(result: contracts.TestResult) -> SchemaTestResult:
    """Converts a Member 2 contract TestResult to Member 1 schema TestResult."""
    status_map = {
        contracts.ExecutionStatus.PASSED: TestExecutionStatus.PASSED,
        contracts.ExecutionStatus.FAILED: TestExecutionStatus.FAILED,
        contracts.ExecutionStatus.TIMED_OUT: TestExecutionStatus.TIMEOUT,
        contracts.ExecutionStatus.INFRASTRUCTURE_ERROR: TestExecutionStatus.INFRASTRUCTURE_ERROR,
    }
    cases = []
    for pt in result.per_test_results:
        pt_status = (
            TestExecutionStatus.PASSED
            if pt.status == "passed"
            else (
                TestExecutionStatus.FAILED
                if pt.status in ("failed", "error")
                else TestExecutionStatus.NOT_RUN
            )
        )
        cases.append(
            SchemaTestCaseResult(
                name=pt.test_name,
                status=pt_status,
                error_message=pt.message,
            )
        )

    is_passed = result.status == contracts.ExecutionStatus.PASSED
    return SchemaTestResult(
        patch_id=result.candidate_id,
        status=status_map.get(result.status, TestExecutionStatus.NOT_RUN),
        passed=is_passed,
        test_cases=cases,
        stdout=result.stdout_excerpt,
        stderr=result.stderr_excerpt,
        exit_code=result.exit_code,
        is_timeout=(result.status == contracts.ExecutionStatus.TIMED_OUT),
        error_details=result.stderr_excerpt if result.status != contracts.ExecutionStatus.PASSED else None,
        duration_seconds=result.duration_ms / 1000.0 if result.duration_ms else 0.0,
    )


def schema_to_contract_result(
    result: SchemaTestResult, session_id: str = ""
) -> contracts.TestResult:
    """Converts a Member 1 schema TestResult to Member 2 contract TestResult."""
    status_map = {
        TestExecutionStatus.PASSED: contracts.ExecutionStatus.PASSED,
        TestExecutionStatus.FAILED: contracts.ExecutionStatus.FAILED,
        TestExecutionStatus.TIMEOUT: contracts.ExecutionStatus.TIMED_OUT,
        TestExecutionStatus.INFRASTRUCTURE_ERROR: contracts.ExecutionStatus.INFRASTRUCTURE_ERROR,
        TestExecutionStatus.NOT_RUN: contracts.ExecutionStatus.FAILED,
    }
    per_tests = []
    for tc in result.test_cases:
        tc_status_str = (
            tc.status.value if hasattr(tc.status, "value") else str(tc.status).lower()
        )
        per_tests.append(
            contracts.PerTestResult(
                test_name=tc.name,
                status=tc_status_str,
                message=tc.error_message or "",
            )
        )

    contract_status = status_map.get(result.status, contracts.ExecutionStatus.FAILED)
    dur_ms = (result.duration_seconds or 0.0) * 1000.0
    return contracts.TestResult(
        result_id=str(uuid4()),
        candidate_id=result.patch_id,
        session_id=session_id,
        status=contract_status,
        exit_code=result.exit_code,
        stdout_excerpt=(result.stdout or "")[:4096],
        stderr_excerpt=(result.stderr or "")[:4096],
        per_test_results=per_tests,
        duration_ms=dur_ms,
        failure_signature=f"sig_{result.patch_id}",
    )

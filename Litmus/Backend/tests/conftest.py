"""
tests/conftest.py
-----------------
Shared pytest fixtures for all test modules.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.contracts import (
    CandidatePatch,
    DebugSession,
    ExecutionEvidence,
    ExecutionStatus,
    PerTestResult,
    RunLimits,
    SessionStatus,
    TestResult,
)
from app.memory.repository import Repository


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _uuid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# Database fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def repo() -> Repository:
    """In-memory Repository; destroyed after each test."""
    return Repository(db_path=":memory:")


# ─────────────────────────────────────────────────────────────────────────────
# Contract factories
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def session_id() -> str:
    return _uuid()


@pytest.fixture()
def candidate_id() -> str:
    return _uuid()


@pytest.fixture()
def result_id() -> str:
    return _uuid()


@pytest.fixture()
def make_session(session_id: str) -> DebugSession:
    return DebugSession(
        session_id=session_id,
        language="python",
        bug_description="Off-by-one error",
        original_source="def add(a, b): return a + b - 1",
        trusted_tests="def test_add(): assert add(1, 2) == 3",
        max_rounds=3,
        status=SessionStatus.PENDING,
    )


@pytest.fixture()
def make_candidate(session_id: str, candidate_id: str) -> CandidatePatch:
    return CandidatePatch(
        candidate_id=candidate_id,
        session_id=session_id,
        agent="agent_alpha",
        round_number=1,
        source_code="def add(a, b): return a + b",
        explanation="Removed the erroneous -1",
    )


@pytest.fixture()
def passing_result(candidate_id: str, session_id: str) -> TestResult:
    return TestResult(
        result_id=_uuid(),
        candidate_id=candidate_id,
        session_id=session_id,
        status=ExecutionStatus.PASSED,
        exit_code=0,
        stdout_excerpt="1 passed",
        per_test_results=[PerTestResult(test_name="test_add", status="passed")],
        duration_ms=100.0,
    )


@pytest.fixture()
def failing_result(candidate_id: str, session_id: str) -> TestResult:
    return TestResult(
        result_id=_uuid(),
        candidate_id=candidate_id,
        session_id=session_id,
        status=ExecutionStatus.FAILED,
        exit_code=1,
        stdout_excerpt="1 failed",
        per_test_results=[
            PerTestResult(
                test_name="test_empty_input",
                status="failed",
                message="IndexError: list index out of range",
            )
        ],
        duration_ms=50.0,
        failure_signature="abc123deadbeef01",
    )


@pytest.fixture()
def timeout_result(candidate_id: str, session_id: str) -> TestResult:
    return TestResult(
        result_id=_uuid(),
        candidate_id=candidate_id,
        session_id=session_id,
        status=ExecutionStatus.TIMED_OUT,
        duration_ms=30_000.0,
    )


@pytest.fixture()
def infra_error_result(candidate_id: str, session_id: str) -> TestResult:
    return TestResult(
        result_id=_uuid(),
        candidate_id=candidate_id,
        session_id=session_id,
        status=ExecutionStatus.INFRASTRUCTURE_ERROR,
        stderr_excerpt="Docker unavailable",
        duration_ms=0.0,
    )

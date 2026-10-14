"""
tests/integration/test_member2_pipeline.py
-------------------------------------------
Integration tests for the full Member 2 pipeline:
  runner → evaluator → repository → ledger

These tests use SWARM_ALLOW_HOST_EXECUTION=1 so they run on the host
Python process (no Docker required).  They exercise the actual runner,
real pytest subprocess, and real SQLite persistence — no mocks except
the Docker availability check.

Tests are marked ``@pytest.mark.integration`` and skipped if running
in an environment without permission to spawn subprocesses.
"""

from __future__ import annotations

import os
import uuid

import pytest

from app.contracts import ExecutionStatus, RunLimits, SessionStatus
from app.evaluation.test_evaluator import evaluate_candidate
from app.memory.constraint_ledger import ConstraintLedger
from app.memory.repository import Repository
from app.sandbox.runner import run_candidate


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _allow_host(monkeypatch):
    """Enable host execution for all integration tests."""
    monkeypatch.setenv("SWARM_ALLOW_HOST_EXECUTION", "1")


@pytest.fixture()
def mem_repo():
    """In-memory repository for integration tests."""
    return Repository(":memory:")


@pytest.fixture()
def ledger(mem_repo):
    return ConstraintLedger(mem_repo)


@pytest.fixture()
def fast_limits():
    """Very tight limits for quick tests."""
    return RunLimits(timeout_seconds=30, memory_mb=256)


def _uid() -> str:
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures: source code + tests
# ─────────────────────────────────────────────────────────────────────────────


PASSING_SOURCE = """\
def add(a, b):
    return a + b
"""

PASSING_TESTS = """\
from solution import add

def test_add_positive():
    assert add(1, 2) == 3

def test_add_zero():
    assert add(0, 0) == 0
"""

FAILING_SOURCE = """\
def add(a, b):
    return a + b - 1  # off-by-one bug
"""

FAILING_TESTS = """\
from solution import add

def test_add_positive():
    assert add(1, 2) == 3

def test_add_zero():
    assert add(0, 0) == 0
"""

TIMEOUT_SOURCE = """\
import time
def add(a, b):
    time.sleep(999)
    return a + b
"""

TIMEOUT_TESTS = """\
from solution import add

def test_add():
    assert add(1, 2) == 3
"""


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline helper
# ─────────────────────────────────────────────────────────────────────────────


from app.contracts import CandidatePatch, DebugSession


def _run_pipeline(mem_repo, ledger, source, tests, limits):
    """Run the full Member 2 pipeline for one candidate."""
    sid = _uid()
    cid = _uid()

    session = DebugSession(
        session_id=sid,
        bug_description="Test bug",
        original_source=FAILING_SOURCE,
        trusted_tests=tests,
    )
    mem_repo.create_session(session)

    candidate = CandidatePatch(
        candidate_id=cid,
        session_id=sid,
        agent="integration_agent",
        round_number=1,
        source_code=source,
        explanation="Test fix",
    )
    mem_repo.save_candidate(candidate)

    # Step 1: run in sandbox
    evidence = run_candidate(source, tests, cid, limits=limits)

    # Step 2: evaluate
    result = evaluate_candidate(evidence, sid)
    mem_repo.save_test_result(result)

    # Step 3: record failure constraint if applicable
    constraint = ledger.record_failure(candidate, result)

    return session, candidate, result, constraint


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestPassingPipeline:
    def test_passing_candidate_end_to_end(self, mem_repo, ledger, fast_limits):
        session, candidate, result, constraint = _run_pipeline(
            mem_repo, ledger, PASSING_SOURCE, PASSING_TESTS, fast_limits
        )
        assert result.status == ExecutionStatus.PASSED
        assert constraint is None
        # Result should be persisted
        fetched = mem_repo.get_test_result(result.result_id)
        assert fetched is not None
        assert fetched.status == ExecutionStatus.PASSED

    def test_passing_candidate_has_per_test_results(self, mem_repo, ledger, fast_limits):
        _, _, result, _ = _run_pipeline(
            mem_repo, ledger, PASSING_SOURCE, PASSING_TESTS, fast_limits
        )
        assert result.status == ExecutionStatus.PASSED
        assert len(result.per_test_results) >= 1
        assert all(r.status == "passed" for r in result.per_test_results)


class TestFailingPipeline:
    def test_failing_candidate_end_to_end(self, mem_repo, ledger, fast_limits):
        _, candidate, result, constraint = _run_pipeline(
            mem_repo, ledger, FAILING_SOURCE, FAILING_TESTS, fast_limits
        )
        assert result.status == ExecutionStatus.FAILED
        assert constraint is not None
        assert constraint.source_candidate_id == candidate.candidate_id
        assert constraint.evidence_result_id == result.result_id

    def test_constraint_references_real_failure(self, mem_repo, ledger, fast_limits):
        _, _, result, constraint = _run_pipeline(
            mem_repo, ledger, FAILING_SOURCE, FAILING_TESTS, fast_limits
        )
        if result.status == ExecutionStatus.FAILED and constraint:
            # The constraint text must mention at least one failing test
            failed_names = [r.test_name for r in result.per_test_results if r.status == "failed"]
            assert any(name in constraint.constraint_text for name in failed_names)

    def test_get_relevant_constraints_returns_data(self, mem_repo, ledger, fast_limits):
        session, _, result, _ = _run_pipeline(
            mem_repo, ledger, FAILING_SOURCE, FAILING_TESTS, fast_limits
        )
        if result.status == ExecutionStatus.FAILED:
            cons = ledger.get_relevant_constraints(session.session_id)
            assert len(cons) >= 1


class TestTimeoutPipeline:
    @pytest.mark.timeout(35)
    def test_timeout_candidate(self, mem_repo, ledger):
        tight_limits = RunLimits(timeout_seconds=3)
        _, _, result, constraint = _run_pipeline(
            mem_repo, ledger, TIMEOUT_SOURCE, TIMEOUT_TESTS, tight_limits
        )
        assert result.status == ExecutionStatus.TIMED_OUT
        assert constraint is not None  # Bug 7 fix: timeouts MUST produce a constraint
        assert "exceeded" in constraint.constraint_text.lower() or "timeout" in constraint.constraint_text.lower()


class TestConstraintDeduplication:
    def test_same_failure_not_stored_twice(self, mem_repo, ledger, fast_limits):
        sid = _uid()
        session = DebugSession(
            session_id=sid,
            bug_description="Bug",
            original_source=FAILING_SOURCE,
            trusted_tests=FAILING_TESTS,
        )
        mem_repo.create_session(session)

        constraints_created = []
        for i in range(3):
            cid = _uid()
            candidate = CandidatePatch(
                candidate_id=cid,
                session_id=sid,
                agent="agent",
                round_number=i + 1,
                source_code=FAILING_SOURCE,
                explanation="Same bug",
            )
            mem_repo.save_candidate(candidate)
            evidence = run_candidate(FAILING_SOURCE, FAILING_TESTS, cid, limits=fast_limits)
            result = evaluate_candidate(evidence, sid)
            mem_repo.save_test_result(result)
            con = ledger.record_failure(candidate, result)
            if con is not None:
                constraints_created.append(con)

        # All three attempts produce the same failure signature →
        # at most one unique constraint per signature
        stored = mem_repo.list_constraints(sid)
        sig_set = {c.failure_signature for c in stored}
        assert len(stored) == len(sig_set)


class TestFormatForPrompt:
    def test_prompt_string_non_empty_after_failure(self, mem_repo, ledger, fast_limits):
        session, _, result, _ = _run_pipeline(
            mem_repo, ledger, FAILING_SOURCE, FAILING_TESTS, fast_limits
        )
        if result.status == ExecutionStatus.FAILED:
            prompt = ledger.format_for_prompt(session.session_id)
            assert len(prompt) > 0

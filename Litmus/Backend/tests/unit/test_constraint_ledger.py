"""
tests/unit/test_constraint_ledger.py
--------------------------------------
Unit tests for app/memory/constraint_ledger.py

All seven required scenarios from the spec are tested.
"""

from __future__ import annotations

import uuid

import pytest

from app.contracts import (
    CandidatePatch,
    ConstraintStatus,
    DebugSession,
    ExecutionStatus,
    PerTestResult,
    SessionStatus,
    TestResult,
)
from app.memory.constraint_ledger import ConstraintLedger
from app.memory.repository import Repository

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


def _uid() -> str:
    return str(uuid.uuid4())


@pytest.fixture()
def repo():
    return Repository(":memory:")


@pytest.fixture()
def ledger(repo):
    return ConstraintLedger(repo)


@pytest.fixture()
def session_id():
    return _uid()


def _make_session(repo: Repository, sid: str) -> DebugSession:
    s = DebugSession(
        session_id=sid,
        bug_description="Bug",
        original_source="def f(): pass",
        trusted_tests="def test_f(): assert f() == 1",
    )
    repo.create_session(s)
    return s


def _make_candidate(repo: Repository, session_id: str, round_number: int = 1) -> CandidatePatch:
    c = CandidatePatch(
        candidate_id=_uid(),
        session_id=session_id,
        agent="agent_alpha",
        round_number=round_number,
        source_code="def f(): return 1",
        explanation="Fix",
    )
    repo.save_candidate(c)
    return c


def _make_result(
    repo: Repository,
    session_id: str,
    candidate_id: str,
    status: ExecutionStatus,
    per_test: list[PerTestResult] | None = None,
    sig: str | None = None,
) -> TestResult:
    r = TestResult(
        result_id=_uid(),
        candidate_id=candidate_id,
        session_id=session_id,
        status=status,
        exit_code=0 if status == ExecutionStatus.PASSED else 1,
        per_test_results=per_test or [],
        failure_signature=sig,
    )
    repo.save_test_result(r)
    return r


def _failed_per_test(name: str = "test_empty", msg: str = "IndexError") -> list[PerTestResult]:
    return [PerTestResult(test_name=name, status="failed", message=msg)]


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 1 — Passing result creates no constraint
# ─────────────────────────────────────────────────────────────────────────────


class TestPassingResult:
    def test_no_constraint_created(self, repo, ledger, session_id):
        _make_session(repo, session_id)
        c = _make_candidate(repo, session_id)
        r = _make_result(repo, session_id, c.candidate_id, ExecutionStatus.PASSED)
        constraint = ledger.record_failure(c, r)
        assert constraint is None
        assert repo.list_constraints(session_id) == []


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 2 — Genuine test failure creates a constraint
# ─────────────────────────────────────────────────────────────────────────────


class TestGenuineTestFailure:
    def test_constraint_created_with_evidence(self, repo, ledger, session_id):
        _make_session(repo, session_id)
        c = _make_candidate(repo, session_id)
        per_test = _failed_per_test()
        r = _make_result(repo, session_id, c.candidate_id, ExecutionStatus.FAILED,
                         per_test=per_test, sig="abc123")
        constraint = ledger.record_failure(c, r)

        assert constraint is not None
        assert constraint.session_id == session_id
        assert constraint.source_candidate_id == c.candidate_id
        assert constraint.evidence_result_id == r.result_id
        assert constraint.failure_signature == "abc123"
        assert "test_empty" in constraint.constraint_text
        assert "IndexError" in constraint.constraint_text

    def test_constraint_is_persisted(self, repo, ledger, session_id):
        _make_session(repo, session_id)
        c = _make_candidate(repo, session_id)
        r = _make_result(repo, session_id, c.candidate_id, ExecutionStatus.FAILED,
                         per_test=_failed_per_test(), sig="persist_sig")
        ledger.record_failure(c, r)
        stored = repo.list_constraints(session_id)
        assert len(stored) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 3 — Timeout does NOT create a constraint
# ─────────────────────────────────────────────────────────────────────────────


class TestTimeout:
    def test_no_constraint_for_timeout(self, repo, ledger, session_id):
        _make_session(repo, session_id)
        c = _make_candidate(repo, session_id)
        r = _make_result(repo, session_id, c.candidate_id, ExecutionStatus.TIMED_OUT)
        constraint = ledger.record_failure(c, r)
        assert constraint is None
        assert repo.list_constraints(session_id) == []


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 4 — Infrastructure error does NOT create a code-level constraint
# ─────────────────────────────────────────────────────────────────────────────


class TestInfrastructureError:
    def test_no_constraint_for_infra_error(self, repo, ledger, session_id):
        _make_session(repo, session_id)
        c = _make_candidate(repo, session_id)
        r = _make_result(repo, session_id, c.candidate_id, ExecutionStatus.INFRASTRUCTURE_ERROR)
        constraint = ledger.record_failure(c, r)
        assert constraint is None
        assert repo.list_constraints(session_id) == []


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 5 — Duplicate failure signature is deduplicated
# ─────────────────────────────────────────────────────────────────────────────


class TestDuplicateFailure:
    def test_same_signature_not_stored_twice(self, repo, ledger, session_id):
        _make_session(repo, session_id)
        c1 = _make_candidate(repo, session_id, round_number=1)
        c2 = _make_candidate(repo, session_id, round_number=2)

        r1 = _make_result(repo, session_id, c1.candidate_id, ExecutionStatus.FAILED,
                          per_test=_failed_per_test(), sig="dup_sig")
        r2 = _make_result(repo, session_id, c2.candidate_id, ExecutionStatus.FAILED,
                          per_test=_failed_per_test(), sig="dup_sig")

        con1 = ledger.record_failure(c1, r1)
        con2 = ledger.record_failure(c2, r2)

        assert con1 is not None
        assert con2 is None  # duplicate — skipped
        assert len(repo.list_constraints(session_id)) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 6 — Session-specific retrieval
# ─────────────────────────────────────────────────────────────────────────────


class TestSessionSpecificRetrieval:
    def test_constraints_isolated_per_session(self, repo, ledger):
        sid_a = _uid()
        sid_b = _uid()
        _make_session(repo, sid_a)
        _make_session(repo, sid_b)

        ca = _make_candidate(repo, sid_a)
        cb = _make_candidate(repo, sid_b)

        ra = _make_result(repo, sid_a, ca.candidate_id, ExecutionStatus.FAILED,
                          per_test=_failed_per_test(), sig="sig_a")
        rb = _make_result(repo, sid_b, cb.candidate_id, ExecutionStatus.FAILED,
                          per_test=_failed_per_test("test_b"), sig="sig_b")

        ledger.record_failure(ca, ra)
        ledger.record_failure(cb, rb)

        # Session A should only see its own constraint
        cons_a = ledger.get_relevant_constraints(sid_a)
        assert len(cons_a) == 1
        assert cons_a[0].session_id == sid_a

        # Session B should only see its own constraint
        cons_b = ledger.get_relevant_constraints(sid_b)
        assert len(cons_b) == 1
        assert cons_b[0].session_id == sid_b

    def test_limit_is_respected(self, repo, ledger, session_id):
        _make_session(repo, session_id)
        for i in range(8):
            c = _make_candidate(repo, session_id, round_number=i + 1)
            r = _make_result(repo, session_id, c.candidate_id, ExecutionStatus.FAILED,
                             per_test=_failed_per_test(), sig=f"sig{i:04d}")
            ledger.record_failure(c, r)

        cons = ledger.get_relevant_constraints(session_id, limit=5)
        assert len(cons) == 5


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 7 — Traceability (constraint links to candidate and result)
# ─────────────────────────────────────────────────────────────────────────────


class TestTraceability:
    def test_constraint_links_to_candidate_and_result(self, repo, ledger, session_id):
        _make_session(repo, session_id)
        c = _make_candidate(repo, session_id)
        r = _make_result(repo, session_id, c.candidate_id, ExecutionStatus.FAILED,
                         per_test=_failed_per_test(), sig="trace_sig")
        con = ledger.record_failure(c, r)

        assert con is not None
        assert con.source_candidate_id == c.candidate_id
        assert con.evidence_result_id == r.result_id

        # Verify the linked objects actually exist in the DB
        assert repo.get_candidate(con.source_candidate_id) is not None
        assert repo.get_test_result(con.evidence_result_id) is not None

    def test_constraint_text_is_grounded_in_test_evidence(self, repo, ledger, session_id):
        """The constraint text must mention actual failing test info."""
        _make_session(repo, session_id)
        c = _make_candidate(repo, session_id)
        per_test = [PerTestResult(test_name="test_divide_by_zero",
                                  status="failed",
                                  message="ZeroDivisionError: division by zero")]
        r = _make_result(repo, session_id, c.candidate_id, ExecutionStatus.FAILED,
                         per_test=per_test, sig="zdiv_sig")
        con = ledger.record_failure(c, r)

        assert "test_divide_by_zero" in con.constraint_text
        assert "ZeroDivisionError" in con.constraint_text

    def test_format_for_prompt_returns_empty_when_no_constraints(self, ledger, session_id):
        assert ledger.format_for_prompt(session_id) == ""

    def test_format_for_prompt_includes_constraints(self, repo, ledger, session_id):
        _make_session(repo, session_id)
        c = _make_candidate(repo, session_id)
        r = _make_result(repo, session_id, c.candidate_id, ExecutionStatus.FAILED,
                         per_test=_failed_per_test(), sig="fmt_sig")
        ledger.record_failure(c, r)
        prompt = ledger.format_for_prompt(session_id)
        assert "Constraint" in prompt
        assert len(prompt) > 0

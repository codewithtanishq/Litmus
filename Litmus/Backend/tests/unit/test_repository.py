"""
tests/unit/test_repository.py
------------------------------
Unit tests for app/memory/repository.py

All tests use an in-memory SQLite database so no files are created.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.contracts import (
    CandidatePatch,
    Constraint,
    ConstraintStatus,
    DebugSession,
    ExecutionStatus,
    PerTestResult,
    SessionStatus,
    TestResult,
)
from app.memory.repository import Repository


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _uid() -> str:
    return str(uuid.uuid4())


def _make_session(sid: str | None = None) -> DebugSession:
    return DebugSession(
        session_id=sid or _uid(),
        bug_description="Off by one",
        original_source="def f(): return 0",
        trusted_tests="def test_f(): assert f() == 1",
    )


def _make_candidate(session_id: str, cid: str | None = None, round_number: int = 1) -> CandidatePatch:
    return CandidatePatch(
        candidate_id=cid or _uid(),
        session_id=session_id,
        agent="agent_alpha",
        round_number=round_number,
        source_code="def f(): return 1",
        explanation="Fixed return value",
    )


def _make_result(session_id: str, candidate_id: str, rid: str | None = None) -> TestResult:
    return TestResult(
        result_id=rid or _uid(),
        candidate_id=candidate_id,
        session_id=session_id,
        status=ExecutionStatus.PASSED,
        exit_code=0,
        stdout_excerpt="1 passed",
        per_test_results=[PerTestResult(test_name="test_f", status="passed")],
        duration_ms=42.0,
    )


def _make_constraint(
    session_id: str,
    candidate_id: str,
    result_id: str,
    cid: str | None = None,
    sig: str = "deadsig1",
) -> Constraint:
    return Constraint(
        constraint_id=cid or _uid(),
        session_id=session_id,
        round_number=1,
        source_candidate_id=candidate_id,
        evidence_result_id=result_id,
        failure_signature=sig,
        constraint_text="Handle empty input before indexing.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Repository initialization
# ─────────────────────────────────────────────────────────────────────────────


class TestRepositoryInit:
    def test_initializes_without_error(self):
        repo = Repository(":memory:")
        repo.close()

    def test_initialize_is_idempotent(self):
        repo = Repository(":memory:")
        repo.initialize()  # second call should not raise
        repo.close()


# ─────────────────────────────────────────────────────────────────────────────
# Sessions
# ─────────────────────────────────────────────────────────────────────────────


class TestSessions:
    def test_create_and_get(self, repo):
        s = _make_session()
        repo.create_session(s)
        fetched = repo.get_session(s.session_id)
        assert fetched is not None
        assert fetched.session_id == s.session_id
        assert fetched.bug_description == s.bug_description

    def test_get_unknown_returns_none(self, repo):
        assert repo.get_session("nonexistent") is None

    def test_list_sessions_empty(self, repo):
        assert repo.list_sessions() == []

    def test_list_sessions_returns_all(self, repo):
        s1 = _make_session()
        s2 = _make_session()
        repo.create_session(s1)
        repo.create_session(s2)
        sessions = repo.list_sessions()
        ids = {s.session_id for s in sessions}
        assert s1.session_id in ids
        assert s2.session_id in ids

    def test_update_session_status(self, repo):
        s = _make_session()
        repo.create_session(s)
        repo.update_session_status(s.session_id, SessionStatus.RUNNING)
        fetched = repo.get_session(s.session_id)
        assert fetched.status == SessionStatus.RUNNING


# ─────────────────────────────────────────────────────────────────────────────
# Candidates
# ─────────────────────────────────────────────────────────────────────────────


class TestCandidates:
    def test_save_and_get(self, repo):
        s = _make_session()
        repo.create_session(s)
        c = _make_candidate(s.session_id)
        repo.save_candidate(c)
        fetched = repo.get_candidate(c.candidate_id)
        assert fetched is not None
        assert fetched.source_code == c.source_code

    def test_get_unknown_returns_none(self, repo):
        assert repo.get_candidate("no-such-id") is None

    def test_list_candidates_empty(self, repo):
        s = _make_session()
        repo.create_session(s)
        assert repo.list_candidates(s.session_id) == []

    def test_list_candidates_ordered_by_round(self, repo):
        s = _make_session()
        repo.create_session(s)
        c1 = _make_candidate(s.session_id, round_number=2)
        c2 = _make_candidate(s.session_id, round_number=1)
        repo.save_candidate(c1)
        repo.save_candidate(c2)
        results = repo.list_candidates(s.session_id)
        assert results[0].round_number == 1
        assert results[1].round_number == 2

    def test_foreign_key_violation_raises(self, repo):
        """Saving a candidate without a parent session should fail."""
        c = _make_candidate("ghost-session-id")
        with pytest.raises(Exception):
            repo.save_candidate(c)


# ─────────────────────────────────────────────────────────────────────────────
# Test Results
# ─────────────────────────────────────────────────────────────────────────────


class TestTestResults:
    def _setup(self, repo):
        s = _make_session()
        repo.create_session(s)
        c = _make_candidate(s.session_id)
        repo.save_candidate(c)
        return s, c

    def test_save_and_get(self, repo):
        s, c = self._setup(repo)
        r = _make_result(s.session_id, c.candidate_id)
        repo.save_test_result(r)
        fetched = repo.get_test_result(r.result_id)
        assert fetched is not None
        assert fetched.status == ExecutionStatus.PASSED
        assert fetched.duration_ms == 42.0

    def test_per_test_results_persisted(self, repo):
        s, c = self._setup(repo)
        r = _make_result(s.session_id, c.candidate_id)
        repo.save_test_result(r)
        fetched = repo.get_test_result(r.result_id)
        assert len(fetched.per_test_results) == 1
        assert fetched.per_test_results[0].test_name == "test_f"

    def test_get_unknown_returns_none(self, repo):
        assert repo.get_test_result("no-result") is None

    def test_list_test_results_empty(self, repo):
        s = _make_session()
        repo.create_session(s)
        assert repo.list_test_results(s.session_id) == []

    def test_list_test_results_for_session(self, repo):
        s, c = self._setup(repo)
        r1 = _make_result(s.session_id, c.candidate_id)
        r2 = _make_result(s.session_id, c.candidate_id)
        repo.save_test_result(r1)
        repo.save_test_result(r2)
        results = repo.list_test_results(s.session_id)
        assert len(results) == 2

    def test_stdout_excerpt_capped(self, repo):
        s, c = self._setup(repo)
        r = _make_result(s.session_id, c.candidate_id)
        r.stdout_excerpt = "x" * 100_000
        repo.save_test_result(r)
        fetched = repo.get_test_result(r.result_id)
        assert len(fetched.stdout_excerpt) <= 4096


# ─────────────────────────────────────────────────────────────────────────────
# Constraints
# ─────────────────────────────────────────────────────────────────────────────


class TestConstraints:
    def _setup(self, repo):
        s = _make_session()
        repo.create_session(s)
        c = _make_candidate(s.session_id)
        repo.save_candidate(c)
        r = _make_result(s.session_id, c.candidate_id)
        repo.save_test_result(r)
        return s, c, r

    def test_save_and_list(self, repo):
        s, c, r = self._setup(repo)
        con = _make_constraint(s.session_id, c.candidate_id, r.result_id)
        repo.save_constraint(con)
        constraints = repo.list_constraints(s.session_id)
        assert len(constraints) == 1
        assert constraints[0].constraint_text == con.constraint_text

    def test_list_constraints_empty(self, repo):
        s = _make_session()
        repo.create_session(s)
        assert repo.list_constraints(s.session_id) == []

    def test_list_constraints_respects_limit(self, repo):
        s, c, r = self._setup(repo)
        for i in range(5):
            con = _make_constraint(s.session_id, c.candidate_id, r.result_id, sig=f"sig{i:03d}")
            repo.save_constraint(con)
        limited = repo.list_constraints(s.session_id, limit=3)
        assert len(limited) == 3

    def test_list_constraints_session_isolation(self, repo):
        """Constraints from session A must not appear in session B results."""
        s1, c1, r1 = self._setup(repo)
        s2 = _make_session()
        repo.create_session(s2)
        c2 = _make_candidate(s2.session_id)
        repo.save_candidate(c2)
        r2 = _make_result(s2.session_id, c2.candidate_id)
        repo.save_test_result(r2)

        con1 = _make_constraint(s1.session_id, c1.candidate_id, r1.result_id, sig="sigA")
        repo.save_constraint(con1)

        assert repo.list_constraints(s2.session_id) == []

    def test_constraint_exists_returns_true(self, repo):
        s, c, r = self._setup(repo)
        con = _make_constraint(s.session_id, c.candidate_id, r.result_id, sig="mysig")
        repo.save_constraint(con)
        assert repo.constraint_exists(s.session_id, "mysig") is True

    def test_constraint_exists_returns_false_when_absent(self, repo):
        s = _make_session()
        repo.create_session(s)
        assert repo.constraint_exists(s.session_id, "not-there") is False


# ─────────────────────────────────────────────────────────────────────────────
# Session history
# ─────────────────────────────────────────────────────────────────────────────


class TestSessionHistory:
    def test_history_for_unknown_session(self, repo):
        h = repo.get_session_history("nonexistent")
        assert h["candidates"] == []
        assert h["test_results"] == []
        assert h["constraints"] == []

    def test_history_contains_all_data(self, repo):
        s = _make_session()
        repo.create_session(s)
        c = _make_candidate(s.session_id)
        repo.save_candidate(c)
        r = _make_result(s.session_id, c.candidate_id)
        repo.save_test_result(r)
        con = _make_constraint(s.session_id, c.candidate_id, r.result_id)
        repo.save_constraint(con)

        h = repo.get_session_history(s.session_id)
        assert h["session"]["session_id"] == s.session_id
        assert len(h["candidates"]) == 1
        assert len(h["test_results"]) == 1
        assert len(h["constraints"]) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Persistence durability (close + reopen)
# ─────────────────────────────────────────────────────────────────────────────


class TestDurability:
    def test_data_survives_reopen(self, tmp_path):
        """Data written to a file DB must survive close+reopen."""
        db_file = str(tmp_path / "test.db")
        repo = Repository(db_file)
        s = _make_session()
        repo.create_session(s)
        repo.close()

        # Reopen and verify
        repo2 = Repository(db_file)
        fetched = repo2.get_session(s.session_id)
        assert fetched is not None
        assert fetched.session_id == s.session_id
        repo2.close()

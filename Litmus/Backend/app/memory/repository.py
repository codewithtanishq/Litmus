"""
app/memory/repository.py
========================
SQLite-backed persistence layer for the Swarm Debugger system.

All SQL lives here.  The runner, evaluator, and constraint ledger
call this module; none of them write SQL directly.

Design decisions
----------------
* SQLite is used with ``check_same_thread=False`` so a single
  ``Repository`` instance can be shared across threads (the GIL and
  WAL mode keep it safe for our sequential use-case).
* Foreign keys are enabled per connection.
* WAL journal mode is enabled for better concurrent read performance.
* All writes are wrapped in transactions.
* Timestamps are stored as ISO-8601 UTC strings.
* Per-test results are stored as JSON in a TEXT column — simple enough
  for the MVP and avoids an extra join table.
* stdout/stderr are capped at ``_EXCERPT_MAX`` bytes before storage so
  the database does not grow unbounded.
* The database path is configurable (default from ``DATABASE_PATH`` env
  var).  Use ``:memory:`` for tests.

Public API (called by ledger, runner glue, orchestrator)
---------------------------------------------------------
``Repository(db_path)``
    Constructor.  Calls ``initialize()`` automatically.

``initialize()``
    Create tables if they do not exist.

Sessions:
    ``create_session(session)`` → ``DebugSession``
    ``get_session(session_id)`` → ``DebugSession | None``
    ``update_session_status(session_id, status)``
    ``list_sessions()`` → ``list[DebugSession]``

Candidates:
    ``save_candidate(candidate)`` → ``CandidatePatch``
    ``get_candidate(candidate_id)`` → ``CandidatePatch | None``
    ``list_candidates(session_id)`` → ``list[CandidatePatch]``

Test Results:
    ``save_test_result(result)`` → ``TestResult``
    ``get_test_result(result_id)`` → ``TestResult | None``
    ``list_test_results(session_id)`` → ``list[TestResult]``

Constraints:
    ``save_constraint(constraint)`` → ``Constraint``
    ``list_constraints(session_id, limit)`` → ``list[Constraint]``

Session history:
    ``get_session_history(session_id)`` → ``dict``
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

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

_EXCERPT_MAX = 4096  # bytes stored per stdout/stderr field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


# ─────────────────────────────────────────────────────────────────────────────
# Repository
# ─────────────────────────────────────────────────────────────────────────────


class Repository:
    """
    Thread-safe SQLite repository for Swarm Debugger data.

    Parameters
    ----------
    db_path:
        Filesystem path to the SQLite database, or ``:memory:`` for an
        in-memory database (useful in tests).  Defaults to the
        ``DATABASE_PATH`` environment variable or ``swarm_debugger.db``.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._lock = threading.RLock()
        self._db_path = db_path or os.environ.get("DATABASE_PATH", "swarm_debugger.db")
        self._conn: sqlite3.Connection = self._connect()
        self.initialize()

    # ── Connection management ─────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def close(self) -> None:
        """Close the underlying database connection."""
        with self._lock:
            self._conn.close()

    def reopen(self) -> None:
        """Close and reopen the connection (useful to verify durability)."""
        with self._lock:
            self.close()
            self._conn = self._connect()

    # ── Schema initialization ─────────────────────────────────────────────────

    def initialize(self) -> None:
        """Create all tables if they do not already exist."""
        with self._lock:
            with self._conn:
                self._conn.executescript("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id      TEXT PRIMARY KEY,
                        language        TEXT NOT NULL DEFAULT 'python',
                        bug_description TEXT NOT NULL,
                        original_source TEXT NOT NULL,
                        trusted_tests   TEXT NOT NULL DEFAULT '',
                        status          TEXT NOT NULL DEFAULT 'pending',
                        max_rounds      INTEGER NOT NULL DEFAULT 3,
                        created_at      TEXT NOT NULL,
                        updated_at      TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS candidates (
                        candidate_id  TEXT PRIMARY KEY,
                        session_id    TEXT NOT NULL REFERENCES sessions(session_id),
                        round_number  INTEGER NOT NULL,
                        agent         TEXT NOT NULL,
                        source_code   TEXT NOT NULL,
                        explanation   TEXT NOT NULL DEFAULT '',
                        base_version  TEXT,
                        created_at    TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_candidates_session
                        ON candidates(session_id);

                    CREATE TABLE IF NOT EXISTS test_results (
                        result_id         TEXT PRIMARY KEY,
                        session_id        TEXT NOT NULL REFERENCES sessions(session_id),
                        candidate_id      TEXT NOT NULL REFERENCES candidates(candidate_id),
                        status            TEXT NOT NULL,
                        exit_code         INTEGER,
                        stdout_excerpt    TEXT NOT NULL DEFAULT '',
                        stderr_excerpt    TEXT NOT NULL DEFAULT '',
                        per_test_results  TEXT NOT NULL DEFAULT '[]',
                        duration_ms       REAL NOT NULL DEFAULT 0.0,
                        failure_signature TEXT,
                        sandbox_id        TEXT,
                        created_at        TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_results_session
                        ON test_results(session_id);

                    CREATE INDEX IF NOT EXISTS idx_results_candidate
                        ON test_results(candidate_id);

                    CREATE TABLE IF NOT EXISTS constraints (
                        constraint_id        TEXT PRIMARY KEY,
                        session_id           TEXT NOT NULL REFERENCES sessions(session_id),
                        round_number         INTEGER NOT NULL,
                        source_candidate_id  TEXT NOT NULL REFERENCES candidates(candidate_id),
                        evidence_result_id   TEXT NOT NULL REFERENCES test_results(result_id),
                        failure_signature    TEXT NOT NULL,
                        constraint_text      TEXT NOT NULL,
                        status               TEXT NOT NULL DEFAULT 'active',
                        confidence           REAL NOT NULL DEFAULT 1.0,
                        created_at           TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_constraints_session
                        ON constraints(session_id);

                    CREATE TABLE IF NOT EXISTS session_results (
                        session_id      TEXT PRIMARY KEY,
                        result_json     TEXT NOT NULL,
                        created_at      TEXT NOT NULL
                    );
                """)

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _cap(text: str) -> str:
        """Cap a text field at ``_EXCERPT_MAX`` characters."""
        return text[:_EXCERPT_MAX] if len(text) > _EXCERPT_MAX else text

    @staticmethod
    def _row_to_session(row: sqlite3.Row) -> DebugSession:
        return DebugSession(
            session_id=row["session_id"],
            language=row["language"],
            bug_description=row["bug_description"],
            original_source=row["original_source"],
            trusted_tests=row["trusted_tests"],
            status=SessionStatus(row["status"]),
            max_rounds=row["max_rounds"],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )

    @staticmethod
    def _row_to_candidate(row: sqlite3.Row) -> CandidatePatch:
        return CandidatePatch(
            candidate_id=row["candidate_id"],
            session_id=row["session_id"],
            round_number=row["round_number"],
            agent=row["agent"],
            source_code=row["source_code"],
            explanation=row["explanation"],
            base_version=row["base_version"],
            created_at=_parse_dt(row["created_at"]),
        )

    @staticmethod
    def _row_to_result(row: sqlite3.Row) -> TestResult:
        per_test_raw = json.loads(row["per_test_results"] or "[]")
        per_test = [PerTestResult(**r) for r in per_test_raw]
        return TestResult(
            result_id=row["result_id"],
            candidate_id=row["candidate_id"],
            session_id=row["session_id"],
            status=ExecutionStatus(row["status"]),
            exit_code=row["exit_code"],
            stdout_excerpt=row["stdout_excerpt"],
            stderr_excerpt=row["stderr_excerpt"],
            per_test_results=per_test,
            duration_ms=row["duration_ms"],
            failure_signature=row["failure_signature"],
            sandbox_id=row["sandbox_id"],
            created_at=_parse_dt(row["created_at"]),
        )

    @staticmethod
    def _row_to_constraint(row: sqlite3.Row) -> Constraint:
        return Constraint(
            constraint_id=row["constraint_id"],
            session_id=row["session_id"],
            round_number=row["round_number"],
            source_candidate_id=row["source_candidate_id"],
            evidence_result_id=row["evidence_result_id"],
            failure_signature=row["failure_signature"],
            constraint_text=row["constraint_text"],
            status=ConstraintStatus(row["status"]),
            confidence=row["confidence"],
            created_at=_parse_dt(row["created_at"]),
        )

    # ── Sessions ──────────────────────────────────────────────────────────────

    def create_session(self, session: DebugSession) -> DebugSession:
        """
        Persist a new ``DebugSession``.

        Parameters
        ----------
        session:
            Fully populated session object (``session_id`` must be set).

        Returns
        -------
        DebugSession
            The persisted session (same object, for convenience).
        """
        with self._lock:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO sessions
                        (session_id, language, bug_description, original_source,
                         trusted_tests, status, max_rounds, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session.session_id,
                        session.language,
                        session.bug_description,
                        session.original_source,
                        session.trusted_tests,
                        session.status.value,
                        session.max_rounds,
                        session.created_at.isoformat(),
                        session.updated_at.isoformat(),
                    ),
                )
        return session

    def get_session(self, session_id: str) -> DebugSession | None:
        """Return a session by ID, or ``None`` if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            return self._row_to_session(row) if row else None

    def update_session_status(self, session_id: str, status: SessionStatus) -> None:
        """Update the ``status`` field of an existing session."""
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "UPDATE sessions SET status = ?, updated_at = ? WHERE session_id = ?",
                    (status.value, _now_iso(), session_id),
                )

    def update_session_tests(self, session_id: str, trusted_tests: str) -> None:
        """Update the trusted_tests field of an existing session."""
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "UPDATE sessions SET trusted_tests = ?, updated_at = ? WHERE session_id = ?",
                    (trusted_tests, _now_iso(), session_id),
                )

    def list_sessions(self) -> list[DebugSession]:
        """Return all sessions ordered by creation time (newest first)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC"
            ).fetchall()
            return [self._row_to_session(r) for r in rows]

    # ── Candidates ────────────────────────────────────────────────────────────

    def save_candidate(self, candidate: CandidatePatch) -> CandidatePatch:
        """
        Persist a ``CandidatePatch``.

        The parent session must already exist (enforced by foreign key).
        """
        with self._lock:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO candidates
                        (candidate_id, session_id, round_number, agent, source_code,
                         explanation, base_version, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        candidate.candidate_id,
                        candidate.session_id,
                        candidate.round_number,
                        candidate.agent,
                        candidate.source_code,
                        candidate.explanation,
                        candidate.base_version,
                        candidate.created_at.isoformat(),
                    ),
                )
        return candidate

    def get_candidate(self, candidate_id: str) -> CandidatePatch | None:
        """Return a candidate by ID, or ``None`` if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM candidates WHERE candidate_id = ?", (candidate_id,)
            ).fetchone()
            return self._row_to_candidate(row) if row else None

    def list_candidates(self, session_id: str) -> list[CandidatePatch]:
        """Return all candidates for a session, ordered by round and creation time."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM candidates
                WHERE session_id = ?
                ORDER BY round_number ASC, created_at ASC
                """,
                (session_id,),
            ).fetchall()
            return [self._row_to_candidate(r) for r in rows]

    # ── Test Results ──────────────────────────────────────────────────────────

    def save_test_result(self, result: TestResult) -> TestResult:
        """
        Persist a ``TestResult``.

        Both the parent session and candidate must already exist.
        stdout/stderr excerpts are capped before storage.
        """
        per_test_json = json.dumps([r.model_dump() for r in result.per_test_results])
        with self._lock:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO test_results
                        (result_id, session_id, candidate_id, status, exit_code,
                         stdout_excerpt, stderr_excerpt, per_test_results,
                         duration_ms, failure_signature, sandbox_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result.result_id,
                        result.session_id,
                        result.candidate_id,
                        result.status.value,
                        result.exit_code,
                        self._cap(result.stdout_excerpt),
                        self._cap(result.stderr_excerpt),
                        per_test_json,
                        result.duration_ms,
                        result.failure_signature,
                        result.sandbox_id,
                        result.created_at.isoformat(),
                    ),
                )
        return result

    def get_test_result(self, result_id: str) -> TestResult | None:
        """Return a test result by ID, or ``None`` if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM test_results WHERE result_id = ?", (result_id,)
            ).fetchone()
            return self._row_to_result(row) if row else None

    def list_test_results(self, session_id: str) -> list[TestResult]:
        """Return all test results for a session, newest first."""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM test_results
                WHERE session_id = ?
                ORDER BY created_at DESC
                """,
                (session_id,),
            ).fetchall()
            return [self._row_to_result(r) for r in rows]

    # ── Constraints ───────────────────────────────────────────────────────────

    def save_constraint(self, constraint: Constraint) -> Constraint:
        """
        Persist a ``Constraint``.

        The parent session, candidate, and evidence result must already
        exist (enforced by foreign keys).
        """
        with self._lock:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT INTO constraints
                        (constraint_id, session_id, round_number, source_candidate_id,
                         evidence_result_id, failure_signature, constraint_text,
                         status, confidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        constraint.constraint_id,
                        constraint.session_id,
                        constraint.round_number,
                        constraint.source_candidate_id,
                        constraint.evidence_result_id,
                        constraint.failure_signature,
                        constraint.constraint_text,
                        constraint.status.value,
                        constraint.confidence,
                        constraint.created_at.isoformat(),
                    ),
                )
        return constraint

    def list_constraints(
        self, session_id: str, limit: int = 10
    ) -> list[Constraint]:
        """
        Return active constraints for *session_id*, newest first.

        Parameters
        ----------
        session_id:
            The session to retrieve constraints for.
        limit:
            Maximum number of constraints to return (default 10).

        Returns
        -------
        list[Constraint]
            Active constraints ordered by creation time (newest first).
        """
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT * FROM constraints
                WHERE session_id = ? AND status = 'active'
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, max(1, limit)),
            ).fetchall()
            return [self._row_to_constraint(r) for r in rows]

    def constraint_exists(self, session_id: str, failure_signature: str) -> bool:
        """
        Return True if an active constraint with this failure signature
        already exists for *session_id*.

        Used by the ledger for deduplication.
        """
        with self._lock:
            row = self._conn.execute(
                """
                SELECT 1 FROM constraints
                WHERE session_id = ? AND failure_signature = ? AND status = 'active'
                LIMIT 1
                """,
                (session_id, failure_signature),
            ).fetchone()
            return row is not None

    # ── Session Results ───────────────────────────────────────────────────────

    def save_session_result(self, session_id: str, result: dict[str, Any]) -> None:
        """Persist or update the finalized result object for a session."""
        with self._lock:
            with self._conn:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO session_results
                        (session_id, result_json, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (session_id, json.dumps(result), _now_iso()),
                )

    def get_session_result(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve the finalized result object for a session, or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT result_json FROM session_results WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if not row:
                return None
            return json.loads(row["result_json"])

    # ── Session history ───────────────────────────────────────────────────────

    def get_session_history(self, session_id: str) -> dict[str, Any]:
        """
        Return a summary of everything recorded for *session_id*.

        Useful for Member 1's orchestrator to inspect current state.

        Returns
        -------
        dict
            Keys: ``session``, ``candidates``, ``test_results``,
            ``constraints``.  ``session`` is ``None`` if not found.
        """
        with self._lock:
            return {
                "session": (s := self.get_session(session_id)) and s.model_dump(),
                "candidates": [c.model_dump() for c in self.list_candidates(session_id)],
                "test_results": [r.model_dump() for r in self.list_test_results(session_id)],
                "constraints": [c.model_dump() for c in self.list_constraints(session_id)],
            }


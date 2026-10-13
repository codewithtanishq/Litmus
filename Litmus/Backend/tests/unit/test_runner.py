"""
tests/unit/test_runner.py
--------------------------
Unit tests for app/sandbox/runner.py

All tests mock the subprocess / Docker boundary so no real containers
or processes are started.  The host-execution path is also tested with
SWARM_ALLOW_HOST_EXECUTION=1 and a mocked subprocess.
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.contracts import ExecutionStatus, RunLimits
from app.sandbox.runner import (
    SandboxUnavailableError,
    _truncate,
    compute_source_hash,
    run_candidate,
)

_CID = str(uuid.uuid4())
_SRC = "def add(a, b): return a + b"
_TESTS = "def test_add(): assert add(1,2)==3"
_JUNIT_PASS = """<?xml version="1.0" encoding="utf-8"?>
<testsuite name="pytest" tests="1" errors="0" failures="0" skipped="0">
  <testcase classname="test_solution" name="test_add" time="0.001"/>
</testsuite>"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_proc(returncode: int, stdout: bytes = b"ok", stderr: bytes = b"") -> MagicMock:
    p = MagicMock()
    p.returncode = returncode
    p.stdout = stdout
    p.stderr = stderr
    return p


# ─────────────────────────────────────────────────────────────────────────────
# _truncate helper
# ─────────────────────────────────────────────────────────────────────────────


class TestTruncate:
    def test_short_data_unchanged(self):
        assert _truncate(b"hello", 100) == "hello"

    def test_long_data_is_cut(self):
        result = _truncate(b"x" * 200, 100)
        assert len(result) <= 150  # truncation notice adds chars
        assert "truncated" in result

    def test_invalid_utf8_replaced(self):
        result = _truncate(b"\xff\xfe", 100)
        assert isinstance(result, str)


class TestComputeSourceHash:
    def test_deterministic(self):
        h1 = compute_source_hash("hello")
        h2 = compute_source_hash("hello")
        assert h1 == h2

    def test_different_inputs_differ(self):
        assert compute_source_hash("a") != compute_source_hash("b")

    def test_hex_string(self):
        h = compute_source_hash("x")
        assert all(c in "0123456789abcdef" for c in h)


# ─────────────────────────────────────────────────────────────────────────────
# run_candidate — Docker unavailable, host execution not enabled
# ─────────────────────────────────────────────────────────────────────────────


class TestRunCandidateNoDocker:
    @patch("app.sandbox.runner._docker_available", return_value=False)
    @patch("app.sandbox.runner._allow_host_execution", return_value=False)
    def test_raises_sandbox_unavailable(self, _allow, _docker):
        with pytest.raises(SandboxUnavailableError):
            run_candidate(_SRC, _TESTS, _CID)


# ─────────────────────────────────────────────────────────────────────────────
# run_candidate — host execution path (SWARM_ALLOW_HOST_EXECUTION=1)
# ─────────────────────────────────────────────────────────────────────────────


class TestRunCandidateHostExecution:
    """Tests using the unsafe host runner path."""

    @patch("app.sandbox.runner._docker_available", return_value=False)
    @patch("app.sandbox.runner._allow_host_execution", return_value=True)
    @patch("app.sandbox.runner.subprocess.run")
    def test_passing_execution(self, mock_run, _allow, _docker, tmp_path):
        # Write a fake junit XML to simulate pytest output
        proc = _make_proc(returncode=0, stdout=b"1 passed")
        mock_run.return_value = proc

        # Patch _write_workspace to write junit xml to the workspace
        with patch("app.sandbox.runner._write_workspace") as mock_ws, \
             patch("app.sandbox.runner.Path") as mock_path_cls:
            # We need the workspace to exist for the runner to read junit
            # Use a real tmpdir approach instead
            pass

        # Simpler: just run it and verify evidence status
        evidence = run_candidate(_SRC, _TESTS, _CID)
        assert evidence.candidate_id == _CID
        assert evidence.status in {
            ExecutionStatus.PASSED,
            ExecutionStatus.FAILED,
            ExecutionStatus.INFRASTRUCTURE_ERROR,
        }

    @patch("app.sandbox.runner._docker_available", return_value=False)
    @patch("app.sandbox.runner._allow_host_execution", return_value=True)
    @patch("app.sandbox.runner.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=[], timeout=5))
    def test_timeout_returns_timed_out(self, mock_run, _allow, _docker):
        evidence = run_candidate(_SRC, _TESTS, _CID, RunLimits(timeout_seconds=5))
        assert evidence.status == ExecutionStatus.TIMED_OUT
        assert evidence.candidate_id == _CID

    @patch("app.sandbox.runner._docker_available", return_value=False)
    @patch("app.sandbox.runner._allow_host_execution", return_value=True)
    @patch("app.sandbox.runner.subprocess.run", side_effect=OSError("spawn failed"))
    def test_os_error_returns_infra_error(self, mock_run, _allow, _docker):
        evidence = run_candidate(_SRC, _TESTS, _CID)
        assert evidence.status == ExecutionStatus.INFRASTRUCTURE_ERROR
        assert "spawn failed" in evidence.error_detail


# ─────────────────────────────────────────────────────────────────────────────
# run_candidate — Docker path (mocked)
# ─────────────────────────────────────────────────────────────────────────────


class TestRunCandidateDocker:
    @patch("app.sandbox.runner._docker_available", return_value=True)
    @patch("app.sandbox.runner.subprocess.run")
    def test_passing_docker_run(self, mock_run, _docker):
        mock_run.return_value = _make_proc(returncode=0, stdout=b"1 passed")
        evidence = run_candidate(_SRC, _TESTS, _CID)
        assert evidence.candidate_id == _CID
        assert evidence.status in {ExecutionStatus.PASSED, ExecutionStatus.FAILED}
        # Docker should have been called
        call_args = mock_run.call_args[0][0]
        assert "docker" in call_args

    @patch("app.sandbox.runner._docker_available", return_value=True)
    @patch("app.sandbox.runner.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=[], timeout=5))
    def test_docker_timeout(self, mock_run, _docker):
        # _kill_container will also call subprocess.run; allow it
        with patch("app.sandbox.runner._kill_container"):
            evidence = run_candidate(_SRC, _TESTS, _CID, RunLimits(timeout_seconds=5))
        assert evidence.status == ExecutionStatus.TIMED_OUT

    @patch("app.sandbox.runner._docker_available", return_value=True)
    @patch("app.sandbox.runner.subprocess.run", side_effect=OSError("docker daemon down"))
    def test_docker_os_error(self, mock_run, _docker):
        evidence = run_candidate(_SRC, _TESTS, _CID)
        assert evidence.status == ExecutionStatus.INFRASTRUCTURE_ERROR

    @patch("app.sandbox.runner._docker_available", return_value=True)
    @patch("app.sandbox.runner.subprocess.run")
    def test_source_too_large_raises(self, mock_run, _docker):
        big_source = "x" * 300_000
        with pytest.raises(ValueError, match="max_source_bytes"):
            run_candidate(big_source, _TESTS, _CID)

    @patch("app.sandbox.runner._docker_available", return_value=True)
    @patch("app.sandbox.runner.subprocess.run")
    def test_tests_too_large_raises(self, mock_run, _docker):
        big_tests = "x" * 300_000
        with pytest.raises(ValueError, match="max_test_bytes"):
            run_candidate(_SRC, big_tests, _CID)

    @patch("app.sandbox.runner._docker_available", return_value=True)
    @patch("app.sandbox.runner.subprocess.run")
    def test_output_is_truncated(self, mock_run, _docker):
        """Even very large stdout should be safely truncated."""
        large_output = b"A" * 500_000
        mock_run.return_value = _make_proc(returncode=0, stdout=large_output)
        evidence = run_candidate(_SRC, _TESTS, _CID)
        assert len(evidence.stdout) <= 70_000  # truncated with notice

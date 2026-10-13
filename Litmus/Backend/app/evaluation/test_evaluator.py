"""
app/evaluation/test_evaluator.py
=================================
Transform raw ``ExecutionEvidence`` into a deterministic ``TestResult``.

Design decisions
----------------
* Pass/fail is determined from the JUnit XML report, NOT from the
  process exit code alone.  Exit code 0 with an empty or corrupt report
  is treated as ``infrastructure_error``, not ``passed``.
* JUnit XML is parsed with ``defusedxml`` to prevent XML entity attacks.
* A missing or malformed report is never treated as success.
* An empty test suite (zero tests in the report) is treated as
  ``infrastructure_error`` with a clear message, so the system never
  claims "all tests passed" when no tests actually ran.
* Per-test results are extracted with truncated failure messages.
* Failure signatures are computed as a stable SHA-256 hash over the
  sorted set of failing test names so duplicates can be detected.
* Log excerpts are capped at ``_EXCERPT_BYTES`` per stream.

Public API
----------
``evaluate_candidate(evidence, result_id, session_id)``
    → ``TestResult``
"""

from __future__ import annotations

import hashlib
import io
import uuid
from datetime import datetime, timezone
from typing import Final

import defusedxml.ElementTree as ET  # safe XML parsing

from app.contracts import (
    ExecutionEvidence,
    ExecutionStatus,
    PerTestResult,
    TestResult,
)

_EXCERPT_BYTES: Final[int] = 4096
_MAX_MESSAGE_BYTES: Final[int] = 512  # per failing test message


# ─────────────────────────────────────────────────────────────────────────────
# JUnit XML parsing
# ─────────────────────────────────────────────────────────────────────────────


class _JUnitParseError(Exception):
    """Raised when the JUnit XML cannot be parsed or is structurally invalid."""


def _parse_junit_xml(xml_text: str) -> list[PerTestResult]:
    """
    Parse a JUnit XML string and return per-test results.

    Parameters
    ----------
    xml_text:
        Raw JUnit XML produced by ``pytest --junitxml=...``.

    Returns
    -------
    list[PerTestResult]
        One entry per ``<testcase>`` element.

    Raises
    ------
    _JUnitParseError
        If the XML is missing, malformed, or lacks expected structure.
    """
    if not xml_text or not xml_text.strip():
        raise _JUnitParseError("JUnit XML content is empty.")

    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except ET.ParseError as exc:
        raise _JUnitParseError(f"XML parse error: {exc}") from exc

    # pytest wraps everything in <testsuites><testsuite> or just <testsuite>
    testcases: list = []
    if root.tag == "testsuites":
        for suite in root.findall("testsuite"):
            testcases.extend(suite.findall("testcase"))
    elif root.tag == "testsuite":
        testcases = root.findall("testcase")
    else:
        raise _JUnitParseError(
            f"Unexpected root element <{root.tag}>; expected <testsuite> or <testsuites>."
        )

    results: list[PerTestResult] = []
    for tc in testcases:
        name = tc.get("classname", "") + "::" + tc.get("name", "")
        name = name.lstrip(":")

        failure = tc.find("failure")
        error = tc.find("error")
        skipped = tc.find("skipped")

        if failure is not None:
            msg = (failure.get("message") or failure.text or "")[:_MAX_MESSAGE_BYTES]
            results.append(PerTestResult(test_name=name, status="failed", message=msg))
        elif error is not None:
            msg = (error.get("message") or error.text or "")[:_MAX_MESSAGE_BYTES]
            results.append(PerTestResult(test_name=name, status="error", message=msg))
        elif skipped is not None:
            results.append(PerTestResult(test_name=name, status="skipped", message=""))
        else:
            results.append(PerTestResult(test_name=name, status="passed", message=""))

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Failure signature
# ─────────────────────────────────────────────────────────────────────────────


def _compute_failure_signature(per_test: list[PerTestResult]) -> str | None:
    """
    Return a stable hex digest over the sorted set of failed test names.

    Returns ``None`` if there are no failures.
    """
    failed_names = sorted(
        r.test_name for r in per_test if r.status in {"failed", "error"}
    )
    if not failed_names:
        return None
    blob = "\n".join(failed_names).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


# ─────────────────────────────────────────────────────────────────────────────
# Excerpt helpers
# ─────────────────────────────────────────────────────────────────────────────


def _excerpt(text: str, max_bytes: int = _EXCERPT_BYTES) -> str:
    """Truncate *text* to *max_bytes* characters."""
    if len(text) > max_bytes:
        return text[:max_bytes] + f"\n[... truncated at {max_bytes} chars ...]"
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def evaluate_candidate(
    evidence: ExecutionEvidence,
    session_id: str,
    result_id: str | None = None,
) -> TestResult:
    """
    Transform raw sandbox evidence into a deterministic ``TestResult``.

    Rules
    -----
    * ``timed_out`` / ``infrastructure_error`` evidence → same status in
      ``TestResult``; per-test results are empty.
    * If execution finished (exit code available) but JUnit XML is absent,
      malformed, or empty → ``infrastructure_error`` (never ``passed``).
    * ``passed`` only when ALL trusted tests completed successfully and the
      JUnit XML confirms it.
    * ``failed`` when one or more tests reported failure/error.

    Parameters
    ----------
    evidence:
        Raw ``ExecutionEvidence`` from ``runner.run_candidate``.
    session_id:
        The session this evaluation belongs to.
    result_id:
        Optional pre-generated UUID for the result record.  A new UUID
        is generated if omitted.

    Returns
    -------
    TestResult
        Structured, deterministic evaluation result.
    """
    rid = result_id or str(uuid.uuid4())

    stdout_ex = _excerpt(evidence.stdout)
    stderr_ex = _excerpt(evidence.stderr)

    # ── Pass-through for non-execution statuses ───────────────────────────────
    if evidence.status == ExecutionStatus.TIMED_OUT:
        return TestResult(
            result_id=rid,
            candidate_id=evidence.candidate_id,
            session_id=session_id,
            status=ExecutionStatus.TIMED_OUT,
            exit_code=evidence.exit_code,
            stdout_excerpt=stdout_ex,
            stderr_excerpt=stderr_ex,
            duration_ms=evidence.duration_ms,
        )

    if evidence.status == ExecutionStatus.INFRASTRUCTURE_ERROR:
        return TestResult(
            result_id=rid,
            candidate_id=evidence.candidate_id,
            session_id=session_id,
            status=ExecutionStatus.INFRASTRUCTURE_ERROR,
            exit_code=evidence.exit_code,
            stdout_excerpt=stdout_ex,
            stderr_excerpt=stderr_ex + (
                f"\n[infrastructure error]: {evidence.error_detail}"
                if evidence.error_detail else ""
            ),
            duration_ms=evidence.duration_ms,
        )

    # ── Execution completed (PASSED or FAILED from runner) ────────────────────
    xml_source = evidence.junit_xml_content
    if not xml_source and evidence.junit_xml_path:
        try:
            from pathlib import Path as _Path
            xml_source = _Path(evidence.junit_xml_path).read_text(encoding="utf-8")
        except OSError:
            pass

    if not xml_source:
        # No JUnit XML — cannot reliably determine pass/fail
        return TestResult(
            result_id=rid,
            candidate_id=evidence.candidate_id,
            session_id=session_id,
            status=ExecutionStatus.INFRASTRUCTURE_ERROR,
            exit_code=evidence.exit_code,
            stdout_excerpt=stdout_ex,
            stderr_excerpt=stderr_ex,
            duration_ms=evidence.duration_ms,
            failure_signature="missing_junit_xml",
        )

    try:
        per_test = _parse_junit_xml(xml_source)
    except _JUnitParseError as exc:
        return TestResult(
            result_id=rid,
            candidate_id=evidence.candidate_id,
            session_id=session_id,
            status=ExecutionStatus.INFRASTRUCTURE_ERROR,
            exit_code=evidence.exit_code,
            stdout_excerpt=stdout_ex,
            stderr_excerpt=stderr_ex + f"\n[junit parse error]: {exc}",
            duration_ms=evidence.duration_ms,
            failure_signature="corrupt_junit_xml",
        )

    # Empty test suite — policy: infrastructure error
    if len(per_test) == 0:
        return TestResult(
            result_id=rid,
            candidate_id=evidence.candidate_id,
            session_id=session_id,
            status=ExecutionStatus.INFRASTRUCTURE_ERROR,
            exit_code=evidence.exit_code,
            stdout_excerpt=stdout_ex,
            stderr_excerpt=stderr_ex,
            duration_ms=evidence.duration_ms,
            failure_signature="empty_test_suite",
        )

    failed = [r for r in per_test if r.status in {"failed", "error"}]
    sig = _compute_failure_signature(per_test)

    overall_status = ExecutionStatus.PASSED if not failed else ExecutionStatus.FAILED

    return TestResult(
        result_id=rid,
        candidate_id=evidence.candidate_id,
        session_id=session_id,
        status=overall_status,
        exit_code=evidence.exit_code,
        stdout_excerpt=stdout_ex,
        stderr_excerpt=stderr_ex,
        per_test_results=per_test,
        duration_ms=evidence.duration_ms,
        failure_signature=sig,
    )

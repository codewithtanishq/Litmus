"""
tests/unit/test_evaluator.py
-----------------------------
Unit tests for app/evaluation/test_evaluator.py

All seven required scenarios from the spec are tested.
"""

from __future__ import annotations

import uuid

import pytest

from app.contracts import ExecutionEvidence, ExecutionStatus
from app.evaluation.test_evaluator import _parse_junit_xml, evaluate_candidate

_CID = str(uuid.uuid4())
_SID = str(uuid.uuid4())

# ─────────────────────────────────────────────────────────────────────────────
# JUnit XML fixtures
# ─────────────────────────────────────────────────────────────────────────────

JUNIT_ALL_PASS = """<?xml version="1.0"?>
<testsuite name="pytest" tests="2" errors="0" failures="0" skipped="0">
  <testcase classname="test_sol" name="test_add" time="0.001"/>
  <testcase classname="test_sol" name="test_sub" time="0.001"/>
</testsuite>"""

JUNIT_ONE_FAIL = """<?xml version="1.0"?>
<testsuite name="pytest" tests="2" errors="0" failures="1" skipped="0">
  <testcase classname="test_sol" name="test_add" time="0.001"/>
  <testcase classname="test_sol" name="test_empty_input" time="0.002">
    <failure message="IndexError: list index out of range">
      AssertionError: assert -1 == 0
    </failure>
  </testcase>
</testsuite>"""

JUNIT_EMPTY = """<?xml version="1.0"?>
<testsuite name="pytest" tests="0" errors="0" failures="0" skipped="0">
</testsuite>"""

JUNIT_WRAPPED = """<?xml version="1.0"?>
<testsuites>
  <testsuite name="pytest" tests="1" errors="0" failures="0" skipped="0">
    <testcase classname="test_sol" name="test_ok" time="0.001"/>
  </testsuite>
</testsuites>"""

JUNIT_CORRUPT = "not xml at all <<<"

JUNIT_BAD_ROOT = """<?xml version="1.0"?>
<rootlement><child/></rootlement>"""


# ─────────────────────────────────────────────────────────────────────────────
# _parse_junit_xml unit tests
# ─────────────────────────────────────────────────────────────────────────────


class TestParseJUnitXml:
    def test_all_pass(self):
        results = _parse_junit_xml(JUNIT_ALL_PASS)
        assert len(results) == 2
        assert all(r.status == "passed" for r in results)

    def test_one_fail_detected(self):
        results = _parse_junit_xml(JUNIT_ONE_FAIL)
        failed = [r for r in results if r.status == "failed"]
        assert len(failed) == 1
        assert "IndexError" in failed[0].message

    def test_wrapped_in_testsuites(self):
        results = _parse_junit_xml(JUNIT_WRAPPED)
        assert len(results) == 1
        assert results[0].status == "passed"

    def test_empty_suite_returns_empty_list(self):
        results = _parse_junit_xml(JUNIT_EMPTY)
        assert results == []

    def test_corrupt_xml_raises(self):
        from app.evaluation.test_evaluator import _JUnitParseError
        with pytest.raises(_JUnitParseError):
            _parse_junit_xml(JUNIT_CORRUPT)

    def test_bad_root_element_raises(self):
        from app.evaluation.test_evaluator import _JUnitParseError
        with pytest.raises(_JUnitParseError, match="Unexpected root"):
            _parse_junit_xml(JUNIT_BAD_ROOT)

    def test_empty_string_raises(self):
        from app.evaluation.test_evaluator import _JUnitParseError
        with pytest.raises(_JUnitParseError):
            _parse_junit_xml("")


# ─────────────────────────────────────────────────────────────────────────────
# evaluate_candidate — all seven required scenarios
# ─────────────────────────────────────────────────────────────────────────────


def _evidence(status: ExecutionStatus, junit: str | None = None, **kw) -> ExecutionEvidence:
    return ExecutionEvidence(
        candidate_id=_CID,
        status=status,
        junit_xml_content=junit,
        **kw,
    )


class TestEvaluateCandidate:

    # 1. All tests passing
    def test_all_tests_passing(self):
        ev = _evidence(ExecutionStatus.FAILED, junit=JUNIT_ALL_PASS, exit_code=0)
        result = evaluate_candidate(ev, _SID)
        assert result.status == ExecutionStatus.PASSED
        assert result.failure_signature is None
        assert all(r.status == "passed" for r in result.per_test_results)

    # 2. One or more assertion failures
    def test_one_test_failing(self):
        ev = _evidence(ExecutionStatus.FAILED, junit=JUNIT_ONE_FAIL, exit_code=1)
        result = evaluate_candidate(ev, _SID)
        assert result.status == ExecutionStatus.FAILED
        assert result.failure_signature is not None
        failed = [r for r in result.per_test_results if r.status == "failed"]
        assert len(failed) == 1

    # 3. Timeout
    def test_timeout(self):
        ev = _evidence(ExecutionStatus.TIMED_OUT)
        result = evaluate_candidate(ev, _SID)
        assert result.status == ExecutionStatus.TIMED_OUT
        assert result.per_test_results == []

    # 4. Infrastructure error
    def test_infra_error(self):
        ev = _evidence(ExecutionStatus.INFRASTRUCTURE_ERROR, error_detail="daemon down")
        result = evaluate_candidate(ev, _SID)
        assert result.status == ExecutionStatus.INFRASTRUCTURE_ERROR
        assert "daemon down" in result.stderr_excerpt

    # 5. Missing test report — never treated as success
    def test_missing_junit_xml_is_infra_error(self):
        ev = _evidence(ExecutionStatus.PASSED, junit=None, exit_code=0)
        result = evaluate_candidate(ev, _SID)
        assert result.status == ExecutionStatus.INFRASTRUCTURE_ERROR
        assert result.failure_signature == "missing_junit_xml"

    # 6. Corrupt test report
    def test_corrupt_junit_xml_is_infra_error(self):
        ev = _evidence(ExecutionStatus.FAILED, junit=JUNIT_CORRUPT, exit_code=1)
        result = evaluate_candidate(ev, _SID)
        assert result.status == ExecutionStatus.INFRASTRUCTURE_ERROR
        assert result.failure_signature == "corrupt_junit_xml"

    # 7. Empty test suite — policy: infrastructure_error
    def test_empty_test_suite_is_infra_error(self):
        ev = _evidence(ExecutionStatus.PASSED, junit=JUNIT_EMPTY, exit_code=0)
        result = evaluate_candidate(ev, _SID)
        assert result.status == ExecutionStatus.INFRASTRUCTURE_ERROR
        assert result.failure_signature == "empty_test_suite"

    # Exit code 0 alone must NOT mean passed
    def test_exit_code_zero_without_xml_is_not_passed(self):
        ev = _evidence(ExecutionStatus.PASSED, junit=None, exit_code=0)
        result = evaluate_candidate(ev, _SID)
        assert result.status != ExecutionStatus.PASSED

    # result_id is preserved when supplied
    def test_result_id_is_preserved(self):
        rid = str(uuid.uuid4())
        ev = _evidence(ExecutionStatus.FAILED, junit=JUNIT_ALL_PASS, exit_code=0)
        result = evaluate_candidate(ev, _SID, result_id=rid)
        assert result.result_id == rid

    # Failure signature is stable (same failing tests → same signature)
    def test_failure_signature_is_stable(self):
        ev = _evidence(ExecutionStatus.FAILED, junit=JUNIT_ONE_FAIL, exit_code=1)
        r1 = evaluate_candidate(ev, _SID)
        r2 = evaluate_candidate(ev, _SID)
        assert r1.failure_signature == r2.failure_signature

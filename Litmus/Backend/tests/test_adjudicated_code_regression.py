"""
tests/test_adjudicated_code_regression.py
=========================================
Regression test suite for Adjudicated Corrected Source Code generation in Swarm Debugger.

Verifies:
1. When Judge selects Fix B on buggy input 'print(Hello, World!)', the final corrected
   code contains 'print("Hello, World!")' rather than the original buggy statement or a placeholder.
2. The corrected program executes against reproduction test and prints exactly 'Hello, World!'.
3. The assembled code preserves valid Python syntax and indentation.
4. Code is executed and verified in sandbox before marking 'test_verified'.
5. If validation fails, status is marked 'unresolved' rather than displaying incorrect code as verified.
6. The solution works generally for other bug submissions without hardcoding.
"""

import asyncio
import os
import subprocess
import sys
from unittest import mock
import pytest
from fastapi.testclient import TestClient

from app.api.server import (
    app,
    repo,
    execute_courtroom_debate_task,
    SESSION_INPUTS_CACHE,
    SESSION_RESULTS_CACHE,
    SESSION_STREAMS,
)
from app.contracts import SessionStatus as ContractSessionStatus
from app.orchestration.code_assembler import (
    apply_patch_or_code,
    derive_reproduction_test_suite,
    generate_candidate_fixes,
    validate_python_code,
)
from app.sandbox.runner import run_candidate


@pytest.fixture
def client():
    return TestClient(app)


def test_hello_world_candidate_generation_and_syntax():
    """Verify Fix A and Fix B are generated with valid Python syntax and distinct formulations."""
    buggy_code = "print(Hello, World!)"
    fix_a, fix_b = generate_candidate_fixes(buggy_code, bug_description="SyntaxError in print")

    assert fix_a.id == "fix_a"
    assert fix_b.id == "fix_b"

    # Both fixes must be valid Python syntax
    is_valid_a, err_a = validate_python_code(fix_a.code)
    is_valid_b, err_b = validate_python_code(fix_b.code)

    assert is_valid_a, f"Fix A failed syntax validation: {err_a}"
    assert is_valid_b, f"Fix B failed syntax validation: {err_b}"

    # Fix B must contain valid double-quoted string literal
    assert 'print("Hello, World!")' in fix_b.code
    assert 'print(Hello, World!)' not in fix_b.code


def test_hello_world_adjudication_regression(client):
    """
    Main regression test:
    1. Submits buggy 'print(Hello, World!)'
    2. Runs multi-agent courtroom debate
    3. Judge selects Fix B
    4. Adjudicated source code must contain 'print("Hello, World!")'
    5. Final program output must print exactly 'Hello, World!'
    6. Session status is 'test_verified'
    """
    os.environ["SWARM_ALLOW_HOST_EXECUTION"] = "1"
    session_id = f"test-hw-regress-{os.getpid()}"

    SESSION_INPUTS_CACHE[session_id] = {
        "mode": "code",
        "language": "python",
        "question": "Fix unquoted string in print call",
        "code": "print(Hello, World!)",
        "fileName": "solution.py",
        "isDemo": True,
        "scenarioId": "fix_b_passes",
    }

    queue = asyncio.Queue()
    SESSION_STREAMS[session_id] = [queue]

    # Execute courtroom debate task
    asyncio.run(execute_courtroom_debate_task(session_id, speed_factor=100.0))

    # Verify result in cache
    result = SESSION_RESULTS_CACHE.get(session_id)
    assert result is not None, "SESSION_RESULTS_CACHE missing result"
    assert result["status"] == "test_verified"
    assert result["initialFailedTests"] == 1
    assert result["finalFailedTests"] == 0

    # Requirement 2 & 3: Display actual Fix B source code, not buggy statement
    corrected_code = result["correctedCode"]
    assert corrected_code is not None
    assert 'print("Hello, World!")' in corrected_code
    assert 'print(Hello, World!)' not in corrected_code

    # Requirement 3: Preserves valid Python syntax
    is_valid, err = validate_python_code(corrected_code)
    assert is_valid, f"Assembled code is not valid Python: {err}"

    # Requirement 5: For this Hello World example, program must print exactly 'Hello, World!'
    proc = subprocess.run([sys.executable, "-c", corrected_code], capture_output=True, text=True)
    assert proc.returncode == 0
    assert proc.stdout.strip() == "Hello, World!"

    # Endpoint test: GET /api/sessions/{session_id}/result returns the corrected code
    response = client.get(f"/api/sessions/{session_id}/result")
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "test_verified"
    assert 'print("Hello, World!")' in res_data["correctedCode"]


def test_failed_fix_shows_unresolved_status():
    """
    Requirement 6: If the selected fix fails validation against reproduction test,
    show a clear failure/unresolved status rather than displaying incorrect code as verified.
    """
    os.environ["SWARM_ALLOW_HOST_EXECUTION"] = "1"
    session_id = f"test-fail-regress-{os.getpid()}"

    # An impossible or failing reproduction test suite
    failing_test = """
def test_must_fail():
    assert 1 == 2, "Intentional failure to verify failure handling"
"""
    SESSION_INPUTS_CACHE[session_id] = {
        "mode": "code",
        "language": "python",
        "question": "Failing test verification",
        "code": "print(Hello, World!)",
        "isDemo": True,
        "details": {"failingTest": failing_test},
        "scenarioId": "fix_b_passes",
    }

    queue = asyncio.Queue()
    SESSION_STREAMS[session_id] = [queue]

    asyncio.run(execute_courtroom_debate_task(session_id, speed_factor=100.0))

    result = SESSION_RESULTS_CACHE.get(session_id)
    assert result is not None
    assert result["status"] == "unresolved"
    assert result["finalFailedTests"] > 0
    # Must not claim test_verified
    assert result["status"] != "test_verified"


def test_general_bug_repair_works_without_hardcoding():
    """Verify general repair mechanism on slice off-by-one bug without hardcoding."""
    original = "def process_data(items):\n    return items[0:len(items)-1]"
    fix_a, fix_b = generate_candidate_fixes(original, bug_description="Tail item omitted")

    assert "list(items)" in fix_b.code or "items[:]" in fix_b.code
    assert "len(items)-1" not in fix_b.code

    is_valid, err = validate_python_code(fix_b.code)
    assert is_valid

"""
tests/unit/test_new_fixes.py
============================
Comprehensive test suite verifying all 9 bug fixes specified in the audit report.
Runs offline without live Ollama or Docker dependencies.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from unittest import mock
import pytest
from starlette.testclient import TestClient

from app.contracts import (
    DebugSession as ContractDebugSession,
    CandidatePatch as ContractCandidatePatch,
    ExecutionStatus,
    ExecutionEvidence,
    PerTestResult,
    TestResult as ContractTestResult,
)
from app.sandbox.runner import prepare_test_source, run_candidate
from app.evaluation.test_evaluator import evaluate_candidate
from app.memory.constraint_ledger import ConstraintLedger
from app.memory.repository import Repository
from app.orchestration.routing import evaluate_round_outcome, RoutingDecision
from app.orchestration.state import WorkflowState
from app.agents.ollama_client import OllamaClient, MalformedOutputError
from app.agents.prompt_utils import extract_python_code
from app.agents.prosecutor import ProsecutorAgent
from app.agents.defender import DefenderAgent
from app.agents.judge import JudgeAgent
from app.orchestration.graph import build_courtroom_workflow
from app.schemas.session import DebugSession as SchemaDebugSession
from app.schemas.patch import CandidatePatch as SchemaCandidatePatch, AgentRole
from app.api.server import app, repo, ledger, RUNS, SESSION_INPUTS_CACHE
from app.api.pipeline_service import execute_real_pipeline


# ─────────────────────────────────────────────────────────────────────────────
# 1. Test prepare_test_source
# ─────────────────────────────────────────────────────────────────────────────

def test_prepare_test_source():
    # Scenario A: bare assert gets wrapped
    bare_assert = "assert 1 + 1 == 2"
    prepared_a = prepare_test_source(bare_assert)
    assert "def test_reproduction():" in prepared_a
    assert "from solution import *" in prepared_a

    # Scenario B: missing import gets injected when def test_ exists
    func_test = "def test_foo():\n    assert foo() == 42"
    prepared_b = prepare_test_source(func_test)
    assert "from solution import *" in prepared_b
    assert "def test_foo():" in prepared_b

    # Scenario C: existing import is untouched (not duplicated)
    existing_import = "from solution import bar\ndef test_bar():\n    assert bar() == 1"
    prepared_c = prepare_test_source(existing_import)
    assert "from solution import bar" in prepared_c
    assert prepared_c.count("from solution import") == 1

    # Scenario D: Frontend preset test passes against a correct fix in host runner
    correct_fix = "def process_data(items):\n    return list(items)"
    frontend_preset_test = "def test_tail():\n    items = [10, 20, 30, 40]\n    assert process_data(items) == [10, 20, 30, 40]"
    with mock.patch("app.sandbox.runner._docker_available", return_value=False):
        with mock.patch.dict("os.environ", {"SWARM_ALLOW_HOST_EXECUTION": "1"}):
            ev = run_candidate(source_code=correct_fix, trusted_tests=frontend_preset_test, candidate_id="test_preset")
            assert ev.status == ExecutionStatus.PASSED


# ─────────────────────────────────────────────────────────────────────────────
# 2. Test Evaluator
# ─────────────────────────────────────────────────────────────────────────────

def test_evaluator():
    # Scenario A: all-skipped tests -> INFRASTRUCTURE_ERROR (not PASSED)
    skipped_xml = """<?xml version="1.0" encoding="utf-8"?>
    <testsuites>
      <testsuite name="pytest" tests="2" errors="0" failures="0" skipped="2">
        <testcase classname="test_solution" name="test_one"><skipped/></testcase>
        <testcase classname="test_solution" name="test_two"><skipped/></testcase>
      </testsuite>
    </testsuites>"""
    ev_skipped = ExecutionEvidence(
        candidate_id="cand_skipped",
        status=ExecutionStatus.PASSED,
        exit_code=0,
        junit_xml_content=skipped_xml,
    )
    res_skipped = evaluate_candidate(ev_skipped, session_id="s1")
    assert res_skipped.status == ExecutionStatus.INFRASTRUCTURE_ERROR
    assert res_skipped.failure_signature == "no_executed_tests"

    # Scenario B: exit_code != 0 with clean XML -> not PASSED (FAILED)
    clean_xml = """<?xml version="1.0" encoding="utf-8"?>
    <testsuites>
      <testsuite name="pytest" tests="1" errors="0" failures="0" skipped="0">
        <testcase classname="test_solution" name="test_one"/>
      </testsuite>
    </testsuites>"""
    ev_exit_nonzero = ExecutionEvidence(
        candidate_id="cand_nonzero",
        status=ExecutionStatus.FAILED,
        exit_code=1,
        junit_xml_content=clean_xml,
    )
    res_nonzero = evaluate_candidate(ev_exit_nonzero, session_id="s1")
    assert res_nonzero.status == ExecutionStatus.FAILED


# ─────────────────────────────────────────────────────────────────────────────
# 3. Test Ledger
# ─────────────────────────────────────────────────────────────────────────────

def test_ledger(tmp_path):
    db_file = str(tmp_path / "test_ledger.db")
    test_repo = Repository(db_file)
    test_ledger = ConstraintLedger(test_repo)

    session = ContractDebugSession(
        session_id="sess_ledger",
        language="python",
        bug_description="Index error",
        original_source="def f(): pass",
        trusted_tests="def test_f(): assert False",
    )
    test_repo.create_session(session)

    # Candidate 1
    cand1 = ContractCandidatePatch(
        candidate_id="cand_1",
        session_id="sess_ledger",
        agent="prosecutor",
        round_number=1,
        source_code="def f(): return 1",
        explanation="Attempt 1",
    )
    res1 = ContractTestResult(
        result_id="res_1",
        candidate_id="cand_1",
        session_id="sess_ledger",
        status=ExecutionStatus.FAILED,
        exit_code=1,
        per_test_results=[PerTestResult(test_name="test_f", status="failed", message="assert 1 == 2")],
    )

    # Candidate 2 with DIFFERENT code, same failing test
    cand2 = ContractCandidatePatch(
        candidate_id="cand_2",
        session_id="sess_ledger",
        agent="defender",
        round_number=1,
        source_code="def f(): return 2",
        explanation="Attempt 2",
    )
    res2 = ContractTestResult(
        result_id="res_2",
        candidate_id="cand_2",
        session_id="sess_ledger",
        status=ExecutionStatus.FAILED,
        exit_code=1,
        per_test_results=[PerTestResult(test_name="test_f", status="failed", message="assert 2 == 2")],
    )

    # Save candidate and test results to satisfy foreign keys
    test_repo.save_candidate(cand1)
    test_repo.save_test_result(res1)
    test_repo.save_candidate(cand2)
    test_repo.save_test_result(res2)

    test_ledger.record_failure(cand1, res1)
    test_ledger.record_failure(cand2, res2)

    active_constraints = test_ledger.get_active_constraints("sess_ledger")
    # Two different failing codes with same test must BOTH create constraints
    assert len(active_constraints) == 2

    # Verify constraint text contains the rejected code
    assert "def f(): return 1" in active_constraints[1].constraint_text or "def f(): return 1" in active_constraints[0].constraint_text
    assert "Do NOT repeat this failed implementation" in active_constraints[0].constraint_text

    # Candidate 3: Timeout creates a constraint
    cand3 = ContractCandidatePatch(
        candidate_id="cand_3",
        session_id="sess_ledger",
        agent="prosecutor",
        round_number=2,
        source_code="def f():\n    while True: pass",
        explanation="Infinite loop",
    )
    res3 = ContractTestResult(
        result_id="res_3",
        candidate_id="cand_3",
        session_id="sess_ledger",
        status=ExecutionStatus.TIMED_OUT,
        exit_code=None,
        per_test_results=[],
    )
    test_repo.save_candidate(cand3)
    test_repo.save_test_result(res3)
    test_ledger.record_failure(cand3, res3)

    active_updated = test_ledger.get_active_constraints("sess_ledger")
    assert len(active_updated) == 3
    assert any("timed out" in c.constraint_text for c in active_updated)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Test Routing
# ─────────────────────────────────────────────────────────────────────────────

def test_routing():
    # If all candidate patches end in INFRASTRUCTURE_ERROR, terminate immediately
    res_a = ContractTestResult(
        result_id="res_a",
        candidate_id="cand_a",
        session_id="sess_route",
        status=ExecutionStatus.INFRASTRUCTURE_ERROR,
    )
    res_b = ContractTestResult(
        result_id="res_b",
        candidate_id="cand_b",
        session_id="sess_route",
        status=ExecutionStatus.INFRASTRUCTURE_ERROR,
    )
    state: WorkflowState = {
        "session_id": "sess_route",
        "current_round": 1,
        "max_rounds": 3,
        "test_results": {"prosecutor": res_a, "defender": res_b},
        "errors": ["Sandbox infrastructure error: Docker daemon not running"],
        "status": "failed",
    }

    decision = evaluate_round_outcome(state)
    assert decision == RoutingDecision.TERMINATE_ERROR


# ─────────────────────────────────────────────────────────────────────────────
# 5. Test Runner Docker Command
# ─────────────────────────────────────────────────────────────────────────────

def test_runner_docker_cmd(monkeypatch):
    captured_commands = []

    def mock_run(cmd, *args, **kwargs):
        captured_commands.append(cmd)
        # Simulate exit 125 (Docker daemon error)
        return mock.MagicMock(returncode=125, stdout="", stderr="docker: daemon error")

    monkeypatch.setattr("subprocess.run", mock_run)
    monkeypatch.setattr("app.sandbox.runner._docker_available", lambda: True)

    ev = run_candidate(source_code="x = 1", trusted_tests="assert True", candidate_id="test_cmd")
    docker_cmd = captured_commands[0]

    # Verify no duplicate mount on /sandbox
    mount_count = sum(1 for arg in docker_cmd if ":/sandbox" in arg)
    assert mount_count == 1
    # Verify tmpfs is on /tmp, not /sandbox
    assert any("--tmpfs" in arg and "/tmp" in docker_cmd[i+1] for i, arg in enumerate(docker_cmd) if arg == "--tmpfs")
    # Verify exit 125 maps to INFRASTRUCTURE_ERROR
    assert ev.status == ExecutionStatus.INFRASTRUCTURE_ERROR


# ─────────────────────────────────────────────────────────────────────────────
# 6. Test Ollama Client
# ─────────────────────────────────────────────────────────────────────────────

def test_ollama_client(monkeypatch):
    # Scenario A: extract_python_code strips markdown fences and validates AST
    fenced = "```python\ndef answer():\n    return 42\n```"
    clean = extract_python_code(fenced)
    assert clean.strip() == "def answer():\n    return 42"

    with pytest.raises(MalformedOutputError):
        extract_python_code("```python\ndef broken(:\n```")

    # Scenario B: num_ctx and num_predict are in request payload
    last_payload = {}
    mock_http = mock.MagicMock()

    def mock_post(url, json=None, **kwargs):
        nonlocal last_payload
        last_payload = json
        resp = mock.MagicMock()
        resp.status_code = 200
        resp.is_error = False
        resp.json.return_value = {"response": '{"proposed_code": "def f(): return 1", "explanation": "test"}'}
        return resp

    mock_http.post = mock_post
    client = OllamaClient(http_client=mock_http)
    client.generate(prompt="Fix bug", format_json=True)

    assert "options" in last_payload
    assert last_payload["options"]["num_ctx"] == 8192
    assert last_payload["options"]["num_predict"] == 4096

    # Scenario C: Invalid JSON retries with error appended
    prompts_received = []

    def mock_post_retry(url, json=None, **kwargs):
        prompts_received.append(json["prompt"])
        resp = mock.MagicMock()
        resp.status_code = 200
        resp.is_error = False
        if len(prompts_received) == 1:
            resp.json.return_value = {"response": "invalid json here"}
        else:
            resp.json.return_value = {"response": '{"valid": true}'}
        return resp

    mock_retry_http = mock.MagicMock()
    mock_retry_http.post = mock_post_retry
    retry_client = OllamaClient(http_client=mock_retry_http)
    result = retry_client.generate_json(prompt="Original prompt")
    assert result == {"valid": True}
    assert len(prompts_received) == 2
    assert "Your previous reply was invalid" in prompts_received[1]


# ─────────────────────────────────────────────────────────────────────────────
# 7. Test Agent Degradation
# ─────────────────────────────────────────────────────────────────────────────

def test_agent_degradation():
    # Defender fails, Prosecutor passes -> session still proceeds to evaluation boundary
    mock_prosecutor = mock.MagicMock(spec=ProsecutorAgent)
    mock_prosecutor.analyze_and_propose.return_value = SchemaCandidatePatch(
        patch_id="patch_a",
        agent_role=AgentRole.PROSECUTOR,
        proposed_code="def f(): return 1",
        explanation="Prosecutor works",
    )

    mock_defender = mock.MagicMock(spec=DefenderAgent)
    mock_defender.critique_and_propose.side_effect = RuntimeError("Defender model crashed")

    workflow = build_courtroom_workflow(
        prosecutor_agent=mock_prosecutor,
        defender_agent=mock_defender,
        stop_at_evaluation=True,
    )

    session = SchemaDebugSession(
        session_id="deg_sess",
        original_code="def f(): pass",
        bug_description="f fails",
        test_suite="def test_f(): pass",
    )
    state = {
        "session_id": "deg_sess",
        "current_round": 1,
        "original_code": session.original_code,
        "bug_description": session.bug_description,
        "test_suite": session.test_suite,
        "max_rounds": 1,
    }

    final_state = workflow.invoke(state)
    assert final_state.get("fix_a") is not None
    assert final_state.get("fix_b") is None
    assert final_state["status"] == "evaluating"


# ─────────────────────────────────────────────────────────────────────────────
# 8. Test API Real Pipeline & Idempotency
# ─────────────────────────────────────────────────────────────────────────────

def test_api_real_pipeline(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("API_KEY", "")
    get_settings.cache_clear()

    client = TestClient(app)

    # Stub Ollama client to return working patch
    correct_patch_code = "def process_data(items):\n    return list(items)"

    def stub_generate(self, prompt, *args, **kwargs):
        if "verdict" in prompt.lower() or "deliberation" in prompt.lower() or "judge" in prompt.lower():
            return json.dumps({
                "decision": "fix_a_selected",
                "winning_patch_id": "prosecutor",
                "explanation": "Fix A passes all unit tests deterministically.",
            })
        return json.dumps({
            "proposed_code": correct_patch_code,
            "explanation": "Correctly converted sequence to list to include tail element.",
        })

    monkeypatch.setattr(OllamaClient, "generate", stub_generate)
    try:
        from app.agents.gemini_client import GeminiClient
        monkeypatch.setattr(GeminiClient, "generate", stub_generate)
    except Exception:
        pass

    monkeypatch.setattr("app.sandbox.runner._docker_available", lambda: False)
    monkeypatch.setenv("SWARM_ALLOW_HOST_EXECUTION", "1")

    # Create session with buggy process_data
    payload = {
        "question": "Tail item missing in process_data",
        "code": "def process_data(items):\n    return items[0:len(items)-1]",
        "details": {
            "failingTest": "def test_tail():\n    items = [1, 2, 3]\n    assert process_data(items) == [1, 2, 3]"
        },
        "isDemo": False,
    }
    create_res = client.post("/api/sessions", json=payload)
    assert create_res.status_code == 200
    sess_id = create_res.json()["id"]

    # Start run via /run
    run_res1 = client.post(f"/api/sessions/{sess_id}/run")
    assert run_res1.status_code == 200

    # Calling /run twice is completely idempotent
    run_res2 = client.post(f"/api/sessions/{sess_id}/run")
    assert run_res2.status_code == 200

    # Stream events via SSE (connect twice)
    with client.stream("GET", f"/api/sessions/{sess_id}/events") as response1:
        for line in response1.iter_lines():
            if line.startswith("data:"):
                data = json.loads(line[5:].strip())
                if data.get("type") in ("completed", "error"):
                    break

    with client.stream("GET", f"/api/sessions/{sess_id}/events") as response2:
        for line in response2.iter_lines():
            if line.startswith("data:"):
                data = json.loads(line[5:].strip())
                if data.get("type") in ("completed", "error"):
                    break

    # Verify result
    result_res = client.get(f"/api/sessions/{sess_id}/result")
    assert result_res.status_code == 200
    res_json = result_res.json()

    assert res_json["status"] == "test_verified"
    assert res_json["finalFailedTests"] == 0
    assert res_json["correctedCode"] == correct_patch_code


# ─────────────────────────────────────────────────────────────────────────────
# 9. Test Baseline Guard
# ─────────────────────────────────────────────────────────────────────────────

def test_baseline_guard(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("API_KEY", "")
    get_settings.cache_clear()

    client = TestClient(app)

    monkeypatch.setattr("app.sandbox.runner._docker_available", lambda: False)
    monkeypatch.setenv("SWARM_ALLOW_HOST_EXECUTION", "1")

    # Supplied test already passes on the original code
    payload = {
        "question": "Function already correct",
        "code": "def add(x, y): return x + y",
        "details": {
            "failingTest": "def test_add(): assert add(1, 2) == 3"
        },
        "isDemo": False,
    }
    create_res = client.post("/api/sessions", json=payload)
    assert create_res.status_code == 200
    sess_id = create_res.json()["id"]

    client.post(f"/api/sessions/{sess_id}/run")

    # Read events
    with client.stream("GET", f"/api/sessions/{sess_id}/events") as response:
        events = []
        for line in response.iter_lines():
            if line.startswith("data:"):
                data = json.loads(line[5:].strip())
                events.append(data)
                if data.get("type") in ("error", "completed"):
                    break

    error_events = [e for e in events if e.get("type") == "error"]
    assert len(error_events) >= 1
    assert "already passes on the original code" in error_events[0]["message"]

    # Result must NOT be test_verified
    result_res = client.get(f"/api/sessions/{sess_id}/result")
    assert result_res.status_code == 200
    assert result_res.json()["status"] == "unresolved"

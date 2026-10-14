"""
app/api/pipeline_service.py
===========================
Executes the real multi-agent courtroom LangGraph pipeline for debugging sessions.
Replaces scripted simulations with true LLM reasoning, deterministic test execution,
and constraint ledger updates.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from app.config import get_settings
from app.contracts import (
    DebugSession as ContractDebugSession,
    SessionStatus as ContractSessionStatus,
    CandidatePatch as ContractCandidatePatch,
    ExecutionStatus,
    TestResult as ContractTestResult,
)
from app.agents.prosecutor import ProsecutorAgent
from app.agents.defender import DefenderAgent
from app.agents.judge import JudgeAgent
from app.agents.prompt_utils import extract_python_code
from app.memory.constraint_ledger import ConstraintLedger
from app.memory.repository import Repository
from app.orchestration.graph import build_courtroom_workflow
from app.orchestration.state import create_initial_workflow_state, WorkflowState
from app.schemas.session import DebugSession as SchemaDebugSession
from app.schemas.patch import CandidatePatch as SchemaCandidatePatch, AgentRole
from app.sandbox.runner import run_candidate, prepare_test_source, _allow_host_execution
from app.evaluation.test_evaluator import evaluate_candidate

logger = logging.getLogger(__name__)


def generate_ai_reproduction_test(
    prosecutor_agent: ProsecutorAgent,
    original_code: str,
    bug_description: str,
    error_message: str = "",
    expected_behavior: str = "",
    sandbox_runner: Optional[Callable] = None,
) -> Optional[str]:
    """
    Prompts the Prosecutor model to draft ONE pytest reproduction test.
    Accepts it ONLY if it fails on the original code (retries up to 2 times).
    """
    runner = sandbox_runner or run_candidate
    prompt = (
        f"Generate a single standalone pytest reproduction test function `test_reproduction()` "
        f"that exposes the following bug.\n\n"
        f"BUG DESCRIPTION:\n{bug_description}\n\n"
        f"ERROR MESSAGE:\n{error_message or 'None'}\n\n"
        f"EXPECTED BEHAVIOR:\n{expected_behavior or 'None'}\n\n"
        f"ORIGINAL CODE (saved as solution.py):\n"
        f"```python\n{original_code}\n```\n\n"
        f"INSTRUCTIONS:\n"
        f"1. Import the necessary symbols from `solution` (e.g., `from solution import ...`).\n"
        f"2. Write `def test_reproduction():` asserting the expected correct behavior.\n"
        f"3. Return ONLY valid Python test code with no markdown fences, comments or prose."
    )

    for attempt in range(1, 3):
        try:
            raw = prosecutor_agent.client.generate(
                prompt=prompt,
                system_instruction="You are an expert software test engineer writing reproduction tests using pytest. Return raw Python only.",
                format_json=False,
            )
            test_code = extract_python_code(raw)
            # Verify it fails on original code
            ev = runner(source_code=original_code, trusted_tests=test_code, candidate_id=f"test_gen_attempt_{attempt}")
            if ev.status == ExecutionStatus.FAILED:
                logger.info("Successfully generated AI reproduction test that fails on original code.")
                return test_code
            logger.warning(f"Generated test attempt {attempt} did not fail on original code (status={ev.status.value}).")
        except Exception as exc:
            logger.warning(f"Error generating AI test attempt {attempt}: {exc}")

    return None


def _format_sandbox_run(res: Optional[ContractTestResult], ev: Optional[Any]) -> Dict[str, Any]:
    """Formats a deterministic TestResult into the frontend sandboxRun structure."""
    if res is None:
        return {
            "status": "not_run",
            "passed": 0,
            "failed": 0,
            "total": 0,
            "exitCode": None,
            "logs": "(no test execution)",
        }

    status_str = res.status.value if hasattr(res.status, "value") else str(res.status).lower()
    if status_str == "passed":
        front_status = "passed"
    elif status_str == "timed_out":
        front_status = "timeout"
    elif status_str == "infrastructure_error":
        front_status = "infrastructure_error"
    else:
        front_status = "failed"

    passed_count = sum(1 for pt in res.per_test_results if pt.status == "passed")
    failed_count = sum(1 for pt in res.per_test_results if pt.status in ("failed", "error"))
    total_count = len(res.per_test_results) or (1 if front_status != "not_run" else 0)

    log_lines = []
    for pt in res.per_test_results:
        st_upper = pt.status.upper()
        line = f"{pt.test_name}: {st_upper}"
        if pt.message:
            line += f" -> {pt.message}"
        log_lines.append(line)

    if res.stdout_excerpt:
        log_lines.append(f"\n[stdout]\n{res.stdout_excerpt}")
    if res.stderr_excerpt:
        log_lines.append(f"\n[stderr]\n{res.stderr_excerpt}")

    logs_str = "\n".join(log_lines) if log_lines else (res.stderr_excerpt or res.stdout_excerpt or f"Exit code {res.exit_code}")

    return {
        "status": front_status,
        "passed": passed_count,
        "failed": failed_count,
        "total": total_count,
        "exitCode": res.exit_code,
        "logs": logs_str,
    }


def execute_real_pipeline(
    session_id: str,
    input_data: Dict[str, Any],
    repo: Repository,
    ledger: ConstraintLedger,
    emit_event_fn: Callable[[Dict[str, Any]], None],
    prosecutor_agent: Optional[ProsecutorAgent] = None,
    defender_agent: Optional[DefenderAgent] = None,
    judge_agent: Optional[JudgeAgent] = None,
    sandbox_runner: Optional[Callable] = None,
    test_evaluator: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Synchronous worker executing the real courtroom debate LangGraph workflow.
    Dispatched via asyncio.to_thread in server.py.
    """
    settings = get_settings()
    now_iso = datetime.now(timezone.utc).isoformat()

    source_code = input_data.get("code") or input_data.get("fileContent") or ""
    details = input_data.get("details") or {}
    failing_test = details.get("failingTest") or ""
    error_message = details.get("errorMessage") or ""
    expected_behavior = details.get("expectedBehavior") or ""

    # Build bug description
    desc_parts = [input_data.get("question", "")]
    if error_message:
        desc_parts.append(f"Observed Error:\n{error_message}")
    if expected_behavior:
        desc_parts.append(f"Expected Behavior:\n{expected_behavior}")
    bug_description = "\n\n".join(filter(None, desc_parts))

    runner = sandbox_runner or run_candidate
    evaluator = test_evaluator or evaluate_candidate

    prosecutor = prosecutor_agent or ProsecutorAgent()
    defender = defender_agent or DefenderAgent()
    judge = judge_agent or JudgeAgent()

    limitations: List[str] = [
        "Verified with deterministic pytest execution in isolated sandbox.",
    ]

    # Emit initial analysis event
    emit_event_fn({
        "type": "analysis_started",
        "sessionId": session_id,
        "roundNumber": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "system",
        "message": "Intake verified. Running initial baseline test against original code.",
    })

    # Step 1.3: Check or generate reproduction test
    if not failing_test.strip():
        emit_event_fn({
            "type": "analysis_started",
            "sessionId": session_id,
            "roundNumber": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "prosecutor",
            "message": "No test supplied. AI is drafting a pytest reproduction test...",
        })
        ai_test = generate_ai_reproduction_test(
            prosecutor_agent=prosecutor,
            original_code=source_code,
            bug_description=bug_description,
            error_message=error_message,
            expected_behavior=expected_behavior,
            sandbox_runner=runner,
        )
        if not ai_test:
            err_msg = "Could not generate an AI reproduction test that fails on the original code."
            repo.update_session_status(session_id, ContractSessionStatus.FAILED)
            emit_event_fn({
                "type": "error",
                "sessionId": session_id,
                "roundNumber": 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent": "system",
                "message": err_msg,
                "payload": {"error_code": "TEST_GENERATION_FAILED"},
            })
            result = {
                "sessionId": session_id,
                "status": "unresolved",
                "initialFailedTests": 0,
                "finalFailedTests": 0,
                "errors": [{"explanation": err_msg}],
                "correctedCode": source_code,
                "summary": err_msg,
                "rounds": [],
                "rejectedAttempts": [],
                "limitations": limitations,
            }
            repo.save_session_result(session_id, result)
            return result

        failing_test = ai_test
        limitations.append("Test was AI-generated, not user-supplied.")

    # Step 1.3: Baseline execution check
    # The tests must FAIL on the original code.
    try:
        baseline_ev = runner(
            source_code=source_code,
            trusted_tests=failing_test,
            candidate_id="baseline_run",
        )
        baseline_res = evaluator(evidence=baseline_ev, session_id=session_id)
    except Exception as exc:
        err_msg = f"Baseline execution error: {exc}"
        repo.update_session_status(session_id, ContractSessionStatus.FAILED)
        emit_event_fn({
            "type": "error",
            "sessionId": session_id,
            "roundNumber": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "system",
            "message": err_msg,
            "payload": {"error_code": "BASELINE_EXECUTION_ERROR"},
        })
        result = {
            "sessionId": session_id,
            "status": "unresolved",
            "initialFailedTests": 0,
            "finalFailedTests": 0,
            "errors": [{"explanation": err_msg}],
            "correctedCode": source_code,
            "summary": err_msg,
            "rounds": [],
            "rejectedAttempts": [],
            "limitations": limitations,
        }
        repo.save_session_result(session_id, result)
        return result

    if baseline_res.status == ExecutionStatus.PASSED:
        err_msg = "The supplied test already passes on the original code, so it cannot verify a fix."
        repo.update_session_status(session_id, ContractSessionStatus.FAILED)
        emit_event_fn({
            "type": "error",
            "sessionId": session_id,
            "roundNumber": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "system",
            "message": err_msg,
            "payload": {"error_code": "BASELINE_ALREADY_PASSES"},
        })
        result = {
            "sessionId": session_id,
            "status": "unresolved",
            "initialFailedTests": 0,
            "finalFailedTests": 0,
            "errors": [
                {
                    "id": "err-baseline",
                    "title": "Invalid Test Suite",
                    "file": input_data.get("fileName") or "solution.py",
                    "line": 1,
                    "originalCode": source_code,
                    "correctedCode": source_code,
                    "explanation": err_msg,
                    "verificationStatus": "failed",
                }
            ],
            "correctedCode": source_code,
            "summary": err_msg,
            "rounds": [],
            "rejectedAttempts": [],
            "limitations": limitations,
        }
        repo.save_session_result(session_id, result)
        return result

    if baseline_res.status == ExecutionStatus.INFRASTRUCTURE_ERROR:
        err_msg = f"Sandbox unavailable during baseline check: {baseline_ev.error_detail or baseline_ev.stderr or 'Execution error'}"
        repo.update_session_status(session_id, ContractSessionStatus.FAILED)
        emit_event_fn({
            "type": "error",
            "sessionId": session_id,
            "roundNumber": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "system",
            "message": err_msg,
            "payload": {"error_code": "INFRASTRUCTURE_ERROR"},
        })
        result = {
            "sessionId": session_id,
            "status": "unresolved",
            "initialFailedTests": 0,
            "finalFailedTests": 0,
            "errors": [{"explanation": err_msg}],
            "correctedCode": source_code,
            "summary": err_msg,
            "rounds": [],
            "rejectedAttempts": [],
            "limitations": limitations,
        }
        repo.save_session_result(session_id, result)
        return result

    initial_failed_tests = sum(
        1 for pt in baseline_res.per_test_results if pt.status in ("failed", "error")
    ) or 1

    # Update session in SQLite with verified tests
    repo.update_session_tests(session_id, failing_test)
    repo.update_session_status(session_id, ContractSessionStatus.RUNNING)

    # Initialize workflow graph
    workflow_graph = build_courtroom_workflow(
        prosecutor_agent=prosecutor,
        defender_agent=defender,
        judge_agent=judge,
        constraint_ledger=ledger,
        sandbox_runner=runner,
        test_evaluator=evaluator,
        full_pipeline=True,
    )

    schema_session = SchemaDebugSession(
        session_id=session_id,
        original_code=source_code,
        bug_description=bug_description,
        test_suite=failing_test,
        current_round=1,
    )
    workflow_state = create_initial_workflow_state(schema_session)
    workflow_state["max_rounds"] = settings.workflow.max_rounds

    collected_rounds: List[Dict[str, Any]] = []
    rejected_attempts: List[Dict[str, Any]] = []
    final_winner_code = source_code
    final_winner_explanation = "No patch passed tests."
    final_status = "unresolved"
    final_failed_tests = initial_failed_tests

    current_round_data: Dict[str, Any] = {
        "roundNumber": 1,
        "prosecutorClaim": "",
        "candidateA": None,
        "defenderChallenge": "",
        "candidateB": None,
        "decision": None,
    }

    try:
        # Stream updates from the LangGraph workflow
        for update in workflow_graph.stream(workflow_state, stream_mode="updates"):
            for node_name, state_update in update.items():
                round_no = state_update.get("current_round", 1)
                current_round_data["roundNumber"] = round_no

                if node_name == "prosecutor":
                    fix_a = state_update.get("fix_a")
                    if fix_a:
                        cid = fix_a.get("patch_id", f"candidate_a_r{round_no}")
                        code = fix_a.get("proposed_code", "")
                        expl = fix_a.get("explanation", "")
                        current_round_data["prosecutorClaim"] = expl
                        current_round_data["candidateA"] = {
                            "id": cid,
                            "author": "prosecutor",
                            "title": "Fix A: Root Cause Remedy",
                            "code": code,
                            "explanation": expl,
                        }
                        emit_event_fn({
                            "type": "root_cause_located",
                            "sessionId": session_id,
                            "roundNumber": round_no,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "agent": "prosecutor",
                            "message": f"Prosecutor located root cause and proposed Fix A ({cid}).",
                            "payload": {
                                "candidateA": current_round_data["candidateA"],
                            },
                        })

                elif node_name == "defender":
                    fix_b = state_update.get("fix_b")
                    if fix_b:
                        cid = fix_b.get("patch_id", f"candidate_b_r{round_no}")
                        code = fix_b.get("proposed_code", "")
                        expl = fix_b.get("explanation", "")
                        current_round_data["defenderChallenge"] = expl
                        current_round_data["candidateB"] = {
                            "id": cid,
                            "author": "defender",
                            "title": "Fix B: Defensive Counter-Proposal",
                            "code": code,
                            "explanation": expl,
                        }
                        emit_event_fn({
                            "type": "fixes_compared",
                            "sessionId": session_id,
                            "roundNumber": round_no,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "agent": "defender",
                            "message": f"Defender critiqued Fix A and proposed Fix B ({cid}).",
                            "payload": {
                                "candidateB": current_round_data["candidateB"],
                            },
                        })

                elif node_name == "execute_candidates":
                    emit_event_fn({
                        "type": "sandbox_started",
                        "sessionId": session_id,
                        "roundNumber": round_no,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "agent": "system",
                        "message": f"Executing Candidate Fixes in isolated sandboxes (Round {round_no}).",
                    })

                elif node_name == "evaluate_tests":
                    ev_dict = state_update.get("execution_evidence", {})
                    test_results = state_update.get("test_results", {})

                    res_a = test_results.get("prosecutor")
                    res_b = test_results.get("defender")
                    ev_a = ev_dict.get("prosecutor")
                    ev_b = ev_dict.get("defender")

                    run_a_payload = _format_sandbox_run(res_a, ev_a)
                    run_b_payload = _format_sandbox_run(res_b, ev_b)

                    if current_round_data.get("candidateA"):
                        current_round_data["candidateA"]["sandboxRun"] = run_a_payload
                    if current_round_data.get("candidateB"):
                        current_round_data["candidateB"]["sandboxRun"] = run_b_payload

                    emit_event_fn({
                        "type": "sandbox_finished",
                        "sessionId": session_id,
                        "roundNumber": round_no,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "agent": "system",
                        "message": f"Sandbox execution completed for Round {round_no}.",
                        "payload": {
                            "sandboxRunA": run_a_payload,
                            "sandboxRunB": run_b_payload,
                        },
                    })

                elif node_name == "judge":
                    verdict = state_update.get("verdict", {})
                    decision_str = (
                        verdict.get("decision", "both_failed")
                        if isinstance(verdict, dict)
                        else getattr(verdict, "decision", "both_failed")
                    )
                    raw_val = decision_str.value if hasattr(decision_str, "value") else str(decision_str)
                    if raw_val in ("accept_prosecutor", "fix_a_selected"):
                        decision_val = "fix_a_selected"
                    elif raw_val in ("accept_defender", "fix_b_selected"):
                        decision_val = "fix_b_selected"
                    else:
                        decision_val = "both_failed"
                    rationale = (
                        verdict.get("explanation", "")
                        if isinstance(verdict, dict)
                        else getattr(verdict, "explanation", "")
                    )
                    evidence_list = [
                        f"Round {round_no} empirical test verification: {decision_val}"
                    ]

                    decision_obj = {
                        "roundNumber": round_no,
                        "verdict": decision_val,
                        "rationale": rationale,
                        "evidence": evidence_list,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    current_round_data["decision"] = decision_obj

                    emit_event_fn({
                        "type": "judge_decision",
                        "sessionId": session_id,
                        "roundNumber": round_no,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "agent": "judge",
                        "message": f"Judge delivered verdict: {decision_val.replace('_', ' ').upper()}.",
                        "payload": decision_obj,
                    })

                    collected_rounds.append(dict(current_round_data))

                    # Track rejected attempts
                    if decision_val in ("fix_b_selected", "both_failed") and current_round_data.get("candidateA"):
                        rejected_attempts.append({
                            "attemptId": current_round_data["candidateA"]["id"],
                            "author": "prosecutor",
                            "code": current_round_data["candidateA"]["code"],
                            "failureReason": "Rejected by Judge based on test evidence.",
                        })
                    if decision_val in ("fix_a_selected", "both_failed") and current_round_data.get("candidateB"):
                        rejected_attempts.append({
                            "attemptId": current_round_data["candidateB"]["id"],
                            "author": "defender",
                            "code": current_round_data["candidateB"]["code"],
                            "failureReason": "Rejected by Judge based on test evidence.",
                        })

                    # If a fix passed
                    winning_patch_id = verdict.get("winning_patch_id") if isinstance(verdict, dict) else getattr(verdict, "winning_patch_id", None)
                    if decision_val == "fix_a_selected" and current_round_data.get("candidateA"):
                        final_winner_code = current_round_data["candidateA"]["code"]
                        final_winner_explanation = current_round_data["candidateA"]["explanation"]
                        final_status = "test_verified"
                        final_failed_tests = 0
                    elif decision_val == "fix_b_selected" and current_round_data.get("candidateB"):
                        final_winner_code = current_round_data["candidateB"]["code"]
                        final_winner_explanation = current_round_data["candidateB"]["explanation"]
                        final_status = "test_verified"
                        final_failed_tests = 0

                elif node_name == "record_constraints_and_retry":
                    new_round_no = state_update.get("current_round", round_no + 1)
                    current_round_data = {
                        "roundNumber": new_round_no,
                        "prosecutorClaim": "",
                        "candidateA": None,
                        "defenderChallenge": "",
                        "candidateB": None,
                        "decision": None,
                    }
                    emit_event_fn({
                        "type": "analysis_started",
                        "sessionId": session_id,
                        "roundNumber": new_round_no,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "agent": "system",
                        "message": f"Entering Retry Round {new_round_no} with constraints ledger updated.",
                    })

                elif node_name == "finalize_failure":
                    errs = state_update.get("errors", [])
                    err_text = "; ".join(errs) if errs else "Max repair rounds reached without clean pass."
                    if any("infrastructure" in e.lower() for e in errs):
                        emit_event_fn({
                            "type": "error",
                            "sessionId": session_id,
                            "roundNumber": round_no,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "agent": "system",
                            "message": err_text,
                            "payload": {"error_code": "INFRASTRUCTURE_ERROR"},
                        })
                    limitations.append(f"Session failed: {err_text}")

    except Exception as exc:
        logger.error(f"Courtroom execution encountered uncaught error: {exc}", exc_info=True)
        err_msg = f"Courtroom workflow error: {exc}"
        repo.update_session_status(session_id, ContractSessionStatus.FAILED)
        emit_event_fn({
            "type": "error",
            "sessionId": session_id,
            "roundNumber": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "system",
            "message": err_msg,
            "payload": {"error_code": "WORKFLOW_EXECUTION_ERROR"},
        })
        result = {
            "sessionId": session_id,
            "status": "unresolved",
            "initialFailedTests": initial_failed_tests,
            "finalFailedTests": initial_failed_tests,
            "errors": [{"explanation": err_msg}],
            "correctedCode": source_code,
            "summary": err_msg,
            "rounds": collected_rounds,
            "rejectedAttempts": rejected_attempts,
            "limitations": limitations,
        }
        repo.save_session_result(session_id, result)
        return result

    # Assemble and persist final result report
    if final_status == "test_verified":
        repo.update_session_status(session_id, ContractSessionStatus.COMPLETED)
        summary = f"The Courtroom verified a working fix. All {initial_failed_tests} failing tests resolved cleanly."
    else:
        repo.update_session_status(session_id, ContractSessionStatus.FAILED)
        summary = "Courtroom debate concluded without finding a fix that cleanly passes all tests."

    result_report = {
        "sessionId": session_id,
        "status": final_status,
        "initialFailedTests": initial_failed_tests,
        "finalFailedTests": final_failed_tests,
        "errors": [
            {
                "id": "err-1",
                "title": input_data.get("question", "Bug Diagnosis")[:60],
                "file": input_data.get("fileName") or "solution.py",
                "line": 1,
                "originalCode": source_code,
                "correctedCode": final_winner_code,
                "explanation": final_winner_explanation,
                "verificationStatus": "verified" if final_status == "test_verified" else "failed",
            }
        ],
        "correctedCode": final_winner_code,
        "summary": summary,
        "rounds": collected_rounds,
        "rejectedAttempts": rejected_attempts,
        "limitations": limitations,
    }

    repo.save_session_result(session_id, result_report)

    # Terminal event
    emit_event_fn({
        "type": "completed",
        "sessionId": session_id,
        "roundNumber": current_round_data.get("roundNumber", 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": "judge",
        "message": "Adjudication complete. Final verdict recorded.",
        "payload": {"result": result_report},
    })

    return result_report

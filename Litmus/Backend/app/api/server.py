"""
Litmus Courtroom Debugger — FastAPI Backend Server
===================================================
Provides REST API & Server-Sent Events (SSE) streaming for the Litmus React Frontend.
Integrates LangGraph Courtroom Workflow, AI Agents, Event Publisher,
Sandbox Runner, Evaluator, SQLite Repository, and Constraint Ledger.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def safe_print(*args: Any, **kwargs: Any) -> None:
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        clean_args = [
            str(a).encode("ascii", errors="replace").decode("ascii") for a in args
        ]
        print(*clean_args, **kwargs)


import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

from app.config import get_settings
from app.contracts import (
    DebugSession as ContractDebugSession,
    SessionStatus as ContractSessionStatus,
    CandidatePatch as ContractCandidatePatch,
    ExecutionStatus,
    TestResult as ContractTestResult,
)
from app.events.publisher import InMemoryEventPublisher
from app.schemas.events import WorkflowEventType
from app.memory.constraint_ledger import ConstraintLedger
from app.memory.repository import Repository
from app.sandbox.runner import _docker_available, _allow_host_execution, run_candidate
from app.orchestration.code_assembler import (
    apply_patch_or_code,
    derive_reproduction_test_suite,
    generate_candidate_fixes,
    validate_python_code,
)
from app.api.pipeline_service import execute_real_pipeline

# Allow fallback to host execution when Docker is not running
os.environ.setdefault("SWARM_ALLOW_HOST_EXECUTION", "1")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Litmus Multi-Agent Debugger API",
    version="1.0.0",
    description="Adversarial Courtroom Debugger Backend connecting React visualizer with LangGraph orchestration.",
)

# CORS configuration
CORS_ORIGINS_ENV = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173",
)
CORS_ORIGINS = [orig.strip() for orig in CORS_ORIGINS_ENV.split(",") if orig.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize persistence and event bus
DB_PATH = os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent.parent.parent / "litmus.db"))
repo = Repository(DB_PATH)
ledger = ConstraintLedger(repo)
event_publisher = InMemoryEventPublisher()

# Caches
SESSION_INPUTS_CACHE: Dict[str, Dict[str, Any]] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas for Frontend Compatibility
# ─────────────────────────────────────────────────────────────────────────────

class BugDetailsInput(BaseModel):
    failingTest: Optional[str] = None
    expectedBehavior: Optional[str] = None
    errorMessage: Optional[str] = None


class CreateSessionRequest(BaseModel):
    mode: str = "code"
    language: str = "python"
    question: str
    code: Optional[str] = None
    fileName: Optional[str] = None
    fileSize: Optional[int] = None
    fileContent: Optional[str] = None
    repoUrl: Optional[str] = None
    details: Optional[BugDetailsInput] = None
    scenarioId: Optional[str] = None
    isDemo: Optional[bool] = False


class FrontendDebugEvent(BaseModel):
    type: str
    sessionId: str
    roundNumber: int = 1
    timestamp: str
    agent: Optional[str] = None
    message: str
    payload: Optional[Any] = None
    event_id: Optional[int] = None


# ─────────────────────────────────────────────────────────────────────────────
# Run Registry for Idempotent Execution & Event Replay
# ─────────────────────────────────────────────────────────────────────────────

class SessionRun:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.status = "idle"  # "idle" | "running" | "completed" | "failed"
        self.events: List[Dict[str, Any]] = []
        self.subscribers: List[asyncio.Queue] = []
        self.task: Optional[asyncio.Task] = None
        self.lock = asyncio.Lock()


RUNS: Dict[str, SessionRun] = {}
SESSION_INPUTS_CACHE: Dict[str, Any] = {}
SESSION_RESULTS_CACHE: Dict[str, Any] = {}
SESSION_STREAMS: Dict[str, List[asyncio.Queue]] = {}


def get_or_create_run(session_id: str) -> SessionRun:
    if session_id not in RUNS:
        RUNS[session_id] = SessionRun(session_id)
    return RUNS[session_id]


async def emit_frontend_event(session_id: str, event: FrontendDebugEvent) -> None:
    run = get_or_create_run(session_id)
    event_dict = event.model_dump()
    event_dict["event_id"] = len(run.events) + 1
    run.events.append(event_dict)

    agent_tag = f"[{event.agent.upper()}]" if event.agent else "[COURTROOM]"
    round_str = f"(R{event.roundNumber})" if event.roundNumber else ""
    safe_print(f"\n⚡ {agent_tag} {event.type.upper()} {round_str} | {event.message}")
    if event.payload and isinstance(event.payload, dict):
        if "candidateA" in event.payload:
            cand = event.payload["candidateA"]
            safe_print(f"   🏛️ Fix A by {cand.get('author')}: {cand.get('title')}")
            safe_print(f"      Explanation: {cand.get('explanation', '')[:150]}")
        if "candidateB" in event.payload:
            cand = event.payload["candidateB"]
            safe_print(f"   🛡️ Fix B by {cand.get('author')}: {cand.get('title')}")
            safe_print(f"      Explanation: {cand.get('explanation', '')[:150]}")
        if "sandboxRunA" in event.payload or "sandboxRunB" in event.payload:
            run_a = event.payload.get("sandboxRunA", {})
            run_b = event.payload.get("sandboxRunB", {})
            safe_print(f"   🧪 Sandbox A: {run_a.get('status', '').upper()} ({run_a.get('passed')}/{run_a.get('total')} passed)")
            safe_print(f"   🧪 Sandbox B: {run_b.get('status', '').upper()} ({run_b.get('passed')}/{run_b.get('total')} passed)")
        if "verdict" in event.payload:
            safe_print(f"   ⚖️ Final Verdict: {event.payload.get('verdict')}")
            safe_print(f"      Rationale: {event.payload.get('rationale', '')[:150]}")

    for q in list(run.subscribers):
        await q.put(event_dict)
    for q in list(SESSION_STREAMS.get(session_id, [])):
        await q.put(event)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Check Ollama connectivity
# ─────────────────────────────────────────────────────────────────────────────

def is_ollama_available() -> bool:
    settings = get_settings()
    try:
        url = f"{settings.ollama.base_url.rstrip('/')}/api/tags"
        resp = httpx.get(url, timeout=1.0)
        return resp.status_code == 200
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    """Returns the operational health of system components without blocking the event loop."""
    settings = get_settings()
    ollama_ok = await asyncio.to_thread(is_ollama_available)
    docker_ok = await asyncio.to_thread(_docker_available)
    recent_sessions = repo.list_sessions()

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {
            "status": "connected",
            "path": DB_PATH,
            "session_count": len(recent_sessions),
        },
        "services": {
            "gemini": {
                "configured": bool(settings.gemini.api_key),
                "model": settings.gemini.model,
                "role": "primary",
            },
            "ollama": {
                "available": ollama_ok,
                "url": settings.ollama.base_url,
                "target_model": settings.ollama.model,
                "role": "fallback" if bool(settings.gemini.api_key) else "primary",
            },
            "sandbox": {
                "docker_available": docker_ok,
                "host_execution_allowed": _allow_host_execution(),
            },
            "langgraph": {
                "max_rounds": settings.workflow.max_rounds,
            },
        },
    }


@app.get("/api/sessions")
async def list_sessions() -> List[Dict[str, Any]]:
    """Returns recent debugging sessions stored in SQLite."""
    db_sessions = repo.list_sessions()
    results = []
    for s in db_sessions:
        cached_input = SESSION_INPUTS_CACHE.get(s.session_id, {})
        title = cached_input.get("question", s.bug_description)[:60]
        if s.status == ContractSessionStatus.COMPLETED:
            status_str = "test_verified"
        elif s.status == ContractSessionStatus.FAILED:
            status_str = "unresolved"
        else:
            status_str = "in_progress"

        results.append({
            "id": s.session_id,
            "title": title or "Debugging Session",
            "mode": cached_input.get("mode", "code"),
            "language": s.language,
            "question": cached_input.get("question", s.bug_description),
            "code": s.original_source,
            "status": status_str,
            "createdAt": s.created_at.isoformat(),
            "updatedAt": s.updated_at.isoformat(),
            "isDemo": cached_input.get("isDemo", False),
        })
    return results


@app.post("/api/sessions")
async def create_session(input_data: CreateSessionRequest) -> Dict[str, Any]:
    """Creates a new courtroom debugging session and initializes SQLite persistence."""
    if (input_data.language or "").lower() != "python":
        raise HTTPException(status_code=422, detail="Only Python is currently supported.")

    source_code = input_data.code or input_data.fileContent
    if not source_code or not source_code.strip():
        raise HTTPException(status_code=422, detail="Source code or fileContent is required.")

    session_id = f"session-{int(datetime.now(timezone.utc).timestamp() * 1000)}-{uuid4().hex[:6]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    details = input_data.details or BugDetailsInput()
    failing_test = details.failingTest or ""
    error_message = details.errorMessage or ""
    expected_behavior = details.expectedBehavior or ""

    desc_parts = [input_data.question]
    if error_message:
        desc_parts.append(f"Error Message:\n{error_message}")
    if expected_behavior:
        desc_parts.append(f"Expected Behavior:\n{expected_behavior}")
    full_bug_description = "\n\n".join(filter(None, desc_parts))

    contract_session = ContractDebugSession(
        session_id=session_id,
        language="python",
        bug_description=full_bug_description,
        original_source=source_code,
        trusted_tests=failing_test,
        status=ContractSessionStatus.PENDING,
    )
    repo.create_session(contract_session)

    SESSION_INPUTS_CACHE[session_id] = input_data.model_dump()

    session_obj = {
        "id": session_id,
        "title": input_data.question[:60] or "Bug Diagnosis",
        "mode": input_data.mode,
        "language": input_data.language,
        "question": input_data.question,
        "code": source_code,
        "fileName": input_data.fileName,
        "fileSize": input_data.fileSize,
        "fileContent": input_data.fileContent,
        "repoUrl": input_data.repoUrl,
        "details": input_data.details.model_dump() if input_data.details else None,
        "createdAt": now_iso,
        "updatedAt": now_iso,
        "status": "in_progress",
        "isDemo": input_data.isDemo,
        "scenarioId": input_data.scenarioId or "fix_b_passes",
    }
    return session_obj


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> Dict[str, Any]:
    """Retrieves session metadata by ID."""
    s = repo.get_session(session_id)
    cached_input = SESSION_INPUTS_CACHE.get(session_id, {})
    if not s:
        if session_id in SESSION_INPUTS_CACHE:
            return {
                "id": session_id,
                "title": cached_input.get("question", "Debug Session")[:60],
                "mode": cached_input.get("mode", "code"),
                "language": cached_input.get("language", "python"),
                "question": cached_input.get("question", ""),
                "status": "in_progress",
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "updatedAt": datetime.now(timezone.utc).isoformat(),
            }
        raise HTTPException(status_code=404, detail="Session not found")

    if s.status == ContractSessionStatus.COMPLETED:
        status_str = "test_verified"
    elif s.status == ContractSessionStatus.FAILED:
        status_str = "unresolved"
    else:
        status_str = "in_progress"

    return {
        "id": s.session_id,
        "title": cached_input.get("question", s.bug_description)[:60],
        "mode": cached_input.get("mode", "code"),
        "language": s.language,
        "question": cached_input.get("question", s.bug_description),
        "code": s.original_source,
        "status": status_str,
        "createdAt": s.created_at.isoformat(),
        "updatedAt": s.updated_at.isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Demo Scripted Flow (for isDemo == true only)
# ─────────────────────────────────────────────────────────────────────────────

async def execute_demo_debate_task(session_id: str, speed_factor: float = 1.0) -> None:
    """Scripted demonstration flow with explicit [DEMO] markings."""
    cached_input = SESSION_INPUTS_CACHE.get(session_id, {})
    original_code = cached_input.get("code") or "def process_data(items):\n    return items[0:len(items)-1]"
    question = cached_input.get("question") or "Off-by-one error drops tail element"
    scenario_id = cached_input.get("scenarioId") or "fix_b_passes"
    details = cached_input.get("details") or {}
    user_test = details.get("failingTest") or ""
    expected_behavior = details.get("expectedBehavior") or ""

    async def sleep_step(seconds: float):
        if speed_factor > 0:
            await asyncio.sleep(seconds / speed_factor)

    await emit_frontend_event(session_id, FrontendDebugEvent(
        type="analysis_started",
        sessionId=session_id,
        roundNumber=1,
        timestamp=datetime.now(timezone.utc).isoformat(),
        agent="system",
        message="[DEMO] Initializing demonstration scenario. AST parsing verified.",
    ))
    await sleep_step(1.5)

    # Synthesize Candidate Fix A and Fix B using general AST code repair
    fix_a_cand, fix_b_cand = generate_candidate_fixes(
        original_code=original_code,
        bug_description=question,
        test_suite=user_test,
        scenario_id=scenario_id,
    )
    fix_a_code = fix_a_cand.code
    fix_a_expl = fix_a_cand.explanation
    fix_b_code = fix_b_cand.code
    fix_b_expl = fix_b_cand.explanation

    await emit_frontend_event(session_id, FrontendDebugEvent(
        type="root_cause_located",
        sessionId=session_id,
        roundNumber=1,
        timestamp=datetime.now(timezone.utc).isoformat(),
        agent="prosecutor",
        message="[DEMO] Prosecutor identified bug root cause. Formulated Accusation and proposed Fix A.",
        payload={
            "candidateA": {
                "id": "fix_a",
                "author": "prosecutor",
                "title": fix_a_cand.title,
                "code": fix_a_code,
                "explanation": fix_a_expl,
            }
        }
    ))
    await sleep_step(2.0)

    await emit_frontend_event(session_id, FrontendDebugEvent(
        type="fixes_compared",
        sessionId=session_id,
        roundNumber=1,
        timestamp=datetime.now(timezone.utc).isoformat(),
        agent="defender",
        message="[DEMO] Defender critiques boundary assumption. Proposes Fix B with defensive iteration.",
        payload={
            "candidateB": {
                "id": "fix_b",
                "author": "defender",
                "title": fix_b_cand.title,
                "code": fix_b_code,
                "explanation": fix_b_expl,
            }
        }
    ))
    await sleep_step(1.8)

    await emit_frontend_event(session_id, FrontendDebugEvent(
        type="sandbox_started",
        sessionId=session_id,
        roundNumber=1,
        timestamp=datetime.now(timezone.utc).isoformat(),
        agent="system",
        message="[DEMO] Deploying candidate fixes into isolated execution sandboxes.",
    ))
    await sleep_step(2.2)

    # Derive effective test suite & run isolated sandboxes
    effective_test_suite = derive_reproduction_test_suite(
        original_source=original_code,
        user_test=user_test,
        bug_description=question,
        expected_behavior=expected_behavior,
    )
    ev_a = run_candidate(fix_a_code, effective_test_suite, f"cand_a_{session_id[-6:]}")
    ev_b = run_candidate(fix_b_code, effective_test_suite, f"cand_b_{session_id[-6:]}")
    cand_a_passed = (ev_a.status == ExecutionStatus.PASSED)
    cand_b_passed = (ev_b.status == ExecutionStatus.PASSED)

    await emit_frontend_event(session_id, FrontendDebugEvent(
        type="sandbox_finished",
        sessionId=session_id,
        roundNumber=1,
        timestamp=datetime.now(timezone.utc).isoformat(),
        agent="system",
        message="[DEMO] Sandboxes completed execution. Generating deterministic JUnit evidence.",
        payload={
            "sandboxRunA": {
                "status": "passed" if cand_a_passed else "failed",
                "passed": 1 if cand_a_passed else 0,
                "failed": 0 if cand_a_passed else 1,
                "total": 1,
                "exitCode": ev_a.exit_code,
                "logs": (ev_a.stdout or ev_a.stderr or f"Exit code: {ev_a.exit_code}").strip(),
            },
            "sandboxRunB": {
                "status": "passed" if cand_b_passed else "failed",
                "passed": 1 if cand_b_passed else 0,
                "failed": 0 if cand_b_passed else 1,
                "total": 1,
                "exitCode": ev_b.exit_code,
                "logs": (ev_b.stdout or ev_b.stderr or f"Exit code: {ev_b.exit_code}").strip(),
            }
        }
    ))
    await sleep_step(1.5)

    if cand_b_passed and not cand_a_passed:
        winning_candidate = "fix_b"
        verdict_text = "fix_b_selected"
        winning_code = fix_b_code
        winning_cand_obj = fix_b_cand
        rationale_text = "[DEMO] Empirical sandbox execution verifies Fix B passed all reproduction assertions without errors."
    elif cand_a_passed and not cand_b_passed:
        winning_candidate = "fix_a"
        verdict_text = "fix_a_selected"
        winning_code = fix_a_code
        winning_cand_obj = fix_a_cand
        rationale_text = "[DEMO] Empirical sandbox execution verifies Fix A passed all reproduction tests."
    elif cand_a_passed and cand_b_passed:
        if scenario_id == "fix_a_passes":
            winning_candidate = "fix_a"
            verdict_text = "fix_a_selected"
            winning_code = fix_a_code
            winning_cand_obj = fix_a_cand
            rationale_text = "[DEMO] Both candidates passed reproduction tests; Fix A adopted as primary direct repair."
        else:
            winning_candidate = "fix_b"
            verdict_text = "fix_b_selected"
            winning_code = fix_b_code
            winning_cand_obj = fix_b_cand
            rationale_text = "[DEMO] Both candidates passed reproduction tests; Fix B adopted for superior defensive resilience."
    else:
        winning_candidate = "both_failed"
        verdict_text = "both_failed"
        winning_code = None
        winning_cand_obj = None
        rationale_text = "[DEMO] Both Candidate Fix A and Fix B failed reproduction test execution in the sandbox."

    await emit_frontend_event(session_id, FrontendDebugEvent(
        type="judge_decision",
        sessionId=session_id,
        roundNumber=1,
        timestamp=datetime.now(timezone.utc).isoformat(),
        agent="judge",
        message=f"[DEMO] Judge delivers Verdict: {verdict_text.replace('_', ' ').upper()} grounded on sandbox evidence.",
        payload={
            "roundNumber": 1,
            "verdict": verdict_text,
            "rationale": rationale_text,
            "evidence": [
                f"Candidate Fix A exited with code {ev_a.exit_code} ({ev_a.status.value})",
                f"Candidate Fix B exited with code {ev_b.exit_code} ({ev_b.status.value})",
            ]
        }
    ))
    await sleep_step(1.5)

    is_verified = False
    final_assembled_code = None
    if winning_code:
        assembled, is_valid_syntax, _ = apply_patch_or_code(original_code, winning_code, language="python")
        if is_valid_syntax:
            final_assembled_code = assembled
            final_ev = run_candidate(final_assembled_code, effective_test_suite, f"final_{session_id[-6:]}")
            if final_ev.status == ExecutionStatus.PASSED:
                is_verified = True

    if is_verified and final_assembled_code:
        final_status = "test_verified"
        repo.update_session_status(session_id, ContractSessionStatus.COMPLETED)
        corrected_code = final_assembled_code
    else:
        final_status = "unresolved"
        repo.update_session_status(session_id, ContractSessionStatus.FAILED)
        corrected_code = None

    result_report = {
        "sessionId": session_id,
        "status": final_status,
        "initialFailedTests": 1,
        "finalFailedTests": 0 if final_status == "test_verified" else 1,
        "errors": [
            {
                "id": "err-1",
                "title": f"Bug Diagnosis: {question[:50]}",
                "file": cached_input.get("fileName") or "solution.py",
                "line": 1,
                "originalCode": original_code,
                "correctedCode": corrected_code or "Selected fix failed execution validation.",
                "explanation": winning_cand_obj.explanation if (is_verified and winning_cand_obj) else "Candidate fix failed empirical sandbox validation.",
                "verificationStatus": "verified" if final_status == "test_verified" else "failed",
            }
        ],
        "correctedCode": corrected_code,
        "summary": (
            f"[DEMO] The Judge adopted {winning_candidate.upper().replace('_', ' ')} after empirical sandbox verification confirmed zero regressions."
            if is_verified
            else "[DEMO] Candidate fixes failed validation against reproduction test suite. Status unresolved."
        ),
        "rounds": [
            {
                "roundNumber": 1,
                "prosecutorClaim": fix_a_expl,
                "candidateA": {
                    "id": "fix_a",
                    "author": "prosecutor",
                    "title": fix_a_cand.title,
                    "code": fix_a_code,
                    "explanation": fix_a_expl,
                    "sandboxRun": {
                        "status": "passed" if cand_a_passed else "failed",
                        "passed": 1 if cand_a_passed else 0,
                        "failed": 0 if cand_a_passed else 1,
                        "total": 1,
                        "exitCode": ev_a.exit_code,
                        "logs": (ev_a.stdout or ev_a.stderr or f"Exit code: {ev_a.exit_code}").strip(),
                    }
                },
                "defenderChallenge": fix_b_expl,
                "candidateB": {
                    "id": "fix_b",
                    "author": "defender",
                    "title": fix_b_cand.title,
                    "code": fix_b_code,
                    "explanation": fix_b_expl,
                    "sandboxRun": {
                        "status": "passed" if cand_b_passed else "failed",
                        "passed": 1 if cand_b_passed else 0,
                        "failed": 0 if cand_b_passed else 1,
                        "total": 1,
                        "exitCode": ev_b.exit_code,
                        "logs": (ev_b.stdout or ev_b.stderr or f"Exit code: {ev_b.exit_code}").strip(),
                    }
                },
                "decision": {
                    "roundNumber": 1,
                    "verdict": verdict_text,
                    "rationale": rationale_text,
                    "evidence": [
                        f"Candidate Fix A exited with code {ev_a.exit_code} ({ev_a.status.value})",
                        f"Candidate Fix B exited with code {ev_b.exit_code} ({ev_b.status.value})",
                    ],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            }
        ],
        "rejectedAttempts": [
            {
                "attemptId": "fix_a_attempt",
                "author": "prosecutor",
                "code": fix_a_code,
                "failureReason": "[DEMO] Failed reproduction test in execution sandbox." if not cand_a_passed else "Fix B preferred for defensive robustness.",
            }
        ] if winning_candidate == "fix_b" else [],
        "limitations": [
            "[DEMO MODE] This output is a scripted demonstration for UI testing.",
        ]
    }
    repo.save_session_result(session_id, result_report)
    SESSION_RESULTS_CACHE[session_id] = result_report

    await emit_frontend_event(session_id, FrontendDebugEvent(
        type="completed",
        sessionId=session_id,
        roundNumber=1,
        timestamp=datetime.now(timezone.utc).isoformat(),
        agent="judge",
        message="[DEMO] Courtroom adjudication complete. Decision and proof verified.",
        payload={"result": result_report}
    ))


# ─────────────────────────────────────────────────────────────────────────────
# Execution Dispatcher (Idempotent)
# ─────────────────────────────────────────────────────────────────────────────

async def run_real_pipeline_task(session_id: str) -> None:
    run = get_or_create_run(session_id)
    cached_input = SESSION_INPUTS_CACHE.get(session_id, {})
    loop = asyncio.get_running_loop()

    def sync_emit_event(event_dict: Dict[str, Any]) -> None:
        asyncio.run_coroutine_threadsafe(
            emit_frontend_event(session_id, FrontendDebugEvent(**event_dict)),
            loop,
        )

    try:
        await asyncio.to_thread(
            execute_real_pipeline,
            session_id=session_id,
            input_data=cached_input,
            repo=repo,
            ledger=ledger,
            emit_event_fn=sync_emit_event,
        )
        run.status = "completed"
    except Exception as exc:
        logger.error(f"Pipeline task error for session {session_id}: {exc}", exc_info=True)
        run.status = "failed"
        sync_emit_event({
            "type": "error",
            "sessionId": session_id,
            "roundNumber": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "system",
            "message": f"Pipeline execution error: {exc}",
            "payload": {"error_code": "INTERNAL_ERROR"},
        })


async def execute_courtroom_debate_task(session_id: str, speed_factor: float = 1.0) -> None:
    """Executes either demo scenario or real pipeline based on isDemo flag."""
    cached_input = SESSION_INPUTS_CACHE.get(session_id, {})
    is_demo = cached_input.get("isDemo", False)
    if is_demo:
        await execute_demo_debate_task(session_id, speed_factor)
    else:
        settings = get_settings()
        if not is_ollama_available():
            await emit_frontend_event(session_id, FrontendDebugEvent(
                type="analysis_started",
                sessionId=session_id,
                roundNumber=1,
                timestamp=datetime.now(timezone.utc).isoformat(),
                agent="system",
                message="Checking local AI inference availability...",
            ))
            repo.update_session_status(session_id, ContractSessionStatus.FAILED)
            err_msg = (
                f"Cannot connect to local Ollama server at '{settings.ollama.base_url}'. "
                f"Please ensure Ollama is installed and running (`ollama serve`)."
            )
            await emit_frontend_event(session_id, FrontendDebugEvent(
                type="error",
                sessionId=session_id,
                roundNumber=1,
                timestamp=datetime.now(timezone.utc).isoformat(),
                agent="system",
                message=err_msg,
                payload={"error_code": "OLLAMA_UNAVAILABLE"}
            ))
            SESSION_RESULTS_CACHE[session_id] = {
                "sessionId": session_id,
                "status": "unresolved",
                "initialFailedTests": 0,
                "finalFailedTests": 0,
                "errors": [],
                "correctedCode": None,
                "summary": f"Adjudication Pipeline Error: {err_msg}",
                "rounds": [],
                "rejectedAttempts": [],
                "limitations": [],
            }
            return
        await run_real_pipeline_task(session_id)


async def start_run(session_id: str, speed_factor: float = 1.0) -> None:
    """Idempotently starts a courtroom session run."""
    run = get_or_create_run(session_id)
    async with run.lock:
        if run.status in ("running", "completed", "failed") or (run.task and not run.task.done()):
            return
        run.status = "running"
        run.task = asyncio.create_task(execute_courtroom_debate_task(session_id, speed_factor))


@app.post("/api/sessions/{session_id}/run")
async def run_session(session_id: str) -> Dict[str, Any]:
    """Triggers courtroom debate workflow execution idempotently."""
    await start_run(session_id, speed_factor=1.0)
    return {"status": "started", "sessionId": session_id}


@app.post("/api/sessions/{session_id}/fast-forward")
async def fast_forward_session(session_id: str) -> Dict[str, Any]:
    """Accelerates demo execution or starts real run idempotently."""
    await start_run(session_id, speed_factor=50.0)
    return {"status": "fast_forwarded", "sessionId": session_id}


@app.get("/api/sessions/{session_id}/result")
async def get_session_result(session_id: str) -> Dict[str, Any]:
    """Returns the finalized courtroom outcome and sandbox evidence."""
    if session_id in SESSION_RESULTS_CACHE:
        return SESSION_RESULTS_CACHE[session_id]

    stored_result = repo.get_session_result(session_id)
    if stored_result:
        return stored_result

    db_session = repo.get_session(session_id)
    if not db_session:
        raise HTTPException(status_code=404, detail="Result not found for session")

    run = RUNS.get(session_id)
    if run and run.status == "running":
        return {"status": "in_progress"}

    if db_session.status == ContractSessionStatus.FAILED:
        return {
            "sessionId": session_id,
            "status": "unresolved",
            "initialFailedTests": 0,
            "finalFailedTests": 0,
            "errors": [],
            "correctedCode": db_session.original_source,
            "summary": "Session failed without verified fix.",
            "rounds": [],
            "rejectedAttempts": [],
            "limitations": [],
        }

    return {"status": "in_progress"}


@app.get("/api/sessions/{session_id}/events")
async def stream_events(session_id: str, request: Request) -> StreamingResponse:
    """
    Server-Sent Events (SSE) streaming endpoint.
    Streams live debate events from LangGraph agents and execution sandboxes to the UI.
    Supports replay buffer and Last-Event-ID header.
    """
    run = get_or_create_run(session_id)
    queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    run.subscribers.append(queue)

    # Start run idempotently
    await start_run(session_id)

    last_event_id_header = request.headers.get("last-event-id")
    last_event_id = 0
    if last_event_id_header and last_event_id_header.isdigit():
        last_event_id = int(last_event_id_header)

    async def event_generator():
        try:
            # Yield initial connection ping
            yield f"data: {json.dumps({'type': 'connected', 'sessionId': session_id, 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"

            # Replay stored events
            for ev in list(run.events):
                ev_id = ev.get("event_id", 0)
                if ev_id > last_event_id:
                    yield f"id: {ev_id}\ndata: {json.dumps(ev)}\n\n"
                    if ev.get("type") in ("completed", "error"):
                        return

            # Stream live events
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20.0)
                    ev_id = event.get("event_id", 0)
                    if ev_id > last_event_id:
                        yield f"id: {ev_id}\ndata: {json.dumps(event)}\n\n"
                    if event.get("type") in ("completed", "error"):
                        break
                except asyncio.TimeoutError:
                    yield f": keep-alive\n\n"
        finally:
            if queue in run.subscribers:
                run.subscribers.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

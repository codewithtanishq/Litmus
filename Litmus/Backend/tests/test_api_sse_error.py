"""
Tests for FastAPI SSE Error Reporting & Ollama-Unavailable Handling.
===================================================================
Verifies Requirement 7:
1. Real sessions fail cleanly with structured error events when Ollama is unavailable.
2. SSE event serialization formats error events correctly for the React frontend.
3. Never fabricates AI fixes or returns false 'test_verified' verdicts.
4. Updates SQLite session status to FAILED and stores unresolved error details.
"""

import asyncio
import json
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
    FrontendDebugEvent,
)
from app.contracts import SessionStatus as ContractSessionStatus


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check_reports_offline_ollama(client):
    """Health check endpoint correctly surfaces Ollama offline status without error."""
    with mock.patch("app.api.server.is_ollama_available", return_value=False):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"]["status"] == "connected"
        assert data["services"]["ollama"]["available"] is False


def test_frontend_debug_event_sse_serialization():
    """FrontendDebugEvent serializes to valid JSON matching the frontend DebugEvent contract."""
    event = FrontendDebugEvent(
        type="error",
        sessionId="test-sess-123",
        roundNumber=1,
        timestamp="2026-10-13T17:00:00Z",
        agent="system",
        message="Cannot connect to local Ollama server at 'http://localhost:11434'.",
        payload={"error_code": "OLLAMA_UNAVAILABLE"},
    )
    dumped = event.model_dump()
    json_str = json.dumps(dumped)
    parsed = json.loads(json_str)

    # Check contract fields expected by React frontend BattlePage
    assert parsed["type"] == "error"
    assert parsed["sessionId"] == "test-sess-123"
    assert parsed["roundNumber"] == 1
    assert parsed["agent"] == "system"
    assert "Cannot connect to local Ollama server" in parsed["message"]
    assert parsed["payload"]["error_code"] == "OLLAMA_UNAVAILABLE"


def test_real_session_fails_cleanly_when_ollama_unavailable():
    """
    When a real debugging session (isDemo=False) runs while Ollama is offline:
    1. Emits analysis_started then structured error event.
    2. Does NOT fabricate candidate fixes or emit root_cause_located.
    3. Updates SQLite session status to FAILED.
    4. Caches unresolved result with clear error summary.
    """
    async def _run():
        session_id = "test-real-ollama-offline-001"
        SESSION_INPUTS_CACHE[session_id] = {
            "mode": "code",
            "language": "python",
            "question": "Zero division error",
            "code": "def div(a, b): return a / b",
            "isDemo": False,
        }

        # Setup queue to capture emitted events
        queue = asyncio.Queue()
        SESSION_STREAMS[session_id] = [queue]

        with mock.patch("app.api.server.is_ollama_available", return_value=False):
            await execute_courtroom_debate_task(session_id, speed_factor=100.0)

        # Drain captured events
        events = []
        while not queue.empty():
            events.append(await queue.get())

        # Verify event types: must include analysis_started and error, must NOT include completed or root_cause_located
        event_types = [e.type for e in events]
        assert "analysis_started" in event_types
        assert "error" in event_types
        assert "root_cause_located" not in event_types
        assert "judge_decision" not in event_types
        assert "completed" not in event_types

        # Verify error event details
        error_event = next(e for e in events if e.type == "error")
        assert "Cannot connect to local Ollama server" in error_event.message
        assert "ollama serve" in error_event.message
        assert error_event.payload["error_code"] == "OLLAMA_UNAVAILABLE"

        # Verify SQLite status was updated to FAILED
        db_session = repo.get_session(session_id)
        if db_session:
            assert db_session.status == ContractSessionStatus.FAILED

        # Verify result cache is marked unresolved (never test_verified)
        cached_result = SESSION_RESULTS_CACHE.get(session_id)
        assert cached_result is not None
        assert cached_result["status"] == "unresolved"
        assert cached_result["correctedCode"] is None
        assert "Adjudication Pipeline Error" in cached_result["summary"]

    asyncio.run(_run())


def test_demo_session_executes_canned_scenario():
    """
    Demo/mock sessions (isDemo=True) continue to execute deterministic scenarios
    for UI inspection even when Ollama is offline.
    """
    async def _run():
        session_id = "test-demo-sess-002"
        SESSION_INPUTS_CACHE[session_id] = {
            "mode": "code",
            "language": "python",
            "question": "Sample demo question",
            "code": "def demo(): pass",
            "isDemo": True,
            "scenarioId": "fix_b_passes",
        }

        queue = asyncio.Queue()
        SESSION_STREAMS[session_id] = [queue]

        with mock.patch("app.api.server.is_ollama_available", return_value=False):
            await execute_courtroom_debate_task(session_id, speed_factor=100.0)

        events = []
        while not queue.empty():
            events.append(await queue.get())

        event_types = [e.type for e in events]
        assert "analysis_started" in event_types
        assert "root_cause_located" in event_types
        assert "fixes_compared" in event_types
        assert "sandbox_finished" in event_types
        assert "judge_decision" in event_types
        assert "completed" in event_types

    asyncio.run(_run())

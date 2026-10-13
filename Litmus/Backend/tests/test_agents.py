"""
Unit tests for ProsecutorAgent and DefenderAgent with mocked Ollama clients.
"""

from unittest import mock
import pytest

from app.config import OllamaSettings
from app.agents.prosecutor import ProsecutorAgent
from app.agents.defender import DefenderAgent
from app.agents.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    MalformedOutputError,
)
from app.schemas.session import DebugSession
from app.schemas.patch import CandidatePatch, AgentRole
from app.schemas.interfaces import ConstraintRecord
from app.schemas.events import WorkflowEventType
from app.events.publisher import InMemoryEventPublisher


@pytest.fixture
def sample_session() -> DebugSession:
    return DebugSession(
        session_id="session-court-101",
        original_code="def divide(a, b):\n    return a / b",
        bug_description="ZeroDivisionError when b is zero. Need safe handling.",
        test_suite="assert divide(4, 2) == 2\nassert divide(4, 0) == 0",
        current_round=1,
    )


@pytest.fixture
def sample_constraints() -> list[ConstraintRecord]:
    return [
        ConstraintRecord(
            session_id="session-court-101",
            round_number=1,
            agent_role=AgentRole.PROSECUTOR,
            patch_id="patch-prev-1",
            rejected_code="if b == 0: return None",
            failure_reason="Returned None instead of 0 as expected by assertion",
            test_stderr="AssertionError: assert None == 0",
        )
    ]


class TestProsecutorAgent:
    def test_prompt_construction_empty_constraints(self, sample_session: DebugSession):
        agent = ProsecutorAgent()
        prompt = agent.build_prompt(sample_session, constraints=None)
        assert "BUG DESCRIPTION:" in prompt
        assert "ZeroDivisionError when b is zero" in prompt
        assert "None (Initial round" in prompt
        assert "ORIGINAL BUGGY SOURCE CODE:" in prompt

    def test_prompt_construction_with_constraints(
        self, sample_session: DebugSession, sample_constraints: list[ConstraintRecord]
    ):
        agent = ProsecutorAgent()
        prompt = agent.build_prompt(sample_session, constraints=sample_constraints)
        assert "Constraint #1" in prompt
        assert "Returned None instead of 0" in prompt
        assert "Rejected Code:" in prompt
        assert "RULE: Do NOT repeat this failed implementation" in prompt

    def test_analyze_and_propose_success(self, sample_session: DebugSession):
        mock_client = mock.MagicMock(spec=OllamaClient)
        mock_client.generate.return_value = '{"root_cause": "unhandled zero denominator", "explanation": "Add guard clause returning 0", "proposed_code": "def divide(a, b):\\n    return a / b if b != 0 else 0"}'
        mock_client.parse_json_response.return_value = {
            "root_cause": "unhandled zero denominator",
            "explanation": "Add guard clause returning 0",
            "proposed_code": "def divide(a, b):\n    return a / b if b != 0 else 0",
            "diff": "- return a / b\n+ return a / b if b != 0 else 0",
        }

        publisher = InMemoryEventPublisher()
        agent = ProsecutorAgent(ollama_client=mock_client, event_publisher=publisher)

        patch = agent.analyze_and_propose(sample_session)

        assert isinstance(patch, CandidatePatch)
        assert patch.agent_role == AgentRole.PROSECUTOR
        assert "divide(a, b)" in patch.proposed_code
        assert "unhandled zero denominator" in patch.explanation
        assert patch.round_number == 1

        # Verify emitted workflow events
        events = publisher.get_events(session_id=sample_session.session_id)
        assert len(events) == 2
        assert events[0].event_type == WorkflowEventType.AGENT_STARTED
        assert events[0].data["agent_role"] == "prosecutor"
        assert events[1].event_type == WorkflowEventType.PATCH_PROPOSED
        assert events[1].data["agent_role"] == "prosecutor"
        assert events[1].data["patch_id"] == patch.patch_id

    def test_malformed_output_missing_proposed_code(self, sample_session: DebugSession):
        mock_client = mock.MagicMock(spec=OllamaClient)
        mock_client.generate.return_value = '{"explanation": "Fix explanation only"}'
        mock_client.parse_json_response.return_value = {
            "explanation": "Fix explanation only",
            "proposed_code": "",  # missing/empty
        }

        agent = ProsecutorAgent(ollama_client=mock_client)
        with pytest.raises(MalformedOutputError, match="missing or empty 'proposed_code'"):
            agent.analyze_and_propose(sample_session)

    def test_connection_error_propagated_without_fabrication(self, sample_session: DebugSession):
        mock_client = mock.MagicMock(spec=OllamaClient)
        mock_client.generate.side_effect = OllamaConnectionError("Connection refused")

        agent = ProsecutorAgent(ollama_client=mock_client)
        with pytest.raises(OllamaConnectionError, match="Connection refused"):
            agent.analyze_and_propose(sample_session)


class TestDefenderAgent:
    def test_prompt_construction_with_prosecutor_patch(self, sample_session: DebugSession):
        agent = DefenderAgent()
        prosecutor_patch = CandidatePatch(
            agent_role=AgentRole.PROSECUTOR,
            proposed_code="def divide(a, b): return a / b if b else 0",
            explanation="Check truthiness of b",
        )
        prompt = agent.build_prompt(sample_session, prosecutor_patch=prosecutor_patch)

        assert "PROSECUTOR'S PROPOSED FIX A FOR SCRUTINY:" in prompt
        assert "Check truthiness of b" in prompt
        assert "Fix A Proposed Code:" in prompt or "Proposed Code:" in prompt

    def test_critique_and_propose_success(self, sample_session: DebugSession):
        mock_client = mock.MagicMock(spec=OllamaClient)
        mock_client.generate.return_value = '{"critique": "Truthiness check fails on negative b", "explanation": "Explicit b == 0 comparison is safer", "proposed_code": "def divide(a, b):\\n    if b == 0:\\n        return 0\\n    return a / b"}'
        mock_client.parse_json_response.return_value = {
            "critique": "Truthiness check fails on negative b",
            "explanation": "Explicit b == 0 comparison is safer",
            "proposed_code": "def divide(a, b):\n    if b == 0:\n        return 0\n    return a / b",
        }

        publisher = InMemoryEventPublisher()
        agent = DefenderAgent(ollama_client=mock_client, event_publisher=publisher)

        prosecutor_patch = CandidatePatch(
            agent_role=AgentRole.PROSECUTOR,
            proposed_code="def divide(a, b): return a / b if b else 0",
            explanation="Check b",
        )

        patch = agent.critique_and_propose(sample_session, prosecutor_patch=prosecutor_patch)

        assert isinstance(patch, CandidatePatch)
        assert patch.agent_role == AgentRole.DEFENDER
        assert "if b == 0:" in patch.proposed_code
        assert "Critique of Fix A" in patch.explanation
        assert patch.round_number == 1

        # Verify emitted workflow events
        events = publisher.get_events(session_id=sample_session.session_id)
        assert len(events) == 2
        assert events[0].event_type == WorkflowEventType.AGENT_STARTED
        assert events[0].data["agent_role"] == "defender"
        assert events[1].event_type == WorkflowEventType.PATCH_PROPOSED
        assert events[1].data["agent_role"] == "defender"
        assert events[1].data["patch_id"] == patch.patch_id

    def test_malformed_output_missing_critique_and_explanation(self, sample_session: DebugSession):
        mock_client = mock.MagicMock(spec=OllamaClient)
        mock_client.generate.return_value = '{"proposed_code": "def divide(): pass"}'
        mock_client.parse_json_response.return_value = {
            "proposed_code": "def divide(): pass",
            "critique": "",
            "explanation": "",
        }

        agent = DefenderAgent(ollama_client=mock_client)
        with pytest.raises(MalformedOutputError, match="missing both 'critique' and 'explanation'"):
            agent.critique_and_propose(sample_session)

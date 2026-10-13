"""
Automated unit and integration tests for LangGraph courtroom workflow integration.
Verifies Prosecutor node, Defender node, graph compilation, routing, event publishing,
evaluation boundary, and failure isolation without requiring a live Ollama server.
"""

from unittest import mock
import pytest

from app.schemas.session import DebugSession, SessionStatus
from app.schemas.patch import CandidatePatch, AgentRole
from app.schemas.interfaces import IConstraintLedger, ConstraintRecord
from app.schemas.events import WorkflowEventType
from app.events.publisher import InMemoryEventPublisher
from app.agents.prosecutor import ProsecutorAgent
from app.agents.defender import DefenderAgent
from app.agents.ollama_client import OllamaConnectionError
from app.orchestration.state import create_initial_workflow_state, WorkflowState
from app.orchestration.graph import CourtroomWorkflow, build_courtroom_workflow


@pytest.fixture
def sample_session() -> DebugSession:
    return DebugSession(
        session_id="case-777",
        original_code="def multiply(x, y): return x + y",
        bug_description="Function uses addition (+) instead of multiplication (*).",
        test_suite="assert multiply(3, 4) == 12",
        current_round=1,
    )


@pytest.fixture
def mock_prosecutor_patch() -> CandidatePatch:
    return CandidatePatch(
        patch_id="patch-fix-a",
        agent_role=AgentRole.PROSECUTOR,
        proposed_code="def multiply(x, y): return x * y",
        explanation="Replaced addition operator with multiplication operator.",
        round_number=1,
    )


@pytest.fixture
def mock_defender_patch() -> CandidatePatch:
    return CandidatePatch(
        patch_id="patch-fix-b",
        agent_role=AgentRole.DEFENDER,
        proposed_code="def multiply(x, y):\n    if x == 0 or y == 0:\n        return 0\n    return x * y",
        explanation="Critique: Fix A works but does not handle zero multiplication early. Fix B adds zero guard.",
        round_number=1,
    )


class TestProsecutorNode:
    def test_prosecutor_node_stores_fix_a_and_calls_agent(
        self, sample_session: DebugSession, mock_prosecutor_patch: CandidatePatch
    ):
        mock_prosecutor = mock.MagicMock(spec=ProsecutorAgent)
        mock_prosecutor.analyze_and_propose.return_value = mock_prosecutor_patch

        publisher = InMemoryEventPublisher()
        workflow = CourtroomWorkflow(prosecutor_agent=mock_prosecutor, event_publisher=publisher)

        state = create_initial_workflow_state(sample_session)
        updated_state = workflow.prosecutor_node(state)

        # Agent called with correct parameters
        mock_prosecutor.analyze_and_propose.assert_called_once()
        call_kwargs = mock_prosecutor.analyze_and_propose.call_args[1]
        assert call_kwargs["session"].session_id == "case-777"
        assert call_kwargs["session"].original_code == sample_session.original_code
        assert call_kwargs["round_number"] == 1

        # State updated
        assert updated_state["fix_a"] is not None
        assert updated_state["fix_a"]["patch_id"] == "patch-fix-a"
        assert updated_state["candidate_patches"]["prosecutor"]["patch_id"] == "patch-fix-a"
        assert "Prosecutor successfully proposed Fix A" in updated_state["audit_log"][-1]
        assert not updated_state.get("errors")

    def test_prosecutor_node_handles_agent_exception_without_fabrication(
        self, sample_session: DebugSession
    ):
        mock_prosecutor = mock.MagicMock(spec=ProsecutorAgent)
        mock_prosecutor.analyze_and_propose.side_effect = OllamaConnectionError("Ollama offline")

        publisher = InMemoryEventPublisher()
        workflow = CourtroomWorkflow(prosecutor_agent=mock_prosecutor, event_publisher=publisher)

        state = create_initial_workflow_state(sample_session)
        updated_state = workflow.prosecutor_node(state)

        # No patch fabricated
        assert updated_state.get("fix_a") is None
        assert "prosecutor" not in updated_state.get("candidate_patches", {})

        # Errors recorded honestly
        assert updated_state["status"] == "failed"
        assert any("Ollama offline" in err for err in updated_state["errors"])
        assert updated_state["agent_errors"]["prosecutor"] == "Ollama offline"

        # Event emitted
        events = publisher.get_events(event_type=WorkflowEventType.SESSION_FAILED)
        assert len(events) == 1
        assert events[0].data["agent_role"] == "prosecutor"


class TestDefenderNode:
    def test_defender_node_stores_fix_b_and_receives_fix_a(
        self,
        sample_session: DebugSession,
        mock_prosecutor_patch: CandidatePatch,
        mock_defender_patch: CandidatePatch,
    ):
        mock_defender = mock.MagicMock(spec=DefenderAgent)
        mock_defender.critique_and_propose.return_value = mock_defender_patch

        publisher = InMemoryEventPublisher()
        workflow = CourtroomWorkflow(defender_agent=mock_defender, event_publisher=publisher)

        state = create_initial_workflow_state(sample_session)
        state["fix_a"] = mock_prosecutor_patch.model_dump()
        state["candidate_patches"]["prosecutor"] = mock_prosecutor_patch.model_dump()

        updated_state = workflow.defender_node(state)

        # Agent called with Fix A
        mock_defender.critique_and_propose.assert_called_once()
        call_kwargs = mock_defender.critique_and_propose.call_args[1]
        assert call_kwargs["prosecutor_patch"].patch_id == "patch-fix-a"
        assert call_kwargs["session"].original_code == sample_session.original_code

        # State updated
        assert updated_state["fix_b"] is not None
        assert updated_state["fix_b"]["patch_id"] == "patch-fix-b"
        assert updated_state["candidate_patches"]["defender"]["patch_id"] == "patch-fix-b"
        assert "Defender successfully proposed Fix B" in updated_state["audit_log"][-1]

    def test_defender_node_aborts_when_fix_a_is_missing(self, sample_session: DebugSession):
        mock_defender = mock.MagicMock(spec=DefenderAgent)
        publisher = InMemoryEventPublisher()
        workflow = CourtroomWorkflow(defender_agent=mock_defender, event_publisher=publisher)

        # State without fix_a
        state = create_initial_workflow_state(sample_session)
        updated_state = workflow.defender_node(state)

        # Defender agent should not even be called
        mock_defender.critique_and_propose.assert_not_called()
        assert updated_state.get("fix_b") is None
        assert updated_state["status"] == "failed"
        assert any("Fix A is missing" in err for err in updated_state["errors"])

    def test_defender_node_handles_agent_exception(
        self, sample_session: DebugSession, mock_prosecutor_patch: CandidatePatch
    ):
        mock_defender = mock.MagicMock(spec=DefenderAgent)
        mock_defender.critique_and_propose.side_effect = RuntimeError("Generation failed")

        publisher = InMemoryEventPublisher()
        workflow = CourtroomWorkflow(defender_agent=mock_defender, event_publisher=publisher)

        state = create_initial_workflow_state(sample_session)
        state["fix_a"] = mock_prosecutor_patch.model_dump()

        updated_state = workflow.defender_node(state)

        assert updated_state.get("fix_b") is None
        assert updated_state["status"] == "failed"
        assert any("Generation failed" in err for err in updated_state["errors"])


class TestLangGraphWorkflowIntegration:
    def test_graph_compiles_successfully(self):
        compiled = build_courtroom_workflow()
        assert compiled is not None
        assert hasattr(compiled, "invoke")

    def test_end_to_end_successful_flow_reaches_evaluation_boundary(
        self,
        sample_session: DebugSession,
        mock_prosecutor_patch: CandidatePatch,
        mock_defender_patch: CandidatePatch,
    ):
        mock_prosecutor = mock.MagicMock(spec=ProsecutorAgent)
        mock_prosecutor.analyze_and_propose.return_value = mock_prosecutor_patch

        mock_defender = mock.MagicMock(spec=DefenderAgent)
        mock_defender.critique_and_propose.return_value = mock_defender_patch

        publisher = InMemoryEventPublisher()

        compiled_graph = build_courtroom_workflow(
            prosecutor_agent=mock_prosecutor,
            defender_agent=mock_defender,
            event_publisher=publisher,
        )

        initial_state = create_initial_workflow_state(sample_session)
        final_state = compiled_graph.invoke(initial_state)

        # Execution reached evaluation boundary
        assert final_state["status"] == "evaluating"
        assert final_state["fix_a"] is not None
        assert final_state["fix_b"] is not None
        assert final_state["fix_a"]["patch_id"] == "patch-fix-a"
        assert final_state["fix_b"]["patch_id"] == "patch-fix-b"

        # Check sequence of events emitted
        events = publisher.get_events(session_id="case-777")
        event_types = [e.event_type for e in events]
        assert WorkflowEventType.SESSION_STARTED in event_types
        assert WorkflowEventType.EXECUTION_STARTED in event_types

        # Verify audit trail confirms readiness without fake test passes
        assert any("Evaluation boundary reached" in log for log in final_state["audit_log"])
        assert final_state.get("test_results") == {}

    def test_prosecutor_failure_stops_workflow_without_defender_or_evaluation(
        self, sample_session: DebugSession, mock_defender_patch: CandidatePatch
    ):
        mock_prosecutor = mock.MagicMock(spec=ProsecutorAgent)
        mock_prosecutor.analyze_and_propose.side_effect = OllamaConnectionError("Ollama offline")

        mock_defender = mock.MagicMock(spec=DefenderAgent)
        mock_defender.critique_and_propose.return_value = mock_defender_patch

        publisher = InMemoryEventPublisher()

        compiled_graph = build_courtroom_workflow(
            prosecutor_agent=mock_prosecutor,
            defender_agent=mock_defender,
            event_publisher=publisher,
        )

        initial_state = create_initial_workflow_state(sample_session)
        final_state = compiled_graph.invoke(initial_state)

        # Workflow terminated with failure
        assert final_state["status"] == "failed"
        assert final_state.get("fix_a") is None
        assert final_state.get("fix_b") is None

        # Defender was never called
        mock_defender.critique_and_propose.assert_not_called()

        # Did NOT reach evaluation boundary
        assert not any("Evaluation boundary reached" in log for log in final_state.get("audit_log", []))

    def test_defender_failure_stops_workflow_at_finalize_failure(
        self, sample_session: DebugSession, mock_prosecutor_patch: CandidatePatch
    ):
        mock_prosecutor = mock.MagicMock(spec=ProsecutorAgent)
        mock_prosecutor.analyze_and_propose.return_value = mock_prosecutor_patch

        mock_defender = mock.MagicMock(spec=DefenderAgent)
        mock_defender.critique_and_propose.side_effect = RuntimeError("Defender model timeout")

        publisher = InMemoryEventPublisher()

        compiled_graph = build_courtroom_workflow(
            prosecutor_agent=mock_prosecutor,
            defender_agent=mock_defender,
            event_publisher=publisher,
        )

        initial_state = create_initial_workflow_state(sample_session)
        final_state = compiled_graph.invoke(initial_state)

        # Fix A was proposed, but Defender failed
        assert final_state["fix_a"] is not None
        assert final_state.get("fix_b") is None
        assert final_state["status"] == "failed"

        # Evaluation boundary NOT reached
        assert not any("Evaluation boundary reached" in log for log in final_state.get("audit_log", []))

    def test_missing_constraint_ledger_handled_safely(
        self,
        sample_session: DebugSession,
        mock_prosecutor_patch: CandidatePatch,
        mock_defender_patch: CandidatePatch,
    ):
        mock_prosecutor = mock.MagicMock(spec=ProsecutorAgent)
        mock_prosecutor.analyze_and_propose.return_value = mock_prosecutor_patch
        mock_defender = mock.MagicMock(spec=DefenderAgent)
        mock_defender.critique_and_propose.return_value = mock_defender_patch

        # constraint_ledger is None
        compiled_graph = build_courtroom_workflow(
            prosecutor_agent=mock_prosecutor,
            defender_agent=mock_defender,
            constraint_ledger=None,
        )

        initial_state = create_initial_workflow_state(sample_session)
        final_state = compiled_graph.invoke(initial_state)

        assert final_state["status"] == "evaluating"
        # Calls succeeded with empty constraints
        assert mock_prosecutor.analyze_and_propose.call_args[1]["constraints"] == []
        assert mock_defender.critique_and_propose.call_args[1]["constraints"] == []

    def test_supplied_constraint_ledger_queried_and_injected(
        self,
        sample_session: DebugSession,
        mock_prosecutor_patch: CandidatePatch,
        mock_defender_patch: CandidatePatch,
    ):
        mock_prosecutor = mock.MagicMock(spec=ProsecutorAgent)
        mock_prosecutor.analyze_and_propose.return_value = mock_prosecutor_patch
        mock_defender = mock.MagicMock(spec=DefenderAgent)
        mock_defender.critique_and_propose.return_value = mock_defender_patch

        mock_ledger = mock.MagicMock(spec=IConstraintLedger)
        sample_constraint = ConstraintRecord(
            session_id="case-777",
            round_number=1,
            agent_role=AgentRole.PROSECUTOR,
            patch_id="p-old",
            rejected_code="x = 0",
            failure_reason="Caused crash",
        )
        mock_ledger.get_active_constraints.return_value = [sample_constraint]

        compiled_graph = build_courtroom_workflow(
            prosecutor_agent=mock_prosecutor,
            defender_agent=mock_defender,
            constraint_ledger=mock_ledger,
        )

        initial_state = create_initial_workflow_state(sample_session)
        final_state = compiled_graph.invoke(initial_state)

        assert final_state["status"] == "evaluating"
        mock_ledger.get_active_constraints.assert_called_with("case-777")
        assert mock_prosecutor.analyze_and_propose.call_args[1]["constraints"] == [sample_constraint]
        assert mock_defender.critique_and_propose.call_args[1]["constraints"] == [sample_constraint]

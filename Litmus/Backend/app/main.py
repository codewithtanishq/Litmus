import sys
from pathlib import Path

# Ensure backend root directory is in sys.path when invoked directly
_backend_root = Path(__file__).resolve().parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from app.config import get_settings
from app.schemas.session import DebugSession, SessionStatus
from app.events.publisher import get_event_publisher
from app.orchestration.state import create_initial_workflow_state
from app.orchestration.graph import WorkflowGraphScaffolding, PLANNED_NODES


def verify_foundation_status() -> dict:
    """Verifies that the backend foundation modules and settings are operational."""
    settings = get_settings()
    publisher = get_event_publisher()

    # Create a dummy verification session to check contract initialization
    sample_session = DebugSession(
        original_code="def add(a, b): return a - b",
        bug_description="Subtraction used instead of addition in add function",
        test_suite="assert add(2, 3) == 5",
    )

    state = create_initial_workflow_state(sample_session, max_rounds=settings.workflow.max_rounds)
    scaffolding = WorkflowGraphScaffolding()
    updated_state = scaffolding.intake_session_node(state)

    events = publisher.get_events(session_id=sample_session.session_id)

    return {
        "status": "healthy",
        "module": "Member 1: AI Agents and Orchestration",
        "ollama_config": {
            "base_url": settings.ollama.base_url,
            "model": settings.ollama.model,
            "temperature": settings.ollama.temperature,
        },
        "workflow_config": {
            "max_rounds": settings.workflow.max_rounds,
            "sandbox_timeout_seconds": settings.workflow.sandbox_timeout_seconds,
        },
        "planned_nodes_count": len(PLANNED_NODES),
        "test_session_id": sample_session.session_id,
        "sample_event_emitted": len(events) > 0,
        "intake_status": updated_state.get("status"),
    }


def main():
    print("=" * 60)
    print("Swarm Debugger — Member 1 Backend Foundation")
    print("=" * 60)
    info = verify_foundation_status()
    print(f"Status: {info['status']}")
    print(f"Module: {info['module']}")
    print(f"Ollama Target Model: {info['ollama_config']['model']} at {info['ollama_config']['base_url']}")
    print(f"Max Debate Rounds: {info['workflow_config']['max_rounds']}")
    print(f"Planned Workflow Nodes: {info['planned_nodes_count']}")
    print(f"Event Publishing Verified: {info['sample_event_emitted']}")
    print("Backend foundation initialized successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()

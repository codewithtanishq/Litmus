"""
Prosecutor Agent for Swarm Debugger.

Role & Responsibilities:
- Analyzes the reported bug description and source code.
- Reviews active constraints accumulated from previous rounds to avoid repeating failed patterns.
- Diagnoses the root cause and formulates Candidate Patch A as a minimal, precise fix.
- Emits real workflow events (`agent_started`, `patch_proposed`).
- Validates generated output strictly against the `CandidatePatch` contract.
- Never executes code inside the agent.
"""

import logging
from typing import Any, List, Optional
from uuid import uuid4

from app.config import OllamaSettings, get_settings
from app.agents.ollama_client import OllamaClient, MalformedOutputError
from app.agents.prompt_utils import format_constraints_summary, extract_python_code
from app.schemas.session import DebugSession
from app.schemas.patch import CandidatePatch, AgentRole
from app.schemas.interfaces import ConstraintRecord
from app.schemas.events import WorkflowEventType
from app.events.publisher import get_event_publisher, BaseEventPublisher

logger = logging.getLogger(__name__)

PROSECUTOR_SYSTEM_PROMPT = """You are the PROSECUTOR in the Swarm Debugger multi-agent debugging courtroom.
Your duty:
1. Examine the submitted bug description, original source code, reproduction test, and active failure constraints.
2. The code is saved as solution.py and pytest tests run against it doing `from solution import ...`. Only Python is supported.
3. Keep all public function/class names and signatures intact so tests can import them.
4. Fix the root cause in the algorithm or logic; do NOT special-case test inputs or hardcode return values. Do NOT edit or rewrite tests.
5. Provide the COMPLETE file in 'proposed_code' (not a diff, snippet, or partial function).
6. 'proposed_code' MUST be raw Python code without any markdown fences (no ```python).
7. Review prior failure constraints carefully: you MUST NOT repeat failed patches or invalid assumptions.
8. Return ONLY a single valid JSON object with the following schema:
{
    "root_cause": "<concise explanation of why the bug occurs>",
    "explanation": "<detailed rationale for Fix A, including modified functions/regions>",
    "proposed_code": "<FULL revised source code containing the fix without markdown fences>",
    "diff": "<optional unified diff or null>"
}
Do NOT include markdown text outside the JSON object."""


class ProsecutorAgent:
    """
    Prosecutor Agent.
    Formulates the initial diagnosis and proposes Fix A.
    """

    def __init__(
        self,
        ollama_settings: Optional[OllamaSettings] = None,
        ollama_client: Optional[Any] = None,
        event_publisher: Optional[BaseEventPublisher] = None,
    ) -> None:
        from app.agents.hybrid_client import HybridLLMClient

        self.settings = ollama_settings or get_settings().ollama
        self.client = ollama_client or HybridLLMClient(ollama_settings=self.settings)
        self.publisher = event_publisher or get_event_publisher()

    def build_prompt(
        self,
        session: DebugSession,
        constraints: Optional[List[ConstraintRecord]] = None,
    ) -> str:
        """
        Builds the prompt instructing the Prosecutor to diagnose the bug and propose Fix A.
        """
        constraints_block = format_constraints_summary(constraints)
        test_block = (
            f"Reproduction Test Suite:\n```\n{session.test_suite}\n```\n"
            if session.test_suite
            else "Reproduction Test Suite: Not explicitly provided.\n"
        )

        return (
            f"=== COURTROOM CASE SUBMISSION (Round {session.current_round}) ===\n"
            f"Session ID: {session.session_id}\n\n"
            f"BUG DESCRIPTION:\n{session.bug_description}\n\n"
            f"ORIGINAL BUGGY SOURCE CODE:\n```\n{session.original_code}\n```\n\n"
            f"{test_block}\n"
            f"ACTIVE CONSTRAINTS FROM PRIOR REJECTED FIXES:\n{constraints_block}\n\n"
            f"TASK FOR PROSECUTOR:\n"
            f"1. Diagnose the bug and explain the root cause.\n"
            f"2. Formulate Fix A and provide the COMPLETE revised code in 'proposed_code'.\n"
            f"3. Return your response as a strict JSON object with fields: 'root_cause', 'explanation', 'proposed_code', and optional 'diff'."
        )

    def analyze_and_propose(
        self,
        session: DebugSession,
        constraints: Optional[List[ConstraintRecord]] = None,
        round_number: Optional[int] = None,
    ) -> CandidatePatch:
        """
        Runs the Prosecutor role:
        1. Emits agent_started event.
        2. Queries Ollama with formatted prompt.
        3. Parses structured JSON response.
        4. Validates CandidatePatch schema.
        5. Emits patch_proposed event.

        Raises:
            OllamaError: If LLM call fails, times out, or cannot connect.
            MalformedOutputError: If model output cannot be converted into a valid CandidatePatch.
        """
        active_round = round_number if round_number is not None else session.current_round

        # Emit agent_started event
        self.publisher.emit(
            event_type=WorkflowEventType.AGENT_STARTED,
            session_id=session.session_id,
            round_number=active_round,
            data={
                "agent_role": AgentRole.PROSECUTOR.value,
                "model": self.settings.model,
            },
        )

        prompt = self.build_prompt(session, constraints)

        parsed_data = None
        clean_code = ""
        current_prompt = prompt
        last_error: Optional[MalformedOutputError] = None

        for attempt in range(1, 4):
            try:
                raw_response = self.client.generate(
                    prompt=current_prompt,
                    system_instruction=PROSECUTOR_SYSTEM_PROMPT,
                    format_json=True,
                )
                data = self.client.parse_json_response(raw_response)

                proposed_code = data.get("proposed_code")
                if not proposed_code or not isinstance(proposed_code, str) or not proposed_code.strip():
                    raise MalformedOutputError(
                        "Prosecutor model output missing or empty 'proposed_code' field."
                    )

                clean_code = extract_python_code(proposed_code)

                explanation = data.get("explanation") or ""
                root_cause = data.get("root_cause") or ""
                if not explanation and not root_cause:
                    raise MalformedOutputError(
                        "Prosecutor model output missing both 'explanation' and 'root_cause' fields."
                    )

                parsed_data = data
                break
            except MalformedOutputError as exc:
                last_error = exc
                logger.warning(f"Prosecutor generation attempt {attempt}/3 failed: {exc}")
                if attempt < 3:
                    current_prompt = (
                        f"{prompt}\n\nYour previous reply was invalid: {exc}. "
                        "Return ONLY valid JSON matching the schema."
                    )
                else:
                    raise last_error

        full_explanation = (
            f"Root Cause: {parsed_data.get('root_cause', '')}\nDiagnosis & Fix A Rationale: {parsed_data.get('explanation', '')}".strip()
            if parsed_data.get("root_cause") and parsed_data.get("explanation")
            else (parsed_data.get("explanation") or parsed_data.get("root_cause") or "")
        )

        diff = parsed_data.get("diff")
        if diff is not None and not isinstance(diff, str):
            diff = str(diff)

        # Instantiate and validate CandidatePatch
        patch = CandidatePatch(
            patch_id=str(uuid4()),
            agent_role=AgentRole.PROSECUTOR,
            proposed_code=clean_code.strip(),
            explanation=full_explanation.strip(),
            round_number=active_round,
            diff=diff.strip() if diff else None,
        )

        # Emit patch_proposed event
        self.publisher.emit(
            event_type=WorkflowEventType.PATCH_PROPOSED,
            session_id=session.session_id,
            round_number=active_round,
            data={
                "agent_role": AgentRole.PROSECUTOR.value,
                "patch_id": patch.patch_id,
                "explanation": patch.explanation[:200],
            },
        )

        return patch

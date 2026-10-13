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
from app.agents.prompt_utils import format_constraints_summary
from app.schemas.session import DebugSession
from app.schemas.patch import CandidatePatch, AgentRole
from app.schemas.interfaces import ConstraintRecord
from app.schemas.events import WorkflowEventType
from app.events.publisher import get_event_publisher, BaseEventPublisher

logger = logging.getLogger(__name__)

PROSECUTOR_SYSTEM_PROMPT = """You are the PROSECUTOR in the Swarm Debugger multi-agent debugging courtroom.
Your duty:
1. Examine the submitted bug description, original source code, reproduction test, and active failure constraints.
2. Identify the root cause of the bug and formulate Fix A as a minimal, clean, robust patch.
3. Review prior failure constraints carefully: you MUST NOT repeat failed patches or invalid assumptions.
4. If the bug evidence is ambiguous or insufficient, clearly state your uncertainty in the explanation.
5. Return ONLY a single valid JSON object with the following schema:
{
    "root_cause": "<concise explanation of why the bug occurs>",
    "explanation": "<detailed rationale for Fix A, including modified functions/regions>",
    "proposed_code": "<FULL revised source code containing the fix>",
    "diff": "<optional unified diff or null>"
}
Do NOT include markdown text outside the JSON object. Do NOT hallucinate tests."""


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

        # Call local Ollama client
        raw_response = self.client.generate(
            prompt=prompt,
            system_instruction=PROSECUTOR_SYSTEM_PROMPT,
            format_json=True,
        )

        parsed_data = self.client.parse_json_response(raw_response)

        # Extract and validate required fields
        proposed_code = parsed_data.get("proposed_code")
        if not proposed_code or not isinstance(proposed_code, str) or not proposed_code.strip():
            raise MalformedOutputError(
                "Prosecutor model output missing or empty 'proposed_code' field."
            )

        explanation = parsed_data.get("explanation") or ""
        root_cause = parsed_data.get("root_cause") or ""
        if not explanation and not root_cause:
            raise MalformedOutputError(
                "Prosecutor model output missing both 'explanation' and 'root_cause' fields."
            )

        full_explanation = (
            f"Root Cause: {root_cause}\nDiagnosis & Fix A Rationale: {explanation}".strip()
            if root_cause and explanation
            else (explanation or root_cause)
        )

        diff = parsed_data.get("diff")
        if diff is not None and not isinstance(diff, str):
            diff = str(diff)

        # Instantiate and validate CandidatePatch
        patch = CandidatePatch(
            patch_id=str(uuid4()),
            agent_role=AgentRole.PROSECUTOR,
            proposed_code=proposed_code.strip(),
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

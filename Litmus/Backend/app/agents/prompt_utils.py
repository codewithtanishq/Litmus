"""
Prompt construction and formatting utilities for Swarm Debugger AI agents.
"""

from typing import Any, List, Optional
from app.schemas.interfaces import ConstraintRecord


def format_constraints_summary(constraints: Optional[List[Any]]) -> str:
    """
    Formats the cumulative active constraints retrieved from Member 2's Constraint Ledger.
    Ensures empty constraints are properly represented for initial debugging rounds.
    Compatible with both Member 2 app.contracts.Constraint and Member 1 ConstraintRecord.

    Args:
        constraints: Cumulative list of rejected hypotheses and test error evidence.

    Returns:
        Structured text block for inclusion in agent prompt.
    """
    if not constraints:
        return "None (Initial round — no prior rejected hypotheses)."

    formatted_entries = []
    for idx, c in enumerate(constraints, 1):
        if hasattr(c, "constraint_text"):
            # app.contracts.Constraint
            formatted_entries.append(
                f"Constraint #{idx} (Failed in Round {c.round_number}, Signature: {c.failure_signature}):\n"
                f"{c.constraint_text}\n"
                f"  -> RULE: Do NOT repeat this failed implementation or reasoning."
            )
        else:
            # app.schemas.interfaces.ConstraintRecord
            agent_role = getattr(c, "agent_role", "PROSECUTOR")
            role_label = agent_role.value.upper() if hasattr(agent_role, "value") else str(agent_role).upper()
            code_preview = getattr(c, "rejected_code", "").strip()
            if len(code_preview) > 300:
                code_preview = code_preview[:300] + "\n... [truncated]"

            stderr_preview = getattr(c, "test_stderr", "").strip()
            if len(stderr_preview) > 200:
                stderr_preview = stderr_preview[:200] + "... [truncated]"
            elif not stderr_preview:
                stderr_preview = "Execution assertion failure or non-zero exit code"

            reason = getattr(c, "failure_reason", "Test assertion failure")

            formatted_entries.append(
                f"Constraint #{idx} (Failed in Round {c.round_number}, Proposed by {role_label}):\n"
                f"  * Failure Reason: {reason}\n"
                f"  * Test Failure Evidence: {stderr_preview}\n"
                f"  * Rejected Code:\n```\n{code_preview}\n```\n"
                f"  -> RULE: Do NOT repeat this failed implementation or reasoning."
            )

    return "\n\n".join(formatted_entries)

"""
Prompt construction and formatting utilities for Swarm Debugger AI agents.
"""

from typing import List, Optional
from app.schemas.interfaces import ConstraintRecord


def format_constraints_summary(constraints: Optional[List[ConstraintRecord]]) -> str:
    """
    Formats the cumulative active constraints retrieved from Member 2's Constraint Ledger.
    Ensures empty constraints are properly represented for initial debugging rounds.

    Args:
        constraints: Cumulative list of rejected hypotheses and test error evidence.

    Returns:
        Structured text block for inclusion in agent prompt.
    """
    if not constraints:
        return "None (Initial round — no prior rejected hypotheses)."

    formatted_entries = []
    for idx, c in enumerate(constraints, 1):
        role_label = c.agent_role.value.upper() if hasattr(c.agent_role, "value") else str(c.agent_role).upper()
        code_preview = c.rejected_code.strip()
        if len(code_preview) > 300:
            code_preview = code_preview[:300] + "\n... [truncated]"

        stderr_preview = c.test_stderr.strip()
        if len(stderr_preview) > 200:
            stderr_preview = stderr_preview[:200] + "... [truncated]"
        elif not stderr_preview:
            stderr_preview = "Execution assertion failure or non-zero exit code"

        formatted_entries.append(
            f"Constraint #{idx} (Failed in Round {c.round_number}, Proposed by {role_label}):\n"
            f"  * Failure Reason: {c.failure_reason}\n"
            f"  * Test Failure Evidence: {stderr_preview}\n"
            f"  * Rejected Code:\n```\n{code_preview}\n```\n"
            f"  -> RULE: Do NOT repeat this failed implementation or reasoning."
        )

    return "\n\n".join(formatted_entries)

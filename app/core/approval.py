"""
ApprovalHandler protocol — pluggable human-in-the-loop approval.

CLI implementation for now (M1). Auto (auto-approve, useful for tests
and READ-only flows) also included. Telegram implementation comes in
M6, using the same protocol so call_tool() never needs to change.
"""

from __future__ import annotations

from typing import Protocol

from app.core.types import PermissionLevel
from app.core.logging_setup import logger


class ApprovalHandler(Protocol):
    def request_approval(self, tool_name: str, permission: PermissionLevel, tool_kwargs: dict) -> bool:
        """Return True if approved, False if denied."""
        ...


class CLIApprovalHandler:
    """Prompts on stdin/stdout. Used for local dev/testing."""

    def request_approval(self, tool_name: str, permission: PermissionLevel, tool_kwargs: dict) -> bool:
        print(f"\n[APPROVAL REQUIRED] tool='{tool_name}' permission={permission.value}")
        print(f"  args: {tool_kwargs}")
        answer = input("  Approve? (yes/no): ").strip().lower()
        approved = answer in ("y", "yes")
        logger.info("CLI approval for '{}': {}", tool_name, "APPROVED" if approved else "DENIED")
        return approved


class AutoApprovalHandler:
    """Always approves. Used for tests and READ-only auto-approve policies."""

    def request_approval(self, tool_name: str, permission: PermissionLevel, tool_kwargs: dict) -> bool:
        logger.debug("Auto-approved '{}' (permission={})", tool_name, permission.value)
        return True
    

class DefaultSafeApprovalHandler:
    """
    The safe default used when call_tool() is not given an explicit
    approval_handler. Auto-approves READ (matches _REQUIRES_APPROVAL
    policy), but RAISES rather than silently approving anything at
    MODIFY/DELETE/ADMIN — a caller must pass a real handler (CLI,
    Telegram, or an explicit AutoApprovalHandler if they really mean
    to bypass approval, e.g. in tests) for anything destructive.
    This closes a gap where forgetting to pass approval_handler=
    would have silently auto-approved destructive actions.
    """

    def request_approval(self, tool_name: str, permission: PermissionLevel, tool_kwargs: dict) -> bool:
        if permission == PermissionLevel.READ:
            return True
        raise RuntimeError(
            f"No approval_handler was provided for tool '{tool_name}' "
            f"(permission={permission.value}). Destructive/modifying tools "
            f"require an explicit approval_handler — refusing to silently "
            f"auto-approve."
        )


__all__ = ["ApprovalHandler", "CLIApprovalHandler", "AutoApprovalHandler", "DefaultSafeApprovalHandler"]
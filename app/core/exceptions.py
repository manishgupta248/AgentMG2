"""
Domain exception hierarchy.

Rule (from Working Rules & Methodology): any `except Exception:` block
must log and re-raise wrapped in one of these, using `raise X(...) from e`
for proper exception chaining — never swallow the original traceback,
and never re-raise bare outside the except block.
"""


class AgentError(Exception):
    """Base class for all domain-specific errors in the agent."""

    def __init__(self, message: str, *, context: dict | None = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            return f"{self.message} | context={self.context}"
        return self.message


class ConfigError(AgentError):
    """Raised for missing/invalid configuration (.env, credentials, paths)."""


class DatabaseError(AgentError):
    """Raised when a SQLite operation fails unexpectedly."""


class ToolError(AgentError):
    """Base class for errors raised during tool execution."""


class ToolNotFoundError(ToolError):
    """Raised when call_tool() is asked to run an unregistered tool name."""


class ToolValidationError(ToolError):
    """Raised when a tool's Pydantic input validation fails."""


class ToolExecutionError(ToolError):
    """Raised when a tool's underlying logic fails during execution."""


class ApprovalDeniedError(AgentError):
    """Raised when a human explicitly denies an approval request (not a timeout)."""


class ApprovalTimeoutError(AgentError):
    """Raised when an approval request times out waiting for a human response."""


class PermissionError_(AgentError):
    """
    Raised when a requested action exceeds the caller's permission level.
    Named with trailing underscore to avoid shadowing the Python builtin.
    """


class IntentResolutionError(AgentError):
    """Raised when no tier (1 through 4) can resolve an incoming instruction."""


class ExternalServiceError(AgentError):
    """Raised when a call to an external service (Google API, Telegram, LLM) fails."""


class GoogleAPIError(ExternalServiceError):
    """Raised for Gmail/Drive/Calendar/Sheets API failures."""


class LLMProviderError(ExternalServiceError):
    """Raised when both Gemini and Groq fail (or a single provider call fails)."""


class JobError(AgentError):
    """Raised for Job Queue execution failures."""


class WorkflowError(AgentError):
    """Raised for Workflow Template execution failures."""


__all__ = [
    "AgentError",
    "ConfigError",
    "DatabaseError",
    "ToolError",
    "ToolNotFoundError",
    "ToolValidationError",
    "ToolExecutionError",
    "ApprovalDeniedError",
    "ApprovalTimeoutError",
    "PermissionError_",
    "IntentResolutionError",
    "ExternalServiceError",
    "GoogleAPIError",
    "LLMProviderError",
    "JobError",
    "WorkflowError",
]
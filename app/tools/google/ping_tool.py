"""
Trivial proof-of-discovery tool, deliberately placed in a nested
subfolder (app/tools/google/) to verify pkgutil.walk_packages finds
it. This is the exact scenario that silently failed in the prior
build under pkgutil.iter_modules.
"""

from pydantic import BaseModel

from app.core.registry import tool
from app.core.types import PermissionLevel


class PingInput(BaseModel):
    """Empty schema — ping takes no arguments, but still declares
    one explicitly. A tool with NO input_schema at all was the exact
    prior-build gap that let unvalidated input reach a live API."""
    model_config = {"extra": "forbid"}


@tool(
    "ping",
    permission=PermissionLevel.READ,
    description="Trivial connectivity check tool, used to verify recursive plugin discovery.",
    input_schema=PingInput,
    example_phrases=["ping the agent", "are you alive", "health check"],
)
def ping() -> dict:
    return {"status": "ok", "message": "pong from nested google/ subfolder"}
"""Trivial top-level tool, for contrast against the nested ping tool."""

from app.core.registry import tool
from app.core.types import PermissionLevel


@tool(
    "echo",
    permission=PermissionLevel.READ,
    description="Echoes back whatever text is given.",
    example_phrases=["echo hello", "repeat this back"],
)
def echo(text: str) -> dict:
    return {"echoed": text}
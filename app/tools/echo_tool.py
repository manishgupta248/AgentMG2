"""Trivial top-level tool, for contrast against the nested ping tool."""

from pydantic import BaseModel, Field

from app.core.registry import tool
from app.core.types import PermissionLevel


class EchoInput(BaseModel):
    text: str = Field(..., min_length=1, description="Text to echo back")


@tool(
    "echo",
    permission=PermissionLevel.READ,
    description="Echoes back whatever text is given.",
    input_schema=EchoInput,
    example_phrases=["echo hello", "repeat this back"],
)
def echo(text: str) -> dict:
    return {"echoed": text}
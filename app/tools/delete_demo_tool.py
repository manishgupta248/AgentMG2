"""
Demo tool at DELETE permission level, used to prove the approval
gate actually blocks destructive actions without an explicit handler.
Not a real destructive action — just simulates one for M2 testing.
"""

from pydantic import BaseModel

from app.core.registry import tool
from app.core.types import PermissionLevel


class DeleteDemoInput(BaseModel):
    target: str
    model_config = {"extra": "forbid"}


@tool(
    "delete_demo",
    permission=PermissionLevel.DELETE,
    description="Simulates a destructive action, for approval-gate testing only.",
    input_schema=DeleteDemoInput,
    example_phrases=["delete the demo file"],
)
def delete_demo(target: str) -> dict:
    return {"deleted": target}
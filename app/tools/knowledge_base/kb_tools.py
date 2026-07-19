"""
Knowledge Base tools — thin @tool wrappers around app.core.knowledge_base
CRUD functions, so they're callable through call_tool() with proper
permission-gated approval.
"""

from pydantic import BaseModel, Field

from app.core.registry import tool
from app.core.types import PermissionLevel
from app.core.knowledge_base import (
    kb_add,
    kb_get,
    kb_update,
    kb_delete,
    kb_search,
    kb_list_by_kind,
)


class KbAddInput(BaseModel):
    kind: str = Field(..., description="note | contact | preference | memory")
    content: str
    title: str | None = None
    metadata: dict | None = None
    model_config = {"extra": "forbid"}


@tool(
    "kb_add",
    permission=PermissionLevel.MODIFY,
    description="Adds a new entry to the Central Knowledge Base.",
    input_schema=KbAddInput,
    example_phrases=["remember that", "save this note", "add a contact"],
)
def kb_add_tool(kind: str, content: str, title: str | None = None, metadata: dict | None = None) -> dict:
    new_id = kb_add(kind, content, title=title, metadata=metadata)
    return {"id": new_id}


class KbGetInput(BaseModel):
    entry_id: int
    model_config = {"extra": "forbid"}


@tool(
    "kb_get",
    permission=PermissionLevel.READ,
    description="Fetches a single Knowledge Base entry by id.",
    input_schema=KbGetInput,
    example_phrases=["look up note", "get contact details"],
)
def kb_get_tool(entry_id: int) -> dict | None:
    return kb_get(entry_id)


class KbUpdateInput(BaseModel):
    entry_id: int
    content: str | None = None
    title: str | None = None
    metadata: dict | None = None
    model_config = {"extra": "forbid"}


@tool(
    "kb_update",
    permission=PermissionLevel.MODIFY,
    description="Updates an existing Knowledge Base entry.",
    input_schema=KbUpdateInput,
    example_phrases=["update that note", "change the contact info"],
)
def kb_update_tool(entry_id: int, content: str | None = None, title: str | None = None, metadata: dict | None = None) -> dict:
    updated = kb_update(entry_id, content=content, title=title, metadata=metadata)
    return {"updated": updated}


class KbDeleteInput(BaseModel):
    entry_id: int
    model_config = {"extra": "forbid"}


@tool(
    "kb_delete",
    permission=PermissionLevel.DELETE,
    description="Deletes a Knowledge Base entry by id.",
    input_schema=KbDeleteInput,
    example_phrases=["delete that note", "forget this contact"],
)
def kb_delete_tool(entry_id: int) -> dict:
    deleted = kb_delete(entry_id)
    return {"deleted": deleted}


class KbSearchInput(BaseModel):
    query: str
    kind: str | None = None
    limit: int = 20
    model_config = {"extra": "forbid"}


@tool(
    "kb_search",
    permission=PermissionLevel.READ,
    description="Searches Knowledge Base entries by substring match on title/content.",
    input_schema=KbSearchInput,
    example_phrases=["search my notes", "find contact"],
)
def kb_search_tool(query: str, kind: str | None = None, limit: int = 20) -> list:
    return kb_search(query, kind=kind, limit=limit)


class KbListByKindInput(BaseModel):
    kind: str
    limit: int = 50
    model_config = {"extra": "forbid"}


@tool(
    "kb_list_by_kind",
    permission=PermissionLevel.READ,
    description="Lists all Knowledge Base entries of a given kind.",
    input_schema=KbListByKindInput,
    example_phrases=["list all my contacts", "show all notes"],
)
def kb_list_by_kind_tool(kind: str, limit: int = 50) -> list:
    return kb_list_by_kind(kind, limit=limit)
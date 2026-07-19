"""
Central Knowledge Base — CRUD over kb_content.

Schema (from M1 init_db): id, kind, title, content, metadata (JSON
string), embedding (nullable BLOB, unused until a later phase),
created_at, updated_at.

kind is a free-form discriminator: 'note' | 'contact' | 'preference'
| 'memory', but not DB-enforced as an enum — kept flexible since new
kinds may emerge as the agent grows.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.core.database import db_cursor
from app.core.logging_setup import logger


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def kb_add(kind: str, content: str, title: str | None = None, metadata: dict[str, Any] | None = None) -> int:
    """Inserts a new KB entry. Returns the new row's id."""
    now = _now_iso()
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO kb_content (kind, title, content, metadata, embedding, created_at, updated_at)
            VALUES (?, ?, ?, ?, NULL, ?, ?)
            """,
            (kind, title, content, json.dumps(metadata) if metadata else None, now, now),
        )
        new_id = cur.lastrowid
    logger.info("KB entry added. id={} kind={}", new_id, kind)
    return new_id


def kb_get(entry_id: int) -> dict[str, Any] | None:
    with db_cursor() as cur:
        cur.execute("SELECT id, kind, title, content, metadata, created_at, updated_at FROM kb_content WHERE id = ?", (entry_id,))
        row = cur.fetchone()
    if row is None:
        return None
    return _row_to_dict(row)


def kb_update(entry_id: int, *, content: str | None = None, title: str | None = None, metadata: dict[str, Any] | None = None) -> bool:
    """Partial update. Only provided fields change. Returns True if a row was updated."""
    existing = kb_get(entry_id)
    if existing is None:
        return False

    new_content = content if content is not None else existing["content"]
    new_title = title if title is not None else existing["title"]
    new_metadata = metadata if metadata is not None else existing["metadata"]

    with db_cursor() as cur:
        cur.execute(
            """
            UPDATE kb_content SET content = ?, title = ?, metadata = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_content, new_title, json.dumps(new_metadata) if new_metadata else None, _now_iso(), entry_id),
        )
    logger.info("KB entry updated. id={}", entry_id)
    return True


def kb_delete(entry_id: int) -> bool:
    with db_cursor() as cur:
        cur.execute("DELETE FROM kb_content WHERE id = ?", (entry_id,))
        deleted = cur.rowcount > 0
    logger.info("KB entry delete attempted. id={} deleted={}", entry_id, deleted)
    return deleted


def kb_search(query: str, kind: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """
    Simple substring search over title+content for now (LIKE-based).
    Embedding-based semantic search is deferred to a later phase —
    this is why the embedding column exists but is untouched here.
    """
    like_query = f"%{query}%"
    with db_cursor() as cur:
        if kind:
            cur.execute(
                """
                SELECT id, kind, title, content, metadata, created_at, updated_at
                FROM kb_content
                WHERE kind = ? AND (title LIKE ? OR content LIKE ?)
                ORDER BY updated_at DESC LIMIT ?
                """,
                (kind, like_query, like_query, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, kind, title, content, metadata, created_at, updated_at
                FROM kb_content
                WHERE title LIKE ? OR content LIKE ?
                ORDER BY updated_at DESC LIMIT ?
                """,
                (like_query, like_query, limit),
            )
        rows = cur.fetchall()
    return [_row_to_dict(row) for row in rows]


def kb_list_by_kind(kind: str, limit: int = 50) -> list[dict[str, Any]]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT id, kind, title, content, metadata, created_at, updated_at FROM kb_content WHERE kind = ? ORDER BY updated_at DESC LIMIT ?",
            (kind, limit),
        )
        rows = cur.fetchall()
    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row) -> dict[str, Any]:
    entry_id, kind, title, content, metadata_json, created_at, updated_at = row
    return {
        "id": entry_id,
        "kind": kind,
        "title": title,
        "content": content,
        "metadata": json.loads(metadata_json) if metadata_json else None,
        "created_at": created_at,
        "updated_at": updated_at,
    }


__all__ = ["kb_add", "kb_get", "kb_update", "kb_delete", "kb_search", "kb_list_by_kind"]
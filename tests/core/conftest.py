"""
Shared pytest fixtures. IMPORTANT: this fixture must actually call
init_db() itself, not assume it happens elsewhere — a prior build
had a test module hit "no such table" because a shared fixture
didn't run schema init.
"""

import pytest
from pathlib import Path

from app.core.database import init_db


@pytest.fixture()
def isolated_db(tmp_path: Path) -> Path:
    """Fresh SQLite DB per test, fully schema-initialized."""
    db_path = tmp_path / "test_agent.db"
    init_db(db_path)
    return db_path
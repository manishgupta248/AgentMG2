"""Regression test for DatabaseError wrap-and-chain behavior."""

import pytest
from app.core.database import db_cursor
from app.core.exceptions import DatabaseError


def test_db_error_wraps_and_chains_original_exception(isolated_db):
    with pytest.raises(DatabaseError) as exc_info:
        with db_cursor(isolated_db) as cur:
            cur.execute("SELECT * FROM this_table_does_not_exist")

    assert exc_info.value.__cause__ is not None
    assert "no such table" in str(exc_info.value.__cause__)
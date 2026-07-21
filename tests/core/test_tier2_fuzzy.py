"""
Regression tests for Tier 2 fuzzy matching.
"""

from app.core.registry import autodiscover_tools
from app.router import tier2_fuzzy
from app.router.router import resolve_intent
from app.core.exceptions import IntentResolutionError


def test_tier2_matches_exact_example_phrase(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    result = tier2_fuzzy.try_match("are you alive")
    assert result is not None
    tool_name, kwargs = result
    assert tool_name == "ping"
    assert kwargs == {}


def test_tier2_rejects_unrelated_text(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    result = tier2_fuzzy.try_match("completely unrelated gibberish about spaceships")
    assert result is None


def test_tier2_threshold_is_88_or_higher():
    """Locks in the documented hard floor — this constant must never
    be silently lowered."""
    assert tier2_fuzzy.MIN_SCORE >= 88.0


def test_router_tries_tier1_before_tier2(isolated_db, monkeypatch):
    """'ping' should hit Tier 1's exact regex, not fall through to
    Tier 2, even though it would also fuzzy-match."""
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    tool_name, kwargs = resolve_intent("ping")
    assert tool_name == "ping"


def test_router_falls_through_to_tier2_when_tier1_misses(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    tool_name, kwargs = resolve_intent("health check")
    assert tool_name == "ping"


def test_router_raises_when_both_tier1_and_tier2_miss(isolated_db, monkeypatch):
    from app.core import database
    monkeypatch.setattr(database.settings, "db_path", isolated_db)
    autodiscover_tools()

    import pytest
    with pytest.raises(IntentResolutionError):
        resolve_intent("this is not close to anything registered at all")
"""
Regression test for recursive tool discovery — locks in the
pkgutil.walk_packages fix (vs. the old non-recursive iter_modules).
"""

from app.core.registry import autodiscover_tools, list_tools


def test_autodiscover_finds_nested_subfolder_tool():
    """
    'ping' lives in app/tools/google/ping_tool.py — a nested
    subfolder. If discovery regresses to iter_modules-style
    non-recursive behavior, this tool silently disappears.
    """
    autodiscover_tools()
    tools = list_tools()
    assert "ping" in tools, "Nested tool 'ping' (app/tools/google/) was not discovered — recursion broken!"
    assert "echo" in tools, "Top-level tool 'echo' was not discovered."
"""
Tier 1 — Regex/pattern matching. Zero LLM cost, instant. The fastest
and most predictable resolution tier; only tries to match single-tool
requests (compound requests are deferred by the compound_detector
before this tier ever runs — see router.py orchestration).

Each pattern maps to a tool_name and a function that extracts
tool_kwargs from the regex match object. Patterns are tried in
registration order; first match wins.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Pattern


@dataclass
class Tier1Pattern:
    pattern: Pattern
    tool_name: str
    extract_kwargs: Callable[[re.Match], dict]
    description: str = ""


_PATTERNS: list[Tier1Pattern] = []


def register_pattern(regex: str, tool_name: str, extract_kwargs: Callable[[re.Match], dict], description: str = "", flags=re.IGNORECASE) -> None:
    _PATTERNS.append(Tier1Pattern(re.compile(regex, flags), tool_name, extract_kwargs, description))


def try_match(text: str) -> tuple[str, dict] | None:
    """Returns (tool_name, tool_kwargs) for the first matching pattern,
    or None if nothing matches."""
    for p in _PATTERNS:
        match = p.pattern.search(text)
        if match:
            return p.tool_name, p.extract_kwargs(match)
    return None


def registered_patterns() -> list[Tier1Pattern]:
    return list(_PATTERNS)


# --- Built-in patterns for tools that exist so far ---
# Tight, specific patterns per the prior-build lesson: greedy .* can
# eat capture groups meant for something else — prefer \s+ and
# explicit boundaries over bare .*.

register_pattern(
    r"^\s*ping\b",
    "ping",
    lambda m: {},
    description="ping the agent",
)

register_pattern(
    r"^\s*echo\s+(?P<text>.+)$",
    "echo",
    lambda m: {"text": m.group("text").strip()},
    description="echo <text>",
)

register_pattern(
    r"^\s*(?:remember|note)\s+(?:that\s+)?(?P<content>.+)$",
    "kb_add",
    lambda m: {"kind": "note", "content": m.group("content").strip()},
    description="remember <content> / note <content>",
)

register_pattern(
    r"^\s*search\s+(?:my\s+)?notes?\s+(?:for\s+)?(?P<query>.+)$",
    "kb_search",
    lambda m: {"query": m.group("query").strip()},
    description="search notes for <query>",
)

register_pattern(
    r"^\s*(?:what'?s|show)\s+on\s+my\s+calendar\b",
    "calendar_list_events",
    lambda m: {},
    description="what's on my calendar",
)


__all__ = ["register_pattern", "try_match", "registered_patterns", "Tier1Pattern"]
"""
Plugin-aware tool registry.

CRITICAL LESSON FROM PRIOR BUILD: autodiscover_tools() must use
pkgutil.walk_packages (recursive), NOT pkgutil.iter_modules (which
does NOT recurse into subpackages). Tools placed in nested folders
like app/tools/google/ were silently never registered under the old
approach. Do not regress this.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core.types import PermissionLevel
from app.core.logging_setup import logger

_REGISTRY: dict[str, "RegisteredTool"] = {}


@dataclass
class RegisteredTool:
    name: str
    func: Callable[..., Any]
    permission: PermissionLevel
    description: str
    input_schema: type | None = None  # Pydantic model, wired in M2
    example_phrases: list[str] = field(default_factory=list)  # used by Tier 2 fuzzy matching later


def tool(
    name: str,
    *,
    permission: PermissionLevel,
    description: str = "",
    input_schema: type | None = None,
    example_phrases: list[str] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator that registers a function as a callable tool.
    Registration happens at import time; discovery (below) is what
    guarantees every tool module actually gets imported.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if name in _REGISTRY:
            logger.warning("Tool '{}' is being re-registered (overwriting).", name)
        _REGISTRY[name] = RegisteredTool(
            name=name,
            func=func,
            permission=permission,
            description=description,
            input_schema=input_schema,
            example_phrases=example_phrases or [],
        )
        logger.debug("Registered tool '{}' (permission={})", name, permission)
        return func

    return decorator


def autodiscover_tools(package_name: str = "app.tools") -> int:
    """
    Recursively imports every module under `package_name` so that all
    @tool-decorated functions register themselves.

    Uses pkgutil.walk_packages (recursive) rather than iter_modules
    (non-recursive) — this is the fix for a real bug from the prior
    build where tools in subfolders (e.g. app/tools/google/) were
    silently never discovered.

    Returns the number of tool modules imported.
    """
    package = importlib.import_module(package_name)
    imported_count = 0

    for module_info in pkgutil.walk_packages(
        path=package.__path__,
        prefix=package.__name__ + ".",
    ):
        importlib.import_module(module_info.name)
        imported_count += 1
        logger.debug("Discovered and imported tool module: {}", module_info.name)

    logger.info(
        "autodiscover_tools complete. modules_imported={} tools_registered={}",
        imported_count,
        len(_REGISTRY),
    )
    return imported_count


def get_tool(name: str) -> RegisteredTool | None:
    return _REGISTRY.get(name)


def list_tools() -> dict[str, RegisteredTool]:
    return dict(_REGISTRY)


__all__ = ["tool", "autodiscover_tools", "get_tool", "list_tools", "RegisteredTool"]
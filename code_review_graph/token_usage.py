"""Local token usage accounting helpers for MCP tool calls."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .graph import GraphStore
from .incremental import find_project_root, get_db_path

logger = logging.getLogger(__name__)

REVIEW_TOOL_NAMES = frozenset({
    "build_or_update_graph",
    "get_impact_radius",
    "get_review_context",
    "get_affected_flows",
    "detect_changes",
})

_SKIP_TRACKING_TOOL_NAMES = frozenset({"get_token_usage"})


def estimate_tokens(payload: Any) -> int:
    """Approximate token count using a simple chars/4 heuristic."""
    if payload is None:
        return 0
    try:
        text = json.dumps(payload, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(payload)
    return max(0, len(text) // 4)


def classify_tool(tool_name: str) -> str:
    """Classify a tool into review vs non-review category."""
    if tool_name in REVIEW_TOOL_NAMES:
        return "code_review_graph"
    return "non_code_review_graph"


def _looks_like_repo_root(path: Path) -> bool:
    return path.is_dir() and (
        (path / ".git").exists() or (path / ".code-review-graph").exists()
    )


def resolve_repo_root(
    repo_root: str | None = None,
    default_repo_root: str | None = None,
) -> Path | None:
    """Resolve a usable repository root for usage accounting."""
    candidates = [repo_root, default_repo_root]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).expanduser().resolve()
        if _looks_like_repo_root(path):
            return path

    discovered = find_project_root()
    if _looks_like_repo_root(discovered):
        return discovered.resolve()
    return None


def track_tool_usage(
    tool_name: str,
    tool_args: dict[str, Any],
    result: dict[str, Any],
    repo_root: str | None = None,
    default_repo_root: str | None = None,
) -> dict[str, Any] | None:
    """Persist usage counters for one MCP tool call."""
    if tool_name in _SKIP_TRACKING_TOOL_NAMES:
        return None

    resolved_root = resolve_repo_root(repo_root, default_repo_root)
    if not resolved_root:
        return None

    category = classify_tool(tool_name)
    input_tokens = estimate_tokens(tool_args)
    output_tokens = estimate_tokens(result)
    total_tokens = input_tokens + output_tokens

    try:
        store = GraphStore(get_db_path(resolved_root))
        try:
            store.record_token_usage(
                tool_name=tool_name,
                category=category,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        finally:
            store.close()
    except Exception:
        logger.debug("Token usage tracking failed for %s", tool_name, exc_info=True)
        return None

    return {
        "tool_name": tool_name,
        "category": category,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "repo_root": str(resolved_root),
    }


def get_token_usage_summary(
    repo_root: str | None = None,
    default_repo_root: str | None = None,
    include_tools: bool = True,
    reset: bool = False,
) -> dict[str, Any]:
    """Fetch token usage summary from local graph metadata."""
    resolved_root = resolve_repo_root(repo_root, default_repo_root)
    if not resolved_root:
        return {
            "status": "error",
            "summary": "Could not resolve a repository root for token usage.",
            "error": "No valid repo_root found",
        }

    store = GraphStore(get_db_path(resolved_root))
    try:
        usage = store.reset_token_usage() if reset else store.get_token_usage()
    finally:
        store.close()

    totals = usage.get("totals", {})
    review = totals.get("code_review_graph", {})
    non_review = totals.get("non_code_review_graph", {})
    summary = (
        "Token usage split — "
        f"code_review_graph: {review.get('total_tokens', 0)} tokens across "
        f"{review.get('calls', 0)} call(s); "
        f"non_code_review_graph: {non_review.get('total_tokens', 0)} tokens across "
        f"{non_review.get('calls', 0)} call(s)."
    )
    if reset:
        summary = "Token usage counters reset. " + summary

    result: dict[str, Any] = {
        "status": "ok",
        "summary": summary,
        "repo_root": str(resolved_root),
        "totals": totals,
        "last_updated": usage.get("last_updated"),
    }

    if include_tools:
        raw_tools = usage.get("tools", {})
        sorted_tools: list[dict[str, Any]] = []
        if isinstance(raw_tools, dict):
            for tool_name, data in raw_tools.items():
                if not isinstance(tool_name, str) or not isinstance(data, dict):
                    continue
                sorted_tools.append(
                    {
                        "tool_name": tool_name,
                        "category": data.get("category", "non_code_review_graph"),
                        "calls": int(data.get("calls", 0)),
                        "input_tokens": int(data.get("input_tokens", 0)),
                        "output_tokens": int(data.get("output_tokens", 0)),
                        "total_tokens": int(data.get("total_tokens", 0)),
                        "last_called_at": data.get("last_called_at"),
                    }
                )
        sorted_tools.sort(key=lambda item: item["total_tokens"], reverse=True)
        result["tools"] = sorted_tools

    return result


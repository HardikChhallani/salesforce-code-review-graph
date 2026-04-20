"""Tests for local token usage tracking helpers."""

import shutil
import tempfile
from pathlib import Path

from code_review_graph.token_usage import (
    classify_tool,
    estimate_tokens,
    get_token_usage_summary,
    track_tool_usage,
)


def test_classify_tool_review_vs_non_review():
    assert classify_tool("detect_changes") == "code_review_graph"
    assert classify_tool("query_graph") == "non_code_review_graph"


def test_estimate_tokens_non_negative():
    assert estimate_tokens(None) == 0
    assert estimate_tokens({"a": "b"}) >= 0


def test_track_tool_usage_and_summary_roundtrip():
    repo_root = Path(tempfile.mkdtemp())
    try:
        (repo_root / ".git").mkdir()

        tracked = track_tool_usage(
            tool_name="detect_changes",
            tool_args={"base": "HEAD~1"},
            result={"status": "ok", "changed_files": ["a.py"]},
            repo_root=str(repo_root),
        )
        assert tracked is not None
        assert tracked["category"] == "code_review_graph"

        summary = get_token_usage_summary(repo_root=str(repo_root))
        assert summary["status"] == "ok"
        assert summary["totals"]["code_review_graph"]["calls"] == 1
        assert summary["totals"]["code_review_graph"]["total_tokens"] > 0
    finally:
        shutil.rmtree(repo_root, ignore_errors=True)

"""
tests/test_tools.py

Unit tests for the five agent tools.
Tools are called directly (without running the agent) using modifier_deps fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cloudforge.agent.tools import (
    ModifierDeps,
    fetch_boto3_docs,
    get_field_validator_map,
    get_schema_definition,
    read_context_file,
    search_aws_docs,
)
from cloudforge.validation.aws_dryrun import FIELD_VALIDATORS


# ---------------------------------------------------------------------------
# Helpers — build a minimal RunContext-like object for tools that need it
# ---------------------------------------------------------------------------

class _FakeCtx:
    """Minimal stand-in for pydantic_ai.RunContext."""
    def __init__(self, deps: ModifierDeps):
        self.deps = deps


# ---------------------------------------------------------------------------
# Tool 1: get_field_validator_map
# ---------------------------------------------------------------------------

def test_get_field_validator_map_returns_all_fields():
    result = get_field_validator_map()
    assert isinstance(result, dict)
    for field in FIELD_VALIDATORS:
        assert field in result


def test_get_field_validator_map_values_are_strings():
    result = get_field_validator_map()
    for v in result.values():
        assert isinstance(v, str)


# ---------------------------------------------------------------------------
# Tool 2: get_schema_definition
# ---------------------------------------------------------------------------

def test_get_schema_definition_returns_dict():
    schema = get_schema_definition()
    assert isinstance(schema, dict)
    assert "properties" in schema


def test_get_schema_definition_includes_fields_property():
    schema = get_schema_definition()
    assert "fields" in schema["properties"]


# ---------------------------------------------------------------------------
# Tool 3: fetch_boto3_docs
# ---------------------------------------------------------------------------

def test_fetch_boto3_docs_known_method(modifier_deps, tmp_path):
    ctx = _FakeCtx(modifier_deps)
    result = fetch_boto3_docs(ctx, "s3", "get_bucket_versioning")
    assert isinstance(result, str)
    assert len(result) > 0


def test_fetch_boto3_docs_caches_result(modifier_deps):
    ctx = _FakeCtx(modifier_deps)
    result1 = fetch_boto3_docs(ctx, "s3", "get_bucket_location")
    result2 = fetch_boto3_docs(ctx, "s3", "get_bucket_location")
    assert result1 == result2
    cache_file = modifier_deps.docs_cache_dir / "s3" / "get_bucket_location.txt"
    assert cache_file.exists()


def test_fetch_boto3_docs_unknown_method(modifier_deps):
    ctx = _FakeCtx(modifier_deps)
    result = fetch_boto3_docs(ctx, "s3", "nonexistent_method_xyz")
    assert "does not exist" in result or "nonexistent_method_xyz" in result


# ---------------------------------------------------------------------------
# Tool 4: search_aws_docs
# ---------------------------------------------------------------------------

def test_search_aws_docs_finds_versioning(modifier_deps):
    ctx = _FakeCtx(modifier_deps)
    results = search_aws_docs(ctx, "s3", "versioning")
    assert isinstance(results, list)
    methods = [r["method"] for r in results]
    assert any("versioning" in m for m in methods)


def test_search_aws_docs_no_match(modifier_deps):
    ctx = _FakeCtx(modifier_deps)
    results = search_aws_docs(ctx, "s3", "zzz_no_match_zzz")
    assert isinstance(results, list)
    assert len(results) == 0


# ---------------------------------------------------------------------------
# Tool 5: read_context_file
# ---------------------------------------------------------------------------

def test_read_context_file_self_agents_md(modifier_deps):
    ctx = _FakeCtx(modifier_deps)
    result = read_context_file(ctx, "self/AGENTS.md")
    assert isinstance(result, str)
    assert len(result) > 0
    assert "CloudForge" in result


def test_read_context_file_invalid_format(modifier_deps):
    ctx = _FakeCtx(modifier_deps)
    result = read_context_file(ctx, "no-slash-here")
    assert "Invalid path format" in result


def test_read_context_file_disallowed_filename(modifier_deps):
    ctx = _FakeCtx(modifier_deps)
    result = read_context_file(ctx, "self/secrets.txt")
    assert "not allowed" in result


def test_read_context_file_unknown_alias(modifier_deps):
    ctx = _FakeCtx(modifier_deps)
    result = read_context_file(ctx, "unknown-svc/AGENTS.md")
    assert "Unknown alias" in result


def test_read_context_file_path_traversal(modifier_deps):
    ctx = _FakeCtx(modifier_deps)
    # Attempt path traversal: split produces alias="self", filename="../../../etc/AGENTS.md"
    # The filename is not in the whitelist, so it is rejected
    result = read_context_file(ctx, "self/../../../etc/AGENTS.md")
    # Any rejection message is acceptable — the important thing is the file is NOT read
    assert "not allowed" in result or "Invalid path format" in result or "Access denied" in result or "Unknown alias" in result


def test_read_context_file_missing_file(tmp_path, fake_s3):
    """Alias exists but file doesn't — should return a helpful message."""
    deps = ModifierDeps(
        s3_client=fake_s3,
        context_roots={"scanning-service": str(tmp_path)},
        docs_cache_dir=tmp_path / "cache",
    )
    ctx = _FakeCtx(deps)
    result = read_context_file(ctx, "scanning-service/AGENTS.md")
    assert "not found" in result or "does not exist" in result

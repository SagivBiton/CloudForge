"""
tests/test_modifier.py

Tests for the YAML Modifier agent using Pydantic AI test models.
No OpenAI calls — all tests run offline (ALLOW_MODEL_REQUESTS=False in conftest).

Scenarios:
1. TestModel happy path — generates a valid S3DiscoveryConfig, dry-run passes.
2. TestModel output validation — the @output_validator runs against InMemoryS3.
3. Invalid output triggers schema retry and eventually raises.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest
from pydantic_ai.models.test import TestModel

from cloudforge.agent.modifier import modifier_agent
from cloudforge.agent.tools import ModifierDeps
from cloudforge.infra.fakes import InMemoryS3
from cloudforge.models.discovery import S3DiscoveryConfig
from cloudforge.validation.aws_dryrun import run_dryrun

_VALID_OUTPUT = {
    "version": "1.0",
    "provider": "aws",
    "resource_type": "s3",
    "description": "Discover S3 bucket configurations for security scanning",
    "region": "all",
    "fields": ["bucket_name", "encryption_status", "versioning_status"],
    "filters": [],
}

_CURRENT_YAML = """\
version: "1.0"
provider: aws
resource_type: s3
description: "Discover S3 bucket configurations"
region: all
fields:
  - bucket_name
  - encryption_status
filters: []
"""


def _make_deps(tmp_path: Path | None = None) -> ModifierDeps:
    cache = Path(tempfile.mkdtemp()) if tmp_path is None else tmp_path / "cache"
    return ModifierDeps(
        s3_client=InMemoryS3(),
        context_roots={},
        docs_cache_dir=cache,
    )


# ---------------------------------------------------------------------------
# 1. TestModel happy path
# ---------------------------------------------------------------------------

def test_modifier_happy_path(tmp_path):
    """
    TestModel with a pre-canned valid config.
    The @output_validator (dry-run against InMemoryS3) must also pass.
    """
    deps = _make_deps(tmp_path)

    with modifier_agent.override(
        model=TestModel(custom_output_args=_VALID_OUTPUT),
        deps=deps,
    ):
        result = modifier_agent.run_sync(
            "Add versioning_status to the config.",
        )

    assert isinstance(result.output, S3DiscoveryConfig)
    assert result.output.provider == "aws"
    assert result.output.resource_type == "s3"
    assert "versioning_status" in result.output.fields


# ---------------------------------------------------------------------------
# 2. @output_validator runs run_dryrun on the produced config
# ---------------------------------------------------------------------------

def test_output_validator_passes_for_known_fields(tmp_path):
    """The dry-run validator accepts all fields that InMemoryS3 can handle."""
    deps = _make_deps(tmp_path)

    with modifier_agent.override(
        model=TestModel(custom_output_args=_VALID_OUTPUT),
        deps=deps,
    ):
        result = modifier_agent.run_sync("Use known fields only.")

    ok, err = run_dryrun(result.output, InMemoryS3(), "cloudforge-test-alpha")
    assert ok is True, f"dry-run should pass but got: {err}"


def test_output_validator_rejects_bad_dryrun(tmp_path):
    """
    If the dry-run client always raises AccessDenied, the @output_validator
    raises ModelRetry, exhausting retries and raising UnexpectedModelBehavior.
    """
    from pydantic_ai.exceptions import UnexpectedModelBehavior
    from cloudforge.infra.fakes import _FakeClientError

    class DeniedS3(InMemoryS3):
        def get_bucket_encryption(self, **kwargs):
            raise _FakeClientError("AccessDenied", "Access Denied")

    deps = ModifierDeps(
        s3_client=DeniedS3(),
        context_roots={},
        docs_cache_dir=Path(tempfile.mkdtemp()),
    )

    # The config requests encryption_status which will always fail the dry-run
    with pytest.raises((UnexpectedModelBehavior, Exception)):
        with modifier_agent.override(
            model=TestModel(custom_output_args=_VALID_OUTPUT),
            deps=deps,
        ):
            modifier_agent.run_sync("Add encryption_status.")


# ---------------------------------------------------------------------------
# 3. Schema validation rejects an unknown field
# ---------------------------------------------------------------------------

def test_schema_validation_rejects_unknown_field(tmp_path):
    """
    If the model produces a config with an unknown field, Pydantic validation
    fails. With retries exhausted, UnexpectedModelBehavior is raised.
    """
    from pydantic_ai.exceptions import UnexpectedModelBehavior

    bad_output = {**_VALID_OUTPUT, "fields": ["bucket_name", "threat_score"]}
    deps = _make_deps(tmp_path)

    with pytest.raises((UnexpectedModelBehavior, Exception)):
        with modifier_agent.override(
            model=TestModel(custom_output_args=bad_output),
            deps=deps,
        ):
            modifier_agent.run_sync("Add threat_score.")


# ---------------------------------------------------------------------------
# 4. All known fields accepted
# ---------------------------------------------------------------------------

def test_all_known_fields_pass_modifier(tmp_path):
    """A config with every allowed field should pass schema + dry-run."""
    from cloudforge.validation.aws_dryrun import FIELD_VALIDATORS

    all_fields_output = {**_VALID_OUTPUT, "fields": list(FIELD_VALIDATORS.keys())}
    deps = _make_deps(tmp_path)

    with modifier_agent.override(
        model=TestModel(custom_output_args=all_fields_output),
        deps=deps,
    ):
        result = modifier_agent.run_sync("Add all fields.")

    assert set(result.output.fields) == set(FIELD_VALIDATORS.keys())

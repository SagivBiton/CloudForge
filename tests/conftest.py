"""
tests/conftest.py

Shared pytest fixtures and global test configuration.
"""

from __future__ import annotations

import os

# Force fake mode for tests; settings.py supplies a placeholder OPENAI_API_KEY
# if none is set, so importing the modifier always works.
os.environ.setdefault("CLOUDFORGE_MODE", "fake")

import pytest
import pydantic_ai.models as _pai_models

# Block all real LLM requests during the test suite.
# TestModel and FunctionModel are NOT affected by this guard.
_pai_models.ALLOW_MODEL_REQUESTS = False


@pytest.fixture()
def fake_s3():
    """Return a fresh InMemoryS3 instance."""
    from cloudforge.infra.fakes import InMemoryS3
    return InMemoryS3()


@pytest.fixture()
def fake_repo():
    """Return a fresh FakeRepo (no seed issues)."""
    from cloudforge.infra.fakes import FakeRepo
    return FakeRepo()


@pytest.fixture()
def tmp_docs_cache(tmp_path):
    """A temporary directory for boto3 doc caching."""
    d = tmp_path / "docs_cache"
    d.mkdir()
    return d


@pytest.fixture()
def modifier_deps(fake_s3, tmp_docs_cache):
    """ModifierDeps with InMemoryS3 and a temporary docs cache dir."""
    from cloudforge.agent.tools import ModifierDeps
    return ModifierDeps(
        s3_client=fake_s3,
        context_roots={},
        docs_cache_dir=tmp_docs_cache,
    )

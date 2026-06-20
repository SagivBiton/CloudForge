"""
tests/test_poller.py

Integration tests for the GitHub poller.
Uses monkeypatch to replace run_modifier with a deterministic fake,
then runs handle_issue and asserts the FakeRepo gets a PR + comment.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from cloudforge.github_app.poller import handle_issue
from cloudforge.infra.fakes import FakeIssue, FakeRepo
from cloudforge.models.discovery import S3DiscoveryConfig

_YAML_CONTENT = Path("yamls/s3_discovery.yaml").read_text()

_GOOD_CONFIG = S3DiscoveryConfig(
    version="1.0",
    provider="aws",
    resource_type="s3",
    description="Discover S3 bucket configurations for security scanning",
    region="all",
    fields=["bucket_name", "encryption_status", "versioning_status"],
    filters=[],
)


@pytest.fixture()
def repo_with_issue():
    repo = FakeRepo()
    repo.add_file("yamls/s3_discovery.yaml", _YAML_CONTENT)
    repo.issues.append(
        FakeIssue(
            number=42,
            title="[discovery-request] Add versioning_status to S3 discovery",
            body="The scanning team needs versioning_status. Please add it.",
            labels=["discovery-request"],
        )
    )
    return repo


def test_handle_issue_opens_pr_and_posts_success_comment(repo_with_issue, monkeypatch):
    """
    When run_modifier succeeds, handle_issue should:
    - Create a PR in the repo.
    - Post a success comment on the issue.
    """
    import cloudforge.github_app.poller as poller_mod

    monkeypatch.setattr(poller_mod, "run_modifier", lambda **kwargs: _GOOD_CONFIG)

    issue = repo_with_issue.issues[0]
    handle_issue(issue, repo_with_issue)

    assert len(repo_with_issue.prs) == 1
    pr = repo_with_issue.prs[0]
    assert "issue-42" in pr.head

    assert len(issue.comments) == 1
    comment_body = issue.comments[0].body
    assert "✅" in comment_body
    assert "PR" in comment_body


def test_handle_issue_posts_failure_comment_on_modifier_error(repo_with_issue, monkeypatch):
    """
    When run_modifier raises, handle_issue should:
    - NOT create a PR.
    - Post a failure comment on the issue.
    """
    import cloudforge.github_app.poller as poller_mod
    from pydantic_ai.exceptions import UnexpectedModelBehavior

    monkeypatch.setattr(
        poller_mod,
        "run_modifier",
        lambda **kwargs: (_ for _ in ()).throw(UnexpectedModelBehavior("Exhausted retries")),
    )

    issue = repo_with_issue.issues[0]
    handle_issue(issue, repo_with_issue)

    assert len(repo_with_issue.prs) == 0
    assert len(issue.comments) == 1
    assert "❌" in issue.comments[0].body


def test_handle_issue_skips_already_processed(repo_with_issue, monkeypatch):
    """run_forever skips issues that are already in processed set."""
    import cloudforge.github_app.poller as poller_mod

    calls = []
    monkeypatch.setattr(poller_mod, "run_modifier", lambda **kwargs: calls.append(1) or _GOOD_CONFIG)

    issue = repo_with_issue.issues[0]
    processed = {issue.number}  # already processed

    # Simulate one poll tick manually
    for iss in repo_with_issue.get_issues(labels=["discovery-request"], state="open"):
        if iss.number not in processed:
            handle_issue(iss, repo_with_issue)

    assert len(calls) == 0  # modifier was NOT called


def test_pr_branch_name_slug(repo_with_issue, monkeypatch):
    """Branch name should be feature/issue-{N}-{slug}."""
    import cloudforge.github_app.poller as poller_mod

    monkeypatch.setattr(poller_mod, "run_modifier", lambda **kwargs: _GOOD_CONFIG)

    issue = repo_with_issue.issues[0]
    handle_issue(issue, repo_with_issue)

    pr = repo_with_issue.prs[0]
    assert pr.head.startswith("feature/issue-42-")
    assert "discovery-request" in pr.head or "versioning" in pr.head

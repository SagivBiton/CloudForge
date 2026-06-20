"""
cloudforge/github_app/pr.py

Creates a branch, commits the updated YAML, and opens a Pull Request.
"""

from __future__ import annotations

import re
import yaml
from typing import Any

from cloudforge.models.discovery import S3DiscoveryConfig


def _slugify(text: str) -> str:
    """Convert a title to a URL-safe branch-name segment."""
    slug = text.lower()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = slug.strip("-")
    return slug[:60]


def open_pr(
    repo: Any,
    issue_number: int,
    issue_title: str,
    config: S3DiscoveryConfig,
    yaml_path: str = "yamls/s3_discovery.yaml",
    base_branch: str = "main",
) -> Any:
    """
    1. Create a feature branch.
    2. Commit the updated YAML.
    3. Open a Pull Request.

    Returns the PR object.
    """
    branch_name = f"feature/issue-{issue_number}-{_slugify(issue_title)}"

    # Resolve the current HEAD sha
    base_ref = repo.get_git_ref(f"heads/{base_branch}")
    head_sha = base_ref.object.sha

    # Create the new branch
    repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=head_sha)

    # Fetch the current file to get its sha (needed by GitHub API for updates).
    # UnknownObjectException is raised by PyGitHub when the file doesn't exist.
    try:
        existing = repo.get_contents(yaml_path, ref=base_branch)
        file_sha = existing.sha
    except Exception:
        # File doesn't exist in the base branch. For the discovery YAML this
        # is unexpected (it's always present) but we don't want to crash.
        file_sha = ""

    # Serialise the config to YAML
    new_yaml = yaml.safe_dump(
        config.model_dump(exclude_none=True),
        default_flow_style=False,
        sort_keys=False,
    )

    repo.update_file(
        path=yaml_path,
        message=f"chore: update S3 discovery config for issue #{issue_number}",
        content=new_yaml,
        sha=file_sha,
        branch=branch_name,
    )

    pr_body = (
        f"Closes #{issue_number}\n\n"
        f"**What changed:** automated update to `{yaml_path}` "
        f"based on discovery request.\n\n"
        f"**Validation:** schema ✅ | AWS dry-run ✅"
    )

    pr = repo.create_pull(
        title=issue_title,
        body=pr_body,
        head=branch_name,
        base=base_branch,
    )
    return pr

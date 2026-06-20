"""
cloudforge/infra/github.py

Returns a real PyGitHub repository object.
Requires GITHUB_TOKEN and GITHUB_REPO to be set in the environment.
"""

from __future__ import annotations

from github import Github

from cloudforge import settings


def get_repo():
    """Return the configured GitHub repository object."""
    if not settings.GITHUB_TOKEN:
        raise RuntimeError(
            "GITHUB_TOKEN env var is required. "
            "Generate a Personal Access Token with 'repo' scope at "
            "https://github.com/settings/tokens"
        )
    if not settings.GITHUB_REPO:
        raise RuntimeError(
            "GITHUB_REPO env var is required (format: 'owner/repo-name')."
        )
    gh = Github(settings.GITHUB_TOKEN)
    return gh.get_repo(settings.GITHUB_REPO)

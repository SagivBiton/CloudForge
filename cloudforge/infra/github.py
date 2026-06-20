"""
cloudforge/infra/github.py

Factory for the GitHub repository object.
Returns a real PyGitHub Repo (CLOUDFORGE_MODE=real) or FakeRepo (CLOUDFORGE_MODE=fake).
"""

from __future__ import annotations

from typing import Any

from cloudforge import settings


def get_repo() -> Any:
    """Return a GitHub repo object appropriate for the current mode."""
    if settings.MODE == "real":
        if not settings.GITHUB_TOKEN:
            raise RuntimeError("GITHUB_TOKEN is required when CLOUDFORGE_MODE=real")
        if not settings.GITHUB_REPO:
            raise RuntimeError("GITHUB_REPO is required when CLOUDFORGE_MODE=real")
        from github import Github
        gh = Github(settings.GITHUB_TOKEN)
        return gh.get_repo(settings.GITHUB_REPO)

    from cloudforge.infra.fakes import FakeRepo
    return FakeRepo()

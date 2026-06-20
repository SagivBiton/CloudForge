"""
cloudforge/github_app/commenter.py

Posts status comments back to the GitHub Issue.
"""

from __future__ import annotations

from typing import Any


def post_success(issue: Any, pr_number: int, pr_url: str, changed_fields: list[str]) -> None:
    """Post a success comment linking to the opened PR."""
    fields_str = ", ".join(f"`{f}`" for f in changed_fields) if changed_fields else "no field changes"
    body = (
        f"✅ PR #{pr_number} has been opened automatically.\n\n"
        f"Changes: {fields_str}\n"
        f"Validation: schema ✅ | AWS dry-run ✅\n\n"
        f"→ {pr_url}"
    )
    issue.create_comment(body)


def post_failure(issue: Any, errors: list[str]) -> None:
    """Post a failure comment explaining why all retries were exhausted."""
    error_lines = "\n".join(f"- {e}" for e in errors)
    body = (
        "❌ CloudForge was unable to process this request after multiple attempts.\n\n"
        f"**Errors:**\n{error_lines}\n\n"
        "Please review the request and update the issue, or handle manually."
    )
    issue.create_comment(body)

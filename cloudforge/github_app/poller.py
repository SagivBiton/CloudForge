"""
cloudforge/github_app/poller.py

Main polling loop: checks GitHub Issues every POLL_INTERVAL_SEC seconds,
dispatches new ones to the modifier agent, then creates a PR or posts a
failure comment.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from cloudforge import settings
from cloudforge.agent.modifier import run_modifier
from cloudforge.github_app import commenter, pr as pr_module
from cloudforge.infra.github import get_repo

_STATE_PATH = Path("state/processed_issues.json")
_YAML_PATH = "yamls/"
_LABEL = "discovery-request"


def _load_processed() -> set[int]:
    if _STATE_PATH.exists():
        data = json.loads(_STATE_PATH.read_text())
        return set(data)
    return set()


def _save_processed(processed: set[int]) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(sorted(processed)))


def _ts() -> str:
    return datetime.now().strftime("[%H:%M:%S]")


def _load_yaml_from_repo(repo: Any, yaml_name: str) -> str:
    """Load the current YAML config from the GitHub repository.

    PyGitHub's ContentFile.decoded_content is a bytes property (base64-decoded).
    Falls back to local disk only when the file is genuinely missing on the repo.
    """
    try:
        contents = repo.get_contents(f"{_YAML_PATH}{yaml_name}")
        raw = contents.decoded_content  # property → bytes
        return raw.decode() if isinstance(raw, (bytes, bytearray)) else str(raw)
    except Exception:
        # If the file cannot be fetched from the repo, fall back to the local copy.
        # This handles first-run scenarios and CLI usage.
        local = Path(f"{_YAML_PATH}{yaml_name}")
        if local.exists():
            return local.read_text()
        raise RuntimeError(
            f"Could not load {_YAML_PATH}{yaml_name} from GitHub or from local disk. "
            "Ensure the file exists in the repository."
        )


def handle_issue(issue: Any, repo: Any) -> None:
    """Process a single GitHub Issue end-to-end."""
    print(f"{_ts()} New issue detected: #{issue.number} — {issue.title!r}")

    update_yaml = re.findall(r'\b[\w.-]+\.(?:yaml|yml)\b', issue.title)

    if update_yaml:
        yaml_name = update_yaml[0]
        current_yaml = _load_yaml_from_repo(repo, yaml_name)
    else:
        raise("Couldn't get YAML file specification")

    print(f"{_ts()} Current YAML loaded")

    print(f"{_ts()} Starting Pydantic AI modifier...")
    try:
        config = run_modifier(
            issue_title=issue.title,
            issue_body=issue.body or "",
            current_yaml=current_yaml,
        )
    except Exception as exc:
        print(f"{_ts()} ❌ Modifier failed: {exc}")
        commenter.post_failure(issue, [str(exc)])
        return

    print(f"{_ts()} Validation passed ✅")

    try:
        opened_pr = pr_module.open_pr(
            repo=repo,
            issue_number=issue.number,
            issue_title=issue.title,
            config=config,
            yaml_path=f"{_YAML_PATH}{yaml_name}",
        )
    except Exception as exc:
        print(f"{_ts()} ❌ PR creation failed: {exc}")
        commenter.post_failure(issue, [f"PR creation failed: {exc}"])
        return

    print(f"{_ts()} PR #{opened_pr.number} opened")

    commenter.post_success(
        issue=issue,
        pr_number=opened_pr.number,
        pr_url=opened_pr.html_url,
        changed_fields=config.fields,
    )
    print(f"✅ Done — {opened_pr.html_url}")


def run_forever(poll_interval: int | None = None) -> None:
    """Poll GitHub Issues indefinitely."""
    interval = poll_interval if poll_interval is not None else settings.POLL_INTERVAL_SEC
    repo = get_repo()

    processed = _load_processed()
    print(
        f"CloudForge running. "
        f"Polling every {interval}s for issues labeled '{_LABEL}'"
    )

    while True:
        try:
            issues = repo.get_issues(labels=[_LABEL], state="open")
            for issue in issues:
                if issue.number in processed:
                    continue
                handle_issue(issue, repo)
                processed.add(issue.number)
                _save_processed(processed)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as exc:
            print(f"{_ts()} Polling error: {exc}")

        time.sleep(interval)

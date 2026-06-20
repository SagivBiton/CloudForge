"""
cloudforge/settings.py

All configuration comes from environment variables (loaded from .env if present).
Copy .env.example to .env and fill in all values before running.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "openai-chat:gpt-4o-mini")
AGENT_RETRIES: int = int(os.environ.get("AGENT_RETRIES", "3"))
TOOL_TIMEOUT_SEC: int = int(os.environ.get("TOOL_TIMEOUT_SEC", "5"))
BOTO3_DOCS_CACHE_DIR: Path = Path(os.environ.get("BOTO3_DOCS_CACHE_DIR", ".boto3_docs_cache"))
CONTEXT_ROOTS_FILE: str | None = os.environ.get("CONTEXT_ROOTS_FILE") or None
POLL_INTERVAL_SEC: int = int(os.environ.get("POLL_INTERVAL_SEC", "30"))

GITHUB_TOKEN: str | None = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO: str | None = os.environ.get("GITHUB_REPO")
AWS_DEFAULT_REGION: str = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
AWS_DRYRUN_BUCKET: str = os.environ.get("AWS_DRYRUN_BUCKET", "cloudforge-test-alpha")

"""
cloudforge/agent/modifier.py

The YAML Modifier agent — built on Pydantic AI.

Key design choices:
- output_type=S3DiscoveryConfig  → every model response is Pydantic-validated.
  If validation fails, Pydantic AI appends the error and asks the model to retry.
- @output_validator → runs the AWS dry-run after schema validation.
  Raising ModelRetry causes the agent to re-prompt itself with the dry-run error.
- Both retry paths are bounded by Agent(retries=AGENT_RETRIES) — default 3.
- ModifierDeps injects the S3 client (real or fake) and context roots via RunContext.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic_ai import Agent, ModelRetry, RunContext

from cloudforge import settings
from cloudforge.agent.prompts import SYSTEM_PROMPT, build_user_message
from cloudforge.agent.tools import ModifierDeps, register_tools
from cloudforge.infra.aws import get_s3_client
from cloudforge.models.discovery import S3DiscoveryConfig
from cloudforge.validation.aws_dryrun import run_dryrun

# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

modifier_agent: Agent[ModifierDeps, S3DiscoveryConfig] = Agent(
    model=settings.OPENAI_MODEL,
    deps_type=ModifierDeps,
    output_type=S3DiscoveryConfig,
    system_prompt=SYSTEM_PROMPT,
    retries=settings.AGENT_RETRIES,
)
register_tools(modifier_agent)


@modifier_agent.output_validator
def _aws_dryrun_validator(
    ctx: RunContext[ModifierDeps],
    output: S3DiscoveryConfig,
) -> S3DiscoveryConfig:
    """
    After Pydantic schema validation, confirm each field maps to a real boto3 call.
    If not, raise ModelRetry so the agent can self-correct.
    """
    ok, err = run_dryrun(output, ctx.deps.s3_client, settings.AWS_DRYRUN_BUCKET)
    if not ok:
        raise ModelRetry(
            f"AWS dry-run failed: {err}. "
            "Use get_field_validator_map() to see which fields are valid, "
            "or omit the problematic field."
        )
    return output


# ---------------------------------------------------------------------------
# Context-roots loader
# ---------------------------------------------------------------------------

def _load_context_roots() -> dict[str, str]:
    """Load alias → path map from CONTEXT_ROOTS_FILE, or fall back to defaults."""
    if settings.CONTEXT_ROOTS_FILE:
        p = Path(settings.CONTEXT_ROOTS_FILE)
        if p.exists():
            return json.loads(p.read_text())

    repo_root = Path(__file__).parent.parent.parent
    return {
        "scanning-service":    str(repo_root.parent / "scanning-service"),
        "remediation-service": str(repo_root.parent / "remediation-service"),
        "infra-utils":         str(repo_root.parent / "infra-utils"),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_modifier(
    issue_title: str,
    issue_body: str,
    current_yaml: str,
) -> S3DiscoveryConfig:
    """
    Run the modifier agent and return a validated S3DiscoveryConfig.

    Both schema validation and the AWS dry-run are handled inside the agent:
    - Schema failure  → Pydantic AI auto-retries with the validation error.
    - Dry-run failure → @output_validator raises ModelRetry with the boto3 error.

    Raises:
        pydantic_ai.exceptions.UnexpectedModelBehavior — when all retries are
        exhausted (equivalent to the original ValidationFailed exception).
    """
    deps = ModifierDeps(
        s3_client=get_s3_client(),
        context_roots=_load_context_roots(),
        docs_cache_dir=settings.BOTO3_DOCS_CACHE_DIR,
    )
    result = modifier_agent.run_sync(
        build_user_message(issue_title, issue_body, current_yaml),
        deps=deps,
    )
    return result.output

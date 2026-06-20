"""
cloudforge/agent/tools.py

The five read-only tools available to the YAML Modifier agent.

All tools:
- Are deterministic and read-only.
- Enforce a wall-clock timeout (cross-platform via concurrent.futures).
- Return plain Python values; Pydantic AI serialises them for the model.
- Raise RuntimeError (or return an error string) on failure — Pydantic AI
  feeds errors back as model hints without crashing the run.

Tool registration happens via register_tools(agent) at the bottom.
"""

from __future__ import annotations

import inspect
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext

from cloudforge import settings
from cloudforge.models.discovery import S3DiscoveryConfig
from cloudforge.validation.aws_dryrun import FIELD_VALIDATORS


# ---------------------------------------------------------------------------
# Dependency type injected into every tool that needs context
# ---------------------------------------------------------------------------

@dataclass
class ModifierDeps:
    s3_client: Any                      # boto3 S3 client (from get_s3_client())
    context_roots: dict[str, str]       # alias → absolute directory path
    docs_cache_dir: Path                # on-disk cache for boto3 docstrings


# ---------------------------------------------------------------------------
# Allowed context filenames (whitelist — prevents arbitrary filesystem reads)
# ---------------------------------------------------------------------------

_ALLOWED_CONTEXT_FILENAMES = frozenset({
    "AGENTS.md", "architecture.md", "README.md", "schema.md"
})

# Known S3 read methods shown when a method is not found (avoids error strings
# buried inside docstrings — kept as a constant, not embedded in error text)
_S3_READ_METHODS = [
    "list_buckets", "get_bucket_location", "get_bucket_encryption",
    "get_bucket_versioning", "get_bucket_tagging", "get_bucket_acl",
    "get_bucket_logging", "get_bucket_lifecycle_configuration",
    "get_bucket_replication", "get_public_access_block",
    "get_object_lock_configuration",
]


# ---------------------------------------------------------------------------
# Timeout helper
# ---------------------------------------------------------------------------

def _run_with_timeout(fn: Any, *args: Any, timeout: int = settings.TOOL_TIMEOUT_SEC) -> Any:
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(fn, *args)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError:
            raise RuntimeError(
                f"Tool timed out after {timeout}s"
            )


# ---------------------------------------------------------------------------
# Tool 1: get_field_validator_map  (no RunContext needed)
# ---------------------------------------------------------------------------

def get_field_validator_map() -> dict[str, str]:
    """
    Return the current YAML-field → boto3-method mapping.
    Call this FIRST to see which fields already have a proven boto3 mapping
    before writing them into the YAML.
    """
    readable: dict[str, str] = {}
    for field_name, validator in FIELD_VALIDATORS.items():
        try:
            src = inspect.getsource(validator).strip()
        except Exception:
            src = repr(validator)
        readable[field_name] = src
    return readable


# ---------------------------------------------------------------------------
# Tool 2: get_schema_definition  (no RunContext needed)
# ---------------------------------------------------------------------------

def get_schema_definition() -> dict[str, Any]:
    """
    Return the JSON schema for S3DiscoveryConfig.
    Use this when you need to re-check constraints after a validation error.
    """
    return S3DiscoveryConfig.model_json_schema()


# ---------------------------------------------------------------------------
# Tool 3: fetch_boto3_docs  (needs RunContext for cache dir + s3 client)
# ---------------------------------------------------------------------------

def fetch_boto3_docs(ctx: RunContext[ModifierDeps], service: str, method: str) -> str:
    """
    Fetch the boto3 SDK documentation for a specific AWS service method.
    Use this to verify that a field you plan to add actually maps to a real
    boto3 method and to understand its response shape.
    Results are cached on disk for speed.
    """
    service = service.lower().strip()
    method = method.lower().strip()

    cache_path = ctx.deps.docs_cache_dir / service / f"{method}.txt"
    if cache_path.exists():
        return cache_path.read_text()

    def _fetch() -> str:
        s3 = ctx.deps.s3_client
        method_fn = getattr(s3, method, None)
        if method_fn is None:
            return (
                f"Method '{method}' does not exist on {service} client. "
                f"Known S3 read methods: {', '.join(_S3_READ_METHODS)}"
            )
        doc = (getattr(method_fn, "__doc__", None) or "").strip()
        if not doc:
            doc = f"No docstring available for {service}.{method}."
        return doc[:4000]

    try:
        doc = _run_with_timeout(_fetch)
    except RuntimeError as exc:
        return str(exc)

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(doc)
    return doc


# ---------------------------------------------------------------------------
# Tool 4: search_aws_docs  (needs RunContext for s3 client)
# ---------------------------------------------------------------------------

def search_aws_docs(
    ctx: RunContext[ModifierDeps],
    service: str,
    query: str,
) -> list[dict[str, str]]:
    """
    Search boto3 client methods by keyword.
    Use when the request names a concept (e.g. 'object lock', 'intelligent tiering')
    rather than an exact method name.
    """
    service = service.lower().strip()
    query = query.lower().strip()

    def _search() -> list[dict[str, str]]:
        s3 = ctx.deps.s3_client
        matches = []
        for name in dir(s3):
            if name.startswith("_"):
                continue
            if query in name.lower():
                fn = getattr(s3, name, None)
                doc_snippet = ""
                if fn and getattr(fn, "__doc__", None):
                    doc_snippet = fn.__doc__.strip().splitlines()[0][:120]
                matches.append({"method": name, "description": doc_snippet})
        return matches[:20]

    try:
        return _run_with_timeout(_search)
    except RuntimeError as exc:
        return [{"method": "error", "description": str(exc)}]


# ---------------------------------------------------------------------------
# Tool 5: read_context_file  (needs RunContext for context_roots)
# ---------------------------------------------------------------------------

def read_context_file(ctx: RunContext[ModifierDeps], path: str) -> str:
    """
    Read AGENTS.md, architecture.md, README.md, or schema.md from a
    whitelisted context root.
    Format: '<alias>/<filename>' — e.g. 'scanning-service/AGENTS.md', 'self/AGENTS.md'.
    """
    path = path.strip().lstrip("/")
    parts = path.split("/", 1)

    available_aliases = list(ctx.deps.context_roots.keys()) + ["self"]

    if len(parts) != 2:
        return (
            f"Invalid path format. Use '<alias>/<filename>'. "
            f"Available aliases: {available_aliases}. "
            f"Allowed filenames: {sorted(_ALLOWED_CONTEXT_FILENAMES)}"
        )

    alias, filename = parts

    if filename not in _ALLOWED_CONTEXT_FILENAMES:
        return (
            f"File '{filename}' is not allowed. "
            f"Allowed filenames: {sorted(_ALLOWED_CONTEXT_FILENAMES)}"
        )

    if alias == "self":
        root = Path(__file__).parent.parent.parent
    elif alias in ctx.deps.context_roots:
        root = Path(ctx.deps.context_roots[alias])
    else:
        return (
            f"Unknown alias '{alias}'. "
            f"Available aliases: {available_aliases}"
        )

    # Prevent path traversal
    target = (root / filename).resolve()
    root_resolved = root.resolve()
    if not str(target).startswith(str(root_resolved)):
        return "Access denied: path traversal detected."

    if not target.exists():
        return (
            f"File not found: '{filename}' does not exist under alias '{alias}'. "
            f"Ensure the path is correct."
        )

    content = target.read_text(encoding="utf-8")
    return content[:6000]  # cap at 6k chars


# ---------------------------------------------------------------------------
# Register all tools on the agent
# ---------------------------------------------------------------------------

def register_tools(agent: Agent[ModifierDeps, S3DiscoveryConfig]) -> None:
    """Attach all five tools to the modifier agent."""
    agent.tool_plain(get_field_validator_map)
    agent.tool_plain(get_schema_definition)
    agent.tool(fetch_boto3_docs)
    agent.tool(search_aws_docs)
    agent.tool(read_context_file)

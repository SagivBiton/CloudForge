# CloudForge — AGENTS.md

Authoritative contract for every AI agent and automated loop in this repository.
Read this file before touching `cloudforge/agent/` or `cloudforge/validation/`.

---

## Agent Overview

| Agent | Module | Role |
|---|---|---|
| **YAML Modifier** | `cloudforge/agent/modifier.py` | Pydantic AI agent — reasons with tools, produces validated `S3DiscoveryConfig` |
| **AWS Dry-Runner** | `cloudforge/validation/aws_dryrun.py` | Deterministic boto3 check — wired as `@output_validator` on the modifier agent |
| **Poller** | `cloudforge/github_app/poller.py` | Autonomous loop — polls GitHub Issues, hands work to the modifier |
| **PR Creator** | `cloudforge/github_app/pr.py` | Deterministic — commits YAML, opens PR |

---

## YAML Modifier Agent

Built on **Pydantic AI** (`pydantic-ai-slim[openai]>=1.100.0`).

```python
from pydantic_ai import Agent, RunContext, ModelRetry
from cloudforge.models.discovery import S3DiscoveryConfig

modifier_agent = Agent(
    model=settings.OPENAI_MODEL,
    deps_type=ModifierDeps,
    output_type=S3DiscoveryConfig,   # auto-validated; auto-retry on failure
    system_prompt=SYSTEM_PROMPT,
    retries=settings.AGENT_RETRIES,
)
```

### Why Pydantic AI

- `output_type=S3DiscoveryConfig` validates every model response at runtime.
  If validation fails, the framework appends the Pydantic error and retries automatically.
- `@modifier_agent.output_validator` wires the AWS dry-run as a post-schema check.
  Raising `ModelRetry(...)` causes the agent to re-prompt itself with the dry-run error.
- Both retry budgets are bounded by `retries=AGENT_RETRIES` (default 3).
- `@agent.tool` / `@agent.tool_plain` decorators auto-generate tool schemas from type hints.
- `TestModel` / `FunctionModel` give offline unit tests — no OpenAI calls.

### Available Tools (defined in `cloudforge/agent/tools.py`)

#### `get_field_validator_map` (tool_plain — no RunContext needed)
Returns `{ field_name: boto3_lambda_source }` from `FIELD_VALIDATORS`.
**Use first in almost every run** — check which fields already have a proven boto3 mapping.

#### `get_schema_definition` (tool_plain)
Returns `S3DiscoveryConfig.model_json_schema()`.
Use after a validation error to re-read the allowed fields and constraints.

#### `fetch_boto3_docs` (tool — uses RunContext for cache dir + s3 client)
Fetches the boto3 docstring for `<service>.<method>`.
Caches to disk under `BOTO3_DOCS_CACHE_DIR`.

#### `search_aws_docs` (tool — uses RunContext for s3 client)
Searches boto3 client method names by keyword.
Use when the request names a concept ("object lock") rather than an exact method name.

#### `read_context_file` (tool — uses RunContext for context_roots)
Reads `AGENTS.md`, `architecture.md`, `README.md`, or `schema.md` from a whitelisted alias.
Format: `"<alias>/<filename>"` — e.g. `"scanning-service/AGENTS.md"`, `"self/AGENTS.md"`.
Available aliases: `self` plus any roots defined in `CONTEXT_ROOTS_FILE`.

### Tool safety rules

1. **Read-only.** No tool modifies AWS resources, GitHub state, or local files.
2. **No secrets in responses.** Tools strip credentials from returned strings.
3. **Timeouts.** Each tool enforces a wall-clock timeout (`TOOL_TIMEOUT_SEC`, default 5s)
   using `concurrent.futures` — cross-platform, no POSIX signals.
4. **Deterministic dispatch.** Tools are Python functions, not LLM calls.

---

## Validation Pipeline

```
Modifier (Pydantic AI)
    → output_type=S3DiscoveryConfig   (Pydantic, auto-retry)
    → @output_validator: run_dryrun() (boto3, ModelRetry on failure)
    → max retries = AGENT_RETRIES (default 3)
    → on exhaustion: raises UnexpectedModelBehavior
         → poller posts failure comment to GitHub Issue
```

---

## Extending the Agent

### Adding a discoverable field (e.g. `intelligent_tiering_config`)

1. Add to `S3DiscoveryConfig.fields_must_be_known` allowed set in `cloudforge/models/discovery.py`
2. Add the boto3 mapping to `FIELD_VALIDATORS` in `cloudforge/validation/aws_dryrun.py`
3. The agent discovers the new entry via `get_field_validator_map` — no prompt changes needed.

### Adding a new tool

1. Implement in `cloudforge/agent/tools.py` — use `@agent.tool_plain` (no RunContext)
   or `@agent.tool` (with RunContext for deps access).
2. Register in `register_tools(agent)`.
3. Document here under "Available Tools".

### Adding a new context-root alias

1. Add the root path to `CONTEXT_FILE_ROOTS` default dict or point `CONTEXT_ROOTS_FILE`
   at a JSON map of `{ alias: abs_path }`.
2. Ensure the path contains the target file.
3. Brief the alias here.

### Changing the model

Set `OPENAI_MODEL` in `.env`. Value is any pydantic-ai model spec string:
`openai:gpt-4o-mini`, `anthropic:claude-sonnet-4-6`, `google-gla:gemini-2.0-flash`, etc.

---

## Cross-Service Context Roots

| Alias | Default path | What to read |
|---|---|---|
| `self` | repo root | `AGENTS.md` — this file |
| `scanning-service` | `../scanning-service/` | `AGENTS.md` — field requirements |
| `remediation-service` | `../remediation-service/` | `architecture.md` — remediation actions |
| `infra-utils` | `../infra-utils/` | `AGENTS.md` — utility wrappers |

Override at runtime: `CONTEXT_ROOTS_FILE=/path/to/roots.json`
where the file is `{ "alias": "/absolute/path" }`.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `CLOUDFORGE_MODE` | `fake` | `fake` wires in-memory fakes; `real` uses live AWS + GitHub |
| `OPENAI_MODEL` | `openai:gpt-4o-mini` | Any pydantic-ai model spec |
| `OPENAI_API_KEY` | _(unset)_ | Required for real model calls |
| `AGENT_RETRIES` | `3` | Max output retries (schema + dry-run combined) |
| `TOOL_TIMEOUT_SEC` | `5` | Per-tool wall-clock timeout |
| `BOTO3_DOCS_CACHE_DIR` | `.boto3_docs_cache/` | On-disk cache for boto3 docstrings |
| `CONTEXT_ROOTS_FILE` | _(unset)_ | JSON file mapping alias → abs path |
| `POLL_INTERVAL_SEC` | `30` | GitHub Issues polling interval |
| `GITHUB_TOKEN` | _(unset)_ | Required when `MODE=real` |
| `GITHUB_REPO` | _(unset)_ | `owner/name` — required when `MODE=real` |
| `AWS_DEFAULT_REGION` | `us-east-1` | Region for boto3 client |
| `AWS_DRYRUN_BUCKET` | `cloudforge-test-alpha` | Bucket used by the dry-run validator |

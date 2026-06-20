# CloudForge

Automates the full lifecycle of a cloud discovery configuration change:
GitHub Issue → AI-driven YAML modification → validation → Pull Request.

Built on [Pydantic AI](https://pydantic.dev/docs/ai/) for the agent layer and
[PyGitHub](https://pygithub.readthedocs.io/) for GitHub integration.

---

## How it works

1. The poller watches GitHub Issues labeled `discovery-request` every 30 s.
2. When a new issue appears, the **YAML Modifier** agent reads the issue and
   the current `yamls/s3_discovery.yaml`.
3. The agent reasons with tools (boto3 docs, field validator map, schema
   definition, sibling-service context files) before writing the updated YAML.
4. Pydantic AI automatically validates the output against `S3DiscoveryConfig`.
   If that fails the agent retries with the validation error as a hint.
5. An `@output_validator` runs the AWS dry-run (real boto3 read calls against
   your test bucket). If that fails, `ModelRetry` triggers another agent pass.
6. On success: a branch is created, the YAML committed, a PR opened, and a
   success comment posted on the original issue.
7. On exhaustion (≥ 3 failures): a failure comment is posted explaining why.

---

## Quick start (fake mode — no AWS or GitHub needed)

```bash
git clone https://github.com/your-username/cloudforge
cd cloudforge
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env .env
# CLOUDFORGE_MODE=fake is the default — no credentials needed

# Run the modifier on a local issue file
python -m cloudforge.cli modify \
  --issue examples/issue_add_versioning.md \
  --yaml yamls/s3_discovery.yaml
```

---

## Real mode (live AWS + GitHub)

Fill in the real-mode section of `.env`:

```bash
CLOUDFORGE_MODE=real
OPENAI_API_KEY=sk-...
GITHUB_TOKEN=ghp_...
GITHUB_REPO=your-username/cloudforge
AWS_DEFAULT_REGION=us-east-1
AWS_DRYRUN_BUCKET=cloudforge-test-alpha
# AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY via standard env vars
```

Create the label in your GitHub repo: `discovery-request` (colour: orange).

Start the poller:

```bash
python -m cloudforge.cli run
# > CloudForge running. Polling every 30s for issues labeled "discovery-request"
```

Open a GitHub Issue:

```
Title: [discovery-request] Add versioning_status to S3 discovery

Body:
The scanning team requires versioning information to identify buckets
where versioning is disabled.

Please add versioning_status to the S3 discovery YAML.
```

Apply the `discovery-request` label. Within 30 s the terminal will print:

```
[10:31:32] New issue detected: #12 — "Add versioning_status to S3 discovery"
[10:31:33] Starting Pydantic AI modifier...
  Tool: get_field_validator_map()  ✅
  Tool: fetch_boto3_docs(s3, get_bucket_versioning)  ✅
  Output validated by S3DiscoveryConfig  ✅
  AWS dry-run on cloudforge-test-alpha  ✅
[10:31:36] PR #8 opened
✅ Done — https://github.com/your-username/cloudforge/pull/8
```

---

## AWS setup

Create three S3 buckets in your free-tier AWS account:

| Bucket | Config | Purpose |
|---|---|---|
| `cloudforge-test-alpha` | default (encrypted, private) | dry-run target |
| `cloudforge-test-beta` | no encryption | demo finding |
| `cloudforge-test-gamma` | public access enabled | demo finding |

IAM policy needed (read-only):

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "s3:ListAllMyBuckets", "s3:GetBucketLocation",
      "s3:GetBucketEncryption", "s3:GetBucketVersioning",
      "s3:GetBucketTagging", "s3:GetBucketAcl",
      "s3:GetBucketLogging", "s3:GetBucketLifecycleConfiguration",
      "s3:GetBucketReplication", "s3:GetPublicAccessBlock",
      "s3:GetObjectLockConfiguration"
    ],
    "Resource": "*"
  }]
}
```

---

## Running tests

```bash
pytest
```

All tests run with no network calls and no credentials.

---

## Project structure

```
cloudforge/
├── cloudforge/
│   ├── agent/          ← Pydantic AI modifier + 5 tools + prompts
│   ├── github_app/     ← poller, PR creator, commenter
│   ├── infra/          ← boto3/PyGitHub factories + in-memory fakes
│   ├── models/         ← S3DiscoveryConfig (Pydantic v2)
│   ├── validation/     ← FIELD_VALIDATORS + AWS dry-run
│   ├── settings.py
│   ├── main.py
│   └── cli.py
├── yamls/
│   └── s3_discovery.yaml
├── tests/
├── examples/           ← sample issue files for `cloudforge modify`
├── AGENTS.md           ← AI agent contract (read before touching agent/)
└── .env.example
```

See [AGENTS.md](AGENTS.md) for the full agent contract.

---

## For developers taking over

**Three entry points, ordered by what you'll touch most:**

1. **`cloudforge/agent/modifier.py`** — the agent. ~50 LOC.
   The Pydantic AI `Agent` definition with `output_type=S3DiscoveryConfig`,
   `@output_validator` for the AWS dry-run, and `run_modifier()` as the public
   entrypoint. Read this first.

2. **`cloudforge/agent/tools.py`** — the 5 tools the agent can call.
   Each tool is a plain Python function decorated via `register_tools()`. Type
   hints + docstrings → JSON schema sent to the LLM. To add a tool: write the
   function, append `agent.tool(my_fn)` to `register_tools()`, document it in
   `AGENTS.md`.

3. **`cloudforge/validation/aws_dryrun.py`** — `FIELD_VALIDATORS` dict mapping
   each allowed YAML field → boto3 lambda. To support a new field: add a line
   here, add the field name to `S3DiscoveryConfig.fields_must_be_known`, done.

**Test discipline:**

- `pytest` runs offline in <1s. No network, no credentials.
- `CLOUDFORGE_MODE=fake` (the default) wires `InMemoryS3` and `FakeRepo`.
- `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` in `tests/conftest.py`
  blocks any accidental real LLM call.
- Agent tests use `TestModel` from `pydantic_ai.models.test` — no OpenAI mocking.

**Flipping to real services:**

Just set `CLOUDFORGE_MODE=real` plus the required creds in `.env`. The factory
pattern in `cloudforge/infra/aws.py` and `cloudforge/infra/github.py` swaps the
fake for the real client. No code changes needed elsewhere.

"""
cloudforge/validation/aws_dryrun.py

AWS dry-run validator: maps each YAML field name to the boto3 call that proves
it is real and accessible, then executes those calls against the configured
test bucket.

Used as a Pydantic AI @output_validator — raises ModelRetry on failure so the
agent can self-correct.
"""

from __future__ import annotations

from typing import Any

from cloudforge.models.discovery import S3DiscoveryConfig
from external_infra_microservice.public_utils import FIELD_VALIDATORS

# ---------------------------------------------------------------------------
# "Empty config" error codes — these mean the field is real but not configured.
# The dry-run treats these as ✅.
# ---------------------------------------------------------------------------

_EMPTY_CONFIG_CODES: frozenset[str] = frozenset({
    "NoSuchLifecycleConfiguration",
    "NoSuchBucketPolicy",
    "ServerSideEncryptionConfigurationNotFoundError",
    "NoSuchTagSet",
    "ObjectLockConfigurationNotFoundError",
    "ReplicationConfigurationNotFoundError",
})


def run_dryrun(
    cfg: S3DiscoveryConfig,
    s3: Any,
    bucket: str,
) -> tuple[bool, str | None]:
    """
    For each field in `cfg.fields`, call the corresponding boto3 method.

    Returns:
        (True, None)        — all fields confirmed real and accessible
        (False, error_msg)  — first field that failed, with the error code
    """
    for field_name in cfg.fields:
        validator = FIELD_VALIDATORS.get(field_name)
        if validator is None:
            return False, f"No boto3 mapping for field '{field_name}'"

        try:
            validator(s3, bucket)
        except Exception as exc:
            error_code = _extract_error_code(exc)
            if error_code and error_code in _EMPTY_CONFIG_CODES:
                continue  # ✅ field is real, just not configured on this bucket
            return False, f"'{field_name}': {error_code or str(exc)}"

    return True, None


def _extract_error_code(exc: Exception) -> str | None:
    """Extract the AWS error code from a botocore ClientError (or our fake)."""
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        return response.get("Error", {}).get("Code")
    return None

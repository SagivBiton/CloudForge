"""
cloudforge/validation/aws_dryrun.py

AWS dry-run validator: maps each YAML field name to the boto3 call that proves
it is real and accessible, then executes those calls against the configured
test bucket.

Used as a Pydantic AI @output_validator — raises ModelRetry on failure so the
agent can self-correct.
"""

from __future__ import annotations

from typing import Any, Callable

from cloudforge.models.discovery import S3DiscoveryConfig

# ---------------------------------------------------------------------------
# Field → boto3 mapping
# ---------------------------------------------------------------------------

FIELD_VALIDATORS: dict[str, Callable[[Any, str], Any]] = {
    "bucket_name":           lambda s3, b: b,                                           # always present from list_buckets
    "region":                lambda s3, b: s3.get_bucket_location(Bucket=b),
    "creation_date":         lambda s3, b: b,                                           # comes from list_buckets response
    "encryption_status":     lambda s3, b: s3.get_bucket_encryption(Bucket=b),
    "public_access_blocked": lambda s3, b: s3.get_public_access_block(Bucket=b),
    "versioning_status":     lambda s3, b: s3.get_bucket_versioning(Bucket=b),
    "tags":                  lambda s3, b: s3.get_bucket_tagging(Bucket=b),
    "acl":                   lambda s3, b: s3.get_bucket_acl(Bucket=b),
    "lifecycle_rules":       lambda s3, b: s3.get_bucket_lifecycle_configuration(Bucket=b),
    "logging_enabled":       lambda s3, b: s3.get_bucket_logging(Bucket=b),
    "object_lock_enabled":   lambda s3, b: s3.get_object_lock_configuration(Bucket=b),
    "replication_config":    lambda s3, b: s3.get_bucket_replication(Bucket=b),
}

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
            # Check for botocore ClientError (real or fake)
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

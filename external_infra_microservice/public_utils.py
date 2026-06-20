from __future__ import annotations

from typing import Callable, Any

# ---------------------------------------------------------------------------
# Field → boto3 mapping
# ---------------------------------------------------------------------------

FIELD_VALIDATORS: dict[str, Callable[[Any, str], Any]] = {
    "bucket_name":           lambda s3, b: b,
    "region":                lambda s3, b: s3.get_bucket_location(Bucket=b),
    "creation_date":         lambda s3, b: b,
    "encryption_status":     lambda s3, b: s3.get_bucket_encryption(Bucket=b),
    "public_access_blocked": lambda s3, b: s3.get_public_access_block(Bucket=b),
    "versioning_status":     lambda s3, b: s3.get_bucket_versioning(Bucket=b),
    "tags":                  lambda s3, b: s3.get_bucket_tagging(Bucket=b),
    "acl":                   lambda s3, b: s3.get_bucket_acl(Bucket=b),
    "lifecycle_rules":       lambda s3, b: s3.get_bucket_lifecycle_configuration(Bucket=b),
    "logging_enabled":       lambda s3, b: s3.get_bucket_logging(Bucket=b),
    "object_lock_enabled":   lambda s3, b: s3.get_object_lock_configuration(Bucket=b),
    "replication_config":    lambda s3, b: s3.get_bucket_replication(Bucket=b),

    "special_operations": lambda s3, b: special_function(s3, b),
}

def special_function(s3, b):
    return "some complicated operation"

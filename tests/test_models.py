"""
tests/test_models.py

Unit tests for S3DiscoveryConfig, Filter, and FilterOperator.
"""

import pytest
from pydantic import ValidationError

from cloudforge.models.discovery import Filter, FilterOperator, S3DiscoveryConfig

VALID_CONFIG = dict(
    version="1.0",
    provider="aws",
    resource_type="s3",
    description="test",
    region="all",
    fields=["bucket_name", "encryption_status"],
    filters=[],
)


def test_valid_config():
    cfg = S3DiscoveryConfig(**VALID_CONFIG)
    assert cfg.provider == "aws"
    assert cfg.resource_type == "s3"
    assert "bucket_name" in cfg.fields


def test_all_allowed_fields_accepted():
    allowed = [
        "bucket_name", "region", "creation_date", "encryption_status",
        "public_access_blocked", "versioning_status", "tags", "acl",
        "lifecycle_rules", "replication_config", "object_lock_enabled",
        "logging_enabled",
    ]
    cfg = S3DiscoveryConfig(**{**VALID_CONFIG, "fields": allowed})
    assert set(cfg.fields) == set(allowed)


def test_unknown_field_raises():
    with pytest.raises(ValidationError, match="Unknown fields"):
        S3DiscoveryConfig(**{**VALID_CONFIG, "fields": ["bucket_name", "threat_score"]})


def test_bad_region_raises():
    with pytest.raises(ValidationError, match="Unknown region"):
        S3DiscoveryConfig(**{**VALID_CONFIG, "region": "mars-west-1"})


def test_valid_region_all():
    cfg = S3DiscoveryConfig(**{**VALID_CONFIG, "region": "all"})
    assert cfg.region == "all"


def test_missing_required_field_raises():
    data = dict(VALID_CONFIG)
    del data["description"]
    with pytest.raises(ValidationError):
        S3DiscoveryConfig(**data)


def test_wrong_provider_raises():
    with pytest.raises(ValidationError):
        S3DiscoveryConfig(**{**VALID_CONFIG, "provider": "gcp"})


def test_wrong_resource_type_raises():
    with pytest.raises(ValidationError):
        S3DiscoveryConfig(**{**VALID_CONFIG, "resource_type": "ec2"})


def test_filter_valid():
    f = Filter(field="encryption_status", operator=FilterOperator.equals, value="AES256")
    assert f.operator == FilterOperator.equals


def test_filter_exists_no_value():
    f = Filter(field="bucket_name", operator=FilterOperator.exists)
    assert f.value is None


def test_filter_invalid_operator():
    with pytest.raises(ValidationError):
        Filter(field="x", operator="INVALID")


def test_config_with_filters():
    cfg = S3DiscoveryConfig(**{
        **VALID_CONFIG,
        "filters": [
            {"field": "region", "operator": "equals", "value": "us-east-1"}
        ],
    })
    assert len(cfg.filters) == 1
    assert cfg.filters[0].field == "region"

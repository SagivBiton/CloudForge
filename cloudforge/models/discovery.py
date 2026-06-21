"""
cloudforge/models/discovery.py

Pydantic v2 schema for the S3 discovery configuration YAML.
This is the single source of truth for what constitutes a valid config.
"""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, field_validator


class FilterOperator(str, Enum):
    equals = "equals"
    not_equals = "not_equals"
    contains = "contains"
    exists = "exists"


class Filter(BaseModel):
    field: str
    operator: FilterOperator
    value: Optional[str] = None  # not required for "exists"


class S3YamlConfig(BaseModel):
    version: str
    provider: Literal["aws"]
    resource_type: Literal["s3"]
    description: str
    region: str
    fields: list[str]
    filters: list[Filter] = []

    @field_validator("fields")
    @classmethod
    def fields_must_be_known(cls, v: list[str]) -> list[str]:
        allowed = {
            "bucket_name",
            "region",
            "creation_date",
            "encryption_status",
            "public_access_blocked",
            "versioning_status",
            "tags",
            "acl",
            "lifecycle_rules",
            "replication_config",
            "object_lock_enabled",
            "logging_enabled",
        }
        unknown = set(v) - allowed
        if unknown:
            raise ValueError(
                f"Unknown fields: {unknown}. "
                f"Allowed fields: {sorted(allowed)}"
            )
        return v

    @field_validator("region")
    @classmethod
    def region_must_be_valid(cls, v: str) -> str:
        allowed = {
            "us-east-1", "us-east-2", "us-west-1", "us-west-2",
            "eu-west-1", "eu-west-2", "eu-central-1",
            "ap-southeast-1", "ap-northeast-1", "all",
        }
        if v not in allowed:
            raise ValueError(f"Unknown region: {v!r}. Allowed: {sorted(allowed)}")
        return v

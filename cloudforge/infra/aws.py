"""
cloudforge/infra/aws.py

Factory for the S3 client.
Returns a real boto3 client (CLOUDFORGE_MODE=real) or InMemoryS3 (CLOUDFORGE_MODE=fake).
"""

from __future__ import annotations

from typing import Any

from cloudforge import settings


def get_s3_client() -> Any:
    """Return an S3 client appropriate for the current mode."""
    if settings.MODE == "real":
        import boto3
        return boto3.client(
            "s3",
            region_name=settings.AWS_DEFAULT_REGION,
        )
    from cloudforge.infra.fakes import InMemoryS3
    return InMemoryS3()

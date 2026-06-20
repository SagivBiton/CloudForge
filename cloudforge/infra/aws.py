"""
cloudforge/infra/aws.py

Returns a real boto3 S3 client configured from environment variables.
Credentials are picked up from the standard boto3 environment variables:
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
"""

from __future__ import annotations

import boto3

from cloudforge import settings


def get_s3_client():
    """Return a boto3 S3 client for the configured region."""
    return boto3.client("s3", region_name=settings.AWS_DEFAULT_REGION)

"""
tests/test_aws_dryrun.py

Tests for the AWS dry-run validator using InMemoryS3.
"""

from cloudforge.infra.fakes import InMemoryS3, _FakeClientError
from cloudforge.models.discovery import S3DiscoveryConfig
from cloudforge.validation.aws_dryrun import FIELD_VALIDATORS, run_dryrun

BUCKET = "cloudforge-test-alpha"

BASE_CONFIG = dict(
    version="1.0",
    provider="aws",
    resource_type="s3",
    description="test",
    region="all",
    fields=[],
    filters=[],
)


def make_config(fields: list[str]) -> S3DiscoveryConfig:
    return S3DiscoveryConfig(**{**BASE_CONFIG, "fields": fields})


def test_known_fields_pass(fake_s3):
    cfg = make_config(["bucket_name", "region", "encryption_status", "public_access_blocked"])
    ok, err = run_dryrun(cfg, fake_s3, BUCKET)
    assert ok is True
    assert err is None


def test_versioning_status_passes(fake_s3):
    cfg = make_config(["versioning_status"])
    ok, err = run_dryrun(cfg, fake_s3, BUCKET)
    assert ok is True


def test_tags_empty_config_is_ok(fake_s3):
    """NoSuchTagSet is whitelisted — field is real, just not configured."""
    cfg = make_config(["tags"])
    ok, err = run_dryrun(cfg, fake_s3, BUCKET)
    assert ok is True


def test_lifecycle_rules_empty_config_is_ok(fake_s3):
    """NoSuchLifecycleConfiguration is whitelisted."""
    cfg = make_config(["lifecycle_rules"])
    ok, err = run_dryrun(cfg, fake_s3, BUCKET)
    assert ok is True


def test_replication_config_empty_is_ok(fake_s3):
    cfg = make_config(["replication_config"])
    ok, err = run_dryrun(cfg, fake_s3, BUCKET)
    assert ok is True


def test_object_lock_empty_is_ok(fake_s3):
    cfg = make_config(["object_lock_enabled"])
    ok, err = run_dryrun(cfg, fake_s3, BUCKET)
    assert ok is True


def test_unknown_field_fails():
    """A field with no boto3 mapping fails dry-run."""
    # Bypass field_validator using model_construct so we can test the dry-run
    # with a field that has no boto3 mapping (would never reach dry-run via normal path)
    from cloudforge.models.discovery import S3DiscoveryConfig as _Cfg
    cfg_raw = _Cfg.model_construct(
        version="1.0", provider="aws", resource_type="s3",
        description="test", region="all",
        fields=["bucket_name", "threat_score"], filters=[],
    )
    ok, err = run_dryrun(cfg_raw, InMemoryS3(), BUCKET)
    assert ok is False
    assert "threat_score" in (err or "")


def test_access_denied_fails():
    """A non-whitelisted ClientError (e.g. AccessDenied) causes dry-run failure."""
    class DeniedS3(InMemoryS3):
        def get_bucket_encryption(self, **kwargs):
            raise _FakeClientError("AccessDenied", "Access Denied")

    cfg = make_config(["encryption_status"])
    ok, err = run_dryrun(cfg, DeniedS3(), BUCKET)
    assert ok is False
    assert "AccessDenied" in (err or "")


def test_all_fields_pass_with_inmemory_s3(fake_s3):
    """Every allowed field should either succeed or hit a whitelisted empty-config error."""
    all_fields = list(FIELD_VALIDATORS.keys())
    cfg = S3DiscoveryConfig(**{**BASE_CONFIG, "fields": all_fields})
    ok, err = run_dryrun(cfg, fake_s3, BUCKET)
    assert ok is True, f"Unexpected failure: {err}"

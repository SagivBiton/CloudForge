"""
cloudforge/infra/fakes.py

In-memory fakes for AWS S3 and GitHub.
Used when CLOUDFORGE_MODE=fake (the default).
No network, no credentials.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Botocore-shaped ClientError — raised by InMemoryS3 for "not configured" cases
# ---------------------------------------------------------------------------

class _FakeClientError(Exception):
    """Mimics botocore.exceptions.ClientError structure."""

    def __init__(self, code: str, message: str = ""):
        self.response = {"Error": {"Code": code, "Message": message}}
        super().__init__(f"ClientError: {code} — {message}")


# ---------------------------------------------------------------------------
# InMemoryS3
# ---------------------------------------------------------------------------

class InMemoryS3:
    """
    Minimal in-memory S3 client implementing only the methods used by
    FIELD_VALIDATORS and the agent's boto3-doc tools.

    - Known methods return realistic dicts.
    - Methods for "not configured" features raise the botocore error code
      that the dry-run whitelist recognises as ✅ (e.g. NoSuchTagSet).
    - dir() exposes all method names so search_aws_docs() works against the fake.
    """

    _BUCKET = "cloudforge-test-alpha"

    # The fake bucket has encryption and versioning enabled; no tags/ACL/lifecycle/etc.

    def list_buckets(self) -> dict[str, Any]:
        return {
            "Buckets": [
                {
                    "Name": self._BUCKET,
                    "CreationDate": "2024-01-01T00:00:00+00:00",
                }
            ]
        }

    def get_bucket_location(self, **kwargs: Any) -> dict[str, Any]:
        return {"LocationConstraint": "us-east-1"}

    def get_bucket_encryption(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "ServerSideEncryptionConfiguration": {
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256"
                        }
                    }
                ]
            }
        }

    def get_public_access_block(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "PublicAccessBlockConfiguration": {
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            }
        }

    def get_bucket_versioning(self, **kwargs: Any) -> dict[str, Any]:
        return {"Status": "Enabled"}

    def get_bucket_tagging(self, **kwargs: Any) -> dict[str, Any]:
        # No tags configured → raise the "empty" error the whitelist knows
        raise _FakeClientError("NoSuchTagSet", "The TagSet does not exist")

    def get_bucket_acl(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "Owner": {"DisplayName": "test", "ID": "abc123"},
            "Grants": [],
        }

    def get_bucket_logging(self, **kwargs: Any) -> dict[str, Any]:
        return {}  # empty dict = logging not enabled (still a valid response)

    def get_bucket_lifecycle_configuration(self, **kwargs: Any) -> dict[str, Any]:
        raise _FakeClientError(
            "NoSuchLifecycleConfiguration",
            "The lifecycle configuration does not exist",
        )

    def get_bucket_replication(self, **kwargs: Any) -> dict[str, Any]:
        raise _FakeClientError(
            "ReplicationConfigurationNotFoundError",
            "The replication configuration was not found",
        )

    def get_object_lock_configuration(self, **kwargs: Any) -> dict[str, Any]:
        raise _FakeClientError(
            "ObjectLockConfigurationNotFoundError",
            "Object Lock configuration does not exist",
        )

    def __dir__(self) -> list[str]:
        """Expose public method names so search_aws_docs() introspection works."""
        return [
            name
            for name in object.__dir__(self)
            if not name.startswith("_")
        ]


# ---------------------------------------------------------------------------
# FakeIssue / FakePR / FakeRepo
# ---------------------------------------------------------------------------

@dataclass
class FakeComment:
    body: str


@dataclass
class FakeIssue:
    number: int
    title: str
    body: str
    labels: list[str] = field(default_factory=list)
    comments: list[FakeComment] = field(default_factory=list)
    state: str = "open"

    def create_comment(self, body: str) -> FakeComment:
        c = FakeComment(body=body)
        self.comments.append(c)
        return c

    def get_labels(self) -> list[Any]:
        """Return label-like objects with a .name attribute."""
        return [type("Label", (), {"name": lbl})() for lbl in self.labels]


@dataclass
class FakePR:
    number: int
    title: str
    body: str
    head: str
    base: str
    html_url: str


@dataclass
class FakeContentFile:
    """Mimics github.ContentFile for repo.get_contents()."""
    path: str
    content: str  # plain text (not base64)
    sha: str = "abc123"
    encoding: str = "none"

    @property
    def decoded_content(self) -> bytes:
        """Matches PyGitHub's ContentFile.decoded_content (property → bytes)."""
        return self.content.encode()


@dataclass
class FakeRepo:
    """
    In-memory GitHub repository.

    Inject seed issues via the constructor:
        repo = FakeRepo(issues=[FakeIssue(1, "Title", "Body", ["discovery-request"])])
    """

    issues: list[FakeIssue] = field(default_factory=list)
    prs: list[FakePR] = field(default_factory=list)
    _files: dict[str, str] = field(default_factory=dict)
    _refs: dict[str, str] = field(default_factory=dict)
    _pr_counter: int = field(default=1, repr=False)

    def __post_init__(self) -> None:
        self._pr_counter = max((pr.number for pr in self.prs), default=0) + 1

    # --- Issues ---

    def get_issues(
        self,
        labels: list[str] | None = None,
        state: str = "open",
    ) -> list[FakeIssue]:
        result = []
        for issue in self.issues:
            if state != "all" and issue.state != state:
                continue
            if labels:
                if not any(lbl in issue.labels for lbl in labels):
                    continue
            result.append(issue)
        return result

    # --- File contents ---

    def get_contents(self, path: str, ref: str = "main") -> FakeContentFile:
        if path not in self._files:
            raise FileNotFoundError(f"FakeRepo: file not found: {path!r}")
        return FakeContentFile(path=path, content=self._files[path])

    def add_file(self, path: str, content: str) -> None:
        """Seed a file so get_contents() finds it."""
        self._files[path] = content

    def update_file(
        self,
        path: str,
        message: str,
        content: str,
        sha: str,
        branch: str = "main",
    ) -> dict[str, Any]:
        self._files[path] = content
        return {"content": {"path": path}}

    # --- Branches / refs ---

    def get_git_ref(self, ref: str) -> Any:
        if ref not in self._refs:
            raise KeyError(f"FakeRepo: ref not found: {ref!r}")
        sha = self._refs[ref]
        obj = type("Obj", (), {"sha": sha})()
        return type("Ref", (), {"object": obj})()

    def create_git_ref(self, ref: str, sha: str) -> Any:
        self._refs[ref] = sha
        obj = type("Obj", (), {"sha": sha})()
        return type("Ref", (), {"object": obj})()

    def get_branch(self, name: str) -> Any:
        key = f"refs/heads/{name}"
        sha = self._refs.get(key, "deadbeef1234")
        commit = type("Commit", (), {"sha": sha})()
        return type("Branch", (), {"commit": commit})()

    # --- Pull Requests ---

    def create_pull(
        self,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> FakePR:
        pr = FakePR(
            number=self._pr_counter,
            title=title,
            body=body,
            head=head,
            base=base,
            html_url=f"https://github.com/fake/cloudforge/pull/{self._pr_counter}",
        )
        self.prs.append(pr)
        self._pr_counter += 1
        return pr
